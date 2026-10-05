"""
Personalized Cold Outreach and Follow-up Email Templates.
Dynamically populated from candidate profile (config/profile.yaml).
"""

import os
import yaml
from pathlib import Path
from typing import NamedTuple, Optional, Dict, Any
from src.models import Contact, OutreachStage


class RenderedEmail(NamedTuple):
    subject: str
    body_text: str
    body_html: str


class TemplateEngine:
    """Renders high-converting, personalized cold outreach emails and follow-ups."""

    @classmethod
    def _load_profile(cls) -> Dict[str, Any]:
        """Dynamically load candidate info and skills from config/profile.yaml."""
        profile_path = Path("config/profile.yaml")
        if profile_path.exists():
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                pass
        return {}

    @classmethod
    def get_candidate_details(cls) -> Dict[str, str]:
        """Extract candidate metadata with intelligent defaults."""
        profile = cls._load_profile()
        candidate = profile.get("candidate", {})
        skills_cfg = profile.get("skills", {})
        core_skills = skills_cfg.get("core", [])

        name = candidate.get("name", "Candidate").strip()
        role = candidate.get("current_title", "Software Engineer").strip()
        exp = candidate.get("years_of_experience", 5)
        exp_str = f"{exp}+ years" if isinstance(exp, (int, float)) else str(exp)

        skills_str = ", ".join(core_skills[:7]) if core_skills else "React, TypeScript, JavaScript, Node.js, Python, PostgreSQL, REST APIs"
        linkedin = candidate.get("linkedin", "https://linkedin.com")
        github = candidate.get("github", "https://github.com")

        return {
            "name": name,
            "role": role,
            "experience": exp_str,
            "skills": skills_str,
            "linkedin": linkedin,
            "github": github,
        }

    @classmethod
    def _get_greeting(cls, contact: Contact) -> str:
        """Friendly, professional greeting handling missing or generic names."""
        first = contact.first_name.strip()
        if first and first.lower() not in ["talent", "recruiting", "recruiter", "team", "careers", "hr"]:
            return f"Hi {first},"
        if contact.name and contact.name.lower() not in ["talent acquisition team", "recruiting team", "careers team"]:
            parts = contact.name.split()
            if parts:
                return f"Hi {parts[0]},"
        return f"Hi {contact.company} Recruiting Team,"

    @classmethod
    def render_initial(cls, contact: Contact, role_focus: Optional[str] = None) -> RenderedEmail:
        """
        Stage 1: High-impact initial cold email.
        Concise (under 120 words), clear value proposition, low friction CTA.
        """
        c = cls.get_candidate_details()
        focus = role_focus or c["role"]
        greeting = cls._get_greeting(contact)
        company = contact.company.strip()

        subject = f"{focus} — {c['name']} ({company})"

        body_text = f"""{greeting}

I've been closely following {company}'s engineering work and wanted to reach out regarding open {focus} opportunities on your team.

I bring {c['experience']} of experience building high-scale web applications and responsive user interfaces, primarily working with {c['skills']}. In my recent work, I've focused on frontend architecture, state management performance, and building resilient full-stack systems.

Given {company}'s growth and technical roadmap, I'd love to explore how my background in scalable frontend and full-stack engineering could contribute to your engineering goals.

Would you be open to a brief 10-minute chat this week, or could you point me to the hiring manager leading frontend/full-stack hiring?

Best regards,

{c['name']}
{c['role']}
{c['linkedin']} | {c['github']}
"""

        body_html = f"""<html>
<body>
<p>{greeting}</p>
<p>I've been closely following <strong>{company}</strong>'s engineering work and wanted to reach out regarding open <strong>{focus}</strong> opportunities on your team.</p>
<p>I bring <strong>{c['experience']}</strong> of experience building high-scale web applications and responsive user interfaces, primarily working with <em>{c['skills']}</em>. In my recent work, I've focused on frontend architecture, state management performance, and building resilient full-stack systems.</p>
<p>Given {company}'s growth and technical roadmap, I'd love to explore how my background in scalable frontend and full-stack engineering could contribute to your engineering goals.</p>
<p>Would you be open to a brief 10-minute chat this week, or could you point me to the hiring manager leading frontend/full-stack hiring?</p>
<p>Best regards,<br>
<strong>{c['name']}</strong><br>
{c['role']}<br>
<a href="{c['linkedin']}">LinkedIn</a> | <a href="{c['github']}">GitHub</a>
</p>
</body>
</html>"""

        return RenderedEmail(subject=subject, body_text=body_text, body_html=body_html)

    @classmethod
    def render_followup_1(cls, contact: Contact, initial_subject: Optional[str] = None) -> RenderedEmail:
        """
        Stage 2: 1st Follow-up (sent after ~12-24 hours).
        Polite bump, keeping the original thread.
        """
        c = cls.get_candidate_details()
        greeting = cls._get_greeting(contact)
        company = contact.company.strip()

        subject = f"Re: {initial_subject}" if initial_subject and not initial_subject.startswith("Re:") else (initial_subject or f"Re: {c['role']} — {c['name']} ({company})")

        body_text = f"""{greeting}

Following up on my previous note. I know inboxes get busy, so I wanted to briefly check in regarding frontend and full-stack engineering openings at {company}.

I'm actively exploring roles where I can leverage my {c['experience']} in React, TypeScript, Node.js, and modern web architecture to build high-performance products.

Happy to share my resume or hop on a quick 10-minute call if you have a moment this week.

Thanks for your time,

{c['name']}
{c['role']}
"""

        body_html = f"""<html>
<body>
<p>{greeting}</p>
<p>Following up on my previous note. I know inboxes get busy, so I wanted to briefly check in regarding frontend and full-stack engineering openings at <strong>{company}</strong>.</p>
<p>I'm actively exploring roles where I can leverage my <strong>{c['experience']}</strong> in <em>React, TypeScript, Node.js</em>, and modern web architecture to build high-performance products.</p>
<p>Happy to share my resume or hop on a quick 10-minute call if you have a moment this week.</p>
<p>Thanks for your time,<br>
<strong>{c['name']}</strong><br>
{c['role']}
</p>
</body>
</html>"""

        return RenderedEmail(subject=subject, body_text=body_text, body_html=body_html)

    @classmethod
    def render_followup_2(cls, contact: Contact, initial_subject: Optional[str] = None) -> RenderedEmail:
        """
        Stage 3: 2nd Follow-up (sent after ~24-48 hours).
        Graceful close-out, preserving goodwill, leaving contact details.
        """
        c = cls.get_candidate_details()
        greeting = cls._get_greeting(contact)
        company = contact.company.strip()

        subject = f"Re: {initial_subject}" if initial_subject and not initial_subject.startswith("Re:") else (initial_subject or f"Re: {c['role']} — {c['name']} ({company})")

        body_text = f"""{greeting}

I know you have a packed schedule, so I won't crowd your inbox any further. Just closing the loop for now.

If {company} is hiring for senior frontend or full-stack engineers in the future, please feel free to keep my details on file or connect with me directly on LinkedIn: {c['linkedin']}.

Wishing you and the {company} team continued success!

Best,

{c['name']}
{c['role']}
"""

        body_html = f"""<html>
<body>
<p>{greeting}</p>
<p>I know you have a packed schedule, so I won't crowd your inbox any further. Just closing the loop for now.</p>
<p>If <strong>{company}</strong> is hiring for senior frontend or full-stack engineers in the future, please feel free to keep my details on file or connect with me directly on <a href="{c['linkedin']}">LinkedIn</a>.</p>
<p>Wishing you and the {company} team continued success!</p>
<p>Best,<br>
<strong>{c['name']}</strong><br>
{c['role']}
</p>
</body>
</html>"""

        return RenderedEmail(subject=subject, body_text=body_text, body_html=body_html)

    @classmethod
    def render(cls, contact: Contact, stage: OutreachStage, initial_subject: Optional[str] = None) -> RenderedEmail:
        """Dispatch template rendering based on outreach stage."""
        if stage == OutreachStage.INITIAL:
            return cls.render_initial(contact)
        elif stage == OutreachStage.FOLLOWUP_1:
            return cls.render_followup_1(contact, initial_subject)
        elif stage == OutreachStage.FOLLOWUP_2:
            return cls.render_followup_2(contact, initial_subject)
        else:
            return cls.render_initial(contact)
