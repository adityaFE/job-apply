# ⚡ Job Apply Intelligence Hub & Local Application Tracker

An all-in-one, privacy-first, ban-proof job intelligence, ATS aggregation, profile match scoring, recruiter lead discovery, and cold outreach automation platform.

It queries official company career platforms (**Greenhouse**, **Lever**, **Ashby**) and public aggregators directly without personal credentials or ban risks. It scores jobs against your custom candidate profile, penalizes unwanted technologies, allows 1-click manual applications, synchronizes recruitment emails locally via **IMAP**, discovers recruiter leads with statistical email permutations, sends threaded cold outreach via **SMTP**, and tracks your full application lifecycle in a high-performance **local SQLite database**.

---

## 🚀 Quick Start (Get Running in 2 Minutes)

```bash
# 1. Clone the repository
git clone https://github.com/your-username/job-apply.git
cd job-apply

# 2. Create & activate virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# .\venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy configuration templates
cp config/profile.example.yaml config/profile.yaml
cp config/email.example.yaml config/email.yaml

# 5. Run the full pipeline (DB init + ATS scrape + email sync + web dashboard)
python cli.py run
```

Open **http://127.0.0.1:8000** in your browser — you're live.

---

## 🌟 Core Platform Capabilities

### 1. 🛡️ Ban-Proof Direct ATS & Guest Ingestion
- **Greenhouse REST Ingestion**: Queries public board APIs (`boards-api.greenhouse.io/v1/boards/{slug}/jobs`) to pull clean job listings, departments, office locations, and HTML descriptions.
- **Lever Postings Ingestion**: Fetches active listings directly from Lever's public API (`api.lever.co/v0/postings/{slug}`).
- **Ashby Job Board Ingestion**: Retrieves postings from Ashby's public API (`api.ashbyhq.com/posting-api/job-board/{slug}`).
- **LinkedIn Public Guest Aggregator**: Searches public guest job listings by role and location without requiring an account login or browser automation.
- **Deduplication Engine**: Generates unique cryptographic SHA-256 hashes per job post to prevent duplicate entries while preserving user notes, statuses, and timeline history across scrape runs.

### 2. 🎯 Intelligent Matching & Negative Keyword Penalization
- **Rule-Based Skill Extraction**: 100+ technology taxonomy handling aliases (e.g. `JS` → `JavaScript`, `K8s` → `Kubernetes`, `Postgres` → `PostgreSQL`, `TS` → `TypeScript`).
- **Weighted Scoring Model**:
  - **Target Role Alignment** ($35\%$): Exact and token-overlap fuzzy matching.
  - **Core Skills** ($40\%$): High-priority skills (e.g., TypeScript, React, Node.js, Python, PostgreSQL).
  - **Secondary Skills** ($15\%$): Bonus technologies (e.g., Redis, Kubernetes, GraphQL, Next.js).
  - **Location Alignment** ($10\%$): Remote flag or target city matching.
- **Omit / Negative Skill Penalties**: Automatically docks $-30\%$ match score per detected unwanted keyword (e.g. `PHP`, `WordPress`, `Salesforce`, `Ruby on Rails`, `COBOL`) and marks jobs with exclusion warnings.

### 3. 👥 Recruiter Lead Discovery & Cold Outreach Automation
- **Statistical Email Permutator**: Generates corporate email patterns adhering to tech industry frequency distributions:
  - `first.last@domain` (~55% market frequency)
  - `first@domain` (~25% startup / tech frequency)
  - `f_initial.last@domain` (~12% enterprise / GCC frequency)
  - `first.l_initial@domain` (~4%)
  - `first_last@domain` (~3%)
  - `firstlast@domain` (~1%)
  - Role-based fallback inboxes: `talent@`, `careers@`, `recruiting@`, `jobs@`
- **Domain Resolver for 60+ Companies**: Auto-resolves company names to corporate domains across Indian tech unicorns (Razorpay, Meesho, CRED, InMobi, Paytm, Zeta), GCCs (Zscaler, Pure Storage, Rubrik, Okta, Toast), Remote-First companies (GitLab, Supabase, Vercel, Sentry, Datadog), and Tier 1 US/Global Tech (Stripe, Airbnb, Figma, Databricks, Uber).
- **Dynamic Profile Hydration**: Multi-stage email templates dynamically pull candidate name, current title, years of experience, core skills, and portfolio links from `config/profile.yaml`.
- **RFC 2822 MIME Email Threading**: Injects persistent `<uuid@domain>` `Message-ID` headers on initial emails and links `In-Reply-To` and `References` headers for Round 1 (12–24h) and Round 2 (24–48h) follow-ups to keep messages neatly organized in the recipient's thread.
- **Autonomous IMAP Reply Detection**: Scans incoming recruiter responses via IMAP and auto-updates contact status to `REPLIED`, permanently halting further automated follow-ups.
- **Rate-Limited Batch Dispatch & Anti-Spam Safety**: Strictly enforces a 50-email batch limit per run with randomized human-like jitter delays (6.0–14.0s) between consecutive SMTP transactions.

