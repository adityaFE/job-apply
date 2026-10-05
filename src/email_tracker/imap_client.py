"""
IMAP client for secure, local email fetching over SSL/TLS.
Decodes email headers, handles multipart messages, and extracts text snippets.
"""

import email
from email.header import decode_header
import imaplib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup

from ..models import EmailConfig

logger = logging.getLogger(__name__)


def clean_header_text(header_val: Optional[str]) -> str:
    """Decodes MIME encoded-word syntax (e.g. =?UTF-8?B?...?=) to plain string."""
    if not header_val:
        return ""
    decoded_fragments = decode_header(header_val)
    parts = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            enc = encoding or "utf-8"
            try:
                parts.append(fragment.decode(enc, errors="replace"))
            except (LookupError, UnicodeDecodeError):
                parts.append(fragment.decode("latin1", errors="replace"))
        else:
            parts.append(str(fragment))
    return "".join(parts).strip()


def parse_email_address(from_header: str) -> tuple[str, str]:
    """Splits 'Full Name <email@domain.com>' into ('Full Name', 'email@domain.com')."""
    cleaned = clean_header_text(from_header)
    match = re.search(r"^(.*?)\s*<([^>]+)>$", cleaned)
    if match:
        name = match.group(1).strip(" \"'")
        addr = match.group(2).strip().lower()
        return name, addr
    # Just an email address
    return "", cleaned.strip().lower()


def extract_body_text(msg: email.message.Message) -> str:
    """Extracts plain text content from a multipart or single-part email message."""
    text_content = ""
    html_content = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition") or "")
            if "attachment" in content_disposition.lower():
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue

            charset = part.get_content_charset() or "utf-8"
            try:
                decoded_str = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded_str = payload.decode("latin1", errors="replace")

            if content_type == "text/plain":
                text_content += "\n" + decoded_str
            elif content_type == "text/html":
                html_content += "\n" + decoded_str
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded_str = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded_str = payload.decode("latin1", errors="replace")

            if msg.get_content_type() == "text/plain":
                text_content = decoded_str
            elif msg.get_content_type() == "text/html":
                html_content = decoded_str

    if text_content.strip():
        return text_content.strip()

    # Fallback to HTML parsing
    if html_content.strip():
        soup = BeautifulSoup(html_content, "html.parser")
        # Strip scripts and styles
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)

    return ""


class ImapEmailClient:
    """Connects to IMAP server and retrieves recruitment emails."""

    def __init__(self, config: EmailConfig):
        self.config = config
        self.client: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> bool:
        """Establishes an SSL/TLS connection and authenticates with credentials."""
        if not self.config.username or not self.config.password:
            raise ValueError("IMAP username and password must be configured.")

        try:
            if self.config.use_ssl:
                self.client = imaplib.IMAP4_SSL(self.config.host, self.config.port, timeout=20.0)
            else:
                self.client = imaplib.IMAP4(self.config.host, self.config.port, timeout=20.0)

            self.client.login(self.config.username, self.config.password)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server {self.config.host}: {e}")
            raise

    def disconnect(self):
        """Safely closes folder and logs out."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            try:
                self.client.logout()
            except Exception:
                pass
            self.client = None

    def fetch_recent_emails(self, days_back: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetches recruitment emails across configured folders matching the lookback window.
        """
        if not self.client:
            self.connect()

        lookback = days_back or self.config.lookback_days
        since_date = (datetime.now(timezone.utc) - timedelta(days=lookback)).strftime("%d-%b-%Y")

        results: List[Dict[str, Any]] = []
        seen_message_ids = set()

        for folder in self.config.folders:
            try:
                status, _ = self.client.select(f'"{folder}"', readonly=True)
                if status != "OK":
                    # Try unquoted
                    status, _ = self.client.select(folder, readonly=True)
                    if status != "OK":
                        continue
            except Exception as e:
                logger.warning(f"Could not open IMAP folder '{folder}': {e}")
                continue

            # IMAP Search query: SINCE date
            search_criteria = f'(SINCE "{since_date}")'
            try:
                status, data = self.client.search(None, search_criteria)
                if status != "OK" or not data or not data[0]:
                    continue

                msg_ids = data[0].split()
                # Fetch recent messages (up to 200 per folder to be fast)
                msg_ids = msg_ids[-200:]

                for mid in reversed(msg_ids):
                    try:
                        _, msg_data = self.client.fetch(mid, "(RFC822)")
                        if not msg_data or not isinstance(msg_data[0], tuple):
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        raw_msg_id = msg.get("Message-ID", "").strip() or f"{folder}-{mid.decode()}"
                        if raw_msg_id in seen_message_ids:
                            continue
                        seen_message_ids.add(raw_msg_id)

                        subject = clean_header_text(msg.get("Subject", ""))
                        sender_raw = msg.get("From", "")
                        sender_name, sender_email = parse_email_address(sender_raw)
                        recipient = clean_header_text(msg.get("To", ""))

                        # Date parsing
                        date_header = msg.get("Date")
                        date_received = datetime.now(timezone.utc)
                        if date_header:
                            try:
                                parsed_tuple = email.utils.parsedate_to_datetime(date_header)
                                if parsed_tuple:
                                    date_received = parsed_tuple if parsed_tuple.tzinfo else parsed_tuple.replace(tzinfo=timezone.utc)
                            except Exception:
                                pass

                        body_text = extract_body_text(msg)
                        snippet = body_text[:600].strip()

                        results.append({
                            "raw_message_id": raw_msg_id,
                            "subject": subject,
                            "sender_name": sender_name,
                            "sender_email": sender_email,
                            "recipient": recipient,
                            "date_received": date_received,
                            "body": body_text,
                            "snippet": snippet
                        })

                    except Exception as msg_err:
                        logger.warning(f"Error reading message {mid}: {msg_err}")
                        continue

            except Exception as search_err:
                logger.warning(f"Error searching folder '{folder}': {search_err}")
                continue

        return results
