"""
Repository layer for storing, updating, and querying job records, email logs, and application audit timelines.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any

from ..models import (
    JobPost, MatchResult, JobRecord, JobStatus, FilterCriteria,
    EmailRecord, EmailCategory, ApplicationEvent, ApplicationEventType,
    Contact, ContactStatus, OutreachMessage, OutreachStage, OutreachStats
)
from .database import Database, get_db


class JobRepository:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        job = JobPost(
            id=row["id"],
            title=row["title"],
            company=row["company"],
            location=row["location"] or "Unknown",
            is_remote=bool(row["is_remote"]),
            description=row["description"] or "",
            url=row["url"],
            source=row["source"],
            ats_type=row["ats_type"] or "unknown",
            department=row["department"],
            salary_min=row["salary_min"],
            salary_max=row["salary_max"],
            salary_currency=row["salary_currency"],
            date_posted=datetime.fromisoformat(row["date_posted"]) if row["date_posted"] else None,
            date_discovered=datetime.fromisoformat(row["date_discovered"]) if row["date_discovered"] else datetime.now(timezone.utc),
            raw_data=json.loads(row["raw_data"]) if row["raw_data"] else None
        )

        match = MatchResult(
            match_score=row["match_score"] or 0,
            is_eligible=bool(row["is_eligible"]),
            matched_skills=json.loads(row["matched_skills"]) if row["matched_skills"] else [],
            missing_skills=json.loads(row["missing_skills"]) if row["missing_skills"] else [],
            omitted_skills_found=json.loads(row["omitted_skills_found"]) if row["omitted_skills_found"] else [],
            title_matched=bool(row["title_matched"]),
            location_matched=bool(row["location_matched"]),
            exclusion_reasons=json.loads(row["exclusion_reasons"]) if row["exclusion_reasons"] else [],
            summary=row["match_summary"] or ""
        )

        status_val = row["status"] or "NEW"
        try:
            status = JobStatus(status_val)
        except ValueError:
            status = JobStatus.NEW

        return JobRecord(
            job=job,
            match=match,
            status=status,
            applied_at=datetime.fromisoformat(row["applied_at"]) if row["applied_at"] else None,
            notes=row["notes"] or "",
            tags=json.loads(row["tags"]) if row["tags"] else []
        )

    def _row_to_email(self, row: sqlite3.Row) -> EmailRecord:
        try:
            cat = EmailCategory(row["category"])
        except ValueError:
            cat = EmailCategory.GENERAL

        return EmailRecord(
            id=row["id"],
            job_id=row["job_id"],
            company=row["company"],
            sender=row["sender"],
            recipient=row["recipient"] or "",
            subject=row["subject"],
            body_snippet=row["body_snippet"] or "",
            category=cat,
            date_received=datetime.fromisoformat(row["date_received"]) if row["date_received"] else datetime.now(timezone.utc),
            raw_message_id=row["raw_message_id"],
            is_read=bool(row["is_read"])
        )

    def _row_to_event(self, row: sqlite3.Row) -> ApplicationEvent:
        old_s = JobStatus(row["old_status"]) if row["old_status"] else None
        new_s = JobStatus(row["new_status"]) if row["new_status"] else None
        try:
            evt_type = ApplicationEventType(row["event_type"])
        except ValueError:
            evt_type = ApplicationEventType.STATUS_CHANGE

        return ApplicationEvent(
            id=row["id"],
            job_id=row["job_id"],
            event_type=evt_type,
            old_status=old_s,
            new_status=new_s,
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc)
        )

    def _row_to_contact(self, row: sqlite3.Row) -> Contact:
        try:
            status = ContactStatus(row["status"])
        except ValueError:
            status = ContactStatus.QUEUED

        return Contact(
            id=row["id"],
            name=row["name"],
            first_name=row["first_name"] or "",
            last_name=row["last_name"] or "",
            email=row["email"],
            title=row["title"] or "Technical Recruiter",
            company=row["company"],
            company_domain=row["company_domain"] or "",
            linkedin_url=row["linkedin_url"] or "",
            source=row["source"] or "discovery",
            status=status,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.now(timezone.utc),
            notes=row["notes"] or ""
        )

    def _row_to_outreach(self, row: sqlite3.Row) -> OutreachMessage:
        try:
            stage = OutreachStage(row["stage"])
        except ValueError:
            stage = OutreachStage.INITIAL

        return OutreachMessage(
            id=row["id"],
            contact_id=row["contact_id"],
            stage=stage,
            subject=row["subject"],
            body=row["body"],
            message_id=row["message_id"] or "",
            in_reply_to=row["in_reply_to"],
            sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else datetime.now(timezone.utc),
            reply_detected=bool(row["reply_detected"]),
            reply_detected_at=datetime.fromisoformat(row["reply_detected_at"]) if row["reply_detected_at"] else None
        )

    def upsert_job(self, record: JobRecord) -> bool:
        """
        Upserts a job record. Returns True if inserted as a new job, False if updated.
        Preserves user's existing status, applied_at, notes, and tags on update.
        """
        j = record.job
        m = record.match

        sql_check = "SELECT id, status, applied_at, notes, tags FROM jobs WHERE id = ? OR url = ?"
        sql_insert = """
        INSERT INTO jobs (
            id, title, company, location, is_remote, description, url, source, ats_type,
            department, salary_min, salary_max, salary_currency, date_posted, date_discovered,
            match_score, is_eligible, matched_skills, missing_skills, omitted_skills_found,
            title_matched, location_matched, exclusion_reasons, match_summary,
            status, applied_at, notes, tags, raw_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        sql_update = """
        UPDATE jobs SET
            title = ?, company = ?, location = ?, is_remote = ?, description = ?,
            source = ?, ats_type = ?, department = ?, salary_min = ?, salary_max = ?,
            salary_currency = ?, date_posted = ?, match_score = ?, is_eligible = ?,
            matched_skills = ?, missing_skills = ?, omitted_skills_found = ?,
            title_matched = ?, location_matched = ?, exclusion_reasons = ?, match_summary = ?,
            raw_data = ?
        WHERE id = ?
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_check, (j.id, j.url))
            existing = cursor.fetchone()

            date_posted_str = j.date_posted.isoformat() if j.date_posted else None
            date_disc_str = j.date_discovered.isoformat() if j.date_discovered else datetime.now(timezone.utc).isoformat()
            applied_at_str = record.applied_at.isoformat() if record.applied_at else None

            if existing is None:
                # Insert brand new
                cursor.execute(sql_insert, (
                    j.id, j.title, j.company, j.location, int(j.is_remote), j.description, j.url,
                    j.source, j.ats_type, j.department, j.salary_min, j.salary_max, j.salary_currency,
                    date_posted_str, date_disc_str,
                    m.match_score, int(m.is_eligible), json.dumps(m.matched_skills),
                    json.dumps(m.missing_skills), json.dumps(m.omitted_skills_found),
                    int(m.title_matched), int(m.location_matched), json.dumps(m.exclusion_reasons),
                    m.summary,
                    record.status.value, applied_at_str, record.notes, json.dumps(record.tags),
                    json.dumps(j.raw_data) if j.raw_data else None
                ))
                conn.commit()
                return True
            else:
                # Update existing record while keeping user status/notes/tags intact
                cursor.execute(sql_update, (
                    j.title, j.company, j.location, int(j.is_remote), j.description,
                    j.source, j.ats_type, j.department, j.salary_min, j.salary_max,
                    j.salary_currency, date_posted_str, m.match_score, int(m.is_eligible),
                    json.dumps(m.matched_skills), json.dumps(m.missing_skills),
                    json.dumps(m.omitted_skills_found), int(m.title_matched),
                    int(m.location_matched), json.dumps(m.exclusion_reasons), m.summary,
                    json.dumps(j.raw_data) if j.raw_data else None,
                    existing["id"]
                ))
                conn.commit()
                return False

    def batch_upsert(self, records: List[JobRecord]) -> Tuple[int, int]:
        new_count = 0
        updated_count = 0
        for record in records:
            if self.upsert_job(record):
                new_count += 1
            else:
                updated_count += 1
        return new_count, updated_count

    def get_job_by_id(self, job_id: str) -> Optional[JobRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_record(row)
        return None

    def update_status(self, job_id: str, status: JobStatus, notes: Optional[str] = None) -> bool:
        """Update job status and auto-record an application timeline event."""
        return self.update_status_with_event(job_id, status, source_desc="Manual status update", notes=notes)

    def update_status_with_event(
        self,
        job_id: str,
        new_status: JobStatus,
        source_desc: str = "Status updated",
        notes: Optional[str] = None
    ) -> bool:
        """Updates status and creates a structured audit event in application_events."""
        applied_at = datetime.now(timezone.utc).isoformat() if new_status == JobStatus.APPLIED else None
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, notes FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return False

            old_status = row["status"]
            old_notes = row["notes"] or ""
            updated_notes = notes if notes is not None else old_notes

            if new_status == JobStatus.APPLIED:
                cursor.execute(
                    "UPDATE jobs SET status = ?, notes = ?, applied_at = COALESCE(applied_at, ?) WHERE id = ?",
                    (new_status.value, updated_notes, applied_at, job_id)
                )
            else:
                cursor.execute(
                    "UPDATE jobs SET status = ?, notes = ? WHERE id = ?",
                    (new_status.value, updated_notes, job_id)
                )

            # Record event in timeline if status actually changed or notes updated
            if old_status != new_status.value or notes is not None:
                cursor.execute(
                    """
                    INSERT INTO application_events (job_id, event_type, old_status, new_status, description)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        ApplicationEventType.STATUS_CHANGE.value,
                        old_status,
                        new_status.value,
                        f"{source_desc}: {old_status} -> {new_status.value}"
                    )
                )
            conn.commit()
            return True

    def update_notes(self, job_id: str, notes: str) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET notes = ? WHERE id = ?", (notes, job_id))
            cursor.execute(
                """
                INSERT INTO application_events (job_id, event_type, description)
                VALUES (?, ?, ?)
                """,
                (job_id, ApplicationEventType.MANUAL_NOTE.value, "Updated notes")
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_job(self, job_id: str) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            return cursor.rowcount > 0

    # --------------------------------------------------------------------------
    # Timeline & Application Events
    # --------------------------------------------------------------------------

    def record_application_event(self, event: ApplicationEvent) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO application_events (job_id, event_type, old_status, new_status, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.job_id,
                    event.event_type.value,
                    event.old_status.value if event.old_status else None,
                    event.new_status.value if event.new_status else None,
                    event.description,
                    event.created_at.isoformat()
                )
            )
            conn.commit()
            return cursor.lastrowid

    def get_job_timeline(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Fetches a merged, unified chronological timeline of:
        - Application status changes
        - Ingested email messages
        - Manual user notes
        """
        timeline: List[Dict[str, Any]] = []

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Fetch application events
            cursor.execute(
                "SELECT * FROM application_events WHERE job_id = ? ORDER BY created_at ASC",
                (job_id,)
            )
            for r in cursor.fetchall():
                timeline.append({
                    "type": "event",
                    "id": r["id"],
                    "event_type": r["event_type"],
                    "old_status": r["old_status"],
                    "new_status": r["new_status"],
                    "description": r["description"],
                    "timestamp": r["created_at"]
                })

            # 2. Fetch linked emails
            cursor.execute(
                "SELECT * FROM emails WHERE job_id = ? ORDER BY date_received ASC",
                (job_id,)
            )
            for r in cursor.fetchall():
                timeline.append({
                    "type": "email",
                    "id": r["id"],
                    "sender": r["sender"],
                    "company": r["company"],
                    "subject": r["subject"],
                    "snippet": r["body_snippet"],
                    "category": r["category"],
                    "timestamp": r["date_received"]
                })

        # Sort all items chronologically (oldest to newest)
        timeline.sort(key=lambda x: x["timestamp"] or "")
        return timeline

    # --------------------------------------------------------------------------
    # Email Management & Job Linking
    # --------------------------------------------------------------------------

    def upsert_email(self, email: EmailRecord) -> Tuple[bool, Optional[int]]:
        """
        Inserts an email record if not already present by raw_message_id.
        Returns (is_new, email_id).
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM emails WHERE raw_message_id = ?", (email.raw_message_id,))
            row = cursor.fetchone()
            if row:
                return False, row["id"]

            cursor.execute(
                """
                INSERT INTO emails (
                    job_id, company, sender, recipient, subject, body_snippet,
                    category, date_received, raw_message_id, is_read
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email.job_id,
                    email.company,
                    email.sender,
                    email.recipient,
                    email.subject,
                    email.body_snippet,
                    email.category.value,
                    email.date_received.isoformat(),
                    email.raw_message_id,
                    int(email.is_read)
                )
            )
            email_id = cursor.lastrowid

            # If linked to a job, also record an application event
            if email.job_id:
                cursor.execute(
                    """
                    INSERT INTO application_events (job_id, event_type, description, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        email.job_id,
                        ApplicationEventType.EMAIL_DETECTED.value,
                        f"Received [{email.category.value}] email: '{email.subject}' from {email.sender}",
                        email.date_received.isoformat()
                    )
                )

            conn.commit()
            return True, email_id

    def get_emails_for_job(self, job_id: str) -> List[EmailRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM emails WHERE job_id = ? ORDER BY date_received DESC",
                (job_id,)
            )
            return [self._row_to_email(r) for r in cursor.fetchall()]

    def get_recent_emails(self, limit: int = 50) -> List[EmailRecord]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM emails ORDER BY date_received DESC LIMIT ?",
                (limit,)
            )
            return [self._row_to_email(r) for r in cursor.fetchall()]

    def find_matching_job(self, company_name: str, title_hint: Optional[str] = None) -> Optional[JobRecord]:
        """
        Finds the most relevant existing job record for an incoming email:
        1. Checks for exact/fuzzy company name where status != 'ARCHIVED'.
        2. If title_hint provided, checks title similarity.
        3. Prefers jobs in active statuses (APPLIED, INTERVIEW, SAVED) over NEW.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            c_term = f"%{company_name.lower().strip()}%"

            # Check for active applications first
            cursor.execute(
                """
                SELECT * FROM jobs
                WHERE LOWER(company) LIKE ?
                ORDER BY
                    CASE status
                        WHEN 'INTERVIEW' THEN 1
                        WHEN 'APPLIED' THEN 2
                        WHEN 'OFFER' THEN 3
                        WHEN 'SAVED' THEN 4
                        WHEN 'NEW' THEN 5
                        ELSE 6
                    END,
                    date_discovered DESC
                LIMIT 5
                """,
                (c_term,)
            )
            rows = cursor.fetchall()
            if not rows:
                return None

            records = [self._row_to_record(r) for r in rows]

            # If title hint provided, check title match
            if title_hint:
                hint_lower = title_hint.lower()
                for rec in records:
                    if hint_lower in rec.job.title.lower() or rec.job.title.lower() in hint_lower:
                        return rec

            # Return the highest priority active job
            return records[0]

    def create_tracked_application_from_email(
        self,
        company: str,
        title: str,
        status: JobStatus,
        email_date: datetime,
        source_email_subject: str
    ) -> str:
        """
        Creates an external tracked job entry if a candidate applied to a job
        not discovered by scrapers, triggered by an inbound confirmation email.
        """
        job_id = hashlib.sha256(f"email:{company}:{title}:{email_date.date()}".encode()).hexdigest()[:16]
        url = f"https://mail.google.com/mail/u/0/#search/{company}"

        record = JobRecord(
            job=JobPost(
                id=job_id,
                title=title or "Software Engineer / Candidate Application",
                company=company,
                location="External / Direct Application",
                is_remote=True,
                description=f"Auto-tracked from incoming email: '{source_email_subject}'",
                url=url,
                source="email_tracker",
                ats_type="email_detected",
                date_posted=email_date,
                date_discovered=datetime.now(timezone.utc)
            ),
            match=MatchResult(
                match_score=80,
                is_eligible=True,
                summary="Auto-tracked application from inbox confirmation"
            ),
            status=status,
            applied_at=email_date,
            notes=f"Created automatically by Local Email Tracker on detection of: {source_email_subject}"
        )

        self.upsert_job(record)
        return job_id

    # --------------------------------------------------------------------------
    # Filtering & Stats
    # --------------------------------------------------------------------------

    def query_jobs(self, criteria: FilterCriteria) -> Tuple[List[JobRecord], int]:
        """
        Dynamic search and filtering engine supporting:
        - Date filters (days_back)
        - Required skills (must have all or any)
        - Omit skills (exclude if contains)
        - Location & remote preferences
        - Match score ranges
        - Free text search
        """
        conditions = ["1=1"]
        params: List[Any] = []

        # 1. Search text (title, company, description)
        if criteria.search and criteria.search.strip():
            term = f"%{criteria.search.strip().lower()}%"
            conditions.append("(LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(description) LIKE ?)")
            params.extend([term, term, term])

        # 2. Statuses filter
        if criteria.statuses:
            status_placeholders = ",".join(["?"] * len(criteria.statuses))
            conditions.append(f"status IN ({status_placeholders})")
            params.extend([s.value if isinstance(s, JobStatus) else str(s) for s in criteria.statuses])

        # 3. Match score range
        if criteria.min_score > 0:
            conditions.append("match_score >= ?")
            params.append(criteria.min_score)
        if criteria.max_score < 100:
            conditions.append("match_score <= ?")
            params.append(criteria.max_score)

        # 4. Date filter (days_back)
        if criteria.days_back is not None and criteria.days_back > 0:
            cutoff_date = (datetime.now(timezone.utc) - timedelta(days=criteria.days_back)).isoformat()
            # Filter against date_posted if available, fallback to date_discovered
            conditions.append("(date_posted >= ? OR (date_posted IS NULL AND date_discovered >= ?))")
            params.extend([cutoff_date, cutoff_date])

        # 5. Remote only filter
        if criteria.remote_only is True:
            conditions.append("(is_remote = 1 OR LOWER(location) LIKE '%remote%')")

        # 6. Specific Locations filter
        if criteria.locations:
            loc_conds = []
            for loc in criteria.locations:
                loc_conds.append("LOWER(location) LIKE ?")
                params.append(f"%{loc.lower()}%")
            if loc_conds:
                conditions.append(f"({' OR '.join(loc_conds)})")

        # 7. Companies filter
        if criteria.companies:
            comp_placeholders = ",".join(["?"] * len(criteria.companies))
            conditions.append(f"LOWER(company) IN ({comp_placeholders})")
            params.extend([c.lower() for c in criteria.companies])

        # 8. ATS types filter
        if criteria.ats_types:
            ats_placeholders = ",".join(["?"] * len(criteria.ats_types))
            conditions.append(f"ats_type IN ({ats_placeholders})")
            params.extend(criteria.ats_types)

        # 9. Skills Filter (job must contain matched skill)
        if criteria.skills:
            for skill in criteria.skills:
                conditions.append("LOWER(matched_skills) LIKE ?")
                params.append(f'%"{skill.lower()}"%')

        # 10. Omit Skills Filter (job MUST NOT contain omitted skill in matched_skills or omitted_skills_found)
        if criteria.omit_skills:
            for omit_s in criteria.omit_skills:
                conditions.append("(LOWER(omitted_skills_found) NOT LIKE ? AND LOWER(matched_skills) NOT LIKE ?)")
                params.append(f'%"{omit_s.lower()}"%')
                params.append(f'%"{omit_s.lower()}"%')

        where_clause = " AND ".join(conditions)

        # Allowed sorting fields
        valid_sort_cols = {
            "match_score": "match_score",
            "date_posted": "COALESCE(date_posted, date_discovered)",
            "date_discovered": "date_discovered",
            "company": "company",
            "title": "title",
            "status": "status"
        }
        sort_col = valid_sort_cols.get(criteria.sort_by, "match_score")
        sort_dir = "ASC" if criteria.sort_order.lower() == "asc" else "DESC"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Count total
            count_sql = f"SELECT COUNT(*) as total FROM jobs WHERE {where_clause}"
            cursor.execute(count_sql, params)
            total_count = cursor.fetchone()["total"]

            # Query items
            query_sql = f"""
            SELECT * FROM jobs
            WHERE {where_clause}
            ORDER BY {sort_col} {sort_dir}
            LIMIT ? OFFSET ?
            """
            cursor.execute(query_sql, params + [criteria.limit, criteria.offset])
            rows = cursor.fetchall()

            records = [self._row_to_record(r) for r in rows]
            return records, total_count

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate statistical summary for dashboard cards."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as total FROM jobs")
            total_jobs = cursor.fetchone()["total"]

            cursor.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status")
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT AVG(match_score) as avg_score FROM jobs WHERE match_score > 0")
            avg_score_row = cursor.fetchone()
            avg_score = round(avg_score_row["avg_score"] or 0, 1)

            cursor.execute("SELECT COUNT(*) as total_remote FROM jobs WHERE is_remote = 1 OR LOWER(location) LIKE '%remote%'")
            total_remote = cursor.fetchone()["total_remote"]

            cursor.execute("""
                SELECT company, COUNT(*) as count
                FROM jobs
                GROUP BY company
                ORDER BY count DESC
                LIMIT 8
            """)
            top_companies = [{"company": r["company"], "count": r["count"]} for r in cursor.fetchall()]

            cursor.execute("""
                SELECT ats_type, COUNT(*) as count
                FROM jobs
                GROUP BY ats_type
                ORDER BY count DESC
            """)
            ats_distribution = [{"ats": r["ats_type"] or "other", "count": r["count"]} for r in cursor.fetchall()]

            cursor.execute("SELECT COUNT(*) as total_emails FROM emails")
            total_emails = cursor.fetchone()["total_emails"]

            return {
                "total_jobs": total_jobs,
                "status_counts": status_counts,
                "avg_match_score": avg_score,
                "total_remote": total_remote,
                "top_companies": top_companies,
                "ats_distribution": ats_distribution,
                "total_emails": total_emails
            }

    def rescore_all_jobs(self, matcher) -> Tuple[int, int]:
        """Re-score every job in the database using the given matcher.

        Returns (total_rescored, changed_count).
        """
        sql_fetch = "SELECT * FROM jobs"
        sql_update = """
        UPDATE jobs SET
            match_score = ?, is_eligible = ?, matched_skills = ?,
            missing_skills = ?, omitted_skills_found = ?, title_matched = ?,
            location_matched = ?, exclusion_reasons = ?, match_summary = ?
        WHERE id = ?
        """

        total = 0
        changed = 0

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql_fetch)
            rows = cursor.fetchall()

            for row in rows:
                record = self._row_to_record(row)
                new_match = matcher.evaluate_job(record.job)
                total += 1

                if new_match.match_score != record.match.match_score or \
                   new_match.matched_skills != record.match.matched_skills or \
                   new_match.omitted_skills_found != record.match.omitted_skills_found:
                    changed += 1

                cursor.execute(sql_update, (
                    new_match.match_score,
                    int(new_match.is_eligible),
                    json.dumps(new_match.matched_skills),
                    json.dumps(new_match.missing_skills),
                    json.dumps(new_match.omitted_skills_found),
                    int(new_match.title_matched),
                    int(new_match.location_matched),
                    json.dumps(new_match.exclusion_reasons),
                    new_match.summary,
                    row["id"]
                ))

            conn.commit()

        return total, changed

    def get_filter_options(self) -> Dict[str, Any]:
        """Returns unique companies, locations, and top skills for filter dropdowns."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT DISTINCT company FROM jobs ORDER BY company ASC")
            companies = [r["company"] for r in cursor.fetchall() if r["company"]]

            cursor.execute("SELECT DISTINCT ats_type FROM jobs WHERE ats_type IS NOT NULL ORDER BY ats_type ASC")
            ats_types = [r["ats_type"] for r in cursor.fetchall() if r["ats_type"]]

            return {
                "companies": companies,
                "ats_types": ats_types
            }

    # --------------------------------------------------------------------------
    # Recruiter Contacts & Cold Outreach
    # --------------------------------------------------------------------------

    def upsert_contact(self, contact: Contact) -> Tuple[bool, int]:
        """
        Inserts or updates a recruiter contact by email.
        Returns (is_new, contact_id).
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, status FROM contacts WHERE LOWER(email) = ?", (contact.email.lower().strip(),))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    """
                    UPDATE contacts SET
                        name = COALESCE(NULLIF(?, ''), name),
                        first_name = COALESCE(NULLIF(?, ''), first_name),
                        last_name = COALESCE(NULLIF(?, ''), last_name),
                        title = COALESCE(NULLIF(?, ''), title),
                        company = COALESCE(NULLIF(?, ''), company),
                        company_domain = COALESCE(NULLIF(?, ''), company_domain),
                        linkedin_url = COALESCE(NULLIF(?, ''), linkedin_url),
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        contact.name, contact.first_name, contact.last_name,
                        contact.title, contact.company, contact.company_domain,
                        contact.linkedin_url, datetime.now(timezone.utc).isoformat(),
                        row["id"]
                    )
                )
                conn.commit()
                return False, row["id"]

            cursor.execute(
                """
                INSERT INTO contacts (
                    name, first_name, last_name, email, title, company,
                    company_domain, linkedin_url, source, status, created_at, updated_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contact.name, contact.first_name, contact.last_name,
                    contact.email.lower().strip(), contact.title, contact.company,
                    contact.company_domain, contact.linkedin_url, contact.source,
                    contact.status.value, contact.created_at.isoformat(),
                    contact.updated_at.isoformat(), contact.notes
                )
            )
            contact_id = cursor.lastrowid
            conn.commit()
            return True, contact_id

    def get_contact_by_email(self, email: str) -> Optional[Contact]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts WHERE LOWER(email) = ?", (email.lower().strip(),))
            row = cursor.fetchone()
            return self._row_to_contact(row) if row else None

    def get_contact_by_id(self, contact_id: int) -> Optional[Contact]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
            row = cursor.fetchone()
            return self._row_to_contact(row) if row else None

    def list_contacts(
        self,
        status: Optional[ContactStatus] = None,
        company: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Contact], int]:
        conditions = ["1=1"]
        params: List[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if company:
            conditions.append("LOWER(company) LIKE ?")
            params.append(f"%{company.lower().strip()}%")

        where_clause = " AND ".join(conditions)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) as total FROM contacts WHERE {where_clause}", params)
            total = cursor.fetchone()["total"]

            cursor.execute(
                f"SELECT * FROM contacts WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [limit, offset]
            )
            rows = cursor.fetchall()
            return [self._row_to_contact(r) for r in rows], total

    def update_contact_status(self, contact_id: int, status: ContactStatus, notes: Optional[str] = None) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            if notes is not None:
                cursor.execute(
                    "UPDATE contacts SET status = ?, notes = ?, updated_at = ? WHERE id = ?",
                    (status.value, notes, now, contact_id)
                )
            else:
                cursor.execute(
                    "UPDATE contacts SET status = ?, updated_at = ? WHERE id = ?",
                    (status.value, now, contact_id)
                )
            conn.commit()
            return cursor.rowcount > 0

    def record_outreach_message(self, msg: OutreachMessage) -> int:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO outreach_messages (
                    contact_id, stage, subject, body, message_id, in_reply_to,
                    sent_at, reply_detected, reply_detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg.contact_id,
                    msg.stage.value,
                    msg.subject,
                    msg.body,
                    msg.message_id,
                    msg.in_reply_to,
                    msg.sent_at.isoformat(),
                    int(msg.reply_detected),
                    msg.reply_detected_at.isoformat() if msg.reply_detected_at else None
                )
            )
            msg_id = cursor.lastrowid
            conn.commit()
            return msg_id

    def get_outreach_messages(self, contact_id: int) -> List[OutreachMessage]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM outreach_messages WHERE contact_id = ? ORDER BY sent_at ASC",
                (contact_id,)
            )
            return [self._row_to_outreach(r) for r in cursor.fetchall()]

    def mark_contact_replied(self, email: str, replied_at: Optional[datetime] = None) -> bool:
        """
        Marks contact as REPLIED and halts further follow-ups.
        """
        replied_dt = replied_at or datetime.now(timezone.utc)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM contacts WHERE LOWER(email) = ?", (email.lower().strip(),))
            row = cursor.fetchone()
            if not row:
                return False

            cid = row["id"]
            cursor.execute(
                "UPDATE contacts SET status = ?, updated_at = ? WHERE id = ?",
                (ContactStatus.REPLIED.value, replied_dt.isoformat(), cid)
            )
            cursor.execute(
                """
                UPDATE outreach_messages SET
                    reply_detected = 1,
                    reply_detected_at = ?
                WHERE contact_id = ?
                """,
                (replied_dt.isoformat(), cid)
            )
            conn.commit()
            return True

    def get_contacts_due_for_followup(
        self,
        current_status: ContactStatus,
        delay_hours: float
    ) -> List[Tuple[Contact, OutreachMessage]]:
        """
        Finds contacts currently in `current_status` whose last outreach message was sent
        at least `delay_hours` ago and who have NOT replied or opted out.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=delay_hours)
        results: List[Tuple[Contact, OutreachMessage]] = []

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.*, m.id as msg_id, m.stage as msg_stage, m.subject as msg_subject,
                       m.body as msg_body, m.message_id as msg_message_id,
                       m.in_reply_to as msg_in_reply_to, m.sent_at as msg_sent_at,
                       m.reply_detected as msg_reply_detected, m.reply_detected_at as msg_reply_detected_at
                FROM contacts c
                JOIN outreach_messages m ON c.id = m.contact_id
                WHERE c.status = ?
                  AND m.sent_at <= ?
                  AND m.reply_detected = 0
                  AND m.id = (
                      SELECT MAX(m2.id) FROM outreach_messages m2 WHERE m2.contact_id = c.id
                  )
                ORDER BY m.sent_at ASC
                """,
                (current_status.value, cutoff.isoformat())
            )
            for row in cursor.fetchall():
                contact = self._row_to_contact(row)
                stage_val = row["msg_stage"]
                try:
                    stage = OutreachStage(stage_val)
                except ValueError:
                    stage = OutreachStage.INITIAL

                msg = OutreachMessage(
                    id=row["msg_id"],
                    contact_id=contact.id,
                    stage=stage,
                    subject=row["msg_subject"],
                    body=row["msg_body"],
                    message_id=row["msg_message_id"] or "",
                    in_reply_to=row["msg_in_reply_to"],
                    sent_at=datetime.fromisoformat(row["msg_sent_at"]),
                    reply_detected=bool(row["msg_reply_detected"]),
                    reply_detected_at=datetime.fromisoformat(row["msg_reply_detected_at"]) if row["msg_reply_detected_at"] else None
                )
                results.append((contact, msg))

        return results

    def log_outreach_message(self, msg: OutreachMessage) -> int:
        """Alias for record_outreach_message."""
        return self.record_outreach_message(msg)

    def get_queued_contacts(
        self,
        limit: int = 50,
        company_filter: Optional[str] = None
    ) -> List[Contact]:
        """Fetches up to `limit` contacts with status QUEUED."""
        contacts, _ = self.list_contacts(
            status=ContactStatus.QUEUED,
            company=company_filter,
            limit=limit,
            offset=0
        )
        return contacts

    def get_contacts_due_for_followup_1(
        self,
        min_hours: float = 12.0,
        limit: int = 50
    ) -> List[Tuple[Contact, OutreachMessage]]:
        """Finds contacts in CONTACTED status ready for Round 1 follow-up."""
        eligible = self.get_contacts_due_for_followup(
            current_status=ContactStatus.CONTACTED,
            delay_hours=min_hours
        )
        return eligible[:limit]

    def get_contacts_due_for_followup_2(
        self,
        min_hours: float = 24.0,
        limit: int = 50
    ) -> List[Tuple[Contact, OutreachMessage]]:
        """Finds contacts in FOLLOWUP_1 status ready for Round 2 follow-up."""
        eligible = self.get_contacts_due_for_followup(
            current_status=ContactStatus.FOLLOWUP_1,
            delay_hours=min_hours
        )
        return eligible[:limit]

    def get_outreach_stats(self) -> OutreachStats:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM contacts")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT status, COUNT(*) as count FROM contacts GROUP BY status")
            counts = {r["status"]: r["count"] for r in cursor.fetchall()}

            cursor.execute("SELECT COUNT(DISTINCT contact_id) as count FROM outreach_messages WHERE stage = 'FOLLOWUP_1'")
            f1 = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(DISTINCT contact_id) as count FROM outreach_messages WHERE stage = 'FOLLOWUP_2'")
            f2 = cursor.fetchone()["count"]

            contacted = counts.get(ContactStatus.CONTACTED.value, 0)
            f1_cnt = counts.get(ContactStatus.FOLLOWUP_1.value, 0)
            f2_cnt = counts.get(ContactStatus.FOLLOWUP_2.value, 0)
            replied = counts.get(ContactStatus.REPLIED.value, 0)
            archived = counts.get(ContactStatus.ARCHIVED.value, 0)

            total_contacted = contacted + f1_cnt + f2_cnt + replied + archived
            response_rate = round((replied / total_contacted * 100), 1) if total_contacted > 0 else 0.0

            return OutreachStats(
                total_contacts=total,
                queued=counts.get(ContactStatus.QUEUED.value, 0),
                contacted=contacted,
                followup_1_sent=f1,
                followup_2_sent=f2,
                replied=replied,
                opted_out=counts.get(ContactStatus.OPTED_OUT.value, 0),
                bounced=counts.get(ContactStatus.BOUNCED.value, 0),
                archived=archived,
                response_rate=response_rate
            )


_repository_instance: Optional[JobRepository] = None


def get_repository() -> JobRepository:
    """Returns the singleton JobRepository instance."""
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = JobRepository()
    return _repository_instance