### 4. 📬 Local IMAP Recruitment Email Ingestion & Classification
- **Direct Mailbox Sync**: Connects locally over TLS/SSL to Gmail (via App Password), Outlook, Apple Mail, or custom IMAP servers.
- **Local Heuristic Intent Classifier**: Categorizes incoming emails into:
  - 📩 `CONFIRMATION`: Application received / under review.
  - 📅 `INTERVIEW`: Recruiter phone screens, technical rounds, Calendly links.
  - 💻 `ASSESSMENT`: Take-home coding challenges, HackerRank, CodeSignal.
  - 🎉 `OFFER`: Formal offers, compensation details.
  - ❌ `REJECTION`: Non-advancement notices.
  - 💬 `GENERAL`: General updates and communications.
- **Auto-Status Transitions**: Automatically links received emails to jobs in your local DB and transitions application statuses accordingly.

### 5. 🗄️ Local SQLite Database with WAL Concurrency
- High-performance, zero-cloud local storage at `data/jobs.db`.
- **Write-Ahead Logging (WAL)** enabled for concurrent reading and writing.
- Relational schema linking `jobs`, `emails`, `application_events`, `contacts`, and `outreach_messages`.

### 6. 💻 Modern Dark-Mode Web Dashboard & Full CLI
- **FastAPI REST API Backend** (`http://127.0.0.1:8000`).
- **Dynamic Multi-Criteria Filters**: Date Range, Min Match Score, Remote Only, Preferred Location, Required Skills, Excluded Skills, and Full-Text Search.
- **Complete CLI**: Headless scraping, CSV exports, email sync, recruiter discovery, and cold outreach batch dispatching.

---

## 🏗️ Directory Structure

```
job-apply/
├── config/
│   ├── profile.example.yaml   # Template for candidate profile, skills, preferences
│   ├── profile.yaml           # Local candidate profile (git-ignored for privacy)
│   ├── email.example.yaml     # Template for IMAP/SMTP credentials
│   ├── email.yaml             # Local credentials (git-ignored for privacy)
│   ├── companies.yaml         # Monitored companies & ATS platforms
│   └── settings.yaml          # Match weights, thresholds, scrape timeouts
├── src/
│   ├── models.py              # Pydantic data schemas & enums
│   ├── storage/
│   │   ├── database.py        # SQLite connection & schema management (WAL mode)
│   │   └── repository.py      # High-performance filtered querying, stats & timeline
│   ├── matching/
│   │   ├── skills_extractor.py # Regex taxonomy skill extractor (100+ technologies)
│   │   └── matcher.py         # Weighted match calculation & omit penalties
│   ├── scrapers/
│   │   ├── base.py            # Base scraper abstract class
│   │   ├── greenhouse.py      # Greenhouse public board API scraper
│   │   ├── lever.py           # Lever public postings API scraper
│   │   ├── ashby.py           # Ashby public job board API scraper
│   │   ├── aggregator.py      # LinkedIn public guest scraper
│   │   └── manager.py         # Concurrent multi-company scraping manager
│   ├── outreach/
│   │   ├── discovery.py       # Email permutations, domain mapping & lead discovery
│   │   ├── templates.py       # Multi-stage dynamic email templates
│   │   ├── sender.py          # SMTP dispatcher with 50-email cap & human jitter
│   │   ├── reply_tracker.py   # IMAP inbound recruiter reply matcher
│   │   └── engine.py          # Unified cold outreach & follow-up coordinator
│   ├── email_tracker/
│   │   ├── syncer.py          # Local IMAP client with MIME/HTML parsing
│   │   ├── classifier.py      # Heuristic intent classification & company extraction
│   │   └── parser.py          # RFC 2047 & email body decoding
│   └── dashboard/
│       ├── app.py             # FastAPI backend REST API
│       ├── templates/
│       │   └── index.html     # Single-page dashboard template
│       └── static/
│           ├── style.css      # Modern dark-mode styling
│           └── app.js         # State, modals, timeline & reactive filters
├── tests/                     # Test suite (18 unit & integration tests)
│   ├── test_api.py            # FastAPI endpoint tests
│   ├── test_email_tracker.py  # Email classifier & entity extraction tests
│   ├── test_matcher.py        # Scoring & negative keyword tests
│   ├── test_outreach.py       # Email permutations, templates, sender & lifecycle tests
│   └── test_storage.py        # SQLite CRUD & timeline tests
├── data/
│   └── jobs.db                # SQLite database file (created automatically, git-ignored)
├── cli.py                     # Unified command-line interface
├── run_dashboard.py           # Quick dashboard launcher script
├── pytest.ini                 # Pytest configuration
└── requirements.txt           # Python dependencies
```

