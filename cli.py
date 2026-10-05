#!/usr/bin/env python3
"""
Command-line interface (CLI) for Job Apply Intelligence Hub.
"""

import sys
import csv
import argparse
from typing import List

from src.storage.repository import JobRepository
from src.matching.matcher import JobMatcher
from src.scrapers.manager import ScraperManager
from src.email_tracker.syncer import EmailSyncManager, load_email_config
from src.models import FilterCriteria, JobStatus, ContactStatus
from src.outreach.engine import OutreachEngine


def cmd_scrape(args):
    """Run full scrape across all configured companies."""
    print("🚀 Starting sync across all configured target companies...")
    manager = ScraperManager()
    results = manager.scrape_all_companies(max_workers=args.workers)

    total_found = sum(r.jobs_found for r in results)
    total_new = sum(r.jobs_new for r in results)

    table_data = [
        [r.company, r.ats_type.upper(), r.jobs_found, r.jobs_new, "OK" if not r.errors else f"ERR: {r.errors[0]}"]
        for r in sorted(results, key=lambda x: x.company)
    ]

    print("\n" + "=" * 60)
    print(f"📊 SCRAPING RESULTS: {total_found} Total Jobs Found | {total_new} Brand New Jobs Added")
    print("=" * 60)
    print(f"{'Company':<20} {'ATS':<12} {'Found':<8} {'New':<8} {'Status'}")
    print("-" * 60)
    for row in table_data:
        print(f"{row[0]:<20} {row[1]:<12} {row[2]:<8} {row[3]:<8} {row[4]}")
    print("=" * 60)


def cmd_scrape_company(args):
    """Scrape a single company."""
    manager = ScraperManager()
    res = manager.scrape_single_company({
        "name": args.name,
        "ats": args.ats,
        "slug": args.slug
    })
    print(f"[{res.company}] ATS: {res.ats_type} | Found: {res.jobs_found} | New: {res.jobs_new}")


def cmd_search_linkedin(args):
    """Run LinkedIn public search."""
    print(f"🔍 Searching LinkedIn guest board for '{args.keywords}' in '{args.location}'...")
    manager = ScraperManager()
    res = manager.run_aggregator_search(
        keywords=args.keywords,
        location=args.location,
        limit=args.limit
    )
    print(f"Found: {res.jobs_found} | Added New: {res.jobs_new}")


def cmd_list(args):
    """List filtered jobs in terminal."""
    repo = JobRepository()
    skills_list = [s.strip() for s in args.skills.split(",")] if args.skills else None
    omit_list = [s.strip() for s in args.omit_skills.split(",")] if args.omit_skills else None

    criteria = FilterCriteria(
        search=args.search,
        min_score=args.min_score,
        days_back=args.days_back,
        skills=skills_list,
        omit_skills=omit_list,
        remote_only=args.remote_only,
        limit=args.limit,
        sort_by="match_score"
    )

    records, total = repo.query_jobs(criteria)
    print(f"\n🎯 Showing {len(records)} of {total} matching jobs:\n")
    print(f"{'Score':<8} {'Company':<18} {'Title':<34} {'Location':<20} {'Status':<10}")
    print("-" * 92)

    for r in records:
        j = r.job
        m = r.match
        title_disp = (j.title[:31] + '...') if len(j.title) > 34 else j.title
        comp_disp = (j.company[:16] + '..') if len(j.company) > 18 else j.company
        loc_disp = (j.location[:18] + '..') if len(j.location) > 20 else j.location
        score_disp = f"{m.match_score}%"

        print(f"{score_disp:<8} {comp_disp:<18} {title_disp:<34} {loc_disp:<20} {r.status.value:<10}")
        if m.matched_skills:
            print(f"         └─ Matched: {', '.join(m.matched_skills[:5])}")
        print(f"         └─ Link: {j.url}")
        print()


