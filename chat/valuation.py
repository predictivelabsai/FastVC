"""Venture round, dilution and fund-outcome model."""

from __future__ import annotations

import json

from fasthtml.common import (
    Body, Button, Div, Form, H2, H3, Head, Html, Input, Label, Link, Meta,
    NotStr, Option, P, Script, Select, Span, Table, Tbody, Td, Th, Thead, Title, Tr,
)

from app import rt
from chat.components import copilot_pane, copilot_toggle_btn, left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from chat.routes import _ensure_user, _list_sessions
from db import execute, fetch_all
from landing.components import TAILWIND_CONFIG, _favicon_links
from utils.i18n import get_lang
from utils.session import get_currency, currency_symbol


def _head():
    return Head(
        Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title("Round & Ownership · FastVC"), *_favicon_links(), *common_scripts(),
        Script(src="https://cdn.tailwindcss.com"), Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _field(label, name, value, step="0.1", suffix=""):
    return Label(
        Span(label, cls="stat-label"),
        Div(Input(type="number", name=name, value=str(value), min="0", step=step,
                  required=True, cls="pd-token-input"),
            Span(suffix, cls="input-suffix") if suffix else "", cls="round-input"),
        cls="round-field",
    )


@rt("/app/valuation")
def valuation_home(sess):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    companies = fetch_all(
        """SELECT id,name,startup_stage,pre_money_valuation,last_round_amount,target_check_size
           FROM fastvc.companies ORDER BY momentum_score DESC NULLS LAST,name LIMIT 200"""
    )
    form = Form(
        Div(
            Label(Span("Startup", cls="stat-label"),
                  Select(Option("Unlinked scenario", value="0"),
                         *[Option(f"{c['name']} · {(c['startup_stage'] or '').replace('_',' ').title()}",
                                  value=str(c["id"])) for c in companies],
                         name="company_id", cls="search-select"), cls="round-field"),
            Label(Span("Round", cls="stat-label"),
                  Select(*[Option(x.replace("_", " ").title(), value=x)
                           for x in ["pre_seed", "seed", "series_a", "series_b", "series_c", "growth"]],
                         name="round_type", cls="search-select"), cls="round-field"),
            _field("Pre-money valuation", "pre_money", 20, suffix="M"),
            _field("Total raise", "raise_amount", 5, suffix="M"),
            _field("Our check", "our_check", 3, suffix="M"),
            _field("Current option pool", "pool_pre", 8, suffix="%"),
            _field("Target post-round pool", "pool_post", 12, suffix="%"),
            _field("Future dilution", "future_dilution", 35, suffix="%"),
            _field("Exit value", "exit_value", 500, suffix="M"),
            _field("Years to exit", "years", 7, step="1"),
            cls="round-model-grid",
        ),
        Button("Model round & outcome", type="submit", cls="search-submit"),
        hx_post="/app/valuation/calculate", hx_target="#round-results",
        cls="integration-card",
    )
    content = Div(
        H2("Round, dilution and ownership"),
        P("Model primary financing, option-pool expansion, future dilution and a simple fund outcome. "
          "All assumptions remain visible; generated terms require legal and tax review."),
        form,
        Div(P("Enter assumptions to calculate the ownership bridge.", cls="text-muted"),
            id="round-results", cls="integration-card"),
        cls="discovery-wrap",
    )
    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess), current_path="/app/valuation", lang=lang),
        Div(
            Div(Div(Span("Round & Ownership", cls="chat-header-title"), cls="chat-header-left"),
                Div(copilot_toggle_btn(lang=lang), cls="chat-header-actions"), cls="chat-header"),
            content, cls="center-pane pipeline-center",
        ),
        copilot_pane(page_name="Round & Ownership",
                     page_context={"companies": len(companies), "purpose": "venture round model"},
                     lang=lang),
        Script(src=_versioned("chat.js")), Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app pipeline-app",
    )
    return Html(_head(), body, lang=lang)