---

## ⚙️ Configuration Setup

### 1. Candidate Profile (`config/profile.yaml`)
Copy `config/profile.example.yaml` to `config/profile.yaml` and customize with your details:

```bash
cp config/profile.example.yaml config/profile.yaml
```

```yaml
candidate:
  name: "Your Name"
  email: "your-email@example.com"
  current_title: "Full Stack / Frontend Engineer"
  years_of_experience: 5
  linkedin: "https://linkedin.com/in/your-profile"
  github: "https://github.com/your-username"

target_roles:
  - "Software Engineer"
  - "Full Stack Engineer"
  - "Frontend Engineer"
  - "Senior Frontend Engineer"

skills:
  core:
    - "JavaScript"
    - "TypeScript"
    - "React"
    - "Node.js"
    - "Python"
    - "PostgreSQL"
  secondary:
    - "Redis"
    - "Kubernetes"
    - "GraphQL"
    - "CI/CD"
    - "Next.js"
    - "Tailwind"

omit_skills:
  - "PHP"
  - "WordPress"
  - "Ruby on Rails"
  - "Salesforce"
  - "COBOL"

locations:
  preferred:
    - "Remote"
    - "Bengaluru, India"
    - "Hyderabad, India"
    - "Pune, India"
  remote_only: false
```

### 2. Email Configuration for IMAP & SMTP (`config/email.yaml`)
Copy `config/email.example.yaml` to `config/email.yaml`:

```bash
cp config/email.example.yaml config/email.yaml
```

```yaml
enabled: true
username: "your.email@gmail.com"
password: "xxxx xxxx xxxx xxxx"    # 16-character Google App Password (2FA)
imap_server: "imap.gmail.com"
imap_port: 993
smtp_host: "smtp.gmail.com"
smtp_port: 587
use_ssl: true
use_tls: true
```

