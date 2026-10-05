"""Database initialization, schema management, and SQLite optimizations."""

import sqlite3
from pathlib import Path
from typing import Optional


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    is_remote INTEGER DEFAULT 0,
    description TEXT,
    url TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    ats_type TEXT,
    department TEXT,
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT,
    date_posted TIMESTAMP,
    date_discovered TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Matching Engine fields
    match_score INTEGER DEFAULT 0,
    is_eligible INTEGER DEFAULT 1,
    matched_skills TEXT,     -- JSON array of strings
    missing_skills TEXT,     -- JSON array of strings
    omitted_skills_found TEXT, -- JSON array of strings
    title_matched INTEGER DEFAULT 0,
    location_matched INTEGER DEFAULT 0,
    exclusion_reasons TEXT,  -- JSON array of strings
    match_summary TEXT,

    -- User Tracking / State fields
    status TEXT DEFAULT 'NEW',  -- NEW, SAVED, APPLIED, INTERVIEW, OFFER, REJECTED, ARCHIVED
    applied_at TIMESTAMP,
    notes TEXT DEFAULT '',
    tags TEXT DEFAULT '[]',   -- JSON array
    raw_data TEXT             -- JSON object
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON jobs(match_score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_date_discovered ON jobs(date_discovered DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_is_remote ON jobs(is_remote);
CREATE INDEX IF NOT EXISTS idx_jobs_ats_type ON jobs(ats_type);

-- Table for tracking ingested emails linked to companies and job applications
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    company TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT DEFAULT '',
    subject TEXT NOT NULL,
    body_snippet TEXT DEFAULT '',
    category TEXT NOT NULL, -- CONFIRMATION, INTERVIEW, ASSESSMENT, REJECTION, OFFER, GENERAL
    date_received TIMESTAMP NOT NULL,
    raw_message_id TEXT UNIQUE NOT NULL,
    is_read INTEGER DEFAULT 0,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_emails_job_id ON emails(job_id);
CREATE INDEX IF NOT EXISTS idx_emails_company ON emails(company);
CREATE INDEX IF NOT EXISTS idx_emails_category ON emails(category);
CREATE INDEX IF NOT EXISTS idx_emails_date_received ON emails(date_received DESC);
CREATE INDEX IF NOT EXISTS idx_emails_raw_id ON emails(raw_message_id);

-- Table for audit trail / chronological application lifecycle events
CREATE TABLE IF NOT EXISTS application_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL, -- STATUS_CHANGE, EMAIL_DETECTED, MANUAL_NOTE, SYNC
    old_status TEXT,
    new_status TEXT,
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_app_events_job_id ON application_events(job_id);
CREATE INDEX IF NOT EXISTS idx_app_events_created ON application_events(created_at DESC);

-- Table for recruiter contacts for cold outreach
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    first_name TEXT DEFAULT '',
    last_name TEXT DEFAULT '',
    email TEXT NOT NULL UNIQUE,
    title TEXT DEFAULT 'Technical Recruiter',
    company TEXT NOT NULL,
    company_domain TEXT DEFAULT '',
    linkedin_url TEXT DEFAULT '',
    source TEXT DEFAULT 'discovery',
    status TEXT DEFAULT 'QUEUED', -- QUEUED, CONTACTED, FOLLOWUP_1, FOLLOWUP_2, REPLIED, OPTED_OUT, BOUNCED, ARCHIVED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);

-- Table for tracking cold outreach sent messages and thread history
CREATE TABLE IF NOT EXISTS outreach_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    stage TEXT NOT NULL, -- INITIAL, FOLLOWUP_1, FOLLOWUP_2
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    message_id TEXT DEFAULT '',
    in_reply_to TEXT,
    sent_at TIMESTAMP NOT NULL,
    reply_detected INTEGER DEFAULT 0,
    reply_detected_at TIMESTAMP,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_outreach_contact_id ON outreach_messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_outreach_stage ON outreach_messages(stage);
CREATE INDEX IF NOT EXISTS idx_outreach_sent_at ON outreach_messages(sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_outreach_message_id ON outreach_messages(message_id);
"""


class Database:
    def __init__(self, db_path: str = "data/jobs.db"):
        self.db_path = db_path
        self._ensure_dir()
        self.init_db()

    def _ensure_dir(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode and optimizations for concurrent local access
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()


# Default singleton instance
_default_db: Optional[Database] = None


def get_db(db_path: str = "data/jobs.db") -> Database:
    global _default_db
    if _default_db is None or _default_db.db_path != db_path:
        _default_db = Database(db_path)
    return _default_db
