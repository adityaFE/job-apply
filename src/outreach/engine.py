"""
Master Orchestration Engine for Recruiter Lead Discovery and Cold Outreach.
Handles batch limits (50 max), 12h/24h follow-up rules, and automatic reply tracking.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

from src.models import (
    Contact,
    ContactStatus,
    OutreachStage,
    OutreachMessage,
    OutreachBatchResult,
    OutreachStats,
    EmailConfig,
    ApplicationEvent,
    ApplicationEventType,
)
from src.storage.repository import JobRepository, get_repository
from src.email_tracker import load_email_config
from src.outreach.discovery import LeadDiscoveryManager
from src.outreach.sender import OutreachSender, SendResult
from src.outreach.tracker import OutreachReplyTracker

logger = logging.getLogger(__name__)


class OutreachEngine:
    """Coordinates lead discovery, rate-limited email sending, follow-ups, and reply tracking."""

    def __init__(
        self,
        repo: Optional[JobRepository] = None,
        email_config: Optional[EmailConfig] = None,
        dry_run: bool = False,
    ):
        self.repo = repo or get_repository()
        self.email_config = email_config or load_email_config()
        self.dry_run = dry_run
        self.discovery = LeadDiscoveryManager()
        self.sender = OutreachSender(self.email_config, dry_run=self.dry_run)
        self.tracker = OutreachReplyTracker(self.email_config, self.repo)

    def seed_starter_contacts(self, target_companies: Optional[List[str]] = None) -> int:
        """Seed database with curated recruiter contacts and talent inboxes."""
        contacts = self.discovery.generate_starter_leads(target_companies)
        new_count = 0
        for c in contacts:
            is_new, _ = self.repo.upsert_contact(c)
            if is_new:
                new_count += 1
        logger.info(f"Seeded {len(contacts)} contacts ({new_count} newly inserted).")
        return new_count

    def import_contacts(self, file_path: str) -> int:
        """Import recruiter contacts from CSV or JSON file."""
        if file_path.endswith(".csv"):
            contacts = self.discovery.import_from_csv(file_path)
        elif file_path.endswith(".json"):
            contacts = self.discovery.import_from_json(file_path)
        else:
            raise ValueError("Unsupported file format. Please provide a .csv or .json file.")

        new_count = 0
        for c in contacts:
            is_new, _ = self.repo.upsert_contact(c)
            if is_new:
                new_count += 1
        logger.info(f"Imported {len(contacts)} contacts ({new_count} newly inserted).")
        return new_count

    def add_single_contact(
        self,
        name: str,
        company: str,
        title: str = "Technical Recruiter",
        email: Optional[str] = None,
        domain: Optional[str] = None,
        linkedin: str = "",
    ) -> Tuple[bool, int]:
        """Manually add or update a recruiter contact."""
        contact = self.discovery.create_contact_from_person(
            full_name=name,
            company=company,
            title=title,
            domain=domain,
            email_override=email,
            linkedin_url=linkedin,
            source="manual",
        )
        return self.repo.upsert_contact(contact)

    def sync_replies(self, days_back: int = 14) -> int:
        """Scan IMAP for recruiter responses and update statuses to REPLIED."""
        res = self.tracker.check_for_replies(days_back=days_back)
        return res.replies_found

    def send_initial_outreach(
        self,
        batch_size: int = 50,
        company_filter: Optional[str] = None,
    ) -> OutreachBatchResult:
        """
        Send Initial cold outreach emails to QUEUED contacts (capped at 50 max).
        Checks for recent replies first to avoid emailing responders.
        """
        # 1. Sync replies first
        if self.email_config.enabled and not self.dry_run:
            self.sync_replies()

        # 2. Fetch QUEUED contacts
        limit = min(batch_size, OutreachSender.MAX_BATCH_SIZE)
        queued_contacts = self.repo.get_queued_contacts(limit=limit, company_filter=company_filter)

        if not queued_contacts:
            logger.info("No QUEUED contacts found for initial outreach.")
            return OutreachBatchResult(stage=OutreachStage.INITIAL, attempted=0)

        # 3. Format batch payload: (contact, stage, in_reply_to, initial_subject)
        batch_payload = [(c, OutreachStage.INITIAL, None, None) for c in queued_contacts]

        # 4. Dispatch batch
        batch_res, send_results = self.sender.dispatch_batch(batch_payload, max_batch=limit)

        # 5. Update database state
        for contact, send_res in zip(queued_contacts, send_results):
            if send_res.success and contact.id:
                # Log sent message
                msg = OutreachMessage(
                    contact_id=contact.id,
                    stage=OutreachStage.INITIAL,
                    subject=send_res.subject,
                    body=send_res.body,
                    message_id=send_res.message_id,
                    sent_at=datetime.now(timezone.utc),
                )
                self.repo.log_outreach_message(msg)

                # Update status
                self.repo.update_contact_status(contact.id, ContactStatus.CONTACTED)

        return batch_res

    def send_followup_round_1(
        self,
        min_hours: float = 12.0,
        batch_size: int = 50,
    ) -> OutreachBatchResult:
        """
        Send Round 1 Follow-up to contacts contacted >= min_hours (default 12h) ago with no reply.
        Preserves original subject and Message-ID threading headers.
        """
        if self.email_config.enabled and not self.dry_run:
            self.sync_replies()

        limit = min(batch_size, OutreachSender.MAX_BATCH_SIZE)
        eligible = self.repo.get_contacts_due_for_followup_1(min_hours=min_hours, limit=limit)

        if not eligible:
            logger.info(f"No contacts due for Follow-up Round 1 (>= {min_hours}h elapsed).")
            return OutreachBatchResult(stage=OutreachStage.FOLLOWUP_1, attempted=0)

        # Format batch payload: (contact, stage, in_reply_to, initial_subject)
        batch_payload = [
            (contact, OutreachStage.FOLLOWUP_1, last_msg.message_id, last_msg.subject)
            for contact, last_msg in eligible
        ]

        batch_res, send_results = self.sender.dispatch_batch(batch_payload, max_batch=limit)

        for (contact, _), send_res in zip(eligible, send_results):
            if send_res.success and contact.id:
                msg = OutreachMessage(
                    contact_id=contact.id,
                    stage=OutreachStage.FOLLOWUP_1,
                    subject=send_res.subject,
                    body=send_res.body,
                    message_id=send_res.message_id,
                    in_reply_to=send_res.message_id,
                    sent_at=datetime.now(timezone.utc),
                )
                self.repo.log_outreach_message(msg)
                self.repo.update_contact_status(contact.id, ContactStatus.FOLLOWUP_1)

        return batch_res

    def send_followup_round_2(
        self,
        min_hours: float = 24.0,
        batch_size: int = 50,
    ) -> OutreachBatchResult:
        """
        Send Round 2 Follow-up to contacts who received Follow-up 1 >= min_hours (default 24h) ago with no reply.
        Preserves original thread and closes the sequence.
        """
        if self.email_config.enabled and not self.dry_run:
            self.sync_replies()

        limit = min(batch_size, OutreachSender.MAX_BATCH_SIZE)
        eligible = self.repo.get_contacts_due_for_followup_2(min_hours=min_hours, limit=limit)

        if not eligible:
            logger.info(f"No contacts due for Follow-up Round 2 (>= {min_hours}h elapsed).")
            return OutreachBatchResult(stage=OutreachStage.FOLLOWUP_2, attempted=0)

        batch_payload = [
            (contact, OutreachStage.FOLLOWUP_2, last_msg.message_id, last_msg.subject)
            for contact, last_msg in eligible
        ]

        batch_res, send_results = self.sender.dispatch_batch(batch_payload, max_batch=limit)

        for (contact, _), send_res in zip(eligible, send_results):
            if send_res.success and contact.id:
                msg = OutreachMessage(
                    contact_id=contact.id,
                    stage=OutreachStage.FOLLOWUP_2,
                    subject=send_res.subject,
                    body=send_res.body,
                    message_id=send_res.message_id,
                    in_reply_to=send_res.message_id,
                    sent_at=datetime.now(timezone.utc),
                )
                self.repo.log_outreach_message(msg)
                self.repo.update_contact_status(contact.id, ContactStatus.FOLLOWUP_2)

        return batch_res

    def get_outreach_stats(self) -> OutreachStats:
        """Get funnel metrics and response rate for all outreach campaigns."""
        return self.repo.get_outreach_stats()
