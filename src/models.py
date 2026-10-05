"""
Core data models and schemas for Job Apply Intelligence Hub.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    NEW = "NEW"
    SAVED = "SAVED"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class ContactStatus(str, Enum):
    QUEUED = "QUEUED"              # Ready for initial outreach
    CONTACTED = "CONTACTED"        # Initial email sent, awaiting response
    FOLLOWUP_1 = "FOLLOWUP_1"      # 1st follow-up sent (after ~12-24h)
    FOLLOWUP_2 = "FOLLOWUP_2"      # 2nd follow-up sent (after ~24-48h)
    REPLIED = "REPLIED"            # Recruiter replied (sequence stopped)
    OPTED_OUT = "OPTED_OUT"        # Contact asked not to be contacted
    BOUNCED = "BOUNCED"            # Email bounced / undeliverable
    ARCHIVED = "ARCHIVED"          # Sequence completed without reply


class OutreachStage(str, Enum):
    INITIAL = "INITIAL"
    FOLLOWUP_1 = "FOLLOWUP_1"
    FOLLOWUP_2 = "FOLLOWUP_2"


class EmailCategory(str, Enum):
    CONFIRMATION = "CONFIRMATION"   # Application received / thank you for applying
    INTERVIEW = "INTERVIEW"         # Interview request, scheduling link, invitation
    ASSESSMENT = "ASSESSMENT"       # OA, HackerRank, CodeSignal, take-home challenge
    REJECTION = "REJECTION"         # Position filled, moving with other candidates
    OFFER = "OFFER"                 # Job offer, offer letter
    GENERAL = "GENERAL"             # General recruiter reach out or follow up


class ApplicationEventType(str, Enum):
    STATUS_CHANGE = "STATUS_CHANGE"
    EMAIL_DETECTED = "EMAIL_DETECTED"
    MANUAL_NOTE = "MANUAL_NOTE"
    SYNC = "SYNC"


class JobPost(BaseModel):
    id: str = Field(description="Unique SHA256/UUID hash for deduplication")
    title: str
    company: str
    location: str = "Unknown"
    is_remote: bool = False
    description: str = ""
    url: str
    source: str = "direct"  # 'greenhouse', 'lever', 'ashby', 'linkedin', 'indeed', etc.
    ats_type: str = "unknown"
    department: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    date_posted: Optional[datetime] = None
    date_discovered: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_data: Optional[Dict[str, Any]] = None


class MatchResult(BaseModel):
    match_score: int = Field(default=0, ge=0, le=100, description="Overall match score 0-100")
    is_eligible: bool = True
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    omitted_skills_found: List[str] = Field(default_factory=list)
    title_matched: bool = False
    location_matched: bool = False
    exclusion_reasons: List[str] = Field(default_factory=list)
    summary: str = ""


class JobRecord(BaseModel):
    job: JobPost
    match: MatchResult
    status: JobStatus = JobStatus.NEW
    applied_at: Optional[datetime] = None
    notes: str = ""
    tags: List[str] = Field(default_factory=list)


class FilterCriteria(BaseModel):
    search: Optional[str] = None
    statuses: Optional[List[JobStatus]] = None
    min_score: int = 0
    max_score: int = 100
    days_back: Optional[int] = None
    skills: Optional[List[str]] = None
    omit_skills: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    remote_only: Optional[bool] = None
    companies: Optional[List[str]] = None
    ats_types: Optional[List[str]] = None
    sort_by: str = "match_score"  # 'match_score', 'date_posted', 'date_discovered', 'company', 'title'
    sort_order: str = "desc"      # 'desc', 'asc'
    limit: int = 100
    offset: int = 0


class ScrapeResult(BaseModel):
    company: str
    ats_type: str
    jobs_found: int
    jobs_new: int
    errors: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EmailRecord(BaseModel):
    id: Optional[int] = None
    job_id: Optional[str] = None
    company: str
    sender: str
    recipient: str = ""
    subject: str
    body_snippet: str = ""
    category: EmailCategory = EmailCategory.GENERAL
    date_received: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_message_id: str
    is_read: bool = False


class ApplicationEvent(BaseModel):
    id: Optional[int] = None
    job_id: str
    event_type: ApplicationEventType
    old_status: Optional[JobStatus] = None
    new_status: Optional[JobStatus] = None
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EmailConfig(BaseModel):
    enabled: bool = False
    host: str = "imap.gmail.com"
    port: int = 993
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    use_ssl: bool = True
    use_tls: bool = True
    folders: List[str] = Field(default_factory=lambda: ["INBOX"])
    lookback_days: int = 30
    auto_update_status: bool = True


class EmailSyncResult(BaseModel):
    emails_processed: int = 0
    emails_matched: int = 0
    status_updates: int = 0
    new_jobs_created: int = 0
    errors: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Contact(BaseModel):
    id: Optional[int] = None
    name: str
    first_name: str = ""
    last_name: str = ""
    email: str
    title: str = "Technical Recruiter"
    company: str
    company_domain: str = ""
    linkedin_url: str = ""
    source: str = "discovery"  # 'curated', 'permutator', 'apollo', 'hunter', 'csv', 'manual'
    status: ContactStatus = ContactStatus.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


class OutreachMessage(BaseModel):
    id: Optional[int] = None
    contact_id: int
    stage: OutreachStage
    subject: str
    body: str
    message_id: str = ""
    in_reply_to: Optional[str] = None
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reply_detected: bool = False
    reply_detected_at: Optional[datetime] = None


class OutreachStats(BaseModel):
    total_contacts: int = 0
    queued: int = 0
    contacted: int = 0
    followup_1_sent: int = 0
    followup_2_sent: int = 0
    replied: int = 0
    opted_out: int = 0
    bounced: int = 0
    archived: int = 0
    response_rate: float = 0.0


class OutreachBatchResult(BaseModel):
    stage: OutreachStage
    attempted: int = 0
    successful: int = 0
    failed: int = 0
    skipped_replied: int = 0
    errors: List[str] = Field(default_factory=list)
    sent_to: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

