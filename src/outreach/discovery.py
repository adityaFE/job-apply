"""
Recruiter and HR Lead Discovery, Email Permutation, and Importer Subsystem.
"""

import csv
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

from src.models import Contact, ContactStatus

logger = logging.getLogger(__name__)


# Curated company to domain mapping for primary target tech companies
COMPANY_DOMAINS: Dict[str, str] = {
    # Indian Unicorns & Tech Startups
    "razorpay": "razorpay.com",
    "meesho": "meesho.com",
    "paytm": "paytm.com",
    "cred": "cred.club",
    "inmobi": "inmobi.com",
    "glance": "glance.com",
    "zeta": "zeta.tech",
    "thoughtworks": "thoughtworks.com",
    "pocket fm": "pocketfm.com",
    "pocketfm": "pocketfm.com",
    "browserstack": "browserstack.com",
    "valuelabs": "valuelabs.com",
    "swiggy": "swiggy.in",
    "flipkart": "flipkart.com",
    "zerodha": "zerodha.com",
    "phonepe": "phonepe.com",

    # GCCs in India & Global Enterprise
    "zscaler": "zscaler.com",
    "pure storage": "purestorage.com",
    "purestorage": "purestorage.com",
    "rubrik": "rubrik.com",
    "okta": "okta.com",
    "toast": "toasttab.com",
    "netskope": "netskope.com",
    "elastic": "elastic.co",
    "mongodb": "mongodb.com",
    "pagerduty": "pagerduty.com",
    "druva": "druva.com",
    "alphasense": "alpha-sense.com",
    "alpha sense": "alpha-sense.com",
    "databricks": "databricks.com",
    "cloudflare": "cloudflare.com",
    "cloudera": "cloudera.com",
    "crowdstrike": "crowdstrike.com",
    "akamai": "akamai.com",
    "servicenow": "servicenow.com",
    "wayfair": "wayfair.com",
    "ebay": "ebay.com",

    # Remote-First & Global Tech
    "gitlab": "gitlab.com",
    "supabase": "supabase.com",
    "cursor": "cursor.com",
    "perplexity": "perplexity.ai",
    "twilio": "twilio.com",
    "vercel": "vercel.com",
    "sentry": "sentry.io",
    "affirm": "affirm.com",
    "datadog": "datadoghq.com",
    "hopper": "hopper.com",
    "weave": "getweave.com",
    "bloomreach": "bloomreach.com",
    "coursera": "coursera.org",
    "highlevel": "gohighlevel.com",
    "gohighlevel": "gohighlevel.com",
    "confluent": "confluent.io",
    "fivetran": "fivetran.com",
    "globalization partners": "g-p.com",
    "g-p": "g-p.com",
    "gp": "g-p.com",
    "deel": "deel.com",
    "avalara": "avalara.com",
    "atlassian": "atlassian.com",
    "mercari": "mercari.com",
    "cimpress": "cimpress.com",
    "kake": "kake.com",
    "kakao": "kakao.com",
    "yahoo": "yahooinc.com",
    "yahoo!": "yahooinc.com",

    # Tier 1 US Tech & AI
    "openai": "openai.com",
    "anthropic": "anthropic.com",
    "stripe": "stripe.com",
    "figma": "figma.com",
    "coinbase": "coinbase.com",
    "linear": "linear.app",
    "reddit": "reddit.com",
    "discord": "discord.com",
    "airbnb": "airbnb.com",
    "pinterest": "pinterest.com",
    "palantir": "palantir.com",
    "spotify": "spotify.com",
    "coupang": "coupang.com",
    "linkedin": "linkedin.com",
    "meta": "meta.com",
    "google": "google.com",
    "microsoft": "microsoft.com",
    "amazon": "amazon.com",
    "rippling": "rippling.com",
    "salesforce": "salesforce.com",
    "uber": "uber.com",
    "nvidia": "nvidia.com",
    "nvdia": "nvidia.com",
    "yahoo": "yahooinc.com",
}


