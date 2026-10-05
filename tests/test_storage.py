"""
Unit tests for SQLite Database Repository, Job CRUD, Status Transitions, and Audit Timelines.
"""

import tempfile
from pathlib import Path
from src.storage.database import Database
from src.storage.repository import JobRepository
from src.models import (
    JobPost, MatchResult, JobRecord, JobStatus, EmailRecord, EmailCategory
)


def test_sqlite_repository_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_jobs.db"
        db = Database(db_path=db_path)
        repo = JobRepository(db=db)

        # 1. Insert a Job Post
        job = JobPost(
            id="job-101",
            company="OpenAI",
            title="Full Stack Engineer",
            url="https://openai.com/careers/101",
            location="San Francisco, CA",
            is_remote=True,
            ats_type="greenhouse",
            description="Build modern AI developer tools with Python and React."
        )
        match = MatchResult(
            match_score=95,
            matched_skills=["Python", "React"],
            missing_skills=[],
            omitted_skills_found=[],
            summary="Exceptional match"
        )
        record = JobRecord(
            job=job,
            match=match,
            status=JobStatus.NEW
        )

        is_new = repo.upsert_job(record)
        assert is_new is True

        # 2. Query Job
        fetched_record = repo.get_job_by_id("job-101")
        assert fetched_record is not None
        assert fetched_record.job.company == "OpenAI"
        assert fetched_record.status == JobStatus.NEW
        assert fetched_record.match.match_score == 95

        # 3. Update Status
        updated = repo.update_status("job-101", JobStatus.APPLIED, "Applied via referral")
        assert updated is True

        refetched = repo.get_job_by_id("job-101")
        assert refetched.status == JobStatus.APPLIED
        assert refetched.notes == "Applied via referral"

        # 4. Insert Email and Check Timeline
        email = EmailRecord(
            job_id="job-101",
            company="OpenAI",
            sender="recruiting@openai.com",
            subject="Interview Invitation: Full Stack Engineer at OpenAI",
            body_snippet="We loved your application and would like to schedule a 45 min technical call.",
            category=EmailCategory.INTERVIEW,
            raw_message_id="msg-101-openai"
        )
        is_email_new, email_id = repo.upsert_email(email)
        assert is_email_new is True
        assert email_id is not None

        timeline = repo.get_job_timeline("job-101")
        assert len(timeline) >= 2  # status change event + email event
        event_types = [item["type"] for item in timeline]
        assert "event" in event_types
        assert "email" in event_types

        # 5. Stats
        stats = repo.get_stats()
        assert stats["total_jobs"] == 1
        assert stats["status_counts"]["APPLIED"] == 1
        assert stats["total_emails"] == 1
