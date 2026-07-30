"""Harmonic-inspired startup discovery, saved theses, signals and founder network."""

from __future__ import annotations

import json

from fasthtml.common import (
    A, Body, Button, Div, Form, H2, H3, Head, Html, Input, Link, Meta, Option,
    NotStr, P, Script, Select, Span, Table, Tbody, Td, Th, Thead, Title, Tr,
)
from starlette.responses import RedirectResponse

from app import rt
from chat.components import copilot_pane, copilot_toggle_btn, left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from chat.routes import _ensure_user, _list_sessions
from db import execute, fetch_all
from landing.components import TAILWIND_CONFIG, _favicon_links
from utils.i18n import get_lang
from utils.session import get_currency, currency_symbol

STARTUP_STAGES = ["stealth", "pre_seed", "seed", "series_a", "series_b", "series_c", "growth"]


def _head(title: str):
    return Head(
        Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(f"{title} · FastVC"), *_favicon_links(), *common_scripts(),
        Script(src="https://cdn.tailwindcss.com"), Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _money(value, symbol="$"):
    if value is None:
        return "—"
    value = float(value)
    return f"{symbol}{value / 1_000_000:.1f}M" if abs(value) >= 1_000_000 else f"{symbol}{value / 1_000:.0f}k"


def _shell(sess, title: str, current_path: str, content, context: dict):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    return Html(
        _head(title),
        Body(
            signin_overlay(lang=lang),
            Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
            left_pane(user_email=email, sessions=sessions, current_sid="",
                      current_currency=get_currency(sess), current_path=current_path, lang=lang),
            Div(
                Div(Div(Span(title, cls="chat-header-title"), cls="chat-header-left"),
                    Div(copilot_toggle_btn(lang=lang), cls="chat-header-actions"), cls="chat-header"),
                Div(content, cls="discovery-wrap"), cls="center-pane pipeline-center",
            ),
            copilot_pane(page_name=title, page_context=context, lang=lang),
            Script(src=_versioned("chat.js")), Script(src=_versioned("copilot.js")),
            cls="bg-bg text-ink font-sans antialiased app pipeline-app",
        ),
        lang=lang,
    )


@rt("/app/discovery")
def discovery(sess, q: str = "", stage: str = "", min_momentum: int = 0):
    uid, _ = _ensure_user(sess)
    where = ["TRUE"]
    params: list = []
    if q:
        where.append("(name ILIKE %s OR description ILIKE %s OR sub_sector ILIKE %s OR sector ILIKE %s)")
        params.extend([f"%{q}%"] * 4)
    if stage:
        where.append("startup_stage=%s")
        params.append(stage)
    if min_momentum:
        where.append("momentum_score >= %s")
        params.append(min_momentum)
    rows = fetch_all(
        """SELECT slug,name,sector,sub_sector,startup_stage,arr,growth_rate,
                  runway_months,burn_multiple,total_funding,momentum_score,thesis_score,
                  fundraising_status
           FROM fastvc.companies WHERE """ + " AND ".join(where) +
        " ORDER BY thesis_score DESC NULLS LAST, momentum_score DESC NULLS LAST LIMIT 200",
        tuple(params),
    )
    searches = fetch_all(
        "SELECT id,name,thesis,filters,alert_frequency FROM fastvc.saved_searches "
        "WHERE user_id=%s AND is_active=TRUE ORDER BY created_at DESC", (uid,),
    ) if uid else []
    symbol = currency_symbol(get_currency(sess))
    form = Form(
        Input(type="search", name="q", value=q,
              placeholder="Describe a thesis, market or company…", cls="search-input"),
        Select(Option("All company stages", value=""),
               *[Option(s.replace("_", " ").title(), value=s, selected=s == stage) for s in STARTUP_STAGES],
               name="stage", cls="search-select"),
        Select(*[Option(f"Momentum ≥ {n}", value=str(n), selected=n == min_momentum)
                 for n in [0, 50, 65, 80]], name="min_momentum", cls="search-select"),
        Button("Search", type="submit", cls="search-submit"),
        method="get", action="/app/discovery", cls="discovery-search",
    )
    save_form = Form(
        Input(type="text", name="name", placeholder="Saved-search name", required=True,
              cls="pd-token-input"),
        Input(type="hidden", name="thesis", value=q or "All venture-backable startups"),
        Input(type="hidden", name="stage", value=stage),
        Input(type="hidden", name="min_momentum", value=str(min_momentum)),
        Select(*[Option(x.title(), value=x) for x in ["realtime", "daily", "weekly", "off"]],
               name="frequency", cls="search-select"),
        Button("Save thesis + alerts", type="submit", cls="integration-action-btn"),
        method="post", action="/app/discovery/save", cls="saved-search-form",
    )
    saved = Div(
        H3("Saved theses"),
        *[
            Div(
                Div(Span(s["name"], cls="company-link"), Span(s["alert_frequency"], cls="sector-chip")),
                P(s["thesis"], cls="text-muted"),
                Form(Button("Remove", type="submit", cls="btn ghost sm"),
                     method="post", action=f"/app/discovery/{s['id']}/delete"),
                cls="saved-search-card",
            ) for s in searches
        ],
        save_form,
        cls="integration-card saved-searches",
    )
    table = Table(
        Thead(Tr(Th("Startup"), Th("Stage"), Th("ARR"), Th("Growth"), Th("Runway"),
                 Th("Burn multiple"), Th("Momentum"), Th("Thesis"), Th("Status"))),
        Tbody(*[
            Tr(
                Td(A(r["name"], href=f"/app/pipeline/{r['slug']}", cls="company-link"),
                   P(r["sub_sector"] or r["sector"], cls="text-muted")),
                Td(Span((r["startup_stage"] or "—").replace("_", " ").title(), cls="sector-chip")),
                Td(_money(r["arr"], symbol), cls="mono"),
                Td(f"{float(r['growth_rate']):.0f}%" if r["growth_rate"] is not None else "—"),
                Td(f"{float(r['runway_months']):.0f} mo" if r["runway_months"] is not None else "—"),
                Td(f"{float(r['burn_multiple']):.1f}x" if r["burn_multiple"] is not None else "—"),
                Td(f"{float(r['momentum_score']):.0f}" if r["momentum_score"] is not None else "—"),
                Td(f"{float(r['thesis_score']):.0f}" if r["thesis_score"] is not None else "—"),
                Td((r["fundraising_status"] or "—").replace("_", " ").title()),
            ) for r in rows
        ]),
        cls="search-table",
    )
    content = Div(
        Div(H2("Discover startups before consensus"),
            P("Search by thesis, stage and momentum. Save the exact view and track only net-new matches."),
            form, cls="discovery-hero"),
        saved,
        Div(H3(f"{len(rows)} matches"), table, cls="integration-card"),
    )
    return _shell(sess, "Discovery", "/app/discovery", content,
                  {"query": q, "stage": stage, "min_momentum": min_momentum,
                   "matches": len(rows), "saved_searches": len(searches)})


@rt("/app/discovery/save", methods=["POST"])
def save_search(sess, name: str, thesis: str, stage: str = "",
                min_momentum: int = 0, frequency: str = "weekly"):
    uid, _ = _ensure_user(sess)
    if uid:
        execute(
            """INSERT INTO fastvc.saved_searches
               (user_id,name,thesis,filters,alert_frequency)
               VALUES (%s,%s,%s,%s::jsonb,%s)""",
            (uid, name, thesis, json.dumps({"stage": stage, "min_momentum": min_momentum}), frequency),
        )
    return RedirectResponse("/app/discovery", status_code=303)


@rt("/app/discovery/{search_id}/delete", methods=["POST"])
def delete_search(sess, search_id: int):
    uid, _ = _ensure_user(sess)
    if uid:
        execute("DELETE FROM fastvc.saved_searches WHERE id=%s AND user_id=%s", (search_id, uid))
    return RedirectResponse("/app/discovery", status_code=303)


@rt("/app/signals")
def signals(sess, signal_type: str = ""):
    where = "WHERE s.signal_type=%s" if signal_type else ""
    params = (signal_type,) if signal_type else ()
    rows = fetch_all(
        f"""SELECT s.signal_type,s.title,s.detail,s.signal_date,s.strength,s.source,
                   c.name,c.slug,c.startup_stage,c.momentum_score
            FROM fastvc.startup_signals s JOIN fastvc.companies c ON c.id=s.company_id
            {where} ORDER BY s.signal_date DESC,s.strength DESC LIMIT 300""", params)
    filters = ["formation", "founder_move", "key_hire", "headcount", "funding", "launch", "traction"]
    content = Div(
        H2("Startup signals"),
        P("Signals are research leads, not conclusions. Open a startup to verify the evidence."),
        Div(A("All", href="/app/signals", cls="filter-chip"),
            *[A(x.replace("_", " ").title(), href=f"/app/signals?signal_type={x}",
                cls=f"filter-chip {'active' if signal_type == x else ''}") for x in filters],
            cls="pipeline-filters"),
        Div(*[
            Div(
                Div(Span(r["signal_type"].replace("_", " ").title(), cls="sector-chip"),
                    Span(str(r["signal_date"]), cls="text-muted")),
                H3(A(r["name"], href=f"/app/pipeline/{r['slug']}")),
                P(r["title"]), P(r["detail"], cls="text-muted"),
                Div(Span(f"Signal {float(r['strength']):.0f}"), " · ",
                    Span(f"Momentum {float(r['momentum_score']):.0f}"), cls="mono"),
                cls="signal-card",
            ) for r in rows
        ], cls="signal-grid"),
    )
    return _shell(sess, "Signals", "/app/signals", content,
                  {"signal_type": signal_type, "signals": len(rows)})


@rt("/app/founders")
def founders(sess, q: str = ""):
    where = "WHERE f.name ILIKE %s OR c.name ILIKE %s OR %s = ''"
    rows = fetch_all(
        f"""SELECT f.name,f.slug,f.title,f.location,f.repeat_founder,f.technical,
                   f.founder_score,c.name company_name,c.slug company_slug,c.startup_stage,
                   max(tc.strength) connection_strength,
                   string_agg(DISTINCT tc.connector_name, ', ') connectors
            FROM fastvc.founders f
            JOIN fastvc.founder_company_links fc ON fc.founder_id=f.id
            JOIN fastvc.companies c ON c.id=fc.company_id
            LEFT JOIN fastvc.team_connections tc ON tc.founder_id=f.id
            {where}
            GROUP BY f.id,c.id ORDER BY connection_strength DESC NULLS LAST,f.founder_score DESC
            LIMIT 250""",
        (f"%{q}%", f"%{q}%", q),
    )
    content = Div(
        H2("Founders & warm paths"),
        Form(Input(type="search", name="q", value=q,
                   placeholder="Founder or startup…", cls="search-input"),
             Button("Search", type="submit", cls="search-submit"),
             method="get", action="/app/founders", cls="discovery-search"),
        Table(
            Thead(Tr(Th("Founder"), Th("Startup"), Th("Profile"), Th("Score"), Th("Warm path"))),
            Tbody(*[
                Tr(
                    Td(r["name"], P(r["location"] or "—", cls="text-muted")),
                    Td(A(r["company_name"], href=f"/app/pipeline/{r['company_slug']}"),
                       P((r["startup_stage"] or "").replace("_", " ").title(), cls="text-muted")),
                    Td("Repeat founder · " if r["repeat_founder"] else "",
                       "Technical" if r["technical"] else "Commercial"),
                    Td(f"{float(r['founder_score']):.0f}", cls="mono"),
                    Td((f"{r['connectors']} · strength {r['connection_strength']}"
                        if r["connectors"] else "No stored path")),
                ) for r in rows
            ]), cls="search-table",
        ),
    )
    return _shell(sess, "Founders", "/app/founders", content,
                  {"query": q, "founders": len(rows)})


@rt("/app/market-map")
def market_map(sess):
    rows = fetch_all(
        """SELECT sector,startup_stage,count(*) n,round(avg(momentum_score),1) momentum,
                  round(avg(thesis_score),1) thesis
           FROM fastvc.companies GROUP BY sector,startup_stage
           ORDER BY sector,startup_stage"""
    )
    by_sector: dict[str, dict] = {}
    for row in rows:
        by_sector.setdefault(row["sector"], {})[row["startup_stage"]] = row
    content = Div(
        H2("Market map"),
        P("Stage distribution and average momentum across the current startup universe."),
        Table(
            Thead(Tr(Th("Sector"), *[Th(s.replace("_", " ").title()) for s in STARTUP_STAGES])),
            Tbody(*[
                Tr(
                    Th(sector.replace("_", " ").title()),
                    *[
                        Td(
                            (f"{by_sector[sector][stage]['n']} companies"
                             if stage in by_sector[sector] else "—"),
                            P((f"momentum {by_sector[sector][stage]['momentum']}"
                               if stage in by_sector[sector] else ""), cls="text-muted"),
                            cls="market-map-cell",
                        ) for stage in STARTUP_STAGES
                    ],
                ) for sector in sorted(by_sector)
            ]), cls="search-table market-map-table",
        ),
    )
    return _shell(sess, "Market Map", "/app/market-map", content,
                  {"sectors": len(by_sector), "cohorts": len(rows)})
