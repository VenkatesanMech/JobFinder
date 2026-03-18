# ============================================================
# EMAILER.PY — Sends Beautiful HTML Email with Job Results
# ============================================================

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def build_job_card(job: dict) -> str:
    """Build HTML for one job card in the email."""
    score = job["score"]
    color = "#00c48c" if score >= 80 else "#f0a30a" if score >= 60 else "#3d7fff"
    border_color = color

    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px">
    <tr><td style="
        background:#0c0f18;
        border:1px solid #1e2438;
        border-left:4px solid {border_color};
        border-radius:10px;
        padding:16px 18px;
    ">
        <!-- Title row -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px">
        <tr>
            <td style="font-size:15px;font-weight:700;color:#e2e8f0">
                {job['emoji']} {job['title']}
            </td>
            <td align="right" style="white-space:nowrap">
                <span style="
                    background:{color}22;
                    color:{color};
                    padding:3px 10px;
                    border-radius:99px;
                    font-size:12px;
                    font-weight:700;
                ">⚡ {score}% match</span>
            </td>
        </tr>
        </table>

        <!-- Company & Domain -->
        <div style="font-size:13px;color:#f0a30a;margin-bottom:6px;font-weight:500">
            {job['company']} &nbsp;·&nbsp;
            <span style="color:#7a859e">{job['domain']}</span>
        </div>

        <!-- Meta info -->
        <div style="font-size:12px;color:#3a4260;margin-bottom:10px">
            📍 {job['location']} &nbsp;·&nbsp;
            🕐 {job['scraped_at']} &nbsp;·&nbsp;
            🔗 Direct Career Page
        </div>

        <!-- Snippet -->
        <div style="font-size:12px;color:#5a6278;line-height:1.6;margin-bottom:12px;
                    background:#070910;border-radius:6px;padding:8px 10px;border-left:2px solid #1e2438">
            {job['raw_snippet'][:180]}...
        </div>

        <!-- Apply button -->
        <a href="{job['apply_url']}"
           style="
               display:inline-block;
               background:#f0a30a;
               color:#000;
               padding:7px 18px;
               border-radius:7px;
               font-size:12px;
               font-weight:700;
               text-decoration:none;
           ">Apply Now →</a>
    </td></tr>
    </table>"""


def build_section(title: str, color: str, jobs: list) -> str:
    """Build a section of the email (e.g. '🔥 Excellent Match')."""
    if not jobs:
        return ""
    return f"""
    <tr><td style="padding:18px 20px 10px">
        <div style="
            color:{color};
            font-size:12px;
            font-weight:700;
            text-transform:uppercase;
            letter-spacing:0.08em;
            border-bottom:1px solid {color}44;
            padding-bottom:8px;
        ">{title} — {len(jobs)} job{'s' if len(jobs) > 1 else ''}</div>
    </td></tr>
    <tr><td style="padding:0 20px">
        {''.join(build_job_card(j) for j in jobs)}
    </td></tr>"""


def build_email_html(jobs: list, run_date: str) -> str:
    """Build the complete HTML email."""

    high   = [j for j in jobs if j["score"] >= 80]
    medium = [j for j in jobs if 60 <= j["score"] < 80]
    low    = [j for j in jobs if 40 <= j["score"] < 60]

    # Company breakdown
    companies_found = {}
    for j in jobs:
        cid = j["company_id"]
        companies_found[cid] = companies_found.get(cid, 0) + 1

    company_pills = "".join(
        f'<span style="background:#1e2438;color:#7a859e;padding:3px 9px;border-radius:4px;font-size:11px;margin:2px">'
        f'{j["emoji"]} {j["company"]} ({n})</span>'
        for cid, n in list(companies_found.items())[:10]
        for j in [next(x for x in jobs if x["company_id"] == cid)]
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#07090e;font-family:Arial,sans-serif">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#07090e;padding:24px 16px">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%">

    <!-- ── HEADER ── -->
    <tr><td style="
        background:#0c0f18;
        border:1px solid #1e2438;
        border-bottom:3px solid #f0a30a;
        border-radius:14px 14px 0 0;
        padding:24px 22px;
    ">
        <div style="font-size:11px;color:#3a4260;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:7px">
            🤖 Headless Scraper · Direct Career Pages · {run_date}
        </div>
        <div style="font-size:24px;font-weight:800;color:#e2e8f0;margin-bottom:5px">
            🎯 {len(jobs)} Jobs Found Today
        </div>
        <div style="font-size:13px;color:#7a859e">
            Venkatesan P &nbsp;·&nbsp; CAPEX / Project Management &nbsp;·&nbsp; India + Gulf
        </div>
    </td></tr>

    <!-- ── STATS ── -->
    <tr><td style="background:#111520;border-left:1px solid #1e2438;border-right:1px solid #1e2438;padding:16px 22px">
        <table width="100%" cellpadding="4" cellspacing="0">
        <tr>
            <td align="center" style="background:#0c0f18;border-radius:9px;border:1px solid #1e2438;padding:12px 8px">
                <div style="font-size:24px;font-weight:800;color:#f0a30a">{len(jobs)}</div>
                <div style="font-size:10px;color:#3a4260;text-transform:uppercase;margin-top:3px">Total Jobs</div>
            </td>
            <td width="8"></td>
            <td align="center" style="background:#0c0f18;border-radius:9px;border:1px solid rgba(0,196,140,0.2);padding:12px 8px">
                <div style="font-size:24px;font-weight:800;color:#00c48c">{len(high)}</div>
                <div style="font-size:10px;color:#3a4260;text-transform:uppercase;margin-top:3px">80%+ Match</div>
            </td>
            <td width="8"></td>
            <td align="center" style="background:#0c0f18;border-radius:9px;border:1px solid rgba(240,163,10,0.2);padding:12px 8px">
                <div style="font-size:24px;font-weight:800;color:#f0a30a">{len(medium)}</div>
                <div style="font-size:10px;color:#3a4260;text-transform:uppercase;margin-top:3px">60-79% Match</div>
            </td>
            <td width="8"></td>
            <td align="center" style="background:#0c0f18;border-radius:9px;border:1px solid #1e2438;padding:12px 8px">
                <div style="font-size:24px;font-weight:800;color:#3d7fff">{len(companies_found)}</div>
                <div style="font-size:10px;color:#3a4260;text-transform:uppercase;margin-top:3px">Companies</div>
            </td>
        </tr>
        </table>

        <!-- Companies found -->
        <div style="margin-top:12px;line-height:1.8">{company_pills}</div>
    </td></tr>

    <!-- ── JOB LISTINGS ── -->
    <tr><td style="background:#0c0f18;border:1px solid #1e2438;border-top:none;border-radius:0 0 14px 14px">
        <table width="100%" cellpadding="0" cellspacing="0">
            {build_section('🔥 Excellent Match — 80%+',  '#00c48c', high)}
            {build_section('✅ Good Match — 60–79%',      '#f0a30a', medium)}
            {build_section('📋 Decent Match — 40–59%',   '#3d7fff', low)}
        </table>
    </td></tr>

    <!-- ── FOOTER ── -->
    <tr><td style="padding:14px 0;text-align:center">
        <div style="font-size:11px;color:#3a4260">
            🤖 Headless Browser Scraper &nbsp;·&nbsp; GitHub Actions &nbsp;·&nbsp; Runs 8 AM & 1 PM IST (Mon–Fri)
        </div>
        <div style="font-size:11px;color:#1e2438;margin-top:4px">
            Data scraped directly from company career pages — no middleman
        </div>
    </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def send_email(jobs: list):
    """Send the job digest email via Gmail."""

    from_email = os.environ.get("FROM_EMAIL")
    to_email   = os.environ.get("TO_EMAIL")
    app_pass   = os.environ.get("GMAIL_APP_PASSWORD")

    if not all([from_email, to_email, app_pass]):
        print("❌ Missing email environment variables!")
        print("   Need: FROM_EMAIL, TO_EMAIL, GMAIL_APP_PASSWORD")
        return False

    run_date = datetime.now().strftime("%A, %d %B %Y")
    subject  = f"🎯 {len(jobs)} Jobs Found — {run_date} | Career Scraper Bot"

    # Build email
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Career Bot 🤖 <{from_email}>"
    msg["To"]      = to_email

    html_content = build_email_html(jobs, run_date)
    msg.attach(MIMEText(html_content, "html"))

    # Send via Gmail
    try:
        print(f"\n📧 Sending email to {to_email}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, app_pass)
            server.sendmail(from_email, to_email, msg.as_string())
        print(f"✅ Email sent successfully!")
        print(f"   Subject: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail authentication failed!")
        print("   Make sure GMAIL_APP_PASSWORD is correct (no spaces)")
        print("   Get app password: myaccount.google.com → Security → App passwords")
        return False
    except Exception as e:
        print(f"❌ Email failed: {str(e)}")
        return False


if __name__ == "__main__":
    # Load jobs from JSON file
    try:
        with open("jobs_found.json", "r") as f:
            jobs = json.load(f)
        print(f"📂 Loaded {len(jobs)} jobs from jobs_found.json")
        send_email(jobs)
    except FileNotFoundError:
        print("❌ jobs_found.json not found. Run scraper.py first.")
