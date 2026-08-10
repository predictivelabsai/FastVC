"""Provider-neutral BYOK integrations page."""

from __future__ import annotations

from fasthtml.common import (
    A, Body, Button, Div, Form, H2, H3, Head, Html, Input, Link, Meta, P,
    NotStr, Script, Small, Span, Title,
)
from starlette.responses import RedirectResponse
from urllib.parse import quote_plus

from app import rt
from chat.components import copilot_pane, copilot_toggle_btn, left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from chat.routes import _ensure_user, _list_sessions
from landing.components import TAILWIND_CONFIG, _favicon_links
from tools.integrations import (
    PROVIDERS, delete_connection, list_connections, list_credentials, load_credential,
    save_connection, test_stub,
)
from db import fetch_all
from ingestion.pilots import run_quality_pilot
from ingestion.service import source_status
from utils.i18n import get_lang
from utils.session import get_currency
from utils.config import settings


DATA_SOURCES = {
    "registry_cache": {
        "name": "Existing Registry Data", "kind": "LT · EE · LV",
        "description": "Quality-filtered registry records and annual statutory financial periods migrated from the shared PEHero dataset.",
        "capabilities": ["registration IDs", "annual filings", "employees", "provenance"],
        "free": True,
    },
    "pappers": {
        "name": "Pappers", "kind": "France",
        "description": "French company identity, officers, filings and financial enrichment through the official Pappers API.",
        "capabilities": ["SIREN/SIRET", "officers", "financials", "daily updates"],
        "free": False,
    },
    "scoris": {
        "name": "Scoris", "kind": "UK · FI · EE · LT · LV · SE",
        "description": "European registry search, bulk filtering and selective full-company enrichment through the Scoris API.",
        "capabilities": ["bulk filters", "registry IDs", "financials", "contacts"],
        "free": False,
    },
    "companies_house": {
        "name": "Companies House", "kind": "United Kingdom",
        "description": "Official UK public company API for profiles, officers and persons with significant control.",
        "capabilities": ["company profiles", "officers", "PSC", "SIC codes"],
        "free": False,
    },
    "sirene": {
        "name": "INSEE SIRENE", "kind": "France open data",
        "description": "Free, daily-updated French company identity data from INSEE for discovery and Pappers targeting.",
        "capabilities": ["SIREN/SIRET", "NAF", "addresses", "bulk discovery"],
        "free": True,
    },
    "prh": {
        "name": "PRH Open Data", "kind": "Finland open data",
        "description": "Free Finnish Business Information System company identities and daily full-company feed.",
        "capabilities": ["Business ID", "industry", "address", "website"],
        "free": True,
    },
    "public_directories": {
        "name": "Public Directories", "kind": "Playwright",
        "description": "Rate-limited, terms-reviewed adapters for public accelerator and ecosystem portfolio pages without structured feeds.",
        "capabilities": ["portfolio pages", "source URLs", "checkpoints", "no gate bypass"],
        "free": True,
    },
}


def _is_ingestion_admin(email: str | None) -> bool:
    allowed = {item.strip().lower() for item in settings().fastvc_admin_emails.split(",") if item.strip()}
    return bool(email and email.lower() in allowed)


def _source_configured(key: str, credential_providers: set[str] | None = None) -> bool:
    cfg = settings()
    environment_ready = {
        "pappers": bool(cfg.pappers_api_key),
        "scoris": bool(cfg.scoris_api_key),
        "companies_house": bool(cfg.companies_house_api_key),
        "sirene": bool(cfg.sirene_api_key),
    }.get(key, True)
    vault_provider = {"sirene": "insee"}.get(key, key)
    return environment_ready or vault_provider in (credential_providers or set())


def _data_source_card(key: str, spec: dict, stats: dict | None, last_run: dict | None,
                      is_admin: bool, message: str = "",
                      credential_providers: set[str] | None = None):
    configured = _source_configured(key, credential_providers)
    badge_text = "Ready" if configured else "API key required"
    controls = []
    if stats:
        controls.extend([
            P(f"{int(stats.get('companies') or 0):,} linked companies · {int(stats.get('snapshots') or 0):,} source snapshots", cls="mono"),
            P(f"Last source refresh: {stats.get('last_sync') or '—'}", cls="text-muted"),
        ])
    if last_run:
        controls.append(P(
            f"Last run: {last_run['status']} · {last_run['processed']} records · {last_run['credits_used']} credits",
            cls="text-muted",
        ))
    if is_admin and key in {"pappers", "scoris", "companies_house", "sirene", "prh"}:
        controls.append(Form(
            Input(type="hidden", name="limit", value="5"),
            Button("Run 5-record quality pilot", type="submit", cls="integration-action-btn",
                   disabled=not configured),
            method="post", action=f"/app/integrations/data/{key}/pilot",
        ))
    return Div(
        Div(Div(H3(spec["name"]), Small(spec["kind"])),
            Span(badge_text, cls=f"integration-provider-badge {'connected' if configured else ''}"),
            cls="integration-status-header"),
        P(spec["description"]),
        Div(*[Span(cap, cls="sector-chip") for cap in spec["capabilities"]],
            cls="integration-capabilities"),
        (P(message, cls="auth-success") if message else ""),
        Div(*controls, cls="integration-connection"),
        cls="integration-card integration-provider-card", id=key,
    )


