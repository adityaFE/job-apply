"""
Unit and integration tests for the Recruiter Lead Discovery and Cold Outreach Engine.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from src.models import Contact, ContactStatus, OutreachStage, EmailConfig
from src.outreach.discovery import EmailPermutator, DomainMapper, LeadDiscoveryManager
from src.outreach.templates import TemplateEngine
from src.outreach.sender import OutreachSender
from src.storage.repository import JobRepository
from src.storage.database import Database


def test_email_permutator():
    """Verify statistical tech industry email permutation ordering."""
    perms = EmailPermutator.generate_permutations("Aditya", "Anand", "stripe.com")
    assert len(perms) >= 4
    assert perms[0] == "aditya.anand@stripe.com"   # Top frequency ~55%
    assert perms[1] == "aditya@stripe.com"         # Startup / medium ~25%
    assert perms[2] == "aanand@stripe.com"         # Enterprise / GCC ~12%
    assert "adityaa@stripe.com" in perms

    # Single name fallback
    single = EmailPermutator.generate_permutations("Recruiter", "", "razorpay.com")
    assert single == ["recruiter@razorpay.com"]

    # Talent inboxes
    inboxes = EmailPermutator.generate_talent_inboxes("meesho.com")
    assert "careers@meesho.com" in inboxes
    assert "talent@meesho.com" in inboxes


def test_domain_mapper():
    """Verify known company domain resolution and fuzzy fallbacks."""
    assert DomainMapper.get_domain_for_company("Razorpay") == "razorpay.com"
    assert DomainMapper.get_domain_for_company("pure storage") == "purestorage.com"
    assert DomainMapper.get_domain_for_company("GitLab") == "gitlab.com"
    assert DomainMapper.get_domain_for_company("Databricks") == "databricks.com"
    assert DomainMapper.get_domain_for_company("UnknownStartupXYZ") == "unknownstartupxyz.com"


def test_lead_discovery_manager():
    """Verify lead contact creation from name and company."""
    mgr = LeadDiscoveryManager()
    contact = mgr.create_contact_from_person(
        full_name="Priya Sharma",
        company="Razorpay",
        title="Technical Recruiter"
    )
    assert contact.email == "priya.sharma@razorpay.com"
    assert contact.company == "Razorpay"
    assert contact.company_domain == "razorpay.com"
    assert contact.status == ContactStatus.QUEUED

    # Seed generation
    seeds = mgr.generate_starter_leads(["Razorpay", "Supabase"])
    assert len(seeds) >= 4
    assert any(c.email == "talent@razorpay.com" for c in seeds)
    assert any(c.email == "talent@supabase.com" for c in seeds)


def test_template_engine():
    """Verify multi-stage email template rendering and RFC threading headers."""
    contact = Contact(
        name="Sarah Jenkins",
        first_name="Sarah",
        last_name="Jenkins",
        email="sarah.jenkins@figma.com",
        company="Figma",
        company_domain="figma.com"
    )

    initial = TemplateEngine.render_initial(contact, "Senior Frontend Engineer")
    assert "Senior Frontend Engineer" in initial.subject
    assert "Hi Sarah," in initial.body_text
    assert "Figma" in initial.body_text
    assert "<html>" in initial.body_html

    followup_1 = TemplateEngine.render_followup_1(contact, initial.subject)
    assert followup_1.subject.startswith("Re: Senior Frontend Engineer")
    assert "Following up on my previous note" in followup_1.body_text

    followup_2 = TemplateEngine.render_followup_2(contact, initial.subject)
    assert followup_2.subject.startswith("Re: Senior Frontend Engineer")
    assert "closing the loop for now" in followup_2.body_text


def test_outreach_sender_dry_run():
    """Verify rate-limited batch dispatch in dry-run mode."""
    cfg = EmailConfig(
        enabled=True,
        username="test@example.com",
        password="app-password-123",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
    )
    sender = OutreachSender(cfg, dry_run=True)

    contacts_batch = [
        (
            Contact(name="Recruiter One", first_name="Recruiter", last_name="One", email="r1@test.com", company="TestCo"),
            OutreachStage.INITIAL,
            None,
            None
        ),
        (
            Contact(name="Recruiter Two", first_name="Recruiter", last_name="Two", email="r2@test.com", company="TestCo"),
            OutreachStage.INITIAL,
            None,
            None
        )
    ]

    result, send_results = sender.dispatch_batch(contacts_batch, max_batch=50)
    assert result.attempted == 2
    assert result.successful == 2
    assert result.failed == 0
    assert len(send_results) == 2
    assert send_results[0].success is True
    assert send_results[0].recipient == "r1@test.com"


def test_repository_outreach_lifecycle():
    """Verify SQLite CRUD, state transitions, and follow-up eligibility queries."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    db = Database(db_path=db_path)
    repo = JobRepository(db=db)

    contact = Contact(
        name="Alex Mercer",
        first_name="Alex",
        last_name="Mercer",
        email="alex.mercer@targetcorp.com",
        company="TargetCorp",
        company_domain="targetcorp.com",
        status=ContactStatus.QUEUED
    )

    is_new, contact_id = repo.upsert_contact(contact)
    assert is_new is True
    assert contact_id > 0

    # Retrieve
    fetched = repo.get_contact_by_email("alex.mercer@targetcorp.com")
    assert fetched is not None
    assert fetched.name == "Alex Mercer"
    assert fetched.status == ContactStatus.QUEUED

    # Update status to CONTACTED
    repo.update_contact_status(fetched.id, ContactStatus.CONTACTED)
    fetched_after = repo.get_contact_by_email("alex.mercer@targetcorp.com")
    assert fetched_after.status == ContactStatus.CONTACTED

    # Mark Replied
    repo.mark_contact_replied("alex.mercer@targetcorp.com")
    fetched_replied = repo.get_contact_by_email("alex.mercer@targetcorp.com")
    assert fetched_replied.status == ContactStatus.REPLIED

    # Stats check
    stats = repo.get_outreach_stats()
    assert stats.total_contacts >= 1
    assert stats.replied >= 1

    # Cleanup temp db
    Path(db_path).unlink(missing_ok=True)
