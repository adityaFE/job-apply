"""
Email synchronization orchestrator.
Fetches, classifies, links to jobs, updates application states, and persists to local SQLite.
"""

import logging
import os
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from ..models import (
    EmailConfig, EmailRecord, EmailCategory, JobStatus, EmailSyncResult
)
from ..storage.repository import JobRepository
from .imap_client import ImapEmailClient
from .classifier import EmailClassifier

logger = logging.getLogger(__name__)


def load_email_config(config_path: str = "config/email.yaml") -> EmailConfig:
    """Loads email settings from YAML configuration file."""
    if not os.path.exists(config_path):
        return EmailConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            email_section = data.get("email", {})
            return EmailConfig(**email_section)
    except Exception as e:
        logger.error(f"Error reading email configuration {config_path}: {e}")
        return EmailConfig()


def save_email_config(config: EmailConfig, config_path: str = "config/email.yaml") -> bool:
    """Saves updated email settings to YAML configuration file."""
    try:
        Path(config_path).parent.mkdir(parents=True, exist_ok=True)
        data = {"email": config.model_dump()}
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save email configuration to {config_path}: {e}")
        return False


class EmailSyncManager:
    """Coordinates IMAP reading, categorization, and local SQLite application updates."""

    def __init__(self, repo: Optional[JobRepository] = None, config_path: str = "config/email.yaml"):
        self.repo = repo or JobRepository()
        self.config_path = config_path
        self.config = load_email_config(config_path)

    def test_connection(self, config_override: Optional[EmailConfig] = None) -> Dict[str, Any]:
        """Validates IMAP credentials and server reachability."""
        cfg = config_override or self.config
        client = ImapEmailClient(cfg)
        try:
            client.connect()
            client.disconnect()
            return {"success": True, "message": f"Successfully connected and authenticated to {cfg.host}:{cfg.port}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def run_sync(self, config_override: Optional[EmailConfig] = None, days_back: Optional[int] = None) -> EmailSyncResult:
        """
        Executes a complete email synchronization cycle:
        1. Connects to local IMAP server.
        2. Retrieves recent emails within lookback window.
        3. Classifies categories (Confirmation, Interview, Assessment, Rejection, Offer, General).
        4. Matches or creates corresponding job application in SQLite.
        5. Updates job status and logs timeline audit events.
        """
        cfg = config_override or load_email_config(self.config_path)
        result = EmailSyncResult()

        if not cfg.enabled:
            result.errors.append("Email sync is disabled in settings. Enable email tracking first.")
            return result

        if not cfg.username or not cfg.password:
            result.errors.append("IMAP username and password/app password are required.")
            return result

        client = ImapEmailClient(cfg)
        try:
            client.connect()
            raw_emails = client.fetch_recent_emails(days_back=days_back)
        except Exception as e:
            logger.error(f"IMAP connection/fetch error: {e}")
            result.errors.append(f"IMAP Error: {str(e)}")
            return result
        finally:
            client.disconnect()

        for item in raw_emails:
            result.emails_processed += 1
            try:
                subject = item["subject"]
                body = item["body"]
                sender_email = item["sender_email"]
                sender_name = item["sender_name"]
                date_rcvd = item["date_received"]

                # 1. Classify intent category
                category = EmailClassifier.classify_category(subject, body)

                # 2. Extract company and role
                company = EmailClassifier.extract_company_name(sender_email, sender_name, subject, body)
                role_hint = EmailClassifier.extract_role_title(subject, body)

                # 3. Find matching job in DB
                matched_job = self.repo.find_matching_job(company, role_hint)
                job_id = matched_job.job.id if matched_job else None

                # 4. If no existing job was found but it's an application confirmation, auto-create a tracked job application
                if not job_id and category in [EmailCategory.CONFIRMATION, EmailCategory.INTERVIEW, EmailCategory.ASSESSMENT]:
                    job_id = self.repo.create_tracked_application_from_email(
                        company=company,
                        title=role_hint or "Software Engineer",
                        status=JobStatus.APPLIED if category == EmailCategory.CONFIRMATION else JobStatus.INTERVIEW,
                        email_date=date_rcvd,
                        source_email_subject=subject
                    )
                    result.new_jobs_created += 1

                if job_id:
                    result.emails_matched += 1

                # 5. Persist EmailRecord
                email_rec = EmailRecord(
                    job_id=job_id,
                    company=company,
                    sender=f"{sender_name} <{sender_email}>".strip(),
                    recipient=item["recipient"],
                    subject=subject,
                    body_snippet=item["snippet"],
                    category=category,
                    date_received=date_rcvd,
                    raw_message_id=item["raw_message_id"],
                    is_read=True
                )
                is_new, _ = self.repo.upsert_email(email_rec)

                # 6. Auto-update status if enabled and email was newly inserted
                if is_new and job_id and cfg.auto_update_status:
                    new_target_status = EmailClassifier.category_to_job_status(category)
                    if new_target_status:
                        # Fetch current status
                        current_rec = self.repo.get_job_by_id(job_id)
                        if current_rec:
                            current_status = current_rec.status
                            # Upgrade logic: only transition forward or to terminal states
                            should_transition = False
                            if new_target_status in [JobStatus.REJECTED, JobStatus.OFFER]:
                                should_transition = True
                            elif new_target_status == JobStatus.INTERVIEW and current_status in [JobStatus.NEW, JobStatus.SAVED, JobStatus.APPLIED]:
                                should_transition = True
                            elif new_target_status == JobStatus.APPLIED and current_status in [JobStatus.NEW, JobStatus.SAVED]:
                                should_transition = True

                            if should_transition and current_status != new_target_status:
                                self.repo.update_status_with_event(
                                    job_id=job_id,
                                    new_status=new_target_status,
                                    source_desc=f"Auto-detected from email [{category.value}] '{subject}'"
                                )
                                result.status_updates += 1

            except Exception as row_err:
                logger.warning(f"Error processing email {item.get('raw_message_id')}: {row_err}")
                result.errors.append(f"Processing error: {str(row_err)}")

        return result
