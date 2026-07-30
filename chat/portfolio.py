"""Venture portfolio monitoring: ARR, growth, burn, runway and retention."""

from __future__ import annotations

from fasthtml.common import (
    A, Body, Div, H2, H3, Head, Html, Link, Meta, NotStr, P, Script, Span,
    Table, Tbody, Td, Th, Thead, Title, Tr,
)

from app import rt
from chat.components import copilot_pane, copilot_toggle_btn, left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from chat.routes import _ensure_user, _list_sessions
from db import fetch_all, fetch_one
from landing.components import TAILWIND_CONFIG, _favicon_links
from utils.i18n import get_lang
from utils.session import currency_symbol, get_currency


PORTFOLIO_STAGES = ("invested", "follow_on", "exited")


def _head(title: str):
    return Head(
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title(f"{title} · FastVC"),
        *_favicon_links(),
        *common_scripts(),
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _money(value, symbol="$"):
    if value is None:
        return "—"
    value = float(value)
    return f"{symbol}{value / 1_000_000:.1f}M" if abs(value) >= 1_000_000 else f"{symbol}{value / 1_000:.0f}k"


def _pct(value):
    return f"{float(value):.1f}%" if value is not None else "—"


def _multiple(value):
    return f"{float(value):.2f}x" if value is not None else "—"


def _shell(sess, title: str, path: str, content, context: dict):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    return Html(
        _head(title),
        Body(
            signin_overlay(lang=lang),
            Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
            left_pane(
                user_email=email,
                sessions=sessions,
                current_sid="",
                current_currency=get_currency(sess),
                current_path=path,
                lang=lang,
            ),
            Div(
                Div(
                    Div(Span(title, cls="chat-header-title"), cls="chat-header-left"),
                    Div(copilot_toggle_btn(lang=lang), cls="chat-header-actions"),
                    cls="chat-header",
                ),
                Div(content, cls="discovery-wrap"),
                cls="center-pane pipeline-center",
            ),
            copilot_pane(page_name=title, page_context=context, lang=lang),
            Script(src=_versioned("chat.js")),
            Script(src=_versioned("copilot.js")),
            cls="bg-bg text-ink font-sans antialiased app pipeline-app",
        ),
        lang=lang,
    )


def _portfolio_rows():
    return fetch_all(
        """SELECT slug,name,sector,startup_stage,arr,growth_rate,gross_margin,
                  net_burn,runway_months,burn_multiple,net_retention,
                  target_ownership_pct,post_money_valuation,deal_stage
           FROM fastvc.companies
           WHERE deal_stage = ANY(%s)
           ORDER BY arr DESC NULLS LAST,name""",
        (list(PORTFOLIO_STAGES),),
    )


def _nav():
    return Div(
        A("Dashboard", href="/app/portfolio", cls="filter-chip"),
        A("Analytics", href="/app/portfolio/analytics", cls="filter-chip"),
        A("KPI monitor", href="/app/portfolio/kpis", cls="filter-chip"),
        cls="pipeline-filters",
    )


@rt("/app/portfolio")
def portfolio_home(sess):
    rows = _portfolio_rows()
    symbol = currency_symbol(get_currency(sess))
    total_arr = sum(float(row["arr"] or 0) for row in rows)
    avg_growth = sum(float(row["growth_rate"] or 0) for row in rows) / len(rows) if rows else 0
    avg_runway = sum(float(row["runway_months"] or 0) for row in rows) / len(rows) if rows else 0
    avg_nrr = sum(float(row["net_retention"] or 0) for row in rows) / len(rows) if rows else 0
    content = Div(
        H2("Portfolio command centre"),
        P("Monitor the operating signals that matter between board meetings."),
        _nav(),
        Div(
            Div(Span("Portfolio companies", cls="stat-label"), Span(str(len(rows)), cls="stat-value")),
            Div(Span("Total ARR", cls="stat-label"), Span(_money(total_arr, symbol), cls="stat-value")),
            Div(Span("Average growth", cls="stat-label"), Span(_pct(avg_growth), cls="stat-value")),
            Div(Span("Average runway", cls="stat-label"), Span(f"{avg_runway:.1f} mo", cls="stat-value")),
            Div(Span("Average NRR", cls="stat-label"), Span(_pct(avg_nrr), cls="stat-value")),
            cls="integration-stats",
        ),
        Div(
            H3("Company health"),
            Table(
                Thead(Tr(Th("Company"), Th("Stage"), Th("ARR"), Th("Growth"), Th("Gross margin"),
                         Th("Burn multiple"), Th("Runway"), Th("NRR"), Th("Ownership"))),
                Tbody(*[
                    Tr(
                        Td(A(row["name"], href=f"/app/pipeline/{row['slug']}", cls="company-link")),
                        Td((row["startup_stage"] or "—").replace("_", " ").title()),
                        Td(_money(row["arr"], symbol)),
                        Td(_pct(row["growth_rate"])),
                        Td(_pct(row["gross_margin"])),
                        Td(_multiple(row["burn_multiple"])),
                        Td(f"{float(row['runway_months']):.1f} mo" if row["runway_months"] is not None else "—"),
                        Td(_pct(row["net_retention"])),
                        Td(_pct(row["target_ownership_pct"])),
                    ) for row in rows
                ]),
                cls="search-table",
            ),
            cls="integration-card",
        ),
    )
    return _shell(
        sess, "Portfolio", "/app/portfolio", content,
        {"companies": len(rows), "total_arr": total_arr, "avg_runway_months": avg_runway},
    )


@rt("/app/portfolio/analytics")
def portfolio_analytics(sess):
    symbol = currency_symbol(get_currency(sess))
    rows = fetch_all(
        """SELECT sector,count(*) AS companies,sum(arr) AS total_arr,
                  avg(growth_rate) AS avg_growth,avg(gross_margin) AS avg_gross_margin,
                  avg(burn_multiple) AS avg_burn_multiple,
                  avg(runway_months) AS avg_runway,avg(net_retention) AS avg_nrr
           FROM fastvc.companies WHERE deal_stage = ANY(%s)
           GROUP BY sector ORDER BY total_arr DESC NULLS LAST""",
        (list(PORTFOLIO_STAGES),),
    )
    content = Div(
        H2("Portfolio analytics"),
        P("Compare sector concentration, growth quality and capital efficiency."),
        _nav(),
        Div(
            Table(
                Thead(Tr(Th("Sector"), Th("Companies"), Th("ARR"), Th("Growth"),
                         Th("Gross margin"), Th("Burn multiple"), Th("Runway"), Th("NRR"))),
                Tbody(*[
                    Tr(
                        Td(row["sector"].replace("_", " ").title()),
                        Td(str(row["companies"])),
                        Td(_money(row["total_arr"], symbol)),
                        Td(_pct(row["avg_growth"])),
                        Td(_pct(row["avg_gross_margin"])),
                        Td(_multiple(row["avg_burn_multiple"])),
                        Td(f"{float(row['avg_runway']):.1f} mo" if row["avg_runway"] is not None else "—"),
                        Td(_pct(row["avg_nrr"])),
                    ) for row in rows
                ]),
                cls="search-table",
            ),
            cls="integration-card",
        ),
    )
    return _shell(sess, "Portfolio Analytics", "/app/portfolio/analytics", content,
                  {"sector_cohorts": len(rows)})


@rt("/app/portfolio/kpis")
def portfolio_kpis(sess):
    rows = fetch_all(
        """SELECT c.slug,c.name,k.month,k.kpi,k.value,k.budget,
                  CASE WHEN k.budget IS NULL OR k.budget=0 THEN NULL
                       ELSE (k.value-k.budget)/abs(k.budget)*100 END AS variance_pct
           FROM fastvc.portfolio_kpis k
           JOIN fastvc.companies c ON c.id=k.company_id
           WHERE c.deal_stage = ANY(%s)
           ORDER BY k.month DESC,c.name,k.kpi LIMIT 300""",
        (list(PORTFOLIO_STAGES),),
    )
    if not rows:
        company_rows = _portfolio_rows()
        rows = [
            {
                "slug": row["slug"], "name": row["name"], "month": "Current",
                "kpi": "runway_months", "value": row["runway_months"],
                "budget": None, "variance_pct": None,
            }
            for row in company_rows
        ]
    content = Div(
        H2("KPI monitor"),
        P("Actual versus plan with company and period context. Metric definitions remain company-specific."),
        _nav(),
        Div(
            Table(
                Thead(Tr(Th("Company"), Th("Period"), Th("KPI"), Th("Actual"), Th("Plan"), Th("Variance"))),
                Tbody(*[
                    Tr(
                        Td(A(row["name"], href=f"/app/pipeline/{row['slug']}", cls="company-link")),
                        Td(str(row["month"])),
                        Td(row["kpi"].replace("_", " ").upper()),
                        Td(f"{float(row['value']):,.1f}" if row["value"] is not None else "—"),
                        Td(f"{float(row['budget']):,.1f}" if row["budget"] is not None else "—"),
                        Td(_pct(row["variance_pct"])),
                    ) for row in rows
                ]),
                cls="search-table",
            ),
            cls="integration-card",
        ),
    )
    return _shell(sess, "Portfolio KPIs", "/app/portfolio/kpis", content,
                  {"kpi_rows": len(rows)})