def _head():
    return Head(
        Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Title("Integrations · FastVC"), *_favicon_links(), *common_scripts(),
        Script(src="https://cdn.tailwindcss.com"), Script(NotStr(TAILWIND_CONFIG)),
        Link(rel="stylesheet", href="/static/site.css"),
        Link(rel="stylesheet", href=_versioned("app.css")),
        Link(rel="stylesheet", href="/static/pipeline.css"),
    )


def _provider_card(key: str, spec: dict, connection: dict | None, message: str = ""):
    connected = bool(connection and connection.get("connected"))
    badge = Span(
        "Configured" if connected else "Bring your own key",
        cls=f"integration-provider-badge {'connected' if connected else ''}",
    )
    capabilities = Div(
        *[Span(cap, cls="sector-chip") for cap in spec["capabilities"]],
        cls="integration-capabilities",
    )
    if connected:
        controls = Div(
            P(f"Key {connection['masked_key']}", cls="mono"),
            P(f"Scope: {connection.get('domain') or 'default workspace'}", cls="text-muted"),
            Form(Button("Remove connection", type="submit", cls="integration-action-btn danger"),
                 method="post", action=f"/app/integrations/{key}/disconnect"),
            cls="integration-connection",
        )
    else:
        controls = Form(
            Input(type="password", name="api_key", placeholder=f"{spec['name']} API key",
                  required=True, autocomplete="new-password", cls="pd-token-input"),
            Input(type="text", name="domain", placeholder=spec["domain_label"],
                  cls="pd-token-input"),
            Button(f"Configure {spec['name']}", type="submit", cls="integration-action-btn"),
            method="post", action=f"/app/integrations/{key}/connect",
            cls="integration-provider-form",
        )
    return Div(
        Div(Div(H3(spec["name"]), Small(spec["kind"])), badge,
            cls="integration-status-header"),
        P(spec["description"]), capabilities,
        (P(message, cls="auth-success") if message else ""),
        controls, cls="integration-card integration-provider-card", id=key,
    )


def _credential_card(credential: dict):
    details = []
    if credential.get("masked_identity"):
        details.append(P(f"Login {credential['masked_identity']}", cls="mono"))
    if credential.get("has_password"):
        details.append(P("Password ••••••••", cls="mono"))
    if credential.get("masked_api_key"):
        details.append(P(f"API key {credential['masked_api_key']}", cls="mono"))
    verified = credential.get("last_verified")
    details.append(P(f"Last verified: {verified or '—'}", cls="text-muted"))
    return Div(
        Div(
            Div(H3(credential["label"]), Small(credential["provider"])),
            Span("Encrypted", cls="integration-provider-badge connected"),
            cls="integration-status-header",
        ),
        *details,
        (A("Open provider portal", href=credential["login_url"], target="_blank",
           rel="noopener noreferrer", cls="integration-action-btn")
         if credential.get("login_url") else ""),
        cls="integration-card integration-provider-card",
    )


