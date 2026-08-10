from __future__ import annotations

import hashlib
import json
from html import unescape
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from playwright.sync_api import Page, sync_playwright

from db import connect


SOURCES = {
    "seedcamp": "https://seedcamp.com/our-companies/",
    "startup_wise_guys": "https://startupwiseguys.com/portfolio/",
}
USER_AGENT = "FastVC/1.0 (+https://fastvc.org)"


def _robots_allowed(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    response = httpx.get(robots_url, timeout=15, headers={"User-Agent": USER_AGENT},
                         follow_redirects=True)
    if response.status_code == 404:
        return True
    response.raise_for_status()
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


def _seedcamp(page: Page, limit: int) -> list[dict]:
    page.goto(SOURCES["seedcamp"], wait_until="domcontentloaded", timeout=45_000)
    reject = page.get_by_role("button", name="Reject All")
    if reject.count():
        reject.click()
    page.wait_for_selector(".company__item", state="attached", timeout=20_000)
    results: list[dict] = []
    seen: set[str] = set()
    # Seedcamp's paginator hides and shows cards, but the complete portfolio is
    # already attached to the DOM. Reading attached cards avoids 27 artificial
    # page clicks and remains resumable through source-record hashes.
    for card in page.locator(".company__item").all()[:limit]:
        name = card.locator(".company__item__name").inner_text().replace("\uf08e", "").strip()
        website = card.locator("a.company__item__link").get_attribute("href") or ""
        if not name or website in seen:
            continue
        seen.add(website)
        year = card.locator(".company__item__year").inner_text().strip()
        description = card.locator(".company__item__description__content").inner_text().strip()
        results.append({
            "name": name, "website": website, "investment_year": year,
            "description": description, "portfolio": "Seedcamp",
            "source_url": SOURCES["seedcamp"],
        })
    return results


def _startup_wise_guys(page: Page, limit: int) -> list[dict]:
    page.goto(SOURCES["startup_wise_guys"], wait_until="domcontentloaded", timeout=45_000)
    page.wait_for_selector("[data-swg-filter-item] [data-portfolio-item]", timeout=20_000)
    results: list[dict] = []
    for item in page.locator("[data-swg-filter-item]").all()[:limit]:
        card = item.locator("[data-portfolio-item]")
        try:
            details = json.loads(unescape(card.get_attribute("data-details") or "{}"))
        except json.JSONDecodeError:
            details = {}
        links = details.get("links") or []
        website = next((str(link.get("value") or "").strip() for link in links
                        if link.get("title") == "Website"), "")
        results.append({
            "name": details.get("title") or card.locator(".portfolio-item__title").inner_text().strip(),
            "website": website,
            "description": card.locator(".portfolio-item__description").inner_text().strip(),
            "country": details.get("countryTitle") or item.get_attribute("data-headquarters-country"),
            "vertical": item.get_attribute("data-vertical") or "",
            "batch": details.get("batch") or "",
            "status": item.get_attribute("data-status") or "",
            "portfolio": "Startup Wise Guys", "source_url": SOURCES["startup_wise_guys"],
        })
    return results


def scrape_public_directory(source: str, *, limit: int = 100, headed: bool = False,
                            persist: bool = True) -> dict:
    if source not in SOURCES:
        raise ValueError(f"Unsupported public directory: {source}")
    if not 1 <= limit <= 1000:
        raise ValueError("Directory limit must be between 1 and 1000")
    url = SOURCES[source]
    if not _robots_allowed(url):
        raise PermissionError(f"robots.txt does not allow automated access to {url}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed, channel="chrome")
        context = browser.new_context(user_agent=USER_AGENT, locale="en-GB")
        page = context.new_page()
        records = (_seedcamp(page, limit) if source == "seedcamp"
                   else _startup_wise_guys(page, limit))
        context.close()
        browser.close()
    result = {"provider": source, "requested": limit, "records": len(records)}
    if not persist:
        result["sample"] = records[:3]
        return result

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO fastvc.ingestion_runs
               (provider,mode,status,requested_limit,processed,inserted,metadata,finished_at)
               VALUES (%s,'public_directory','completed',%s,%s,%s,%s::jsonb,now()) RETURNING id""",
            (source, limit, len(records), len(records), json.dumps(result)),
        )
        run_id = cur.fetchone()[0]
        inserted = 0
        for record in records:
            external_id = record.get("website") or record["name"].lower()
            payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
            digest = hashlib.sha256(payload.encode()).hexdigest()
            cur.execute(
                """INSERT INTO fastvc.company_source_records
                   (company_id,source,external_id,source_url,payload,payload_hash,license)
                   VALUES (NULL,%s,%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT (source,external_id,payload_hash) DO NOTHING""",
                (source, external_id, url, payload, digest, "Public page; source terms apply"),
            )
            inserted += cur.rowcount
        cur.execute("UPDATE fastvc.ingestion_runs SET inserted=%s WHERE id=%s", (inserted, run_id))
        conn.commit()
    return {**result, "inserted": inserted, "run_id": run_id}