@rt("/app/valuation/calculate", methods=["POST"])
def calculate_round(sess, company_id: int = 0, round_type: str = "series_a",
                    pre_money: float = 20, raise_amount: float = 5, our_check: float = 3,
                    pool_pre: float = 8, pool_post: float = 12,
                    future_dilution: float = 35, exit_value: float = 500,
                    years: int = 7):
    if pre_money <= 0 or raise_amount <= 0 or our_check < 0 or our_check > raise_amount:
        return Div(P("Check the valuation, raise and check assumptions.", cls="auth-error"))
    post_money = pre_money + raise_amount
    new_investors = raise_amount / post_money * 100
    our_post = our_check / post_money * 100
    other_new = max(0, new_investors - our_post)
    pool_top_up = max(0, pool_post - pool_pre)
    existing_post = max(0, 100 - new_investors - pool_top_up)
    our_exit = our_post * max(0, 1 - future_dilution / 100)
    proceeds = exit_value * our_exit / 100
    moic = proceeds / our_check if our_check else 0
    irr = ((moic ** (1 / max(years, 1))) - 1) * 100 if moic > 0 else -100
    assumptions = {
        "round_type": round_type, "pre_money_m": pre_money, "raise_m": raise_amount,
        "our_check_m": our_check, "pool_pre_pct": pool_pre, "pool_post_pct": pool_post,
        "future_dilution_pct": future_dilution, "exit_value_m": exit_value, "years": years,
    }
    ownership = [
        {"holder": "Existing fully diluted holders", "post_round_pct": existing_post},
        {"holder": "FastVC fund", "post_round_pct": our_post},
        {"holder": "Other new investors", "post_round_pct": other_new},
        {"holder": "Incremental option pool", "post_round_pct": pool_top_up},
    ]
    if company_id:
        execute(
            """INSERT INTO fastvc.round_models
               (company_id,name,round_type,pre_money,raise_amount,new_money,
                option_pool_pre_pct,option_pool_post_pct,ownership,dilution)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb)""",
            (company_id, f"{round_type.replace('_',' ').title()} scenario", round_type,
             pre_money * 1_000_000, raise_amount * 1_000_000,
             json.dumps([{"investor": "FastVC fund", "amount_m": our_check},
                         {"investor": "Other new investors", "amount_m": raise_amount - our_check}]),
             pool_pre, pool_post, json.dumps(ownership),
             json.dumps({"existing_holder_dilution_pct": 100 - existing_post,
                         "future_dilution_pct": future_dilution})),
        )
    sym = currency_symbol(get_currency(sess))
    return Div(
        H3(f"{round_type.replace('_', ' ').title()} ownership bridge"),
        Div(
            Div(Span("Post-money", cls="stat-label"), Span(f"{sym}{post_money:.1f}M", cls="stat-value")),
            Div(Span("Our post-round ownership", cls="stat-label"), Span(f"{our_post:.1f}%", cls="stat-value")),
            Div(Span("Our exit ownership", cls="stat-label"), Span(f"{our_exit:.1f}%", cls="stat-value")),
            Div(Span("Illustrative proceeds", cls="stat-label"), Span(f"{sym}{proceeds:.1f}M", cls="stat-value")),
            Div(Span("Gross MOIC", cls="stat-label"), Span(f"{moic:.1f}x", cls="stat-value")),
            Div(Span("Gross IRR", cls="stat-label"), Span(f"{irr:.1f}%", cls="stat-value")),
            cls="integration-stats",
        ),
        Table(
            Thead(Tr(Th("Holder"), Th("Post-round ownership"))),
            Tbody(*[Tr(Td(row["holder"]), Td(f"{row['post_round_pct']:.1f}%"))
                    for row in ownership]),
            cls="search-table",
        ),
        P("Illustrative only: future rounds, preferences, participation, reserves, taxes and fees "
          "can materially change proceeds.", cls="text-muted"),
    )