class EmailPermutator:
    """Generates standard corporate email permutation variations."""

    @staticmethod
    def clean_name(name_str: str) -> str:
        """Strip non-alphanumeric characters for email pattern generation."""
        return re.sub(r"[^a-zA-Z0-9]", "", name_str.lower().strip())

    @classmethod
    def generate_permutations(
        cls, first_name: str, last_name: str, domain: str
    ) -> List[str]:
        """
        Generate common corporate email permutations.
        Order by standard tech industry frequency:
        1. first.last@domain (e.g. aditya.anand@company.com) - ~55% of tech companies
        2. first@domain (e.g. aditya@company.com) - ~25% (startups / medium)
        3. f_initial.last@domain (e.g. aanand@company.com) - ~12% (enterprise / GCCs)
        4. first.l_initial@domain (e.g. adityaa@company.com) - ~4%
        5. first_last@domain (e.g. aditya_anand@company.com) - ~3%
        6. firstlast@domain (e.g. adityaanand@company.com) - ~1%
        """
        first = cls.clean_name(first_name)
        last = cls.clean_name(last_name)
        dom = domain.lower().strip().lstrip("@")

        if not first or not dom:
            return []

        if not last:
            return [f"{first}@{dom}"]

        f_init = first[0]
        l_init = last[0]

        patterns = [
            f"{first}.{last}@{dom}",      # aditya.anand@
            f"{first}@{dom}",             # aditya@
            f"{f_init}{last}@{dom}",      # aanand@
            f"{first}{l_init}@{dom}",     # adityaa@
            f"{first}_{last}@{dom}",      # aditya_anand@
            f"{first}{last}@{dom}",       # adityaanand@
        ]

        # Return unique ordered list
        seen = set()
        res = []
        for p in patterns:
            if p not in seen:
                seen.add(p)
                res.append(p)
        return res

    @classmethod
    def generate_talent_inboxes(cls, domain: str) -> List[str]:
        """Generate common role-based talent / recruiter mailboxes."""
        dom = domain.lower().strip().lstrip("@")
        if not dom:
            return []
        return [
            f"careers@{dom}",
            f"talent@{dom}",
            f"recruiting@{dom}",
            f"jobs@{dom}",
            f"hiring@{dom}",
            f"tech-hiring@{dom}",
        ]


class DomainMapper:
    """Manages company-to-domain resolutions."""

    @staticmethod
    def get_domain_for_company(company_name: str) -> Optional[str]:
        cleaned = company_name.lower().strip()
        if cleaned in COMPANY_DOMAINS:
            return COMPANY_DOMAINS[cleaned]

        # Fuzzy lookup
        for k, v in COMPANY_DOMAINS.items():
            if k in cleaned or cleaned in k:
                return v

        # Fallback: sanitize company name to domain
        sanitized = re.sub(r"[^a-zA-Z0-9]", "", cleaned)
        if sanitized:
            return f"{sanitized}.com"
        return None


