"""
Rule-based email intent classifier and company/role entity extractor.
Classifies recruitment emails into lifecycle categories and identifies companies.
"""

import re
from typing import Tuple, Optional, Dict, Any
from ..models import EmailCategory, JobStatus


# Common ATS domains and known recruiter platform domains
ATS_DOMAINS = {
    "greenhouse.io": "Greenhouse",
    "greenhouse-mail.io": "Greenhouse",
    "ghmail.greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "lever-mail.co": "Lever",
    "ashbyhq.com": "Ashby",
    "ashby-mail.com": "Ashby",
    "smartrecruiters.com": "SmartRecruiters",
    "workday.com": "Workday",
    "myworkday.com": "Workday",
    "icims.com": "iCIMS",
    "bamboohr.com": "BambooHR",
    "breezy.hr": "Breezy",
    "jazzhr.com": "JazzHR",
    "jobvite.com": "Jobvite",
    "recruitee.com": "Recruitee",
    "workable.com": "Workable",
    "rippling.com": "Rippling"
}

# Generic domain providers that do not correspond to a company
GENERIC_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com",
    "outlook.com", "icloud.com", "protonmail.com", "zoho.com",
    "mail.com", "aol.com"
}


# Intent Classification Keywords and Patterns
PATTERNS_OFFER = [
    r"\boffer\s+letter\b",
    r"\boffer\s+of\s+employment\b",
    r"\bpleased\s+to\s+offer\b",
    r"\bcongratulations\s+on\s+your\s+offer\b",
    r"\bwelcome\s+to\s+the\s+team\b",
    r"\bjob\s+offer\b",
    r"\boffer\s+details\b",
]

PATTERNS_REJECTION = [
    r"\bnot\s+(to\s+)?moving\s+forward\b",
    r"\bwill\s+not\s+be\s+moving\s+forward\b",
    r"\bdecided\s+not\s+to\s+move\s+forward\b",
    r"\bdecided\s+to\s+pursue\s+other\s+candidates\b",
    r"\bmoving\s+forward\s+with\s+other\s+candidates\b",
    r"\bselected\s+another\s+candidate\b",
    r"\bunfortunately\b.*\b(not|unable|decided)\b",
    r"\bafter\s+careful\s+consideration\b",
    r"\bnot\s+a\s+fit\s+at\s+this\s+time\b",
    r"\bposition\s+has\s+been\s+filled\b",
    r"\bdecided\s+not\s+to\s+proceed\b",
    r"\bwe\s+regret\s+to\s+inform\b",
]

PATTERNS_INTERVIEW = [
    r"\binvitation\s+to\s+interview\b",
    r"\binterview\s+invitation\b",
    r"\bschedule\s+(an?|your|the)\s+interview\b",
    r"\btime\s+to\s+connect\b",
    r"\bphone\s+screen\b",
    r"\brecruiter\s+(screen|chat|call)\b",
    r"\bhiring\s+manager\s+(interview|chat|call|speak)\b",
    r"\btechnical\s+interview\b",
    r"\bvirtual\s+onsite\b",
    r"\bonsite\s+interview\b",
    r"\bcalendly\.com\b",
    r"\bgood\s+time\s+to\s+speak\b",
    r"\bwould\s+like\s+to\s+schedule\b",
    r"\bnext\s+steps\s+in\s+the\s+(interview\s+)?process\b",
    r"\bavailability\s+for\s+a\s+(call|chat|interview)\b",
]

PATTERNS_ASSESSMENT = [
    r"\bonline\s+assessment\b",
    r"\bcoding\s+assessment\b",
    r"\bcoding\s+challenge\b",
    r"\btechnical\s+assessment\b",
    r"\btake-?home\s+(challenge|test|assignment|project)\b",
    r"\bhackerrank\b",
    r"\bcodesignal\b",
    r"\bcoderbyte\b",
    r"\bbyteboard\b",
    r"\bkarat\b",
    r"\bcodility\b",
    r"\bqualified\.io\b",
]

PATTERNS_CONFIRMATION = [
    r"\bthank\s+you\s+for\s+applying\b",
    r"\bthanks\s+for\s+applying\b",
    r"\bapplication\s+(has\s+been\s+)?received\b",
    r"\bwe('ve|\s+have)\s+received\s+your\s+application\b",
    r"\bconfirmation\s+of\s+your\s+application\b",
    r"\bapplication\s+submitted\b",
    r"\bsuccessfully\s+submitted\s+your\s+application\b",
    r"\bthanks\s+for\s+your\s+interest\s+in\b",
    r"\bthank\s+you\s+for\s+your\s+interest\s+in\b",
    r"\bapplication\s+confirmation\b",
    r"\byour\s+application\s+for\b",
]


