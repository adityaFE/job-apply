"""
Base scraper interface and shared utilities.
"""

import hashlib
import re
from abc import ABC, abstractmethod
from typing import List, Optional
from bs4 import BeautifulSoup

from ..models import JobPost


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, application/xhtml+xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


class BaseScraper(ABC):
    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.headers = DEFAULT_HEADERS

    @abstractmethod
    def scrape_company(self, company_name: str, slug: str) -> List[JobPost]:
        """Scrape all available job listings for a specific company."""
        pass

    @staticmethod
    def generate_job_id(company: str, title: str, url: str) -> str:
        """Generate deterministic unique SHA-256 hash."""
        raw = f"{company.strip().lower()}:{title.strip().lower()}:{url.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def clean_html(raw_html: Optional[str]) -> str:
        """Strips HTML tags, scripts, and collapses whitespace into clean plain text."""
        if not raw_html:
            return ""
        soup = BeautifulSoup(raw_html, "html.parser")

        # Remove scripts, styles
        for element in soup(["script", "style", "noscript", "meta", "head"]):
            element.decompose()

        text = soup.get_text(separator="\n")
        # Collapse multiple newlines/spaces
        cleaned = re.sub(r"\n\s*\n+", "\n\n", text).strip()
        return cleaned
