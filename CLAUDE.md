# Job Apply Intelligence Hub — Project Context

> **Purpose of this file:** This is the persistent context file for AI coding assistants.
> Any new chat session should read this first to understand the project state, architecture,
> what has been built, what's configured, and what to work on next.

---

## 🧑 User Profile

- **Name:** Aditya Anand
- **Role:** Full Stack / Frontend Engineer (~5.5 years experience)
- **Target Jobs:** Frontend Engineer, Full Stack Engineer, Senior Frontend Engineer, Software Engineer
- **Target Locations:** India (Bengaluru, Hyderabad, Pune, Noida, Gurgaon, Chennai) + Remote globally
- **Core Stack:** JavaScript, TypeScript, React, Node.js, Python, MongoDB, PostgreSQL, HTML/CSS, Express.js, REST APIs, Git
- **Secondary:** Redis, Kubernetes, GraphQL, CI/CD, Linux, Next.js, Tailwind
- **Omit/Exclude:** PHP, Ruby on Rails, WordPress, Salesforce, .NET, COBOL, Perl, Flash, Manual QA
- **Config file:** `config/profile.yaml`

---

## 🏗️ What This Project Is

A **local-first job application intelligence hub** that:

1. **Scrapes public ATS portals** (Greenhouse, Lever, Ashby) for job listings from 39+ target companies
2. **AI-scores every job** against the user's profile using a weighted matching engine
3. **Tracks recruitment emails** via local IMAP (Gmail App Password) and auto-transitions job statuses
4. **Serves a web dashboard** (FastAPI + vanilla JS) at `http://127.0.0.1:8000` for filtering, searching, and managing applications
5. **Stores everything locally** in SQLite (`data/jobs.db`) — zero cloud dependencies

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn |
| Frontend | Vanilla JS + CSS (Jinja2 templates) |
| Database | SQLite with WAL mode (`data/jobs.db`) |
| ATS Scrapers | Python `requests` — direct public API calls (no browser automation) |
| Email Tracker | IMAP (imaplib) — local-only email parsing and classification |
| Match Scoring | Custom weighted engine (Title 35%, Core Skills 40%, Secondary 15%, Location 10%, -30% per omitted skill) |

---

## 📁 Project Structure

```
job-apply/
├── cli.py                          # Main CLI entry point (all commands)
├── run_dashboard.py                # Quick dashboard launcher
├── config/
│   ├── companies.yaml              # Target companies + ATS slugs (39 companies)
│   ├── profile.yaml                # Candidate profile, skills, preferences
│   └── email.yaml                  # IMAP email tracking config (created after setup)
├── data/
│   └── jobs.db                     # SQLite database (all jobs, emails, events)
├── src/
│   ├── models.py                   # Pydantic models (JobPost, MatchResult, FilterCriteria, etc.)
│   ├── dashboard/
│   │   ├── app.py                  # FastAPI application (REST API + HTML serving)
│   │   ├── static/
│   │   │   ├── app.js              # Frontend controller (state, filters, rendering)
│   │   │   └── style.css           # Dashboard styles
│   │   └── templates/
│   │       └── index.html          # Main dashboard HTML template
│   ├── scrapers/
│   │   ├── manager.py              # ScraperManager — orchestrates all scrapers
│   │   ├── greenhouse.py           # Greenhouse public API scraper
│   │   ├── lever.py                # Lever public API scraper
│   │   ├── ashby.py                # Ashby public API scraper
│   │   └── linkedin_guest.py       # LinkedIn public guest search
│   ├── matching/
│   │   ├── matcher.py              # JobMatcher — weighted scoring engine
│   │   └── skills_extractor.py     # Skills taxonomy + regex alias extraction
│   ├── storage/
│   │   ├── database.py             # SQLite connection manager (WAL mode)
│   │   └── repository.py           # JobRepository — CRUD, queries, rescore, timeline
│   └── email_tracker/
│       ├── __init__.py             # EmailSyncManager, load/save config
│       ├── syncer.py               # IMAP sync engine
│       ├── parser.py               # RFC 2047/MIME email parser
│       └── classifier.py           # Heuristic intent classifier (application, interview, rejection)
├── tests/                          # Test suite
├── requirements.txt                # Python dependencies
└── README.md                       # Full documentation
```

---

## 🚀 How to Run

### Full Pipeline (recommended)
```bash
python cli.py run
```
This does: DB init → scrape all companies → sync emails (if configured) → launch dashboard at `http://127.0.0.1:8000`

### Individual Commands
```bash
python cli.py scrape              # Scrape all 39 companies
python cli.py rescore             # Re-score all jobs after profile.yaml changes
python cli.py serve               # Launch web dashboard only
python cli.py list --min-score 50 # Terminal listing of top matches
python cli.py stats               # Show application funnel metrics
python cli.py sync-emails         # Sync recruitment emails via IMAP
python cli.py export-csv          # Export jobs to CSV
python cli.py search-linkedin     # LinkedIn public job search
```