def cmd_stats(args):
    """Print high level stats."""
    repo = JobRepository()
    stats = repo.get_stats()

    print("\n" + "=" * 45)
    print("📈 JOB APPLICATION FUNNEL & METRICS")
    print("=" * 45)
    print(f"Total Discovered Jobs:  {stats['total_jobs']}")
    print(f"Average Match Score:    {stats['avg_match_score']}%")
    print(f"Remote Postings:        {stats['total_remote']}")
    print(f"Tracked Emails:         {stats.get('total_emails', 0)}")
    print("-" * 45)
    print("Status Breakdown:")
    for status, count in stats["status_counts"].items():
        print(f"  • {status:<12}: {count}")
    print("-" * 45)
    print("Top Companies:")
    for c in stats["top_companies"]:
        print(f"  • {c['company']:<16}: {c['count']} openings")
    print("=" * 45 + "\n")


def cmd_sync_emails(args):
    """Run local IMAP email synchronization."""
    print("📧 Connecting to IMAP server and synchronizing recruitment emails...")
    cfg = load_email_config()
    if not cfg.enabled:
        print("⚠️ Email tracking is disabled in config/email.yaml.")
        print("Please edit config/email.yaml or configure it via the web dashboard.")
        return

    manager = EmailSyncManager()
    res = manager.run_sync(days_back=args.days_back)

    print("\n" + "=" * 55)
    print("📬 EMAIL TRACKING SYNCHRONIZATION SUMMARY")
    print("=" * 55)
    print(f"Emails Processed:        {res.emails_processed}")
    print(f"Emails Linked to Jobs:   {res.emails_matched}")
    print(f"New Applications Added:  {res.new_jobs_created}")
    print(f"Status Transitions Made: {res.status_updates}")
    if res.errors:
        print("\n⚠️ Warnings / Errors:")
        for err in res.errors:
            print(f"  - {err}")
    print("=" * 55 + "\n")


def cmd_timeline(args):
    """Show application audit timeline for a job ID."""
    repo = JobRepository()
    job = repo.get_job_by_id(args.job_id)
    if not job:
        print(f"❌ Job with ID '{args.job_id}' not found.")
        return

    timeline = repo.get_job_timeline(args.job_id)
    print(f"\n📋 Application Timeline for {job.job.company} - {job.job.title} [{job.status.value}]")
    print("=" * 75)
    if not timeline:
        print("No timeline events recorded yet.")
    for item in timeline:
        t_type = item["type"]
        ts = item["timestamp"]
        if t_type == "event":
            print(f"[{ts}] ⚡ EVENT: {item['description']}")
        elif t_type == "email":
            print(f"[{ts}] ✉️ EMAIL [{item['category']}]: '{item['subject']}' from {item['sender']}")
    print("=" * 75 + "\n")


def cmd_email_logs(args):
    """Display recent recruitment email logs."""
    repo = JobRepository()
    emails = repo.get_recent_emails(limit=args.limit)
    print(f"\n📬 Recent Detected Recruitment Emails ({len(emails)}):")
    print(f"{'Date':<20} {'Category':<14} {'Company':<16} {'Subject'}")
    print("-" * 80)
    for e in emails:
        d_str = e.date_received.strftime("%Y-%m-%d %H:%M") if e.date_received else ""
        subj = (e.subject[:36] + '..') if len(e.subject) > 38 else e.subject
        print(f"{d_str:<20} {e.category.value:<14} {e.company:<16} {subj}")
    print("-" * 80 + "\n")


def cmd_rescore(args):
    """Re-score all existing jobs against the current profile without re-scraping."""
    repo = JobRepository()
    matcher = JobMatcher()
    matcher.reload_config()

    print("🔄 Re-scoring all jobs against the current profile.yaml...")
    total, changed = repo.rescore_all_jobs(matcher)
    print(f"\n✓ Done! {total} jobs re-scored, {changed} had score changes.")
    if not changed:
        print("  (No scores changed — your profile may already match the stored scores.)")


def cmd_export_csv(args):
    """Export jobs to CSV."""
    repo = JobRepository()
    criteria = FilterCriteria(min_score=args.min_score, limit=5000)
    records, total = repo.query_jobs(criteria)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ID", "Company", "Title", "Location", "Is Remote", "Match Score",
            "Matched Skills", "Missing Skills", "Status", "URL", "Date Posted"
        ])
        for r in records:
            j = r.job
            m = r.match
            writer.writerow([
                j.id, j.company, j.title, j.location, j.is_remote, m.match_score,
                ", ".join(m.matched_skills), ", ".join(m.missing_skills),
                r.status.value, j.url, j.date_posted.isoformat() if j.date_posted else ""
            ])

    print(f"✓ Exported {len(records)} jobs to {args.output}")


