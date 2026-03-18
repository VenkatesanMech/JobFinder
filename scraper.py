# ============================================================
# SCRAPER.PY — Fixed Headless Browser Job Scraper
# Better waits, smarter selectors, more job titles
# ============================================================

import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from companies import COMPANIES, PROFILE_KEYWORDS


def calculate_match(title: str, description: str = "") -> int:
    text = (title + " " + description).lower()
    hits = sum(1 for kw in PROFILE_KEYWORDS if kw in text)
    raw = round((hits / len(PROFILE_KEYWORDS)) * 100)
    return min(97, max(10, raw))


def clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:300]


def is_valid_job_title(title: str) -> bool:
    """Check if text looks like a real job title"""
    if not title or len(title) < 5 or len(title) > 200:
        return False
    skip = [
        "cookie", "privacy", "login", "sign in", "menu", "search",
        "filter", "sort", "load more", "next", "previous", "page",
        "home", "about", "contact", "apply", "submit", "back",
        "javascript", "error", "undefined", "null", "careers",
        "jobs", "all jobs", "view all", "see all", "more jobs"
    ]
    title_lower = title.lower().strip()
    if any(s == title_lower for s in skip):
        return False
    if sum(1 for c in title if c.isalpha()) < 4:
        return False
    return True


async def wait_for_jobs(page, selectors: list, timeout: int = 8000) -> list:
    """Try multiple selectors and return first match"""
    for selector in selectors:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            elements = await page.query_selector_all(selector)
            if len(elements) >= 2:
                return elements[:25]
        except Exception:
            continue
    return []


