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
    # The ten Europe-focused sources selected for every user by default.
    {"id": "sifted", "name": "Sifted", "url": "https://sifted.eu/feed", "homepage": "https://sifted.eu/", "category": "European startup news", "description": "Pan-European startup, founder, funding and venture reporting.", "icon": "SFT", "default": True},
    {"id": "tech_eu", "name": "Tech.eu", "url": "https://tech.eu/feed", "homepage": "https://tech.eu/", "category": "European startup news", "description": "European technology companies, investment rounds and exits.", "icon": "TEU", "default": True},
    {"id": "eu_startups", "name": "EU-Startups", "url": "https://www.eu-startups.com/feed/", "homepage": "https://www.eu-startups.com/", "category": "European startup news", "description": "European startup launches, funding rounds and ecosystem news.", "icon": "EU", "default": True},
    {"id": "tech_funding_news", "name": "Tech Funding News", "url": "https://techfundingnews.com/feed/", "homepage": "https://techfundingnews.com/", "category": "European startup news", "description": "Funding rounds, venture activity and startup news across Europe.", "icon": "TFN", "default": True},
    {"id": "silicon_canals", "name": "Silicon Canals", "url": "https://siliconcanals.com/feed/", "homepage": "https://siliconcanals.com/", "category": "European startup news", "description": "European and Benelux startup funding and technology coverage.", "icon": "SC", "default": True},
    {"id": "techcrunch_europe", "name": "TechCrunch Europe", "url": "https://techcrunch.com/region/europe/feed/", "homepage": "https://techcrunch.com/region/europe/", "category": "European startup news", "description": "TechCrunch reporting focused on European startups and technology.", "icon": "TC", "default": True},
    {"id": "startus_magazine", "name": "StartUs Magazine", "url": "https://magazine.startus.cc/feed/", "homepage": "https://magazine.startus.cc/", "category": "European startup news", "description": "European startup, innovation and technology intelligence.", "icon": "SU", "default": True},
    {"id": "peak_capital", "name": "Peak Capital", "url": "https://peak.capital/feed/", "homepage": "https://peak.capital/", "category": "European VC thinking", "description": "Early-stage European VC perspectives, investments and founder advice.", "icon": "PK", "default": True},
    {"id": "deutsche_startups", "name": "Deutsche Startups", "url": "https://www.deutsche-startups.de/feed/", "homepage": "https://www.deutsche-startups.de/", "category": "European startup news", "description": "German-language coverage of DACH startups, funding and exits.", "icon": "DS", "default": True},
    {"id": "invest_europe", "name": "Invest Europe", "url": "https://www.investeurope.eu/rss/", "homepage": "https://www.investeurope.eu/news/", "category": "European private capital", "description": "European venture-capital and private-equity industry news and analysis.", "icon": "IE", "default": True},

    # Additional focused sources remain available as optional user choices.
    {"id": "techcrunch_startups", "name": "TechCrunch Startups", "url": "https://techcrunch.com/category/startups/feed/", "homepage": "https://techcrunch.com/category/startups/", "category": "Additional startup news", "description": "Global funding, founders and startup operating news.", "icon": "TC", "default": False},
    {"id": "crunchbase_news", "name": "Crunchbase News", "url": "https://news.crunchbase.com/feed/", "homepage": "https://news.crunchbase.com/", "category": "Additional venture news", "description": "Data-led reporting on private markets, startups and investors.", "icon": "CB", "default": False},
    {"id": "arctic_startup", "name": "ArcticStartup", "url": "https://arcticstartup.com/feed/", "homepage": "https://arcticstartup.com/", "category": "Nordics", "description": "Nordic and Baltic startup and funding news.", "icon": "ARC", "default": False},
    {"id": "uktn", "name": "UKTN", "url": "https://www.uktech.news/feed", "homepage": "https://www.uktech.news/", "category": "United Kingdom", "description": "UK technology startup, funding and policy news.", "icon": "UK", "default": False},
    {"id": "seedcamp", "name": "Seedcamp", "url": "https://seedcamp.com/feed/", "homepage": "https://seedcamp.com/", "category": "Additional VC thinking", "description": "Operator and early-stage investor perspectives.", "icon": "SDC", "default": False},
    {"id": "saastr", "name": "SaaStr", "url": "https://www.saastr.com/feed/", "homepage": "https://www.saastr.com/", "category": "VC thinking", "description": "SaaS growth, fundraising and operating benchmarks.", "icon": "SAS", "default": False},
    {"id": "avc", "name": "AVC", "url": "https://feeds.feedblitz.com/avc", "homepage": "https://avc.com/", "category": "VC thinking", "description": "Long-running venture and company-building essays.", "icon": "AVC", "default": False},
    {"id": "vc_cafe", "name": "VC Cafe", "url": "https://www.vccafe.com/feed/", "homepage": "https://www.vccafe.com/", "category": "VC thinking", "description": "Venture capital, AI and startup ecosystem analysis.", "icon": "VCC", "default": False},
    {"id": "pe_hub", "name": "PE Hub", "url": "https://www.pehub.com/feed/", "homepage": "https://www.pehub.com/", "category": "Additional private equity", "description": "Private-equity deals, funds and portfolio-company news.", "icon": "PEH", "default": False},
    {"id": "private_equity_international", "name": "Private Equity International", "url": "https://www.privateequityinternational.com/feed/", "homepage": "https://www.privateequityinternational.com/", "category": "Additional private equity", "description": "Institutional private-equity fundraising and deal coverage.", "icon": "PEI", "default": False},
    {"id": "ft_private_equity", "name": "Financial Times · Private Equity", "url": "https://www.ft.com/private-equity?format=rss", "homepage": "https://www.ft.com/private-equity", "category": "Additional private equity", "description": "FT reporting from its dedicated private-equity topic.", "icon": "FT", "default": False},
    {"id": "bloomberg_private_markets", "name": "Bloomberg · Private Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "homepage": "https://www.bloomberg.com/markets", "category": "Additional private markets", "description": "Bloomberg Markets items admitted only when explicitly relevant to venture, private equity or deals.", "icon": "BBG", "default": False, "strict": True},
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


def _limit_with_source_coverage(
    articles: list[dict], selected_ids: tuple[str, ...], limit: int = 80,
) -> list[dict]:
    """Keep the newest items while reserving one slot per selected source."""
    ordered = sorted(articles, key=lambda article: article["published"], reverse=True)
    representatives: list[dict] = []
    representative_urls: set[str] = set()
    for source_id in selected_ids:
        article = next((item for item in ordered if item["source_id"] == source_id), None)
        if article and article["url"] not in representative_urls:
            representatives.append(article)
            representative_urls.add(article["url"])

    remaining = [article for article in ordered if article["url"] not in representative_urls]
    result = representatives + remaining[:max(0, limit - len(representatives))]
    result.sort(key=lambda article: article["published"], reverse=True)
    return result[:limit]


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
    return _limit_with_source_coverage(articles, selected_ids)


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
