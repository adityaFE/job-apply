"""
Lever ATS API Scraper.
Uses Lever's public postings API for clean structured job posts.
"""

import httpx
from datetime import datetime, timezone
from typing import List, Optional

from ..models import JobPost
from .base import BaseScraper


class LeverScraper(BaseScraper):
    BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"

    def scrape_company(self, company_name: str, slug: str) -> List[JobPost]:
        url = self.BASE_URL.format(slug=slug)
        jobs: List[JobPost] = []

        try:
            with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code != 200:
                    return jobs

                raw_jobs = response.json()
                if not isinstance(raw_jobs, list):
                    return jobs

                for item in raw_jobs:
                    title = (item.get("text") or "").strip()
                    job_url = item.get("hostedUrl") or item.get("applyUrl") or ""
                    if not title or not job_url:
                        continue

                    categories = item.get("categories") or {}
                    location_name = categories.get("location") or "Unknown"
                    team = categories.get("team") or categories.get("department")
                    commitment = categories.get("commitment") or ""  # e.g., Full-time

                    # Description construction
                    description_plain = item.get("descriptionPlain") or ""
                    additional_plain = item.get("additionalPlain") or ""
                    clean_description = f"{description_plain}\n\n{additional_plain}".strip()
                    if not clean_description:
                        clean_description = self.clean_html(item.get("description", ""))

                    # Remote check
                    workplace_type = item.get("workplaceType", "").lower()
                    is_remote = (
                        workplace_type == "remote" or
                        "remote" in location_name.lower() or
                        "remote" in title.lower()
                    )

                    # Date posted parsing (createdAt is in ms timestamp)
                    date_posted = None
                    created_at_ms = item.get("createdAt")
                    if created_at_ms and isinstance(created_at_ms, (int, float)):
                        try:
                            date_posted = datetime.fromtimestamp(created_at_ms / 1000.0, tz=timezone.utc)
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
                        source="lever",
                        ats_type="lever",
                        department=team,
                        date_posted=date_posted,
                        raw_data={"lever_id": item.get("id"), "commitment": commitment}
                    ))

        except Exception as e:
            pass

        return jobs
