"""
Scraper Orchestration Manager.
Runs scrapers concurrently, evaluates matches, and persists results.
"""

import os
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from ..models import JobPost, JobRecord, MatchResult, ScrapeResult
from ..storage.repository import JobRepository
from ..matching.matcher import JobMatcher
from .greenhouse import GreenhouseScraper
from .lever import LeverScraper
from .ashby import AshbyScraper
from .aggregator import LinkedInGuestScraper


class ScraperManager:
    def __init__(
        self,
        repository: Optional[JobRepository] = None,
        matcher: Optional[JobMatcher] = None,
        companies_path: str = "config/companies.yaml",
        settings_path: str = "config/settings.yaml"
    ):
        self.repository = repository or JobRepository()
        self.matcher = matcher or JobMatcher()
        self.companies_path = companies_path
        self.settings_path = settings_path

        self.scrapers = {
            "greenhouse": GreenhouseScraper(),
            "lever": LeverScraper(),
            "ashby": AshbyScraper(),
            "linkedin": LinkedInGuestScraper()
        }

    def _load_yaml(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def scrape_single_company(self, company: Dict[str, str]) -> ScrapeResult:
        name = company.get("name", "Unknown")
        ats = company.get("ats", "").lower()
        slug = company.get("slug", "")

        scraper = self.scrapers.get(ats)
        if not scraper:
            return ScrapeResult(
                company=name,
                ats_type=ats,
                jobs_found=0,
                jobs_new=0,
                errors=[f"Unsupported ATS type: {ats}"]
            )

        try:
            raw_jobs: List[JobPost] = scraper.scrape_company(name, slug)
            new_count = 0

            for job in raw_jobs:
                match_result: MatchResult = self.matcher.evaluate_job(job)
                record = JobRecord(job=job, match=match_result)
                if self.repository.upsert_job(record):
                    new_count += 1

            return ScrapeResult(
                company=name,
                ats_type=ats,
                jobs_found=len(raw_jobs),
                jobs_new=new_count
            )

        except Exception as e:
            return ScrapeResult(
                company=name,
                ats_type=ats,
                jobs_found=0,
                jobs_new=0,
                errors=[str(e)]
            )

    def scrape_all_companies(self, max_workers: int = 8) -> List[ScrapeResult]:
        companies_cfg = self._load_yaml(self.companies_path)
        companies_list = companies_cfg.get("companies", [])

        results: List[ScrapeResult] = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_company = {
                executor.submit(self.scrape_single_company, c): c
                for c in companies_list
            }

            for future in as_completed(future_to_company):
                res = future.result()
                results.append(res)

        return results

    def run_aggregator_search(self, keywords: str = "Software Engineer", location: str = "Remote", limit: int = 25) -> ScrapeResult:
        """Run public search query across LinkedIn guest board."""
        scraper = self.scrapers.get("linkedin")
        if not isinstance(scraper, LinkedInGuestScraper):
            return ScrapeResult(company="LinkedIn Guest", ats_type="aggregator", jobs_found=0, jobs_new=0)

        try:
            raw_jobs = scraper.search_jobs(keywords=keywords, location=location, limit=limit)
            new_count = 0

            for job in raw_jobs:
                match_result: MatchResult = self.matcher.evaluate_job(job)
                record = JobRecord(job=job, match=match_result)
                if self.repository.upsert_job(record):
                    new_count += 1

            return ScrapeResult(
                company=f"LinkedIn ({keywords})",
                ats_type="aggregator",
                jobs_found=len(raw_jobs),
                jobs_new=new_count
            )
        except Exception as e:
            return ScrapeResult(
                company="LinkedIn Guest",
                ats_type="aggregator",
                jobs_found=0,
                jobs_new=0,
                errors=[str(e)]
            )