class EmailClassifier:
    """Classifies email messages and extracts recruitment metadata."""

    @staticmethod
    def classify_category(subject: str, body: str) -> EmailCategory:
        """Classify email category based on subject line and body text."""
        text = f"{subject}\n{body}".lower()

        # Highest priority: Offer
        for pat in PATTERNS_OFFER:
            if re.search(pat, text, re.IGNORECASE):
                return EmailCategory.OFFER

        # Second priority: Rejection
        for pat in PATTERNS_REJECTION:
            if re.search(pat, text, re.IGNORECASE):
                return EmailCategory.REJECTION

        # Third priority: Assessment
        for pat in PATTERNS_ASSESSMENT:
            if re.search(pat, text, re.IGNORECASE):
                return EmailCategory.ASSESSMENT

        # Fourth priority: Interview
        for pat in PATTERNS_INTERVIEW:
            if re.search(pat, text, re.IGNORECASE):
                return EmailCategory.INTERVIEW

        # Fifth priority: Confirmation
        for pat in PATTERNS_CONFIRMATION:
            if re.search(pat, text, re.IGNORECASE):
                return EmailCategory.CONFIRMATION

        return EmailCategory.GENERAL

    @staticmethod
    def category_to_job_status(category: EmailCategory) -> Optional[JobStatus]:
        """Maps an email category to an automated target JobStatus."""
        mapping = {
            EmailCategory.CONFIRMATION: JobStatus.APPLIED,
            EmailCategory.ASSESSMENT: JobStatus.INTERVIEW,
            EmailCategory.INTERVIEW: JobStatus.INTERVIEW,
            EmailCategory.OFFER: JobStatus.OFFER,
            EmailCategory.REJECTION: JobStatus.REJECTED,
        }
        return mapping.get(category)

    @staticmethod
    def extract_company_name(sender_email: str, sender_name: str, subject: str, body: str) -> str:
        """
        Heuristically extracts company name from sender domain, headers, and subject line.
        """
        # 1. Check subject patterns (e.g. "Your application to Stripe", "Thank you for applying to Figma")
        subject_patterns = [
            r"(?:application|applying|applied)\s+(?:to|at|for)\s+([A-Za-z0-9\.\s&-]+?)(?:\s+-\s+|\s+for\s+|\s+as\s+|\s+role|\s+position|\!|\?|\.|$)",
            r"(?:welcome to|interview with|team at)\s+([A-Za-z0-9\.\s&-]+?)(?:\s+-\s+|\s+for\s+|\s+as\s+|\!|\?|\.|$)",
            r"\[([A-Za-z0-9\.\s&-]+)\]\s+(?:Thank you|Application|Interview|Status|Update)",
            r"([A-Za-z0-9\.\s&-]+)\s+(?:Careers|Recruiting|Talent|Hiring|Jobs)",
        ]

        for pat in subject_patterns:
            m = re.search(pat, subject, re.IGNORECASE)
            if m:
                extracted = m.group(1).strip()
                # Validate length and cleanup
                if 2 <= len(extracted) <= 35 and not any(w in extracted.lower() for w in ["your", "the", "a", "an", "new"]):
                    return EmailClassifier._clean_company_name(extracted)

        # 2. Check Sender Name (e.g. "Stripe Recruiting", "Datadog Careers", "OpenAI Talent")
        if sender_name:
            clean_sender = re.sub(r"(?i)\b(recruiting|careers|talent|jobs|hiring|team|notifications|no-reply|hr|people)\b", "", sender_name)
            clean_sender = clean_sender.strip(" -_:")
            if 2 <= len(clean_sender) <= 35 and not any(w in clean_sender.lower() for w in ["google", "microsoft", "yahoo", "mailer"]):
                return EmailClassifier._clean_company_name(clean_sender)

        # 3. Check Domain Name of Sender
        domain_match = re.search(r"@([a-zA-Z0-9\.\-]+)", sender_email)
        if domain_match:
            domain = domain_match.group(1).lower()

            # If it's an ATS domain (e.g. no-reply@greenhouse.io), attempt to find company in subject
            if domain in ATS_DOMAINS:
                # Re-check body or subject for company
                body_match = re.search(r"(?:thank you for applying to|interest in)\s+([A-Za-z0-9\s]+)", body[:500], re.IGNORECASE)
                if body_match:
                    return EmailClassifier._clean_company_name(body_match.group(1))
                return ATS_DOMAINS[domain]

            # If not a generic public provider, extract domain root
            if domain not in GENERIC_DOMAINS:
                parts = domain.split(".")
                if len(parts) >= 2:
                    root_name = parts[-2] if parts[-1] in ["com", "io", "co", "org", "ai", "net", "app", "dev"] else parts[0]
                    return EmailClassifier._clean_company_name(root_name)

        return "Unknown Company"

    @staticmethod
    def extract_role_title(subject: str, body: str) -> Optional[str]:
        """Extracts job title hint from subject or early body text."""
        patterns = [
            r"(?:for|role of|position of|as an?)\s+([A-Za-z0-9\s/]+?(?:Engineer|Developer|Architect|Scientist|Manager|Specialist|Analyst|Designer|Lead))",
            r"([A-Za-z0-9\s/]+?(?:Engineer|Developer|Architect|Scientist|Manager|Specialist|Analyst|Designer|Lead))\s+(?:Application|Role|Position)",
        ]

        for pat in patterns:
            m = re.search(pat, subject, re.IGNORECASE)
            if m:
                return m.group(1).strip()

        # Check early body
        for pat in patterns:
            m = re.search(pat, body[:400], re.IGNORECASE)
            if m:
                return m.group(1).strip()

        return None

    @staticmethod
    def _clean_company_name(name: str) -> str:
        """Standardizes capitalization and trims suffixes like Inc, LLC, Corp."""
        name = re.sub(r"(?i)\b(inc\.?|llc\.?|corp\.?|ltd\.?|co\.?|corporation|technologies|solutions)\b", "", name)
        name = name.strip(" ,.-_:")
        if not name:
            return "Unknown Company"
        # Title case if all lowercase
        if name.islower():
            return name.title()
        return name
