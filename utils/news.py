"""Curated startup, venture-capital and private-markets RSS aggregation.

The default catalogue deliberately excludes general business, macro and political
feeds.  Broad financial publishers are admitted only through topic-specific feeds
or a strict private-markets filter.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from html import unescape
from time import mktime

import feedparser
import httpx

log = logging.getLogger(__name__)


NEWS_SOURCES: tuple[dict, ...] = (
    {"id": "techcrunch_startups", "name": "TechCrunch Startups", "url": "https://techcrunch.com/category/startups/feed/", "homepage": "https://techcrunch.com/category/startups/", "category": "Startups", "description": "Funding, founders and startup operating news.", "icon": "TC", "default": True},
    {"id": "eu_startups", "name": "EU-Startups", "url": "https://www.eu-startups.com/feed/", "homepage": "https://www.eu-startups.com/", "category": "Europe", "description": "European startup launches, rounds and ecosystem news.", "icon": "EU", "default": True},
    {"id": "sifted", "name": "Sifted", "url": "https://sifted.eu/feed", "homepage": "https://sifted.eu/", "category": "Europe", "description": "European startup and venture reporting.", "icon": "SFT", "default": True},
    {"id": "crunchbase_news", "name": "Crunchbase News", "url": "https://news.crunchbase.com/feed/", "homepage": "https://news.crunchbase.com/", "category": "Venture", "description": "Data-led reporting on private markets, startups and investors.", "icon": "CB", "default": True},
    {"id": "tech_eu", "name": "Tech.eu", "url": "https://tech.eu/feed/", "homepage": "https://tech.eu/", "category": "Europe", "description": "European technology companies, investment and exits.", "icon": "TEU", "default": True},
    {"id": "arctic_startup", "name": "ArcticStartup", "url": "https://arcticstartup.com/feed/", "homepage": "https://arcticstartup.com/", "category": "Nordics", "description": "Nordic and Baltic startup and funding news.", "icon": "ARC", "default": True},
    {"id": "silicon_canals", "name": "Silicon Canals", "url": "https://siliconcanals.com/feed/", "homepage": "https://siliconcanals.com/", "category": "Europe", "description": "European startup funding and technology coverage.", "icon": "SC", "default": False},
    {"id": "uktn", "name": "UKTN", "url": "https://www.uktech.news/feed", "homepage": "https://www.uktech.news/", "category": "United Kingdom", "description": "UK technology startup, funding and policy news.", "icon": "UK", "default": False},
    {"id": "seedcamp", "name": "Seedcamp", "url": "https://seedcamp.com/feed/", "homepage": "https://seedcamp.com/", "category": "VC thinking", "description": "Operator and early-stage investor perspectives.", "icon": "SDC", "default": True},
    {"id": "saastr", "name": "SaaStr", "url": "https://www.saastr.com/feed/", "homepage": "https://www.saastr.com/", "category": "VC thinking", "description": "SaaS growth, fundraising and operating benchmarks.", "icon": "SAS", "default": False},
    {"id": "avc", "name": "AVC", "url": "https://feeds.feedblitz.com/avc", "homepage": "https://avc.com/", "category": "VC thinking", "description": "Long-running venture and company-building essays.", "icon": "AVC", "default": False},
    {"id": "vc_cafe", "name": "VC Cafe", "url": "https://www.vccafe.com/feed/", "homepage": "https://www.vccafe.com/", "category": "VC thinking", "description": "Venture capital, AI and startup ecosystem analysis.", "icon": "VCC", "default": False},
    {"id": "pe_hub", "name": "PE Hub", "url": "https://www.pehub.com/feed/", "homepage": "https://www.pehub.com/", "category": "Private equity", "description": "Private-equity deals, funds and portfolio-company news.", "icon": "PEH", "default": True},
    {"id": "private_equity_international", "name": "Private Equity International", "url": "https://www.privateequityinternational.com/feed/", "homepage": "https://www.privateequityinternational.com/", "category": "Private equity", "description": "Institutional private-equity fundraising and deal coverage.", "icon": "PEI", "default": True},
    {"id": "ft_private_equity", "name": "Financial Times · Private Equity", "url": "https://www.ft.com/private-equity?format=rss", "homepage": "https://www.ft.com/private-equity", "category": "Private equity", "description": "FT reporting from its dedicated private-equity topic.", "icon": "FT", "default": True},
    {"id": "bloomberg_private_markets", "name": "Bloomberg · Private Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "homepage": "https://www.bloomberg.com/markets", "category": "Private markets", "description": "Bloomberg Markets items admitted only when explicitly relevant to venture, private equity or deals.", "icon": "BBG", "default": True, "strict": True},
)

# Backwards-compatible alias used by a few external scripts.
FEEDS = list(NEWS_SOURCES)
_SOURCE_BY_ID = {source["id"]: source for source in NEWS_SOURCES}
DEFAULT_SOURCE_IDS = tuple(source["id"] for source in NEWS_SOURCES if source["default"])

_PRIVATE_MARKETS_RE = re.compile(
    r"\b(?:venture capital|venture fund|private equity|private credit|buyout|"
    r"growth equity|seed round|series [a-f]|fundrais(?:e|es|ing)|startup|"
    r"take-private|portfolio compan(?:y|ies)|merger|acquisition|m&a|ipo|"
    r"dealmakers?|limited partners?|secondaries)\b",
    re.IGNORECASE,
)

_cache: dict = {"source_articles": {}, "source_fetched_at": {}}


def available_sources() -> list[dict]:
    """Return public catalogue metadata without internal filtering details."""
    return [
        {key: value for key, value in source.items() if key not in {"strict"}}
        for source in NEWS_SOURCES
    ]


def normalise_source_ids(source_ids: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Validate a selection, preserving catalogue order; empty means defaults."""
    requested = set(source_ids or DEFAULT_SOURCE_IDS)
    selected = tuple(source["id"] for source in NEWS_SOURCES if source["id"] in requested)
    return selected or DEFAULT_SOURCE_IDS


