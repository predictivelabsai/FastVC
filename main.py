"""Entrypoint. Kept as a thin shim so standard runners (`python main.py`)
work without changes. All routing lives in app.py."""

import logging
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from utils.logging import setup_logging

setup_logging()

from app import app, serve  # noqa: E402,F401
from utils.config import settings

log = logging.getLogger("scheduler")

EET = ZoneInfo("Europe/Tallinn")


def _news_cache_loop():
    """Refresh every RSS source into the shared process cache every ten minutes."""
    from utils.news import NEWS_SOURCES, _cache_ttl, refresh_news_in_background
    source_ids = tuple(source["id"] for source in NEWS_SOURCES)
    while True:
        refresh_news_in_background(source_ids)
        time.sleep(_cache_ttl())


def _daily_deals_loop():
    """Send daily deals digest to all opted-in users. Runs as a daemon thread."""
    s = settings()
    if not s.digest_enabled:
        log.info("Daily deals scheduler disabled (DIGEST_ENABLED=0)")
        return
    if not s.postmark_api_token:
        log.info("Daily deals scheduler disabled (no POSTMARK_API_TOKEN)")
        return

    target_hour, target_minute = s.digest_hour, 0
    log.info("Daily deals scheduler started — target %02d:%02d EET to opted-in users",
             target_hour, target_minute)

    while True:
        now = datetime.now(EET)
        target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        wait_secs = (target - now).total_seconds()
        log.info("Next daily deals email at %s (in %.0f min)", target.isoformat(), wait_secs / 60)
        time.sleep(wait_secs)

        try:
            from scripts.daily_deals import _top_deals, _fetch_news_sync, send_to_all_users

            deals = _top_deals(5)
            if not deals:
                log.warning("No active deals — skipping daily email")
                continue

            news = _fetch_news_sync(5)
            sent = send_to_all_users(deals, news)
            log.info("Daily deals loop complete — sent to %d users", sent)
        except Exception:
            log.exception("Daily deals email failed")


_news_t = threading.Thread(target=_news_cache_loop, daemon=True, name="news-cache")
_news_t.start()

_deals_t = threading.Thread(target=_daily_deals_loop, daemon=True, name="daily-deals")
_deals_t.start()

if __name__ == "__main__":
    # A deterministic single process avoids duplicate scheduler threads and
    # file-watcher exhaustion in repositories with local virtual environments.
    serve(port=settings().port, reload=False)
