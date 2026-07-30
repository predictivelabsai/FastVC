"""Provider-neutral BYOK integrations page."""

from __future__ import annotations

from fasthtml.common import (
    A, Body, Button, Div, Form, H2, H3, Head, Html, Input, Link, Meta, P,
    NotStr, Script, Small, Span, Title,
)
from starlette.responses import RedirectResponse

from app import rt
from chat.components import copilot_pane, copilot_toggle_btn, left_pane, signin_overlay
from chat.layout import _versioned, common_scripts
from chat.routes import _ensure_user, _list_sessions
from landing.components import TAILWIND_CONFIG, _favicon_links
from tools.integrations import (
    PROVIDERS, delete_connection, list_connections, save_connection, test_stub,
)
from utils.i18n import get_lang
from utils.session import get_currency


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
                Div(
                    H3("Adapter contract"),
                    P("Each provider implements the same boundary: authenticate, test, pull/push "
                      "companies and people, map pipeline stages, and record sync provenance. "
                      "The current adapters are safe stubs; live sync can be enabled provider by provider."),
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
