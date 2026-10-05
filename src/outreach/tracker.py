"""
Inbound IMAP Reply Tracker for Cold Outreach Sequences.
Detects recruiter responses, matches against active outreach contacts, and halts follow-ups.
"""

import email
import imaplib
import logging
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from typing import List, Dict, Optional, Tuple, NamedTuple

from src.models import EmailConfig, ContactStatus
from src.storage.repository import JobRepository

logger = logging.getLogger(__name__)


class ReplyCheckResult(NamedTuple):
    replies_found: int
    matched_senders: List[str]
    errors: List[str]


class OutreachReplyTracker:
    """Monitors inbox via IMAP to detect recruiter replies and stop outreach sequences."""

    def __init__(self, email_config: EmailConfig, repository: JobRepository):
        self.config = email_config
        self.repo = repository

    def _decode_header_val(self, header_raw: Optional[str]) -> str:
        """Decode MIME encoded email headers safely."""
        if not header_raw:
            return ""
        decoded_fragments = decode_header(header_raw)
        result = []
        for text, encoding in decoded_fragments:
            if isinstance(text, bytes):
                try:
                    result.append(text.decode(encoding or "utf-8", errors="replace"))
                except Exception:
                    result.append(text.decode("latin1", errors="replace"))
            else:
                result.append(str(text))
        return " ".join(result)

    def check_for_replies(self, days_back: int = 14) -> ReplyCheckResult:
        """
        Scan inbox for incoming messages from contacted recruiters or references to outreach threads.
        Transitions matched contacts to REPLIED immediately.
        """
        if not self.config.username or not self.config.password:
            logger.warning("Email credentials not configured for IMAP reply checking.")
            return ReplyCheckResult(replies_found=0, matched_senders=[], errors=["Email credentials not configured"])

        errors: List[str] = []
        matched_senders: List[str] = []

        try:
            client = imaplib.IMAP4_SSL(self.config.host, self.config.port)
            client.login(self.config.username, self.config.password)
            client.select("INBOX", readonly=True)

            since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%d-%b-%Y")
            status, data = client.search(None, f'(SINCE "{since_date}")')

            if status != "OK" or not data or not data[0]:
                client.logout()
                return ReplyCheckResult(replies_found=0, matched_senders=[], errors=[])

            message_nums = data[0].split()
            # Inspect last 150 emails for efficiency
            recent_nums = message_nums[-150:]

            for num in recent_nums:
                try:
                    _, msg_data = client.fetch(num, "(RFC822.HEADER)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            raw_email = response_part[1]
                            parsed = email.message_from_bytes(raw_email)

                            from_hdr = self._decode_header_val(parsed.get("From", ""))
                            # Extract clean email address
                            from_email = ""
                            if "<" in from_hdr and ">" in from_hdr:
                                from_email = from_hdr.split("<")[1].split(">")[0].strip().lower()
                            else:
                                from_email = from_hdr.strip().lower()

                            in_reply_to = parsed.get("In-Reply-To", "").strip()
                            references = parsed.get("References", "").strip()

                            # 1. Direct sender match against active contacts
                            contact = self.repo.get_contact_by_email(from_email)
                            if contact and contact.status in [
                                ContactStatus.CONTACTED,
                                ContactStatus.FOLLOWUP_1,
                                ContactStatus.FOLLOWUP_2,
                            ]:
                                marked = self.repo.mark_contact_replied(from_email)
                                if marked:
                                    logger.info(f"Detected recruiter reply from: {from_email} ({contact.company})")
                                    matched_senders.append(from_email)
                                    continue

                            # 2. Thread reference check (if recruiter responded from a different alias/thread)
                            if in_reply_to or references:
                                with self.repo.db.get_connection() as conn:
                                    cursor = conn.cursor()
                                    target_ref = in_reply_to or references.split()[0]
                                    cursor.execute(
                                        """
                                        SELECT c.email, c.company
                                        FROM contacts c
                                        JOIN outreach_messages m ON m.contact_id = c.id
                                        WHERE m.message_id = ? AND c.status IN ('CONTACTED', 'FOLLOWUP_1', 'FOLLOWUP_2')
                                        """,
                                        (target_ref,)
                                    )
                                    row = cursor.fetchone()
                                    if row:
                                        target_email = row["email"]
                                        self.repo.mark_contact_replied(target_email)
                                        logger.info(f"Detected thread reply via Message-ID for contact: {target_email}")
                                        matched_senders.append(target_email)

                except Exception as e:
                    logger.debug(f"Error parsing header for msg #{num}: {e}")

            client.logout()

        except Exception as e:
            err = f"IMAP reply check failed: {str(e)}"
            logger.error(err)
            errors.append(err)

        return ReplyCheckResult(
            replies_found=len(matched_senders),
            matched_senders=matched_senders,
            errors=errors,
        )