def cmd_serve(args):
    """Start web dashboard server."""
    try:
        import uvicorn
    except ImportError:
        print("❌ Error: uvicorn is required to launch the web dashboard.")
        print("Please install requirements: pip install -r requirements.txt")
        sys.exit(1)
    print(f"\n⚡ Starting Job Intelligence Dashboard at http://{args.host}:{args.port}")
    uvicorn.run("src.dashboard.app:app", host=args.host, port=args.port, reload=args.reload)


def cmd_run(args):
    """Initialize DB, scrape jobs, sync emails, and launch the dashboard."""
    try:
        import uvicorn
    except ImportError:
        print("❌ Error: uvicorn is required. Run: pip install -r requirements.txt")
        sys.exit(1)

    from src.storage.database import get_db

    # Step 1: Initialize / verify DB
    print("🗄️  Initializing database...")
    get_db()
    print("   ✓ Database ready at data/jobs.db\n")

    # Step 2: Scrape all configured companies
    if not args.skip_scrape:
        print("🔍 Scraping all configured company portals...")
        manager = ScraperManager()
        results = manager.scrape_all_companies(max_workers=args.workers)
        total_found = sum(r.jobs_found for r in results)
        total_new = sum(r.jobs_new for r in results)
        errors = sum(1 for r in results if r.errors)
        print(f"   ✓ {total_found} jobs found, {total_new} new")
        if errors:
            print(f"   ⚠ {errors} source(s) had errors\n")
        else:
            print()

    # Step 3: Sync recruitment emails (if configured)
    if not args.skip_email:
        try:
            cfg = load_email_config()
            if cfg.enabled:
                print("📬 Syncing recruitment emails via IMAP...")
                email_mgr = EmailSyncManager()
                res = email_mgr.run_sync(days_back=args.email_days_back)
                print(f"   ✓ {res.emails_processed} emails processed, "
                      f"{res.emails_matched} matched to jobs\n")
            else:
                print("📬 Email tracking not configured — skipping (set up in dashboard or config/email.yaml)\n")
        except Exception as e:
            print(f"📬 Email sync skipped: {e}\n")

    # Step 4: Launch the web dashboard
    print(f"🚀 Launching dashboard at http://{args.host}:{args.port}")
    print("   Press Ctrl+C to stop\n")
    uvicorn.run("src.dashboard.app:app", host=args.host, port=args.port, reload=args.reload)


# ==========================================
# Recruiter Lead Discovery & Cold Outreach Commands
# ==========================================

def cmd_outreach_seed(args):
    """Seed database with starter recruiter leads and talent inboxes."""
    print("🌱 Seeding curated recruiter leads for Indian tech unicorns and Remote companies...")
    engine = OutreachEngine()
    new_count = engine.seed_starter_contacts()
    print(f"✓ Added {new_count} new recruiter contacts to database.")


def cmd_outreach_import(args):
    """Import contacts from CSV or JSON file."""
    print(f"📥 Importing recruiter contacts from: {args.file}...")
    engine = OutreachEngine()
    try:
        new_count = engine.import_contacts(args.file)
        print(f"✓ Successfully imported contacts ({new_count} new entries created).")
    except Exception as e:
        print(f"❌ Failed to import contacts: {e}")


def cmd_outreach_add(args):
    """Manually add or update a recruiter lead."""
    engine = OutreachEngine()
    is_new, contact_id = engine.add_single_contact(
        name=args.name,
        company=args.company,
        title=args.title,
        email=args.email,
        domain=args.domain,
        linkedin=args.linkedin or "",
    )
    action = "Created new" if is_new else "Updated"
    print(f"✓ {action} contact ID #{contact_id} for {args.name} ({args.company}).")


