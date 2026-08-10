"""Capture a curated, error-free FastVC product walkthrough with Playwright.

Start FastVC first, then run:

    DEMO_BASE_URL=http://127.0.0.1:5059 \
      .venv/bin/python scripts/capture_demo.py

Only successful frames are written to ``docs/demo/frames/manifest.txt``. A
failed route or AI action is reported and excluded, so stale/error screenshots
cannot leak into the published GIF.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
FRAMES_DIR = ROOT / "docs" / "demo" / "frames"
MANIFEST = FRAMES_DIR / "manifest.txt"
BASE_URL = os.getenv("DEMO_BASE_URL", "http://127.0.0.1:5059").rstrip("/")
VIEWPORT = {"width": 1440, "height": 900}


@dataclass(frozen=True)
class Frame:
    filename: str
    route: str
    ready: str
    action: str = ""


# Agentic work appears first, followed by every primary workspace exposed in
# the left navigation. User Guide represents the Training submenu without
# relying on a long-running game turn.
FRAMES = (
    Frame("01-agent-screening.png", "/app", "#chat-input", "chat_screening"),
    Frame("02-agent-round-model.png", "/app", "#chat-input", "chat_round"),
    Frame("03-agent-ic-memo.png", "/app", "#chat-input", "chat_memo"),
    Frame("04-pipeline-copilot.png", "/app/pipeline", ".kanban-board", "copilot"),
    Frame("05-discovery.png", "/app/discovery?stage=series_a&min_momentum=65", ".discovery-hero"),
    Frame("06-signals.png", "/app/signals", ".signal-grid"),
    Frame("07-market-map.png", "/app/market-map", ".market-map-table"),
    Frame("08-founders.png", "/app/founders", ".search-table"),
    Frame("09-pipeline.png", "/app/pipeline", ".kanban-board"),
    Frame("10-companies.png", "/app/companies?sector=healthtech", ".search-table"),
    Frame("11-investors.png", "/app/investors", ".companies-wrap"),
    Frame("12-data-room.png", "/app/dataroom", ".companies-wrap"),
    Frame("13-agent-instructions.png", "/app/instructions/deal_triage", ".instr-edit"),
    Frame("14-genai-analytics.png", "/app/analytics", "#analytics-q", "analytics"),
    Frame("15-round-ownership.png", "/app/valuation", "#round-results", "round_model"),
    Frame("16-portfolio.png", "/app/portfolio", ".integration-stats"),
    Frame("17-integrations.png", "/app/integrations", ".integration-provider-grid"),
    Frame("18-user-guide.png", "/app/help", ".guide-content"),
)

CHAT_PROMPTS = {
    "chat_screening": "screen: assess Meridian Health using our internal data and recommend the next diligence step",
    "chat_round": "round: model an $8M Series A at $32M pre-money for Northwind AI",
    "chat_memo": "memo: draft a concise Series A IC recommendation for Northwind AI using our internal data",
}

BAD_TEXT = re.compile(
    r"internal server error|traceback \(most recent call last\)|application error|"
    r"connection error|redirect_uri_mismatch",
    re.IGNORECASE,
)
BAD_AI_TEXT = re.compile(
    r"\berror:\s|connection error|not configured|failed to (?:run|load|generate)|"
    r"i (?:cannot|can't) access",
    re.IGNORECASE,
)


def _goto(page: Page, route: str):
    response = page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded", timeout=45_000)
    if response is None or not response.ok:
        status = response.status if response is not None else "no response"
        raise RuntimeError(f"{route} returned {status}")
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except PlaywrightTimeoutError:
        pass


def _last_assistant_text(page: Page, container: str = "#messages") -> str:
    bubbles = page.locator(f"{container} .msg-assistant .msg-bubble")
    if not bubbles.count():
        return ""
    return bubbles.last.inner_text().strip()


def _run_chat(page: Page, prompt: str):
    page.fill("#chat-input", prompt)
    page.evaluate(
        """() => document.querySelector('#chat-form').dispatchEvent(
            new Event('submit', {cancelable: true}))"""
    )
    page.wait_for_function(
        """() => {
            const bubbles = document.querySelectorAll('#messages .msg-assistant .msg-bubble');
            if (!bubbles.length) return false;
            const last = bubbles[bubbles.length - 1];
            return (last.textContent || '').trim().length > 180 &&
                   !last.parentElement.classList.contains('streaming');
        }""",
        timeout=150_000,
    )
    text = _last_assistant_text(page)
    if BAD_AI_TEXT.search(text):
        raise RuntimeError(f"agent returned an error state: {text[:140]!r}")
    first_group = page.locator("details.agent-group").first
    if first_group.count():
        first_group.evaluate("el => el.open = true")
    page.wait_for_timeout(700)


def _run_copilot(page: Page):
    page.wait_for_selector("#copilot-input", timeout=10_000)
    page.fill("#copilot-input", "Which three deals deserve partner attention first, and why?")
    page.evaluate("() => window.copilotSend(null)")
    page.wait_for_function(
        """() => {
            const bubbles = document.querySelectorAll('#copilot-messages .msg-assistant .msg-bubble');
            if (!bubbles.length) return false;
            const last = bubbles[bubbles.length - 1];
            return (last.textContent || '').trim().length > 160 &&
                   !last.classList.contains('streaming');
        }""",
        timeout=150_000,
    )
    text = _last_assistant_text(page, "#copilot-messages")
    if BAD_AI_TEXT.search(text):
        raise RuntimeError(f"copilot returned an error state: {text[:140]!r}")
    page.wait_for_timeout(700)


def _run_analytics(page: Page):
    page.fill("#analytics-q", "Company count by deal stage")
    page.evaluate("() => window.runAnalytics()")
    page.wait_for_function(
        """() => document.querySelector('#analytics-result .analytics-chart') ||
                  document.querySelector('#analytics-result .analytics-error')""",
        timeout=90_000,
    )
    if page.locator("#analytics-result .analytics-error").count():
        raise RuntimeError(
            "analytics returned an error state: "
            + page.locator("#analytics-result .analytics-error").inner_text()[:160]
        )
    page.wait_for_timeout(1_000)


def _run_round_model(page: Page):
    page.get_by_role("button", name="Model round & outcome").click()
    page.wait_for_function(
        """() => {
            const out = document.querySelector('#round-results');
            return out && (out.querySelector('table') || out.querySelector('.auth-error'));
        }""",
        timeout=20_000,
    )
    if page.locator("#round-results .auth-error").count():
        raise RuntimeError(page.locator("#round-results .auth-error").inner_text())
    page.wait_for_timeout(600)


def _assert_clean(page: Page, browser_errors: list[str], response_errors: list[str]):
    body = page.locator("body").inner_text()
    if BAD_TEXT.search(body):
        raise RuntimeError("visible application error detected")
    visible_errors = page.locator(
        ".analytics-error:visible, .auth-error:visible, .error-message:visible, [role='alert']:visible"
    )
    for index in range(visible_errors.count()):
        text = visible_errors.nth(index).inner_text().strip()
        if text:
            raise RuntimeError(f"visible error element: {text[:160]!r}")
    if browser_errors:
        raise RuntimeError("browser error: " + browser_errors[0][:180])
    if response_errors:
        raise RuntimeError("failed same-origin request: " + response_errors[0][:180])


def _capture(page: Page, frame: Frame, browser_errors: list[str], response_errors: list[str]):
    browser_errors.clear()
    response_errors.clear()
    _goto(page, frame.route)
    page.wait_for_selector(frame.ready, timeout=15_000)
    if frame.action in CHAT_PROMPTS:
        _run_chat(page, CHAT_PROMPTS[frame.action])
    elif frame.action == "copilot":
        _run_copilot(page)
    elif frame.action == "analytics":
        _run_analytics(page)
    elif frame.action == "round_model":
        _run_round_model(page)
    page.wait_for_timeout(600)
    _assert_clean(page, browser_errors, response_errors)
    page.screenshot(path=FRAMES_DIR / frame.filename, full_page=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        default="",
        help="comma-separated frame filenames to recapture without replacing other clean frames",
    )
    args = parser.parse_args()
    only = {name.strip() for name in args.only.split(",") if name.strip()}
    known = {frame.filename for frame in FRAMES}
    unknown = only - known
    if unknown:
        raise SystemExit("Unknown frame(s): " + ", ".join(sorted(unknown)))

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    if only:
        successful_set = {
            name.strip()
            for name in MANIFEST.read_text(encoding="utf-8").splitlines()
            if name.strip()
        } if MANIFEST.exists() else set()
        targets = tuple(frame for frame in FRAMES if frame.filename in only)
    else:
        for old in FRAMES_DIR.glob("*.png"):
            old.unlink()
        MANIFEST.unlink(missing_ok=True)
        successful_set: set[str] = set()
        targets = FRAMES

    skipped: list[tuple[str, str]] = []
    origin = urlsplit(BASE_URL).netloc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            locale="en-GB",
            device_scale_factor=1,
            reduced_motion="reduce",
            color_scheme="light",
        )
        page = context.new_page()
        browser_errors: list[str] = []
        response_errors: list[str] = []
        page.on("pageerror", lambda exc: browser_errors.append(str(exc)))
        page.on(
            "console",
            lambda msg: browser_errors.append(msg.text)
            if msg.type == "error" and "favicon" not in msg.text.lower()
            else None,
        )
        page.on(
            "response",
            lambda response: response_errors.append(f"HTTP {response.status} {response.url}")
            if urlsplit(response.url).netloc == origin and response.status >= 400
            else None,
        )

        health = page.request.get(f"{BASE_URL}/healthz")
        if not health.ok:
            raise SystemExit(f"FastVC health check failed: HTTP {health.status}")

        for frame in targets:
            successful_set.discard(frame.filename)
            try:
                _capture(page, frame, browser_errors, response_errors)
            except Exception as exc:  # keep valid frames, exclude the failed one
                (FRAMES_DIR / frame.filename).unlink(missing_ok=True)
                skipped.append((frame.filename, str(exc)))
                print(f"  skip {frame.filename}: {exc}", file=sys.stderr)
            else:
                successful_set.add(frame.filename)
                print(f"  captured {frame.filename}")
        browser.close()

    successful = [
        frame.filename
        for frame in FRAMES
        if frame.filename in successful_set and (FRAMES_DIR / frame.filename).exists()
    ]
    MANIFEST.write_text("\n".join(successful) + ("\n" if successful else ""), encoding="utf-8")
    print(f"\nManifest contains {len(successful)}/{len(FRAMES)} clean frames")
    if skipped:
        print("Excluded frames:")
        for filename, reason in skipped:
            print(f"  - {filename}: {reason}")
    if len(successful) < 10:
        print("Too few clean frames to build a useful walkthrough.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
