"""
Greenhouse ATS API Scraper.
Uses Greenhouse's official public board REST API for 100% structured data.
"""

import httpx
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from ..models import JobPost
from .base import BaseScraper


class GreenhouseScraper(BaseScraper):
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

    def scrape_company(self, company_name: str, slug: str) -> List[JobPost]:
        url = self.BASE_URL.format(slug=slug)
        jobs: List[JobPost] = []

        try:
            with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code != 200:
                    return jobs

                data = response.json()
                raw_jobs = data.get("jobs", [])

                for item in raw_jobs:
                    title = (item.get("title") or "").strip()
                    job_url = item.get("absolute_url") or ""
                    if not title or not job_url:
                        continue

                    location_obj = item.get("location") or {}
                    location_name = location_obj.get("name", "Unknown") if isinstance(location_obj, dict) else str(location_obj)

                    raw_content = item.get("content") or ""
                    clean_description = self.clean_html(raw_content)

                    # Determine if remote
                    is_remote = "remote" in location_name.lower() or "remote" in title.lower()

                    # Department
                    departments = item.get("departments", [])
                    dept_name = departments[0].get("name") if departments and isinstance(departments[0], dict) else None

                    # Date parsing
                    date_posted = None
                    updated_at = item.get("updated_at")
                    if updated_at:
                        try:
                            date_posted = date_parser.parse(updated_at)
                        except Exception:
                            date_posted = None

                    job_id = self.generate_job_id(company_name, title, job_url)

                    jobs.append(JobPost(
                        id=job_id,
                        title=title,
                        company=company_name,
                        location=location_name,
                        is_remote=is_remote,
                        description=clean_description,
                        url=job_url,
                        source="greenhouse",
                        ats_type="greenhouse",
                        department=dept_name,
                        date_posted=date_posted,
                        raw_data={"greenhouse_id": item.get("id"), "requisition_id": item.get("requisition_id")}
                    ))

        except Exception as e:
            # Silently catch or log to caller
            pass

        return jobs