def _cache_ttl() -> int:
    try:
        import yaml
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "config" / "params.yaml"
        if p.exists():
            cfg = yaml.safe_load(p.read_text()) or {}
            val = (cfg.get("news") or {}).get("interval_seconds")
            if val:
                return int(val)
    except Exception:
        pass
    from utils.config import settings
    return settings().news_interval_seconds


def _parse_date(entry) -> datetime:
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None) or entry.get(field)
        if val:
            try:
                return datetime.fromtimestamp(mktime(val), tz=timezone.utc)
            except Exception:
                pass
    return datetime.now(tz=timezone.utc)


def _extract_image(entry) -> str | None:
    for media in getattr(entry, "media_thumbnail", []):
        if "url" in media:
            return media["url"]
    for media in getattr(entry, "media_content", []):
        if "url" in media:
            return media["url"]
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image/"):
            return enc.get("href") or enc.get("url")
    return None


def _is_relevant(source: dict, title: str, summary: str) -> bool:
    if not source.get("strict"):
        return True
    plain_summary = re.sub(r"<[^>]+>", " ", summary)
    return bool(_PRIVATE_MARKETS_RE.search(f"{title} {plain_summary}"))


def _fetch_one(source: dict) -> list[dict]:
    try:
        response = httpx.get(
            source["url"], follow_redirects=True, timeout=8,
            headers={"User-Agent": "FastVC/1.0 (+https://fastvc.org)"},
        )
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
    except Exception as exc:
        log.warning("RSS fetch failed for %s: %s", source["name"], exc)
        return []

    articles = []
    for entry in parsed.entries[:20]:
        url = entry.get("link", "").strip()
        title = entry.get("title", "Untitled").strip()
        summary = entry.get("summary", "").strip()
        if not url or not _is_relevant(source, title, summary):
            continue
        summary = unescape(re.sub(r"<[^>]+>", " ", summary))
        summary = re.sub(r"\s+", " ", summary).strip()
        if len(summary) > 300:
            summary = summary[:297] + "..."
        articles.append({
            "title": title,
            "url": url,
            "summary": summary,
            "source": source["name"],
            "source_id": source["id"],
            "category": source["category"],
            "icon": source["icon"],
            "published": _parse_date(entry).isoformat(),
            "image": _extract_image(entry),
        })
    return articles


async def fetch_news(source_ids: list[str] | tuple[str, ...] | None = None) -> list[dict]:
    """Fetch selected feeds and return a merged, deduplicated, recent list."""
    selected_ids = normalise_source_ids(source_ids)
    now = datetime.now(tz=timezone.utc)
    stale_sources = []
    for source_id in selected_ids:
        fetched_at = _cache["source_fetched_at"].get(source_id)
        if not fetched_at or (now - fetched_at).total_seconds() >= _cache_ttl():
            stale_sources.append(_SOURCE_BY_ID[source_id])

    if stale_sources:
        results = await asyncio.gather(
            *[asyncio.to_thread(_fetch_one, source) for source in stale_sources],
            return_exceptions=True,
        )
        for source, result in zip(stale_sources, results):
            if isinstance(result, Exception):
                log.warning("RSS feed error for %s: %s", source["name"], result)
                continue
            _cache["source_articles"][source["id"]] = result
            _cache["source_fetched_at"][source["id"]] = now

    articles: list[dict] = []
    seen_urls: set[str] = set()
    for source_id in selected_ids:
        for article in _cache["source_articles"].get(source_id, []):
            if article["url"] not in seen_urls:
                seen_urls.add(article["url"])
                articles.append(article)
    articles.sort(key=lambda article: article["published"], reverse=True)
    return articles[:80]


async def fetch_news_translated(
    lang: str = "en", source_ids: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    """Fetch selected news and translate titles when the UI is not English."""
    selected_ids = normalise_source_ids(source_ids)
    articles = await fetch_news(selected_ids)
    if lang == "en" or not articles:
        return articles

    cache_key = f"translated_{lang}_{','.join(selected_ids)}"
    fingerprint = tuple((article["url"], article["published"]) for article in articles)
    if _cache.get(cache_key) and _cache.get(f"{cache_key}_fingerprint") == fingerprint:
        return _cache[cache_key]

    from utils.i18n import LANGUAGES
    lang_name = LANGUAGES.get(lang, {}).get("name", "English")
    try:
        from utils.llm import default_llm
        llm = default_llm()
        titles = [article["title"] for article in articles[:30]]
        prompt = (
            f"Translate these news headlines to {lang_name}. Return only the translations, "
            "one per line in the same order. Keep proper nouns, company names and acronyms unchanged.\n\n"
            + "\n".join(f"{index + 1}. {title}" for index, title in enumerate(titles))
        )
        result = await asyncio.to_thread(llm.invoke, prompt)
        translated_lines = [line.strip() for line in result.content.strip().split("\n") if line.strip()]
        cleaned = [re.sub(r"^\d+\.\s*", "", line) for line in translated_lines]
        translated = []
        for index, article in enumerate(articles):
            copy = dict(article)
            if index < len(cleaned) and cleaned[index]:
                copy["title"] = cleaned[index]
            translated.append(copy)
        _cache[cache_key] = translated
        _cache[f"{cache_key}_fingerprint"] = fingerprint
        return translated
    except Exception as exc:
        log.warning("Title translation failed: %s", exc)
        return articles
