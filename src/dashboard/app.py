"""
FastAPI Backend Application for Job Apply Intelligence Hub.
Provides REST API endpoints and serves the frontend dashboard.
"""

import os
import yaml
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Request, Query, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..models import (
    FilterCriteria, JobStatus, JobRecord, ScrapeResult,
    EmailConfig, EmailSyncResult, EmailCategory
)
from ..storage.repository import JobRepository
from ..storage.database import get_db
from ..matching.matcher import JobMatcher
from ..scrapers.manager import ScraperManager
from ..email_tracker import (
    EmailSyncManager, load_email_config, save_email_config
)


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Job Apply Intelligence Hub",
    description="Intelligent job scraper, AI match scorer, manual application workflow, and local email tracker hub",
    version="1.1.0"
)

# Static & Templates setup
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Singletons
repository = JobRepository()
matcher = JobMatcher()
scraper_manager = ScraperManager(repository=repository, matcher=matcher)
email_sync_manager = EmailSyncManager(repo=repository)


# Request schemas
class StatusUpdateRequest(BaseModel):
    status: JobStatus
    notes: Optional[str] = None


class NotesUpdateRequest(BaseModel):
    notes: str


class LinkedInSearchRequest(BaseModel):
    keywords: str = "Software Engineer"
    location: str = "Remote"
    limit: int = 25


class ProfileUpdateRequest(BaseModel):
    target_roles: List[str]
    core_skills: List[str]
    secondary_skills: List[str]
    omit_skills: List[str]
    remote_only: bool
    preferred_locations: List[str]


class EmailConfigUpdateRequest(BaseModel):
    enabled: bool
    host: str = "imap.gmail.com"
    port: int = 993
    username: str
    password: Optional[str] = None  # None/empty means keep existing password
    use_ssl: bool = True
    folders: List[str] = ["INBOX"]
    lookback_days: int = 30
    auto_update_status: bool = True


class EmailSyncRequest(BaseModel):
    days_back: Optional[int] = None


# --------------------------------------------------------------------------
# Dashboard HTML View
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# --------------------------------------------------------------------------
# Job Query & Statistics APIs
# --------------------------------------------------------------------------

@app.get("/api/stats")
async def get_dashboard_stats():
    return repository.get_stats()


@app.get("/api/filter-options")
async def get_filter_options():
    options = repository.get_filter_options()
    profile = matcher.profile
    options["profile_skills"] = profile.get("skills", {}).get("core", []) + profile.get("skills", {}).get("secondary", [])
    options["profile_omit_skills"] = profile.get("omit_skills", [])
    return options


