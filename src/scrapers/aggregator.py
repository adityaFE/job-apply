"""
Public Job Board Aggregator (LinkedIn Guest API & General Boards).
Safely retrieves public job posts without requiring authentication.
"""

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Optional

from ..models import JobPost
from .base import BaseScraper


class LinkedInGuestScraper(BaseScraper):
    """
    Scrapes LinkedIn's public guest search endpoint.
    No login required; zero risk to personal user account.
    """
    SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def search_jobs(self, keywords: str, location: str = "United States", limit: int = 25) -> List[JobPost]:
        jobs: List[JobPost] = []
        params = {
            "keywords": keywords,
            "location": location,
            "start": 0
        }

        try:
            with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(self.SEARCH_URL, params=params)
                if response.status_code != 200:
                    return jobs

                soup = BeautifulSoup(response.text, "html.parser")
                cards = soup.find_all("li")

                for card in cards:
                    title_elem = card.find("h3", class_="base-search-card__title")
                    company_elem = card.find("h4", class_="base-search-card__subtitle")
                    location_elem = card.find("span", class_="job-search-card__location")
                    link_elem = card.find("a", class_="base-card__full-link")
                    time_elem = card.find("time")

                    if not title_elem or not link_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
                    loc_text = location_elem.get_text(strip=True) if location_elem else "Unknown"
                    job_url = link_elem.get("href", "").split("?")[0]  # Clean tracking params

                    if not title or not job_url:
                        continue

                    is_remote = "remote" in loc_text.lower() or "remote" in title.lower()

                    date_posted = None
                    if time_elem and time_elem.get("datetime"):
                        try:
                            date_posted = datetime.fromisoformat(time_elem["datetime"]).replace(tzinfo=timezone.utc)
                        except Exception:
                            date_posted = None

                    job_id = self.generate_job_id(company, title, job_url)

                    jobs.append(JobPost(
                        id=job_id,
                        title=title,
                        company=company,
                        location=loc_text,
                        is_remote=is_remote,
                        description=f"{title} at {company} in {loc_text}",
                        url=job_url,
                        source="linkedin_guest",
                        ats_type="linkedin",
                        date_posted=date_posted
                    ))

                    if len(jobs) >= limit:
                        break

        except Exception:
            pass

        return jobs

    def scrape_company(self, company_name: str, slug: str) -> List[JobPost]:
        return self.search_jobs(keywords=f"{company_name} software engineer", limit=15)