def cmd_outreach_send(args):
    """Dispatch initial cold outreach batch (capped at 50 max)."""
    print(f"🚀 Preparing initial cold outreach batch (limit: {args.batch_size}, dry_run: {args.dry_run})...")
    engine = OutreachEngine(dry_run=args.dry_run)
    res = engine.send_initial_outreach(batch_size=args.batch_size, company_filter=args.company)

    print("\n" + "=" * 55)
    print("📤 INITIAL COLD OUTREACH DISPATCH SUMMARY")
    print("=" * 55)
    print(f"Attempted:   {res.attempted}")
    print(f"Successful:  {res.successful}")
    print(f"Failed:      {res.failed}")
    if res.sent_to:
        print(f"Recipients:  {', '.join(res.sent_to[:8])}{'...' if len(res.sent_to) > 8 else ''}")
    if res.errors:
        print("\n⚠️ Errors:")
        for err in res.errors:
            print(f"  - {err}")
    print("=" * 55 + "\n")


def cmd_outreach_followup_1(args):
    """Dispatch Round 1 follow-up for contacts contacted >= hours ago."""
    print(f"🔄 Preparing Round 1 follow-ups (min_hours: {args.hours}h, limit: {args.batch_size}, dry_run: {args.dry_run})...")
    engine = OutreachEngine(dry_run=args.dry_run)
    res = engine.send_followup_round_1(min_hours=args.hours, batch_size=args.batch_size)

    print("\n" + "=" * 55)
    print("📤 FOLLOW-UP ROUND 1 DISPATCH SUMMARY")
    print("=" * 55)
    print(f"Attempted:   {res.attempted}")
    print(f"Successful:  {res.successful}")
    print(f"Failed:      {res.failed}")
    if res.sent_to:
        print(f"Recipients:  {', '.join(res.sent_to[:8])}{'...' if len(res.sent_to) > 8 else ''}")
    if res.errors:
        print("\n⚠️ Errors:")
        for err in res.errors:
            print(f"  - {err}")
    print("=" * 55 + "\n")


def cmd_outreach_followup_2(args):
    """Dispatch Round 2 follow-up for contacts with followup 1 sent >= hours ago."""
    print(f"🔄 Preparing Round 2 follow-ups (min_hours: {args.hours}h, limit: {args.batch_size}, dry_run: {args.dry_run})...")
    engine = OutreachEngine(dry_run=args.dry_run)
    res = engine.send_followup_round_2(min_hours=args.hours, batch_size=args.batch_size)

    print("\n" + "=" * 55)
    print("📤 FOLLOW-UP ROUND 2 DISPATCH SUMMARY")
    print("=" * 55)
    print(f"Attempted:   {res.attempted}")
    print(f"Successful:  {res.successful}")
    print(f"Failed:      {res.failed}")
    if res.sent_to:
        print(f"Recipients:  {', '.join(res.sent_to[:8])}{'...' if len(res.sent_to) > 8 else ''}")
    if res.errors:
        print("\n⚠️ Errors:")
        for err in res.errors:
            print(f"  - {err}")
    print("=" * 55 + "\n")


def cmd_outreach_sync_replies(args):
    """Check IMAP inbox for responses from recruiters and update state to REPLIED."""
    print("📥 Checking inbox for recruiter replies...")
    engine = OutreachEngine()
    replies = engine.sync_replies(days_back=args.days_back)
    print(f"✓ Found and processed {replies} recruiter reply/replies.")


def cmd_outreach_stats(args):
    """Show recruiter outreach funnel statistics."""
    engine = OutreachEngine()
    stats = engine.get_outreach_stats()

    print("\n" + "=" * 50)
    print("📊 RECRUITER COLD OUTREACH FUNNEL & METRICS")
    print("=" * 50)
    print(f"Total Leads Tracked:     {stats.total_contacts}")
    print(f"Queued for Outreach:     {stats.queued}")
    print(f"Initial Contact Sent:    {stats.contacted}")
    print(f"Follow-up Round 1 Sent:  {stats.followup_1_sent}")
    print(f"Follow-up Round 2 Sent:  {stats.followup_2_sent}")
    print(f"Recruiter Replies:       {stats.replied}")
    print(f"Overall Response Rate:   {stats.response_rate}%")
    print("=" * 50 + "\n")