#### How to Generate a Gmail App Password:
1. Go to your **Google Account** → **Security**.
2. Ensure **2-Step Verification** is turned ON.
3. Visit [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
4. Create an App Password named `Job Apply Hub`.
5. Copy the 16-character password into `config/email.yaml`.

---

## 🏃‍♂️ How to Run the Tool

### Option A: Run Everything — One Command (Recommended)

```bash
python cli.py run
```

This single command executes in sequence:
1. 🗄️ **Database**: Initializes SQLite schema with WAL mode at `data/jobs.db`.
2. 🔍 **Scrape**: Fetches live postings from all 39+ target companies concurrently.
3. 📬 **Email Sync**: Syncs recruitment emails via IMAP (skips gracefully if not configured).
4. 🚀 **Dashboard**: Launches the web dashboard at `http://127.0.0.1:8000`.

### Option B: Recruiter Lead Discovery & Cold Outreach Workflow

You can run the entire recruiter discovery and follow-up engine headlessly from the CLI:

```bash
# 1. Seed curated recruiter leads & talent inboxes for target companies
python cli.py outreach-seed

# 2. Add a specific recruiter lead manually (auto-generates standard email permutations)
python cli.py outreach-add --name "Priya Sharma" --company "Razorpay" --title "Technical Recruiter"

# 3. View the outreach funnel and pipeline stats
python cli.py outreach-stats

# 4. Preview initial outreach without sending (Dry Run)
python cli.py outreach-send --dry-run --batch-size 10

# 5. Dispatch initial cold email batch (capped at 50 max, with 6-14s human jitter)
python cli.py outreach-send --batch-size 50

# 6. Check IMAP inbox for recruiter replies (halts follow-ups for respondents)
python cli.py outreach-sync-replies

# 7. Dispatch Follow-up Round 1 (for contacts emailed >= 12h ago with no reply)
python cli.py outreach-followup-1 --hours 12 --batch-size 50

# 8. Dispatch Follow-up Round 2 (closing the loop after another 24-48h)
python cli.py outreach-followup-2 --hours 24 --batch-size 50

# 9. List leads filtered by status (QUEUED, CONTACTED, FOLLOWUP_1, FOLLOWUP_2, REPLIED)
python cli.py outreach-list --status REPLIED
```

### Option C: Launch Only the Web Dashboard

```bash
python run_dashboard.py
# Or: python cli.py serve --port 8000
```

---

## 📋 Complete CLI Command Reference

| Command | Description | Example |
|---------|-------------|---------|
| `run` | **Unified Pipeline** — DB, scrape, email sync, dashboard | `python cli.py run` |
| `serve` | Launch web dashboard only | `python cli.py serve --port 8000` |
| `scrape` | Scrape all configured company ATS portals | `python cli.py scrape --workers 8` |
| `scrape-company` | Scrape a single company | `python cli.py scrape-company --name "Stripe" --ats greenhouse --slug "stripe"` |
| `search-linkedin` | Search public LinkedIn guest postings | `python cli.py search-linkedin --keywords "Frontend Engineer" --location "Remote"` |
| `sync-emails` | Sync recruitment emails via IMAP | `python cli.py sync-emails --days-back 30` |
| `rescore` | Re-evaluate all jobs against updated `profile.yaml` | `python cli.py rescore` |
| `list` | List matching jobs in the terminal | `python cli.py list --min-score 60 --remote-only --limit 20` |
| `stats` | View job application funnel metrics | `python cli.py stats` |
| `email-logs` | Show recent detected recruitment emails | `python cli.py email-logs --limit 25` |
| `timeline` | Show audit timeline for a specific job ID | `python cli.py timeline --job-id <JOB_ID>` |
| `export-csv` | Export filtered jobs to CSV | `python cli.py export-csv --output my_top_jobs.csv --min-score 70` |
| **`outreach-seed`** | Seed starter recruiter leads for target companies | `python cli.py outreach-seed` |
| **`outreach-add`** | Add/update a recruiter contact | `python cli.py outreach-add --name "Alex" --company "Figma"` |
| **`outreach-import`** | Import recruiter contacts from CSV/JSON | `python cli.py outreach-import --file leads.csv` |
| **`outreach-send`** | Send initial cold email batch (max 50) | `python cli.py outreach-send --batch-size 50` |
| **`outreach-followup-1`** | Send Round 1 threaded follow-up | `python cli.py outreach-followup-1 --hours 12` |
| **`outreach-followup-2`** | Send Round 2 threaded follow-up | `python cli.py outreach-followup-2 --hours 24` |
| **`outreach-sync-replies`** | Check IMAP inbox for recruiter responses | `python cli.py outreach-sync-replies` |
| **`outreach-stats`** | View outreach funnel & response rate | `python cli.py outreach-stats` |
| **`outreach-list`** | List recruiter leads and outreach stages | `python cli.py outreach-list --status QUEUED` |

---

## ⚖️ Match Scoring Formula

The matching engine computes a percentage score $(0 - 100\%)$ for each job post based on:

$$\text{Raw Score} = (S_{\text{title}} \times W_{\text{title}}) + (S_{\text{core}} \times W_{\text{core}}) + (S_{\text{secondary}} \times W_{\text{secondary}}) + (S_{\text{location}} \times W_{\text{location}})$$

$$\text{Final Score} = \max(0, \min(100, \text{Raw Score} - (\text{Count}(\text{Omitted Skills}) \times \text{Penalty})))$$

- **Title Match ($35\%$)**: Exact and token-overlap fuzzy matching against target roles.
- **Core Skills ($40\%$):** Percentage of core profile skills found in the job text.
- **Secondary Skills ($15\%$):** Percentage of secondary profile skills found.
- **Location Alignment ($10\%$):** Remote flag or preferred geographic region match.
- **Omitted Skill Penalty ($-30\%$ per found omit keyword):** Heavy score deduction for posts requiring excluded legacy or out-of-scope technologies.

---

## 🧪 Running Automated Tests

Run the full Pytest test suite:

```bash
pytest
```

Output:
```
============================= test session starts ==============================
rootdir: /Users/adityaanand/Documents/gitrepos/job-apply
configfile: pytest.ini
testpaths: tests
collected 18 items

tests/test_api.py ......                                                 [ 33%]
tests/test_email_tracker.py ...                                          [ 50%]
tests/test_matcher.py ..                                                 [ 61%]
tests/test_outreach.py ......                                            [ 94%]
tests/test_storage.py .                                                  [100%]

======================== 18 passed in 0.27s ========================
```

---

## 🔒 Privacy, Security & Git Hygiene

- **Zero Accidental Credential Leaks**: `.gitignore` strictly blocks personal credentials (`config/email.yaml`), candidate personal details (`config/profile.yaml`), and local database files (`data/*.db`, `data/*.sqlite`).
- **Example Templates Provided**: Clean starter configurations (`config/profile.example.yaml`, `config/email.example.yaml`) allow easy onboarding for any candidate without exposing personal information.
- **Local Data Sovereignty**: All job listings, notes, application statuses, IMAP/SMTP credentials, and outreach history remain strictly on your local machine.
- **Zero Ban Risk**: No automated application form botting, no fake browser sessions, and no private LinkedIn account scraping.
