"""
Unit tests for Candidate Matching Engine and negative keyword filtering.
"""

import pytest
from src.models import JobPost
from src.matching.matcher import JobMatcher


@pytest.fixture
def matcher():
    return JobMatcher()


def test_perfect_match_job(matcher):
    job = JobPost(
        id="test-1",
        company="Stripe",
        title="Senior Frontend Engineer",
        url="https://stripe.com/jobs/1",
        location="Remote",
        is_remote=True,
        ats_type="greenhouse",
        description="We are seeking a Senior Frontend Engineer experienced with React, TypeScript, JavaScript, Node.js, and PostgreSQL architecture."
    )
    match_score = matcher.evaluate_job(job)
    assert match_score.match_score >= 80
    assert "React" in match_score.matched_skills or "TypeScript" in match_score.matched_skills
    assert len(match_score.omitted_skills_found) == 0


def test_negative_omit_skill_penalty(matcher):
    job_with_omit = JobPost(
        id="test-2",
        company="Legacy Corp",
        title="Software Engineer",
        url="https://legacy.com/jobs/2",
        location="New York",
        is_remote=False,
        ats_type="lever",
        description="Looking for an engineer to maintain PHP and WordPress legacy systems alongside some Python scripts."
    )
    match_score = matcher.evaluate_job(job_with_omit)
    assert "PHP" in match_score.omitted_skills_found or "WordPress" in match_score.omitted_skills_found
    # Score should be heavily penalized
    assert match_score.match_score <= 50