class LeadDiscoveryManager:
    """Discovers, parses, and formats recruiter contacts for outreach."""

    def __init__(self):
        self.permutator = EmailPermutator()
        self.domain_mapper = DomainMapper()

    def create_contact_from_person(
        self,
        full_name: str,
        company: str,
        title: str = "Technical Recruiter",
        domain: Optional[str] = None,
        email_override: Optional[str] = None,
        linkedin_url: str = "",
        source: str = "manual",
    ) -> Contact:
        """Parse names, resolve domain, generate primary email and construct Contact."""
        parts = full_name.strip().split(maxsplit=1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        resolved_domain = domain or self.domain_mapper.get_domain_for_company(company) or "unknown.com"

        if email_override:
            email = email_override.strip().lower()
        else:
            perms = self.permutator.generate_permutations(first_name, last_name, resolved_domain)
            email = perms[0] if perms else f"careers@{resolved_domain}"

        return Contact(
            name=full_name.strip(),
            first_name=first_name,
            last_name=last_name,
            email=email,
            title=title.strip() or "Technical Recruiter",
            company=company.strip(),
            company_domain=resolved_domain,
            linkedin_url=linkedin_url.strip(),
            source=source,
            status=ContactStatus.QUEUED,
        )

    def import_from_csv(self, file_path: str) -> List[Contact]:
        """
        Import contacts from a CSV file.
        Accepts standard column headers:
        - name / full_name / recruiter_name
        - first_name, last_name
        - email / email_address
        - company / company_name
        - title / role / job_title
        - domain / company_domain
        - linkedin / linkedin_url
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        contacts: List[Contact] = []
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Normalize key names
                row_norm = {k.strip().lower().replace(" ", "_"): v.strip() for k, v in row.items() if k}

                name = row_norm.get("name") or row_norm.get("full_name") or row_norm.get("recruiter_name") or ""
                first_name = row_norm.get("first_name", "")
                last_name = row_norm.get("last_name", "")

                if not name and first_name:
                    name = f"{first_name} {last_name}".strip()

                if not name:
                    continue

                company = row_norm.get("company") or row_norm.get("company_name") or "Tech Company"
                title = row_norm.get("title") or row_norm.get("role") or row_norm.get("job_title") or "Technical Recruiter"
                email = row_norm.get("email") or row_norm.get("email_address") or ""
                domain = row_norm.get("domain") or row_norm.get("company_domain")
                linkedin = row_norm.get("linkedin") or row_norm.get("linkedin_url") or ""

                contact = self.create_contact_from_person(
                    full_name=name,
                    company=company,
                    title=title,
                    domain=domain,
                    email_override=email if email else None,
                    linkedin_url=linkedin,
                    source=f"csv:{path.name}",
                )
                contacts.append(contact)

        logger.info(f"Imported {len(contacts)} contacts from CSV: {file_path}")
        return contacts

    def import_from_json(self, file_path: str) -> List[Contact]:
        """Import contacts from JSON array of objects."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Expected a JSON array of contact objects.")

        contacts: List[Contact] = []
        for item in data:
            name = item.get("name") or f"{item.get('first_name', '')} {item.get('last_name', '')}".strip()
            if not name:
                continue
            contact = self.create_contact_from_person(
                full_name=name,
                company=item.get("company", "Tech Company"),
                title=item.get("title", "Technical Recruiter"),
                domain=item.get("domain") or item.get("company_domain"),
                email_override=item.get("email"),
                linkedin_url=item.get("linkedin_url", ""),
                source=f"json:{path.name}",
            )
            contacts.append(contact)

        logger.info(f"Imported {len(contacts)} contacts from JSON: {file_path}")
        return contacts

    def generate_starter_leads(self, target_companies: Optional[List[str]] = None) -> List[Contact]:
        """
        Generate curated starter recruiter contacts for Indian tech unicorns and Remote companies.
        Provides both talent team inboxes and typical talent acquisition lead structures.
        """
        companies = target_companies or [
            # Indian Tech Unicorns & Startups
            "Razorpay", "Meesho", "Paytm", "CRED", "InMobi", "Zeta", "Thoughtworks", "Pocket FM", "BrowserStack", "ValueLabs",
            # GCCs & Enterprise Tech
            "Pure Storage", "Okta", "Rubrik", "Zscaler", "Toast", "Elastic", "MongoDB", "PagerDuty", "Druva", "AlphaSense", "Databricks", "Cloudflare", "Cloudera", "CrowdStrike", "Akamai", "ServiceNow", "Wayfair", "Ebay",
            # Remote-First Tech
            "GitLab", "Supabase", "Cursor", "Perplexity", "Vercel", "Sentry", "Datadog", "Hopper", "Weave", "Bloomreach", "Coursera", "HighLevel", "Confluent", "Fivetran", "G-P", "Deel", "Avalara", "Atlassian", "Mercari", "Cimpress", "Twilio",
            # Tier 1 US Tech & AI
            "Stripe", "Figma", "Coinbase", "OpenAI", "Anthropic", "Linear", "Reddit", "Discord", "Airbnb", "Pinterest", "Palantir", "Spotify", "Coupang", "LinkedIn", "Meta", "Google", "Microsoft", "Amazon", "Rippling", "Salesforce", "Uber", "Nvidia", "Yahoo"
        ]

        contacts: List[Contact] = []
        for comp in companies:
            domain = self.domain_mapper.get_domain_for_company(comp)
            if not domain:
                continue

            # Add Talent Acquisition Lead
            contacts.append(
                Contact(
                    name=f"Talent Acquisition Team",
                    first_name="Talent",
                    last_name="Team",
                    email=f"talent@{domain}",
                    title="Talent Acquisition / Engineering Recruiting",
                    company=comp,
                    company_domain=domain,
                    source="curated_seed",
                    status=ContactStatus.QUEUED,
                    notes=f"General engineering talent mailbox for {comp}"
                )
            )

            # Add Careers / Hiring Mailbox
            contacts.append(
                Contact(
                    name=f"Tech Recruiting {comp}",
                    first_name="Recruiting",
                    last_name="Team",
                    email=f"careers@{domain}",
                    title="Engineering Recruiting Lead",
                    company=comp,
                    company_domain=domain,
                    source="curated_seed",
                    status=ContactStatus.QUEUED,
                    notes=f"Primary engineering careers channel for {comp}"
                )
            )

        return contacts
