"""
Advanced job matching and scoring engine.
Evaluates title similarity, core/secondary skills, omitted skills, and locations.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..models import JobPost, MatchResult
from .skills_extractor import SkillsExtractor


class JobMatcher:
    def __init__(self, profile_path: str = "config/profile.yaml", settings_path: str = "config/settings.yaml"):
        self.profile_path = profile_path
        self.settings_path = settings_path
        self.extractor = SkillsExtractor()
        self.profile = self._load_yaml(profile_path)
        self.settings = self._load_yaml(settings_path)

    def _load_yaml(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def reload_config(self):
        self.profile = self._load_yaml(self.profile_path)
        self.settings = self._load_yaml(self.settings_path)

    def _calculate_title_score(self, job_title: str, target_roles: List[str]) -> Tuple[float, bool]:
        if not target_roles:
            return 0.5, False

        clean_job_title = job_title.lower()

        # Exact or strong substring match
        for role in target_roles:
            role_clean = role.lower()
            if role_clean in clean_job_title or clean_job_title in role_clean:
                return 1.0, True

        # Token overlap matching
        job_tokens = set(re.findall(r"\w+", clean_job_title))
        best_overlap_ratio = 0.0

        for role in target_roles:
            role_tokens = set(re.findall(r"\w+", role.lower()))
            overlap = job_tokens.intersection(role_tokens)
            if role_tokens:
                ratio = len(overlap) / len(role_tokens)
                if ratio > best_overlap_ratio:
                    best_overlap_ratio = ratio

        is_matched = best_overlap_ratio >= 0.5
        return best_overlap_ratio, is_matched

    def evaluate_job(self, job: JobPost) -> MatchResult:
        full_text = f"{job.title}\n{job.location}\n{job.description}"

        exclusions = self.profile.get("exclusions", {})
        blacklist_companies = [c.lower() for c in exclusions.get("companies", [])]
        blacklist_titles = [t.lower() for t in exclusions.get("titles", [])]

        exclusion_reasons = []

        # 1. Company blacklist check
        if job.company.lower() in blacklist_companies:
            exclusion_reasons.append(f"Company '{job.company}' is in exclusion blacklist.")

        # 2. Title exclusion check
        job_title_lower = job.title.lower()
        for excluded_title in blacklist_titles:
            if re.search(rf"\b{re.escape(excluded_title)}\b", job_title_lower):
                exclusion_reasons.append(f"Title contains excluded keyword '{excluded_title}'.")
                break

        # 3. Target role evaluation
        target_roles = self.profile.get("target_roles", [])
        title_score, title_matched = self._calculate_title_score(job.title, target_roles)

        # 4. Skills extraction from Job Description
        job_skills = set(self.extractor.extract_skills(full_text))

        candidate_skills = self.profile.get("skills", {})
        core_skills = set(candidate_skills.get("core", []))
        secondary_skills = set(candidate_skills.get("secondary", []))
        all_candidate_skills = core_skills.union(secondary_skills)

        # Matched candidate skills
        matched_skills = sorted(list(job_skills.intersection(all_candidate_skills)))

        # Skills required by job that candidate lacks
        missing_skills = sorted(list(job_skills - all_candidate_skills))

        # 5. Omit Skills Detection (Negative keywords)
        omit_skills_config = self.profile.get("omit_skills", [])
        omitted_skills_found = []
        for omit_s in omit_skills_config:
            if self.extractor.has_skill(full_text, omit_s):
                omitted_skills_found.append(omit_s)

        # 6. Location & Remote evaluation
        locations_cfg = self.profile.get("locations", {})
        remote_only = locations_cfg.get("remote_only", False)
        preferred_locs = [loc.lower() for loc in locations_cfg.get("preferred", [])]

        job_loc_lower = (job.location or "").lower()
        location_matched = False

        if job.is_remote or "remote" in job_loc_lower:
            location_matched = True
        else:
            for pref in preferred_locs:
                if pref in job_loc_lower:
                    location_matched = True
                    break

        if remote_only and not (job.is_remote or "remote" in job_loc_lower):
            exclusion_reasons.append("Job is not Remote (profile specifies remote_only: true).")

        # 7. Calculate Weighted Match Score
        weights = self.settings.get("matching", {}).get("weights", {
            "title_match": 0.35,
            "core_skills": 0.40,
            "secondary_skills": 0.15,
            "location_match": 0.10
        })

        # Core skills coverage: matching 3-4 core skills is 100% coverage
        core_matched = core_skills.intersection(job_skills)
        core_target = min(len(core_skills), 4) if core_skills else 1
        core_score = min(len(core_matched) / core_target, 1.0) if core_target > 0 else 1.0

        # Secondary skills coverage: matching 2-3 secondary skills is 100% coverage
        secondary_matched = secondary_skills.intersection(job_skills)
        sec_target = min(len(secondary_skills), 2) if secondary_skills else 1
        secondary_score = min(len(secondary_matched) / sec_target, 1.0) if sec_target > 0 else 0.5

        location_score = 1.0 if location_matched else 0.3

        raw_score = (
            (title_score * weights.get("title_match", 0.35)) +
            (core_score * weights.get("core_skills", 0.40)) +
            (secondary_score * weights.get("secondary_skills", 0.15)) +
            (location_score * weights.get("location_match", 0.10))
        ) * 100

        # Apply Omit Skills Penalty
        omit_penalty_rate = self.settings.get("matching", {}).get("omit_skill_penalty", 30)
        total_omit_penalty = len(omitted_skills_found) * omit_penalty_rate
        final_score = max(0, min(100, int(round(raw_score - total_omit_penalty))))

        if exclusion_reasons:
            final_score = min(final_score, 25)

        is_eligible = len(exclusion_reasons) == 0 and len(omitted_skills_found) == 0

        # 8. Summary Generation
        summary_parts = []
        if matched_skills:
            summary_parts.append(f"✓ Skills: {', '.join(matched_skills[:6])}")
        if missing_skills:
            summary_parts.append(f"✗ Missing: {', '.join(missing_skills[:4])}")
        if omitted_skills_found:
            summary_parts.append(f"⚠ Warning (Omitted): {', '.join(omitted_skills_found)}")
        if exclusion_reasons:
            summary_parts.append(f"⛔ Excluded: {'; '.join(exclusion_reasons)}")

        summary = " | ".join(summary_parts) if summary_parts else "No specific skill keywords detected."

        return MatchResult(
            match_score=final_score,
            is_eligible=is_eligible,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            omitted_skills_found=omitted_skills_found,
            title_matched=title_matched,
            location_matched=location_matched,
            exclusion_reasons=exclusion_reasons,
            summary=summary
        )