---

## 📊 Current Database State (as of 2026-10-05)

| Metric | Value |
|--------|-------|
| Total Jobs | 7,877 |
| India Jobs | 781 |
| Remote Jobs | 2,658 |
| Companies Tracked | 56 |
| Jobs with 50%+ Match | 856 |
| Average Match Score | 21% |

### Top Companies by India Openings
Okta (98), Pure Storage (94), MongoDB (77), Zscaler (71), Meesho (49), Paytm (49), Stripe (47), InMobi (34), Rubrik (33), GitLab (30)

---

## 🏢 Monitored Companies (`config/companies.yaml`)

### Indian Tech Unicorns & Startups
Razorpay, Meesho, Paytm, CRED, InMobi, Glance, Zeta, Thoughtworks, Pocket FM

### Global Capability Centers (GCCs) in India
Zscaler, Pure Storage, Rubrik, Okta, Toast, Netskope, Elastic, MongoDB, PagerDuty

### Remote-First Global Companies
GitLab, Supabase, Cursor, Perplexity, Twilio, Vercel, Sentry, Affirm, Datadog

### US Tech & AI Companies
OpenAI, Anthropic, Stripe, Figma, Coinbase, Linear, Reddit, Discord, Airbnb, Pinterest, Palantir, Spotify

---

## ⚙️ Key Configuration Details

### Match Scoring Formula
- **Title Alignment:** 35% — does the job title match target roles?
- **Core Skills Match:** 40% — overlap with core skills list
- **Secondary Skills:** 15% — overlap with secondary skills
- **Location Match:** 10% — is the job in a preferred location or remote?
- **Omit Penalty:** -30% per omitted skill found in job description

### Dashboard Defaults
- **Date Filter:** "Any Time" (no time restriction)
- **Min Score Filter:** 0% (show all scores)
- **Sort:** Highest Match Score first
- **Limit:** 50 jobs per page

### Email Tracking (IMAP)
- Uses Gmail App Passwords (2FA required)
- 100% local processing — credentials stay in `config/email.yaml`
- Auto-detects: application confirmations, interview invites, rejections
- Auto-transitions job status when emails match

---

## 🔄 Important Workflows

### After Editing `config/profile.yaml`
The database does NOT auto-update. Run:
```bash
python cli.py rescore
```
This re-evaluates all 7,877 jobs against the new profile without re-scraping.

### After Adding Companies to `config/companies.yaml`
```bash
python cli.py scrape --workers 12
```

### Re-score via Dashboard API
```
POST http://127.0.0.1:8000/api/rescore
```

### View Database Directly
Open `data/jobs.db` in VS Code with the SQLite extension, or:
```bash
sqlite3 data/jobs.db "SELECT company, count(*) FROM jobs GROUP BY company ORDER BY count(*) DESC LIMIT 15;"
```

---

## 📝 Session History & Decisions Made

### Session 1 (2026-09-27 to 2026-10-05)

1. **Built the full `python cli.py run` command** — unified pipeline that initializes DB, scrapes all companies, syncs emails, and launches the dashboard in one step.

2. **Wrote comprehensive README.md** — covers quickstart, all CLI commands, email setup flow, scoring formula, and directory structure.

3. **Diagnosed static match scores issue** — after editing `config/profile.yaml`, old scores persisted because the DB wasn't re-evaluated. Built `rescore_all_jobs()` in the repository layer, exposed it as:
   - CLI: `python cli.py rescore`
   - API: `POST /api/rescore`
   - Dashboard: Profile modal's "Save & Re-evaluate Matches" button

4. **Expanded target companies massively** — researched and added Indian unicorns, GCCs operating in India, and remote-first employers. Verified every ATS slug endpoint is active before adding. Went from ~15 US-only companies to 39 companies across India + Remote + Global.

5. **Fixed dashboard filter defaults** — changed from restrictive (7 days, 50% min score) to open (Any Time, 0% min score) so the user sees all jobs immediately and can narrow down from there.

6. **Email tracking setup** — documented Gmail App Password flow for local IMAP tracking. All email data stays local in SQLite.

7. **Database inspection** — guided setup of VS Code SQLite extension for visual DB browsing.

---

## 🔮 Potential Next Steps / Ideas

- [ ] Add more Indian companies (Flipkart via their careers API, Swiggy, Zerodha, PhonePe, etc.)
- [ ] Implement auto-scheduled scraping (cron jobs or background scheduler)
- [ ] Add resume upload and per-job cover letter generation
- [ ] Build job application auto-fill (if company has simple apply forms)
- [ ] Add Slack/Telegram notifications for new high-match jobs
- [ ] Dashboard dark mode toggle
- [ ] Export filtered results to Google Sheets
- [ ] Add Workday ATS scraper (many large companies use it)
- [ ] Job description summarization with LLM
- [ ] Salary estimation from job descriptions