def cmd_outreach_list(args):
    """List recruiter leads in terminal."""
    repo = JobRepository()
    status_filter = ContactStatus(args.status) if args.status else None
    contacts, total = repo.list_contacts(status=status_filter, company=args.company, limit=args.limit)

    print(f"\n👥 Showing {len(contacts)} of {total} Recruiter Leads:\n")
    print(f"{'Name':<24} {'Company':<18} {'Email':<32} {'Status':<12}")
    print("-" * 90)
    for c in contacts:
        print(f"{c.name[:22]:<24} {c.company[:16]:<18} {c.email[:30]:<32} {c.status.value:<12}")
    print("-" * 90 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Job Apply Intelligence Hub CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Scrape
    p_scrape = subparsers.add_parser("scrape", help="Scrape all target company portals")
    p_scrape.add_argument("--workers", type=int, default=8, help="Concurrent worker count")

    # Scrape Single
    p_single = subparsers.add_parser("scrape-company", help="Scrape a single company")
    p_single.add_argument("--name", required=True, help="Company name")
    p_single.add_argument("--ats", required=True, choices=["greenhouse", "lever", "ashby"], help="ATS type")
    p_single.add_argument("--slug", required=True, help="Company slug on ATS")

    # LinkedIn Search
    p_li = subparsers.add_parser("search-linkedin", help="Public LinkedIn guest search")
    p_li.add_argument("--keywords", default="Software Engineer", help="Search keywords")
    p_li.add_argument("--location", default="Remote", help="Location")
    p_li.add_argument("--limit", type=int, default=25, help="Max jobs to fetch")

    # List
    p_list = subparsers.add_parser("list", help="List matching jobs")
    p_list.add_argument("--min-score", type=int, default=50, help="Minimum match score (0-100)")
    p_list.add_argument("--days-back", type=int, default=14, help="Max days back")
    p_list.add_argument("--skills", help="Required skills (comma-separated)")
    p_list.add_argument("--omit-skills", help="Skills to omit (comma-separated)")
    p_list.add_argument("--remote-only", action="store_true", help="Remote only")
    p_list.add_argument("--search", help="Search term")
    p_list.add_argument("--limit", type=int, default=25, help="Number of records to display")

    # Stats
    subparsers.add_parser("stats", help="Show application tracking stats")

    # Email Sync
    p_esync = subparsers.add_parser("sync-emails", help="Sync recruitment emails via IMAP")
    p_esync.add_argument("--days-back", type=int, default=None, help="Lookback window in days")

    # Email Logs
    p_elogs = subparsers.add_parser("email-logs", help="List recent recruitment email logs")
    p_elogs.add_argument("--limit", type=int, default=25, help="Number of records to display")

    # Timeline
    p_tl = subparsers.add_parser("timeline", help="Show application timeline and email logs for a job")
    p_tl.add_argument("--job-id", required=True, help="Job ID")

    # Export
    p_export = subparsers.add_parser("export-csv", help="Export matching jobs to CSV")
    p_export.add_argument("--output", default="jobs.csv", help="Output CSV path")
    p_export.add_argument("--min-score", type=int, default=50, help="Min match score")

    # Rescore
    subparsers.add_parser("rescore", help="Re-score all jobs against updated profile.yaml")

    # Outreach Subcommands
    p_oseed = subparsers.add_parser("outreach-seed", help="Seed database with curated recruiter leads and talent inboxes")

    p_oimport = subparsers.add_parser("outreach-import", help="Import recruiter leads from CSV or JSON")
    p_oimport.add_argument("--file", required=True, help="Path to CSV or JSON file")

    p_oadd = subparsers.add_parser("outreach-add", help="Manually add or update a recruiter lead")
    p_oadd.add_argument("--name", required=True, help="Recruiter full name")
    p_oadd.add_argument("--company", required=True, help="Company name")
    p_oadd.add_argument("--title", default="Technical Recruiter", help="Job title")
    p_oadd.add_argument("--email", help="Direct email override (or auto-generates permutation)")
    p_oadd.add_argument("--domain", help="Company domain override (e.g. razorpay.com)")
    p_oadd.add_argument("--linkedin", help="LinkedIn profile URL")

    p_osend = subparsers.add_parser("outreach-send", help="Send initial cold outreach batch (max 50 limit)")
    p_osend.add_argument("--batch-size", type=int, default=50, help="Batch size (max 50)")
    p_osend.add_argument("--company", help="Optional filter by company name")
    p_osend.add_argument("--dry-run", action="store_true", help="Simulate send without emailing")

    p_of1 = subparsers.add_parser("outreach-followup-1", help="Send Round 1 follow-up (12h+ elapsed)")
    p_of1.add_argument("--hours", type=float, default=12.0, help="Minimum elapsed hours since initial email (default: 12.0)")
    p_of1.add_argument("--batch-size", type=int, default=50, help="Batch size (max 50)")
    p_of1.add_argument("--dry-run", action="store_true", help="Simulate send without emailing")

    p_of2 = subparsers.add_parser("outreach-followup-2", help="Send Round 2 follow-up (24h+ elapsed)")
    p_of2.add_argument("--hours", type=float, default=24.0, help="Minimum elapsed hours since followup 1 (default: 24.0)")
    p_of2.add_argument("--batch-size", type=int, default=50, help="Batch size (max 50)")
    p_of2.add_argument("--dry-run", action="store_true", help="Simulate send without emailing")

    p_oreplies = subparsers.add_parser("outreach-sync-replies", help="Scan IMAP inbox for recruiter replies")
    p_oreplies.add_argument("--days-back", type=int, default=14, help="Days to look back for replies")

    subparsers.add_parser("outreach-stats", help="Show recruiter cold outreach funnel and response metrics")

    p_olist = subparsers.add_parser("outreach-list", help="List recruiter leads in terminal")
    p_olist.add_argument("--status", choices=["QUEUED", "CONTACTED", "FOLLOWUP_1", "FOLLOWUP_2", "REPLIED", "BOUNCED", "OPTED_OUT", "ARCHIVED"], help="Filter by status")
    p_olist.add_argument("--company", help="Filter by company")
    p_olist.add_argument("--limit", type=int, default=30, help="Number of leads to display")

    # Serve
    p_serve = subparsers.add_parser("serve", help="Launch the web dashboard")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind host")
    p_serve.add_argument("--port", type=int, default=8000, help="Bind port")
    p_serve.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # Run (full pipeline: DB + scrape + email sync + dashboard)
    p_run = subparsers.add_parser("run", help="Initialize DB, scrape jobs, sync emails, and launch the dashboard")
    p_run.add_argument("--host", default="127.0.0.1", help="Bind host")
    p_run.add_argument("--port", type=int, default=8000, help="Bind port")
    p_run.add_argument("--reload", action="store_true", help="Enable auto-reload")
    p_run.add_argument("--workers", type=int, default=8, help="Concurrent scrape workers")
    p_run.add_argument("--skip-scrape", action="store_true", help="Skip initial job scraping")
    p_run.add_argument("--skip-email", action="store_true", help="Skip email synchronization")
    p_run.add_argument("--email-days-back", type=int, default=30, help="Email sync lookback window in days")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "scrape": cmd_scrape,
        "scrape-company": cmd_scrape_company,
        "search-linkedin": cmd_search_linkedin,
        "list": cmd_list,
        "stats": cmd_stats,
        "sync-emails": cmd_sync_emails,
        "email-logs": cmd_email_logs,
        "timeline": cmd_timeline,
        "export-csv": cmd_export_csv,
        "rescore": cmd_rescore,
        "serve": cmd_serve,
        "run": cmd_run,
        "outreach-seed": cmd_outreach_seed,
        "outreach-import": cmd_outreach_import,
        "outreach-add": cmd_outreach_add,
        "outreach-send": cmd_outreach_send,
        "outreach-followup-1": cmd_outreach_followup_1,
        "outreach-followup-2": cmd_outreach_followup_2,
        "outreach-sync-replies": cmd_outreach_sync_replies,
        "outreach-stats": cmd_outreach_stats,
        "outreach-list": cmd_outreach_list,
    }

    func = dispatch.get(args.command)
    if func:
        func(args)


if __name__ == "__main__":
    main()
