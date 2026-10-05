"""
SMTP Email Dispatcher for Cold Outreach and Threaded Follow-ups.
Enforces 50-email batch safety caps, human-like jitter, and RFC 2822 headers.
"""

import email.utils
import logging
import random
import smtplib
import time
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Tuple, NamedTuple

from src.models import Contact, OutreachStage, OutreachBatchResult, EmailConfig
from src.outreach.templates import TemplateEngine, RenderedEmail

logger = logging.getLogger(__name__)


class SendResult(NamedTuple):
    success: bool
    recipient: str
    message_id: str
    subject: str
    body: str
    error: Optional[str] = None


class OutreachSender:
    """Dispatches cold outreach emails and follow-ups with safety limits."""

    MAX_BATCH_SIZE = 50
    DEFAULT_MIN_DELAY = 6.0  # seconds between sends
    DEFAULT_MAX_DELAY = 14.0

    def __init__(self, email_config: EmailConfig, dry_run: bool = False):
        self.config = email_config
        self.dry_run = dry_run
        self.template_engine = TemplateEngine()

    def _create_smtp_session(self) -> smtplib.SMTP:
        """Create and authenticate a secure SMTP session."""
        if not self.config.username or not self.config.password:
            raise ValueError("Email credentials not configured in config/email.yaml (username and app password required).")

        host = self.config.smtp_host or "smtp.gmail.com"
        port = self.config.smtp_port or 587

        if port == 465 or self.config.use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.ehlo()
            if self.config.use_tls:
                server.starttls()
                server.ehlo()

        server.login(self.config.username, self.config.password)
        return server

    def _build_mime_message(
        self,
        contact: Contact,
        rendered: RenderedEmail,
        in_reply_to: Optional[str] = None,
    ) -> Tuple[MIMEMultipart, str]:
        """Build RFC-compliant MIME message with threading headers."""
        msg = MIMEMultipart("alternative")

        cand_details = self.template_engine.get_candidate_details()
        cand_name = cand_details.get("name", "Candidate")
        msg["From"] = f"{cand_name} <{self.config.username}>"
        msg["To"] = f"{contact.name} <{contact.email}>" if contact.name else contact.email
        msg["Subject"] = rendered.subject
        msg["Date"] = email.utils.formatdate(localtime=True)

        # Generate unique Message-ID
        domain = self.config.username.split("@")[-1] if "@" in self.config.username else "mail.local"
        message_id = f"<{uuid.uuid4().hex}@{domain}>"
        msg["Message-ID"] = message_id

        # Threading headers for follow-ups
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = in_reply_to

        # Attach text and html versions
        part_text = MIMEText(rendered.body_text, "plain", "utf-8")
        part_html = MIMEText(rendered.body_html, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        return msg, message_id

    def send_single(
        self,
        contact: Contact,
        stage: OutreachStage,
        in_reply_to: Optional[str] = None,
        initial_subject: Optional[str] = None,
        smtp_session: Optional[smtplib.SMTP] = None,
    ) -> SendResult:
        """Send a single outreach or follow-up email."""
        rendered = self.template_engine.render(contact, stage, initial_subject)

        if self.dry_run:
            logger.info(f"[DRY-RUN] Would send {stage.value} to {contact.email} ({contact.company}): {rendered.subject}")
            return SendResult(
                success=True,
                recipient=contact.email,
                message_id=f"<dry-run-{uuid.uuid4().hex[:12]}@local>",
                subject=rendered.subject,
                body=rendered.body_text,
            )

        msg, message_id = self._build_mime_message(contact, rendered, in_reply_to)

        try:
            if smtp_session is not None:
                smtp_session.sendmail(self.config.username, [contact.email], msg.as_string())
            else:
                with self._create_smtp_session() as server:
                    server.sendmail(self.config.username, [contact.email], msg.as_string())

            logger.info(f"Successfully sent {stage.value} email to {contact.email} ({contact.company})")
            return SendResult(
                success=True,
                recipient=contact.email,
                message_id=message_id,
                subject=rendered.subject,
                body=rendered.body_text,
            )
        except Exception as e:
            err_msg = f"Failed to send to {contact.email}: {str(e)}"
            logger.error(err_msg)
            return SendResult(
                success=False,
                recipient=contact.email,
                message_id="",
                subject=rendered.subject,
                body=rendered.body_text,
                error=err_msg,
            )

    def dispatch_batch(
        self,
        contacts_with_context: List[Tuple[Contact, OutreachStage, Optional[str], Optional[str]]],
        max_batch: int = MAX_BATCH_SIZE,
    ) -> Tuple[OutreachBatchResult, List[SendResult]]:
        """
        Dispatch a batch of emails (max 50) with jitter delay between sends.
        Each tuple item: (contact, stage, in_reply_to_msg_id, initial_subject)
        """
        batch_slice = contacts_with_context[:max_batch]
        stage = batch_slice[0][1] if batch_slice else OutreachStage.INITIAL

        result = OutreachBatchResult(stage=stage, attempted=len(batch_slice))
        results_list: List[SendResult] = []

        if not batch_slice:
            return result, results_list

        smtp_session: Optional[smtplib.SMTP] = None
        if not self.dry_run:
            try:
                smtp_session = self._create_smtp_session()
            except Exception as e:
                err = f"SMTP connection error: {str(e)}"
                result.errors.append(err)
                logger.error(err)
                return result, results_list

        try:
            for idx, (contact, cur_stage, in_reply_to, init_subj) in enumerate(batch_slice):
                send_res = self.send_single(
                    contact=contact,
                    stage=cur_stage,
                    in_reply_to=in_reply_to,
                    initial_subject=init_subj,
                    smtp_session=smtp_session,
                )
                results_list.append(send_res)

                if send_res.success:
                    result.successful += 1
                    result.sent_to.append(contact.email)
                else:
                    result.failed += 1
                    if send_res.error:
                        result.errors.append(send_res.error)

                # Add delay between sends if more emails remain (and not in dry run)
                if idx < len(batch_slice) - 1 and not self.dry_run:
                    delay = random.uniform(self.DEFAULT_MIN_DELAY, self.DEFAULT_MAX_DELAY)
                    logger.debug(f"Jitter pause {delay:.1f}s before next send...")
                    time.sleep(delay)

        finally:
            if smtp_session is not None:
                try:
                    smtp_session.quit()
                except Exception:
                    pass

        return result, results_list