@rt("/app/integrations")
def integrations_home(sess, saved: str = "", error: str = ""):
    uid, email = _ensure_user(sess)
    sessions = _list_sessions(uid) if uid else []
    lang = get_lang(sess)
    connections = list_connections(uid) if uid else {}
    cards = [
        _provider_card(key, spec, connections.get(key),
                       f"{spec['name']} configuration saved." if saved == key else "")
        for key, spec in PROVIDERS.items()
    ]
    stats = {row["provider"]: row for row in source_status()}
    registry_stats = {
        "companies": sum(int(stats.get(key, {}).get("companies") or 0)
                         for key in ("registry_lt", "registry_ee", "registry_lv")),
        "snapshots": sum(int(stats.get(key, {}).get("snapshots") or 0)
                         for key in ("registry_lt", "registry_ee", "registry_lv")),
        "last_sync": max((stats.get(key, {}).get("last_sync")
                          for key in ("registry_lt", "registry_ee", "registry_lv")
                          if stats.get(key, {}).get("last_sync")), default=None),
    }
    stats["registry_cache"] = registry_stats
    stats["public_directories"] = {
        "companies": 0,
        "snapshots": sum(int(stats.get(key, {}).get("snapshots") or 0)
                         for key in ("seedcamp", "startup_wise_guys")),
        "last_sync": max((stats.get(key, {}).get("last_sync")
                          for key in ("seedcamp", "startup_wise_guys")
                          if stats.get(key, {}).get("last_sync")), default=None),
    }
    runs = fetch_all(
        """SELECT DISTINCT ON (provider) provider,status,processed,credits_used,finished_at
           FROM fastvc.ingestion_runs ORDER BY provider,started_at DESC"""
    )
    latest_runs = {row["provider"]: row for row in runs}
    is_admin = _is_ingestion_admin(email)
    credentials = list_credentials(uid) if uid and is_admin else []
    credential_providers = {item["provider"] for item in credentials}
    data_cards = [
        _data_source_card(key, spec, stats.get(key), latest_runs.get(key), is_admin,
                          f"{spec['name']} pilot completed." if saved == key else "",
                          credential_providers)
        for key, spec in DATA_SOURCES.items()
    ]
    body = Body(
        signin_overlay(lang=lang),
        Div(id="left-overlay", cls="left-overlay", onclick="toggleLeftPane()"),
        left_pane(user_email=email, sessions=sessions, current_sid="",
                  current_currency=get_currency(sess), current_path="/app/integrations", lang=lang),
        Div(
            Div(Div(Span("Integrations", cls="chat-header-title"), cls="chat-header-left"),
                Div(copilot_toggle_btn(lang=lang), cls="chat-header-actions"), cls="chat-header"),
            Div(
                H2("Bring your own systems"),
                P("FastVC remains useful without a CRM. Configure only the providers your team uses; "
                  "keys are encrypted at rest and never rendered back to the browser."),
                (P(error, cls="auth-error") if error else ""),
                Div(*cards, cls="integration-provider-grid"),
                H2("Company data sources"),
                P("Registry and API ingestion is provenance-preserving, resumable and quota-capped. "
                  "Only authorised administrators can run quality pilots."),
                Div(*data_cards, cls="integration-provider-grid"),
                (Div(
                    H2("Credentials"),
                    P("Administrator-owned portal logins and API keys. Secret values are encrypted "
                      "at rest and only masked metadata is rendered here."),
                    (Div(*[_credential_card(item) for item in credentials],
                         cls="integration-provider-grid")
                     if credentials else P("No portal credentials stored yet.", cls="text-muted")),
                    id="credentials",
                ) if is_admin else ""),
                Div(
                    H3("Adapter contract"),
                    P("CRM adapters share one boundary for authentication, connection testing, "
                      "pipeline mapping and sync provenance. Company-data adapters are live, "
                      "read-only importers with bounded pilots and source-level audit records."),
                    cls="integration-card",
                ),
                cls="integrations-wrap",
            ),
            cls="center-pane pipeline-center",
        ),
        copilot_pane(page_name="Integrations",
                     page_context={"providers": list(PROVIDERS), "configured": list(connections)},
                     lang=lang),
        Script(src=_versioned("chat.js")), Script(src=_versioned("copilot.js")),
        cls="bg-bg text-ink font-sans antialiased app pipeline-app",
    )
    return Html(_head(), body, lang=lang)


@rt("/app/integrations/{provider}/connect", methods=["POST"])
def connect_provider(sess, provider: str, api_key: str, domain: str = ""):
    uid, _ = _ensure_user(sess)
    if not uid:
        return RedirectResponse("/app/integrations?error=Sign+in+first", status_code=303)
    result = test_stub(provider, api_key, domain)
    if not result["ok"]:
        return RedirectResponse(f"/app/integrations?error={result['message'].replace(' ', '+')}",
                                status_code=303)
    save_connection(uid, provider, api_key, domain, {"adapter": "stub", "capabilities": PROVIDERS[provider]["capabilities"]})
    return RedirectResponse(f"/app/integrations?saved={provider}#{provider}", status_code=303)


@rt("/app/integrations/{provider}/disconnect", methods=["POST"])
def disconnect_provider(sess, provider: str):
    uid, _ = _ensure_user(sess)
    if uid:
        delete_connection(uid, provider)
    return RedirectResponse("/app/integrations", status_code=303)


@rt("/app/integrations/data/{provider}/pilot", methods=["POST"])
def run_data_pilot(sess, provider: str, limit: int = 5):
    uid, email = _ensure_user(sess)
    if not _is_ingestion_admin(email):
        return RedirectResponse("/app/integrations?error=Administrator+access+required", status_code=303)
    if provider not in {"pappers", "scoris", "companies_house", "sirene", "prh"}:
        return RedirectResponse("/app/integrations?error=Unsupported+data+provider", status_code=303)
    try:
        credential_provider = {"sirene": "insee"}.get(provider, provider)
        credential = load_credential(uid, credential_provider, reveal=True) if uid else None
        api_key = (credential or {}).get("api_key", "")
        run_quality_pilot(provider, limit=min(max(int(limit), 1), 10), api_key=api_key)
    except Exception as exc:
        return RedirectResponse(f"/app/integrations?error={quote_plus(str(exc)[:240])}#{provider}", status_code=303)
    return RedirectResponse(f"/app/integrations?saved={provider}#{provider}", status_code=303)
