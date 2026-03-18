# ============================================================
# MAIN.PY — Entry point
# Runs scraper first, then sends email
# ============================================================

import asyncio
import json
import sys
from datetime import datetime
from scraper import run_scraper
from emailer import send_email


async def main():
    print("\n" + "=" * 60)
    print("🚀 CAREER SCRAPER BOT STARTING")
    print(f"⏰ {datetime.now().strftime('%A, %d %B %Y — %I:%M %p')}")
    print("=" * 60)

    # ── Step 1: Scrape all company career pages ──
    print("\n📡 STEP 1: Scraping career pages...")
    jobs = await run_scraper()

    if not jobs:
        print("\n⚠️  No jobs found today. Skipping email.")
        sys.exit(0)

    # ── Step 2: Save jobs to file ──
    with open("jobs_found.json", "w") as f:
        json.dump(jobs, f, indent=2)
    print(f"\n💾 Saved {len(jobs)} jobs to jobs_found.json")

    # ── Step 3: Send email digest ──
    print("\n📧 STEP 2: Sending email digest...")
    success = send_email(jobs)

    if success:
        print("\n✅ ALL DONE! Check your inbox.")
        print(f"   📊 Summary: {len(jobs)} total | "
              f"{len([j for j in jobs if j['score']>=80])} excellent | "
              f"{len([j for j in jobs if 60<=j['score']<80])} good")
    else:
        print("\n❌ Email failed but scraping succeeded.")
        print("   Check your GitHub Secrets configuration.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