@app.get("/api/jobs")
async def get_jobs(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    max_score: int = Query(100, ge=0, le=100),
    days_back: Optional[int] = Query(None),
    skills: Optional[str] = Query(None, description="Comma-separated list of required skills"),
    omit_skills: Optional[str] = Query(None, description="Comma-separated list of skills to omit"),
    location: Optional[str] = Query(None),
    remote_only: Optional[bool] = Query(None),
    company: Optional[str] = Query(None),
    ats_type: Optional[str] = Query(None),
    sort_by: str = Query("match_score"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    statuses = [JobStatus(status)] if status and status != "ALL" else None
    skill_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else None
    omit_list = [s.strip() for s in omit_skills.split(",") if s.strip()] if omit_skills else None
    locations_list = [location.strip()] if location else None
    companies_list = [company.strip()] if company else None
    ats_types_list = [ats_type.strip()] if ats_type else None

    criteria = FilterCriteria(
        search=search,
        statuses=statuses,
        min_score=min_score,
        max_score=max_score,
        days_back=days_back,
        skills=skill_list,
        omit_skills=omit_list,
        locations=locations_list,
        remote_only=remote_only,
        companies=companies_list,
        ats_types=ats_types_list,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )

    records, total_count = repository.query_jobs(criteria)
    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "jobs": [r.model_dump() for r in records]
    }


@app.get("/api/jobs/{job_id}")
async def get_job_detail(job_id: str):
    record = repository.get_job_by_id(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job post not found")
    return record.model_dump()


@app.get("/api/jobs/{job_id}/timeline")
async def get_job_timeline(job_id: str):
    """Retrieves chronological history of application status changes and emails."""
    record = repository.get_job_by_id(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job post not found")
    timeline = repository.get_job_timeline(job_id)
    return {"job_id": job_id, "timeline": timeline}


@app.get("/api/jobs/{job_id}/emails")
async def get_job_emails(job_id: str):
    """Retrieves emails associated with a job."""
    emails = repository.get_emails_for_job(job_id)
    return {"job_id": job_id, "emails": [e.model_dump() for e in emails]}


@app.post("/api/jobs/{job_id}/status")
async def update_job_status(job_id: str, req: StatusUpdateRequest):
    success = repository.update_status(job_id, req.status, req.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Job post not found")
    return {"status": "ok", "job_id": job_id, "new_status": req.status}


@app.post("/api/jobs/{job_id}/notes")
async def update_job_notes(job_id: str, req: NotesUpdateRequest):
    success = repository.update_notes(job_id, req.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Job post not found")
    return {"status": "ok", "job_id": job_id}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    success = repository.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job post not found")
    return {"status": "ok", "job_id": job_id}


# --------------------------------------------------------------------------
# Scraper APIs
# --------------------------------------------------------------------------

@app.post("/api/scrape/all")
async def trigger_full_scrape(background_tasks: BackgroundTasks):
    def run_scrape():
        scraper_manager.scrape_all_companies()

    background_tasks.add_task(run_scrape)
    return {"status": "started", "message": "Scraping all configured companies in background"}


@app.post("/api/rescore")
async def trigger_rescore():
    """Re-score all jobs against the current profile without re-scraping."""
    matcher.reload_config()
    total, changed = repository.rescore_all_jobs(matcher)
    return {
        "status": "ok",
        "total_rescored": total,
        "scores_changed": changed,
        "message": f"{total} jobs re-scored, {changed} had score changes"
    }


@app.post("/api/scrape/linkedin")
async def trigger_linkedin_search(req: LinkedInSearchRequest):
    result = scraper_manager.run_aggregator_search(
        keywords=req.keywords,
        location=req.location,
        limit=req.limit
    )
    return result.model_dump()


# --------------------------------------------------------------------------
# Candidate Profile & Matching Configuration APIs
# --------------------------------------------------------------------------

@app.get("/api/config/profile")
async def get_profile():
    return matcher.profile


@app.post("/api/config/profile")
async def update_profile(req: ProfileUpdateRequest):
    current = matcher.profile
    current["target_roles"] = req.target_roles
    current["skills"] = {
        "core": req.core_skills,
        "secondary": req.secondary_skills
    }
    current["omit_skills"] = req.omit_skills
    current["locations"]["remote_only"] = req.remote_only
    current["locations"]["preferred"] = req.preferred_locations

    with open(matcher.profile_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(current, f, sort_keys=False)

    matcher.reload_config()
    return {"status": "ok", "message": "Profile configuration updated and reloaded"}


# --------------------------------------------------------------------------
# Local Email Tracking & Synchronization APIs
# --------------------------------------------------------------------------

@app.get("/api/email/config")
async def get_email_config():
    cfg = load_email_config()
    data = cfg.model_dump()
    # Mask password for secure UI display
    data["has_password"] = bool(cfg.password)
    data["password"] = "********" if cfg.password else ""
    return data


@app.post("/api/email/config")
async def update_email_config(req: EmailConfigUpdateRequest):
    current_cfg = load_email_config()
    password = req.password if req.password and req.password != "********" else current_cfg.password

    new_cfg = EmailConfig(
        enabled=req.enabled,
        host=req.host,
        port=req.port,
        username=req.username,
        password=password,
        use_ssl=req.use_ssl,
        folders=req.folders,
        lookback_days=req.lookback_days,
        auto_update_status=req.auto_update_status
    )
    saved = save_email_config(new_cfg)
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to save email configuration")
    return {"status": "ok", "message": "Email configuration saved successfully"}


@app.post("/api/email/test")
async def test_email_connection(req: EmailConfigUpdateRequest):
    current_cfg = load_email_config()
    password = req.password if req.password and req.password != "********" else current_cfg.password

    cfg = EmailConfig(
        enabled=req.enabled,
        host=req.host,
        port=req.port,
        username=req.username,
        password=password,
        use_ssl=req.use_ssl,
        folders=req.folders,
        lookback_days=req.lookback_days,
        auto_update_status=req.auto_update_status
    )
    result = email_sync_manager.test_connection(cfg)
    return result


@app.post("/api/email/sync")
async def sync_emails(req: Optional[EmailSyncRequest] = None):
    days_back = req.days_back if req else None
    res = email_sync_manager.run_sync(days_back=days_back)
    return res.model_dump()


@app.get("/api/email/logs")
async def get_email_logs(limit: int = Query(50, ge=1, le=100)):
    records = repository.get_recent_emails(limit=limit)
    return {"emails": [e.model_dump() for e in records]}
