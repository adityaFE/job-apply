"""
Ashby ATS API Scraper.
Uses Ashby's posting API to retrieve structured job postings.
"""

import httpx
from datetime import datetime
from typing import List, Optional
from dateutil import parser as date_parser

from ..models import JobPost
from .base import BaseScraper


class AshbyScraper(BaseScraper):
    API_URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"

    def scrape_company(self, company_name: str, slug: str) -> List[JobPost]:
        url = self.API_URL.format(slug=slug)
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
                    job_url = item.get("jobUrl") or item.get("applyUrl") or ""
                    if not title or not job_url:
                        continue

                    location_name = item.get("location") or "Unknown"
                    is_remote = bool(item.get("isRemote", False)) or "remote" in location_name.lower() or "remote" in title.lower()

                    department = item.get("department")

                    # Description
                    raw_desc = item.get("descriptionHtml") or item.get("description") or ""
                    clean_desc = self.clean_html(raw_desc)

                    # Date parsing
                    date_posted = None
                    published_at = item.get("publishedAt")
                    if published_at:
                        try:
                            date_posted = date_parser.parse(published_at)
                        except Exception:
                            date_posted = None

                    # Compensation info if available
                    salary_min = None
                    salary_max = None
                    salary_currency = None
                    comp = item.get("compensation") or {}
                    if comp:
                        salary_min = comp.get("min")
                        salary_max = comp.get("max")
                        salary_currency = comp.get("currency")

                    job_id = self.generate_job_id(company_name, title, job_url)

                    jobs.append(JobPost(
                        id=job_id,
                        title=title,
                        company=company_name,
                        location=location_name,
                        is_remote=is_remote,
                        description=clean_desc,
                        url=job_url,
                        source="ashby",
                        ats_type="ashby",
                        department=department,
                        salary_min=salary_min,
                        salary_max=salary_max,
                        salary_currency=salary_currency,
                        date_posted=date_posted,
                        raw_data={"ashby_id": item.get("id")}
                    ))

        except Exception as e:
            pass

        return jobs
