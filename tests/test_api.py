"""
Integration tests for FastAPI REST Endpoints.
"""

from fastapi.testclient import TestClient
from src.dashboard.app import app

client = TestClient(app)


def test_api_dashboard_html_view():
    response = client.get("/")
    assert response.status_code == 200
    assert "Job Apply Intelligence Hub" in response.text


def test_api_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_jobs" in data
    assert "status_counts" in data
    assert "total_emails" in data


def test_api_filter_options():
    response = client.get("/api/filter-options")
    assert response.status_code == 200
    data = response.json()
    assert "profile_skills" in data
    assert "profile_omit_skills" in data


def test_api_jobs_query():
    response = client.get("/api/jobs?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "jobs" in data
    assert isinstance(data["jobs"], list)


def test_api_profile_config():
    response = client.get("/api/config/profile")
    assert response.status_code == 200
    data = response.json()
    assert "target_roles" in data
    assert "skills" in data


def test_api_email_config_masked():
    response = client.get("/api/email/config")
    assert response.status_code == 200
    data = response.json()
    assert "has_password" in data
    # Raw password should not be exposed
    if data["has_password"]:
        assert data["password"] == "********"
