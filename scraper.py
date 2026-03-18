# ============================================================
# SCRAPER.PY — Headless Browser Job Scraper
# Uses Playwright to open real Chrome and visit career pages
# ============================================================

import asyncio
import json
import re
import time
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from companies import COMPANIES, PROFILE_KEYWORDS, SEARCH_TERMS


# ── MATCH SCORE ──
# Checks how well a job matches your profile (0-100%)
def calculate_match(title: str, description: str = "") -> int:
    text = (title + " " + description).lower()
    hits = sum(1 for kw in PROFILE_KEYWORDS if kw in text)
    raw = round((hits / len(PROFILE_KEYWORDS)) * 100)
    return min(97, max(15, raw))


# ── CLEAN TEXT ──
def clean(text: str) -> str:
    if not text:
        return ""
    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:200]  # Limit length


# ── SCRAPE ONE COMPANY ──
async def scrape_company(page, company: dict) -> list:
    """
    Opens Chrome, goes to the career page, and extracts job listings.
    Returns a list of job dictionaries.
    """
    jobs_found = []
    company_name = company["name"]

    print(f"\n  🌐 Opening {company_name}...")

    try:
        # ── Step 1: Go to the career page ──
        await page.goto(company["search_url"], timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(3)  # Wait for JavaScript to load jobs

        # ── Step 2: Try to find job listings ──
        # Different companies use different HTML structures
        # We try multiple selectors to find job cards

        selectors_to_try = [
            # Common job listing selectors across career sites
            "[data-job-id]",
            "[data-ph-at-id='job-item']",
            ".job-tile",
            ".job-card",
            ".job-list-item",
            ".job-item",
            ".jobs-list-item",
            "[class*='jobResult']",
            "[class*='job-result']",
            "[class*='JobCard']",
            "[class*='job_card']",
            "article[class*='job']",
            "li[class*='job']",
            # Fallback: any link that looks like a job posting
            "a[href*='job']",
            "a[href*='career']",
            "a[href*='position']",
        ]

        job_elements = []
        used_selector = None

        for selector in selectors_to_try:
            try:
                elements = await page.query_selector_all(selector)
                if len(elements) >= 2:  # Found at least 2 — looks like a real list
                    job_elements = elements[:20]  # Max 20 jobs per company
                    used_selector = selector
                    print(f"  ✅ Found {len(elements)} items with '{selector}'")
                    break
            except Exception:
                continue

        # ── Step 3: Extract job details from each card ──
        if job_elements:
            for element in job_elements:
                try:
                    # Get all text from the job card
                    raw_text = await element.inner_text()
                    raw_text = clean(raw_text)

                    if len(raw_text) < 10:  # Skip empty elements
                        continue

                    # Try to get the job title specifically
                    title = ""
                    title_selectors = [
                        "h1", "h2", "h3", "h4",
                        "[class*='title']",
                        "[class*='job-name']",
                        "[class*='position']",
                        "a",
                    ]
                    for ts in title_selectors:
                        try:
                            title_el = await element.query_selector(ts)
                            if title_el:
                                t = await title_el.inner_text()
                                t = clean(t)
                                if len(t) > 5 and len(t) < 150:
                                    title = t
                                    break
                        except Exception:
                            continue

                    if not title:
                        # Use first line of raw text as title
                        title = raw_text.split('\n')[0][:100]

                    # Skip clearly irrelevant titles
                    skip_words = ["cookie", "privacy", "login", "sign in", "menu", "search", "filter", "sort"]
                    if any(w in title.lower() for w in skip_words):
                        continue

                    # Try to get the apply link
                    apply_url = company["search_url"]
                    try:
                        link_el = await element.query_selector("a")
                        if link_el:
                            href = await link_el.get_attribute("href")
                            if href:
                                if href.startswith("http"):
                                    apply_url = href
                                elif href.startswith("/"):
                                    # Relative URL — add domain
                                    from urllib.parse import urlparse
                                    parsed = urlparse(company["search_url"])
                                    apply_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                    except Exception:
                        pass

                    # Try to find location in the card text
                    location = "India"
                    location_keywords = ["india", "bengaluru", "bangalore", "mumbai", "chennai",
                                        "pune", "delhi", "hyderabad", "coimbatore", "noida", "gurgaon"]
                    for loc_kw in location_keywords:
                        if loc_kw in raw_text.lower():
                            location = loc_kw.title()
                            break

                    # Calculate match score
                    score = calculate_match(title, raw_text)

                    # Only add if score is above minimum threshold
                    if score >= 20:
                        jobs_found.append({
                            "title": title,
                            "company": company_name,
                            "company_id": company["id"],
                            "domain": company["domain"],
                            "color": company["color"],
                            "emoji": company["emoji"],
                            "location": location,
                            "apply_url": apply_url,
                            "source_url": company["search_url"],
                            "score": score,
                            "raw_snippet": raw_text[:200],
                            "scraped_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
                        })

                except Exception as e:
                    continue  # Skip problematic elements silently

        # ── Step 4: If no jobs found, try Google fallback ──
        if not jobs_found and company.get("fallback_url"):
            print(f"  ⚠️  No jobs found directly. Trying Google fallback...")
            jobs_found = await scrape_google_fallback(page, company)

    except PlaywrightTimeout:
        print(f"  ⏱️  Timeout for {company_name} — skipping")
    except Exception as e:
        print(f"  ❌ Error scraping {company_name}: {str(e)[:100]}")

    print(f"  📋 {company_name}: {len(jobs_found)} relevant jobs found")
    return jobs_found


# ── GOOGLE FALLBACK ──
async def scrape_google_fallback(page, company: dict) -> list:
    """
    When direct scraping fails, search Google for jobs at this company.
    Google indexes all career pages so this usually works.
    """
    jobs_found = []

    try:
        search_query = f'site:{extract_domain(company["search_url"])} project manager'
        google_url = f'https://www.google.com/search?q={search_query.replace(" ", "+")}'

        await page.goto(google_url, timeout=20000, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Extract search results
        results = await page.query_selector_all(".tF2Cxc, .g")
        for result in results[:5]:
            try:
                title_el = await result.query_selector("h3")
                link_el = await result.query_selector("a")

                if not title_el or not link_el:
                    continue

                title = clean(await title_el.inner_text())
                href = await link_el.get_attribute("href")

                if not title or not href:
                    continue

                score = calculate_match(title)
                if score >= 20:
                    jobs_found.append({
                        "title": title,
                        "company": company["name"],
                        "company_id": company["id"],
                        "domain": company["domain"],
                        "color": company["color"],
                        "emoji": company["emoji"],
                        "location": "India",
                        "apply_url": href if href.startswith("http") else company["search_url"],
                        "source_url": company["search_url"],
                        "score": score,
                        "raw_snippet": f"Found via Google — visit career page for details",
                        "scraped_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
                    })
            except Exception:
                continue

    except Exception as e:
        print(f"  Google fallback failed: {str(e)[:80]}")

    return jobs_found


def extract_domain(url: str) -> str:
    """Extracts domain from URL e.g. 'https://jobs.boeing.com/...' → 'jobs.boeing.com'"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return url


# ── MAIN SCRAPER ──
async def run_scraper() -> list:
    """
    Main function — opens Chrome headlessly and scrapes all 25 companies.
    Returns list of all jobs found.
    """
    all_jobs = []
    total_companies = len(COMPANIES)

    print("=" * 60)
    print("🤖 HEADLESS JOB SCRAPER — Venkatesan P")
    print(f"📅 {datetime.now().strftime('%A, %d %B %Y — %I:%M %p IST')}")
    print(f"🏢 Scraping {total_companies} companies...")
    print("=" * 60)

    async with async_playwright() as p:

        # ── Launch Chrome in headless mode ──
        # headless=True means no visible window — runs silently in background
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",  # Hide bot detection
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )

        # Create a browser context (like a fresh Chrome profile)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )

        # Open a new tab
        page = await context.new_page()

        # ── Scrape each company one by one ──
        for i, company in enumerate(COMPANIES, 1):
            print(f"\n[{i}/{total_companies}] {company['emoji']} {company['name']}")

            company_jobs = await scrape_company(page, company)
            all_jobs.extend(company_jobs)

            # Wait between requests — be polite to servers
            # Random delay 2-5 seconds to avoid being blocked
            delay = 2 + (i % 3)
            print(f"  ⏳ Waiting {delay}s before next company...")
            await asyncio.sleep(delay)

        await browser.close()

    # ── Sort all jobs by match score (highest first) ──
    all_jobs.sort(key=lambda x: x["score"], reverse=True)

    print("\n" + "=" * 60)
    print(f"✅ SCRAPING COMPLETE!")
    print(f"📊 Total jobs found: {len(all_jobs)}")
    print(f"🟢 80%+ match: {len([j for j in all_jobs if j['score'] >= 80])}")
    print(f"🟡 60-79% match: {len([j for j in all_jobs if 60 <= j['score'] < 80])}")
    print(f"🔵 Below 60%: {len([j for j in all_jobs if j['score'] < 60])}")
    print("=" * 60)

    return all_jobs


# ── RUN ──
if __name__ == "__main__":
    jobs = asyncio.run(run_scraper())
    # Save to JSON file for emailer to use
    with open("jobs_found.json", "w") as f:
        json.dump(jobs, f, indent=2)
    print(f"\n💾 Saved {len(jobs)} jobs to jobs_found.json")