async def scrape_google_jobs(page, company: dict) -> list:
    """
    Use Google Jobs search — most reliable fallback
    Google indexes ALL company career pages
    """
    jobs = []
    company_name = company["name"]

    search_queries = company.get("search_terms", ["project manager", "program manager"])

    for term in search_queries[:2]:  # Try 2 search terms per company
        try:
            # Google Jobs search URL
            query = f'{term} {company_name} India'
            url = f'https://www.google.com/search?q={query.replace(" ", "+")}&ibp=htl;jobs'

            await page.goto(url, timeout=25000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Try to get job cards from Google Jobs panel
            job_selectors = [
                '[data-ved] li',
                '.iFjolb',
                '.gws-plugins-horizon-jobs__li-ed',
                '[jscontroller] li',
                '.lLfZXe',
            ]

            for selector in job_selectors:
                try:
                    items = await page.query_selector_all(selector)
                    if items:
                        for item in items[:8]:
                            try:
                                text = clean(await item.inner_text())
                                lines = [l.strip() for l in text.split('\n') if l.strip()]
                                if not lines:
                                    continue

                                title = lines[0]
                                if not is_valid_job_title(title):
                                    continue

                                # Get link
                                link_el = await item.query_selector('a')
                                url_found = company["search_url"]
                                if link_el:
                                    href = await link_el.get_attribute('href')
                                    if href and href.startswith('http'):
                                        url_found = href

                                score = calculate_match(title, text)
                                if score >= 10:
                                    jobs.append({
                                        "title": title,
                                        "company": company_name,
                                        "company_id": company["id"],
                                        "domain": company["domain"],
                                        "color": company["color"],
                                        "emoji": company["emoji"],
                                        "location": "India",
                                        "apply_url": url_found,
                                        "source": "Google Jobs",
                                        "score": score,
                                        "snippet": text[:200],
                                        "found_at": datetime.now().strftime("%d %b %Y %I:%M %p"),
                                    })
                            except Exception:
                                continue
                        if jobs:
                            break
                except Exception:
                    continue

            if jobs:
                break
            await asyncio.sleep(2)

        except Exception as e:
            print(f"    Google search error: {str(e)[:60]}")
            continue

    return jobs


async def scrape_direct(page, company: dict) -> list:
    """
    Directly visit the company career page
    """
    jobs = []
    name = company["name"]

    try:
        print(f"    → Direct: {company['search_url'][:60]}...")
        await page.goto(company["search_url"], timeout=30000, wait_until="domcontentloaded")

        # Wait extra time for JavaScript to render jobs
        await asyncio.sleep(5)

        # Try scrolling to trigger lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(2)

        # All possible job card selectors
        selectors = [
            # Generic job card patterns
            "[data-job-id]",
            "[data-jobid]",
            "[data-job]",
            "[data-ph-at-id='job-item']",
            "[data-automation='job-list-item']",
            # Class-based selectors
            ".job-tile", ".job-card", ".job-item",
            ".job-list-item", ".jobs-list-item",
            ".job-result", ".job-result-item",
            ".job-posting", ".job-post",
            ".position-item", ".position-card",
            ".opening-item", ".vacancy-item",
            ".career-item", ".careers-item",
            # Framework-specific
            "[class*='JobCard']", "[class*='job-card']",
            "[class*='JobItem']", "[class*='job-item']",
            "[class*='JobResult']", "[class*='job-result']",
            "[class*='PositionCard']", "[class*='position']",
            "[class*='jobTitle']", "[class*='job_title']",
            # Table rows (older sites like HAL, DRDO)
            "table tbody tr",
            # List items with job links
            "ul.jobs li", "ol.jobs li",
            ".jobs-list li", ".job-list li",
        ]

        elements = await wait_for_jobs(page, selectors, timeout=5000)

        if elements:
            print(f"    ✓ Found {len(elements)} elements")
            for el in elements:
                try:
                    text = clean(await el.inner_text())
                    if len(text) < 8:
                        continue

                    # Get title
                    title = ""
                    for ts in ["h1","h2","h3","h4","h5","[class*='title']","[class*='name']","a","td"]:
                        try:
                            t_el = await el.query_selector(ts)
                            if t_el:
                                t = clean(await t_el.inner_text())
                                if is_valid_job_title(t):
                                    title = t
                                    break
                        except Exception:
                            continue

                    if not title:
                        lines = [l.strip() for l in text.split('\n') if l.strip()]
                        for line in lines:
                            if is_valid_job_title(line):
                                title = line
                                break

                    if not title or not is_valid_job_title(title):
                        continue

                    # Get link
                    apply_url = company["search_url"]
                    try:
                        a = await el.query_selector("a")
                        if a:
                            href = await a.get_attribute("href")
                            if href:
                                if href.startswith("http"):
                                    apply_url = href
                                elif href.startswith("/"):
                                    from urllib.parse import urlparse
                                    p = urlparse(company["search_url"])
                                    apply_url = f"{p.scheme}://{p.netloc}{href}"
                    except Exception:
                        pass

                    # Location
                    location = "India"
                    for loc in ["bengaluru","bangalore","mumbai","chennai","pune","delhi",
                                "hyderabad","coimbatore","noida","gurgaon","india"]:
                        if loc in text.lower():
                            location = loc.title()
                            break

                    score = calculate_match(title, text)
                    if score >= 10:
                        jobs.append({
                            "title": title,
                            "company": name,
                            "company_id": company["id"],
                            "domain": company["domain"],
                            "color": company["color"],
                            "emoji": company["emoji"],
                            "location": location,
                            "apply_url": apply_url,
                            "source": "Career Page",
                            "score": score,
                            "snippet": text[:200],
                            "found_at": datetime.now().strftime("%d %b %Y %I:%M %p"),
                        })
                except Exception:
                    continue

    except PlaywrightTimeout:
        print(f"    ⏱ Timeout — will try Google fallback")
    except Exception as e:
        print(f"    ✗ Error: {str(e)[:80]}")

    return jobs


async def scrape_company(page, company: dict) -> list:
    """Try direct scraping first, then Google Jobs as fallback"""
    name = company["name"]
    print(f"\n  [{company['emoji']}] {name}")

    # Try direct career page first
    jobs = await scrape_direct(page, company)

    # If nothing found, use Google Jobs
    if not jobs:
        print(f"    → Trying Google Jobs fallback...")
        jobs = await scrape_google_jobs(page, company)

    # Deduplicate by title
    seen = set()
    unique = []
    for j in jobs:
        key = j["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(j)

    print(f"    ✅ {len(unique)} jobs found")
    return unique


async def run_scraper() -> list:
    all_jobs = []
    total = len(COMPANIES)

    print("=" * 60)
    print("🤖 CAREER SCRAPER BOT — Venkatesan P")
    print(f"📅 {datetime.now().strftime('%A, %d %B %Y — %I:%M %p')}")
    print(f"🏢 Scanning {total} companies...")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
        )

        # Block images and fonts to speed things up
        await context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}", lambda r: r.abort())

        page = await context.new_page()

        for i, company in enumerate(COMPANIES, 1):
            print(f"\n[{i}/{total}]", end="")
            jobs = await scrape_company(page, company)
            all_jobs.extend(jobs)
            # Polite delay between companies
            await asyncio.sleep(3)

        await browser.close()

    # Sort by score
    all_jobs.sort(key=lambda x: x["score"], reverse=True)

    print("\n" + "=" * 60)
    print(f"✅ SCRAPING COMPLETE")
    print(f"📊 Total jobs: {len(all_jobs)}")
    print(f"🟢 80%+  : {len([j for j in all_jobs if j['score'] >= 80])}")
    print(f"🟡 60-79%: {len([j for j in all_jobs if 60 <= j['score'] < 80])}")
    print(f"🔵 40-59%: {len([j for j in all_jobs if 40 <= j['score'] < 60])}")
    print(f"⚪ 10-39%: {len([j for j in all_jobs if 10 <= j['score'] < 40])}")
    print("=" * 60)

    return all_jobs


if __name__ == "__main__":
    jobs = asyncio.run(run_scraper())
    with open("jobs_found.json", "w") as f:
        json.dump(jobs, f, indent=2)
    print(f"\n💾 Saved {len(jobs)} jobs")
