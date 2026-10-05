"""
Unit tests for Local Email Classification and Entity Matching.
"""

from src.models import EmailCategory
from src.email_tracker.classifier import EmailClassifier


def test_confirmation_classification():
    subject = "Thank you for applying to Stripe!"
    body = "Hi Aditya, We have received your application for Senior Software Engineer. Our talent team is reviewing your profile."
    sender_email = "jobs@stripe.com"
    sender_name = "Stripe Recruiting"

    category = EmailClassifier.classify_category(subject, body)
    assert category == EmailCategory.CONFIRMATION

    company = EmailClassifier.extract_company_name(sender_email, sender_name, subject, body)
    assert company.lower() == "stripe"


def test_interview_classification():
    subject = "Invitation to Interview with Anthropic"
    body = "Hi there, We'd love to schedule a technical chat regarding the AI Research Engineer opening. Please find time on my Calendly."
    sender_email = "recruiting@anthropic.com"
    sender_name = "Anthropic Talent"

    category = EmailClassifier.classify_category(subject, body)
    assert category == EmailCategory.INTERVIEW

    company = EmailClassifier.extract_company_name(sender_email, sender_name, subject, body)
    assert company.lower() == "anthropic"


def test_rejection_classification():
    subject = "Update on your application with Acme Corp"
    body = "Thank you for taking the time to interview with us. After careful consideration, we have decided to pursue other candidates whose experience more closely aligns with our current needs."
    sender_email = "no-reply@acme.com"
    sender_name = "Acme Corp Careers"

    category = EmailClassifier.classify_category(subject, body)
    assert category == EmailCategory.REJECTION

    company = EmailClassifier.extract_company_name(sender_email, sender_name, subject, body)
    assert "acme" in company.lower()
