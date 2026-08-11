"""News-source configuration page."""

from __future__ import annotations

from collections import defaultdict

from fasthtml.common import (
    A, Body, Button, Div, Form, H2, H3, Head, Html, Input, Label, Link,
    Meta, NotStr, P, Script, Small, Span, Title,
)
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app import rt
from chat.components import copilot_pane, copilot_toggle_btn, left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from chat.routes import _ensure_user, _list_sessions
from landing.components import TAILWIND_CONFIG, _favicon_links
from utils.i18n import get_lang
from utils.news import available_sources
from utils.news_preferences import get_news_source_ids, save_news_source_ids
from utils.session import get_currency


def _head():
    return Head(
        Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title("News sources · FastVC"), *_favicon_links(), *common_scripts(),
        Script(src="https://cdn.tailwindcss.com"), Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _source_card(source: dict, selected: set[str]):
    source_id = source["id"]
    return Label(
        Input(type="checkbox", name="source_id", value=source_id,
              checked=source_id in selected, cls="news-source-checkbox"),
        Div(
            Div(
                Span(source["icon"], cls="news-source-config-icon"),
                Div(H3(source["name"]), Small(source["category"])),
                Span("Default" if source.get("default") else "Optional",
                     cls=f"integration-provider-badge {'connected' if source.get('default') else ''}"),
                cls="integration-status-header",
            ),
            P(source["description"]),
            A("Visit source", href=source["homepage"], target="_blank",
              rel="noopener noreferrer", cls="integration-action-btn",
              onclick="event.stopPropagation()"),
            cls="integration-card integration-provider-card news-source-config-card",
        ),
        cls="news-source-config-label",
    )


@rt("/app/news-sources")
def news_sources_home(sess, saved: str = ""):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    selected = set(get_news_source_ids(uid))
    groups: dict[str, list[dict]] = defaultdict(list)
    for source in available_sources():
        groups[source["category"]].append(source)

    sections = []
    for category, sources in groups.items():
        sections.extend([
            H3(category, cls="news-source-category"),
            Div(*[_source_card(source, selected) for source in sources],
                cls="integration-provider-grid news-source-grid"),
        ])

    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess), current_path="/app/news-sources", lang=lang),
        Div(
            Div(Div(Span("News sources", cls="chat-header-title"), cls="chat-header-left"),
                Div(copilot_toggle_btn(lang=lang), cls="chat-header-actions"), cls="chat-header"),
            Div(
                H2("Choose the intelligence in your news feed"),
                P("FastVC includes focused startup, venture-capital and private-equity sources. "
                  "General macro and political feeds are excluded. Bloomberg articles pass a "
                  "private-markets filter, and FT uses its dedicated Private Equity feed."),
                P("News-source preferences saved." if saved else "", cls="auth-success"),
                (Form(
                    *sections,
                    Div(
                        Button("Save news sources", type="submit", cls="integration-action-btn"),
                        Small("Select at least one source. Clearing every box restores the defaults."),
                        cls="news-source-save",
                    ),
                    method="post", action="/app/news-sources/save", cls="news-source-form",
                ) if uid else Div(
                    *sections,
                    P("Sign in to save a personal source selection."),
                    A("Sign in", href="/signin", cls="integration-action-btn"),
                    cls="integration-card",
                )),
                cls="integrations-wrap news-sources-wrap",
            ),
            cls="center-pane pipeline-center",
        ),
        copilot_pane(page_name="News", page_context={"selected_sources": sorted(selected)}, lang=lang),
        Script(src=_versioned("chat.js")), Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app pipeline-app",
    )
    return Html(_head(), body, lang=lang)


@rt("/app/news-sources/save", methods=["POST"])
async def save_news_sources(request: Request):
    uid, _ = _ensure_user(request.session)
    if not uid:
        return RedirectResponse("/signin", status_code=303)
    form = await request.form()
    save_news_source_ids(uid, list(form.getlist("source_id")))
    return RedirectResponse("/app/news-sources?saved=1", status_code=303)
