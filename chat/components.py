"""Chat-UI building blocks."""

from __future__ import annotations

from fasthtml.common import (
    Div, Span, Button, A, P, H1, H2, H3, H4, Ul, Li, NotStr,
    Form, Textarea, Input, Hr, Article, Details, Summary,
)

from agents.registry import AGENTS, AGENTS_BY_CATEGORY, CATEGORIES, AGENTS_BY_SLUG
from utils.i18n import t, agent_t, category_t, js_translations, LANGUAGES
from utils.version import __version__, __version_date__
from utils.config import settings

# Mic SVG for the voice button (inline so no extra asset request).
_VOICE_ICON = (
    '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>'
    '<path d="M19 10v2a7 7 0 0 1-14 0v-2"/>'
    '<line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>'
)


def message_bubble(role: str, content: str, agent_slug: str | None = None):
    """Render a single persisted message."""
    header = None
    if role == "assistant" and agent_slug:
        agent = AGENTS_BY_SLUG.get(agent_slug)
        label = agent.name if agent else agent_slug
        header = Div(
            Span(agent.icon if agent else "◆", cls="msg-agent-icon"),
            Span(label, cls="msg-agent-label"),
            cls="msg-agent",
        )
    return Div(
        header,
        Div(NotStr(_render_content(content)), cls="msg-bubble"),
        cls=f"msg msg-{role}",
    )


_TABLE_PREVIEW_ROWS = 5


def _render_content(content: str) -> str:
    """Server-side markdown → HTML for persisted messages."""
    import html as _html
    import re

    safe = _html.escape(content)
    # code fences → <pre>
    safe = re.sub(r"```(.*?)```", lambda m: f"<pre>{m.group(1)}</pre>", safe, flags=re.DOTALL)
    # **bold**
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)

    lines = safe.split("\n")
    out = []
    in_list = False
    in_table = False
    is_header = True
    table_row_count = 0
    table_hidden_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if re.fullmatch(r"\|[\s\-:|]+\|", stripped):
                continue
            if not in_table:
                out.append('<table>')
                in_table = True
                is_header = True
                table_row_count = 0
                table_hidden_count = 0
            cells = [c.strip() for c in stripped[1:-1].split("|")]
            tag = "th" if is_header else "td"
            if not is_header:
                table_row_count += 1
            if not is_header and table_row_count > _TABLE_PREVIEW_ROWS:
                out.append('<tr class="table-hidden-row" style="display:none">'
                           + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
                table_hidden_count += 1
            else:
                out.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
            is_header = False
        else:
            if in_table:
                out.append("</table>")
                if table_hidden_count > 0:
                    out.append(
                        f'<button class="table-see-more" onclick="toggleTableRows(this)"'
                        f' data-more="See more ({table_hidden_count})"'
                        f' data-less="See less">'
                        f'See more ({table_hidden_count})</button>'
                    )
                in_table = False
            if stripped.startswith("- "):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{stripped[2:]}</li>")
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                if stripped.startswith("### "):
                    out.append(f"<h4>{stripped[4:]}</h4>")
                elif stripped.startswith("## "):
                    out.append(f"<h3>{stripped[3:]}</h3>")
                elif stripped.startswith("# "):
                    out.append(f"<h2>{stripped[2:]}</h2>")
                else:
                    out.append(line if line.strip() else "<br>")
    if in_list:
        out.append("</ul>")
    if in_table:
        out.append("</table>")
        if table_hidden_count > 0:
            out.append(
                f'<button class="table-see-more" onclick="toggleTableRows(this)"'
                f' data-more="See more ({table_hidden_count})"'
                f' data-less="See less">'
                f'See more ({table_hidden_count})</button>'
            )
    return "\n".join(out)


def welcome_hero(prompt_map: dict[str, list[str]], lang: str = "en"):
    """Empty-state hero with category chips + example prompts."""
    from chat.suggestions import welcome_suggestions
    prompts = welcome_suggestions(prompt_map)
    return Div(
        Div(
            Span("◆", cls="hero-mark"),
            H1(t("chat_welcome_title", lang), cls="welcome-title"),
            P(t("chat_welcome_sub", lang), cls="welcome-sub"),
            cls="welcome-head",
        ),
        Div(
            *[Button(
                Span(AGENTS_BY_SLUG[slug].icon if slug in AGENTS_BY_SLUG else "◆", cls="sugg-icon"),
                Span(text, cls="sugg-text"),
                cls="suggestion-chip",
                onclick=f"fillChat({text!r})",
            ) for text, slug in prompts],
            cls="suggestions",
        ),
        id="welcome-hero",
        cls="welcome-hero",
    )


def agent_browser(lang: str = "en"):
    """Left-pane browser of all 22 agents, grouped by category."""
    groups = []
    for cat in CATEGORIES:
        agents = AGENTS_BY_CATEGORY.get(cat["key"], [])
        links = [
            A(
                Span(a.icon, cls="aitem-icon"),
                Span(agent_t(a.slug, "name", lang), cls="aitem-name"),
                cls="agent-item",
                href=f"/app?agent={a.slug}",
                title=agent_t(a.slug, "one_liner", lang),
            )
            for a in agents
        ]
        groups.append(Details(
            Summary(
                Span(cat["icon"], cls="cat-icon"),
                Span(category_t(cat["key"], "name", lang), cls="cat-name"),
                Span(f"{len(agents)}", cls="cat-count"),
                Span("▸", cls="cat-arrow"),
                cls="cat-toggle",
            ),
            Div(*links, cls="agent-list"),
            cls="agent-group",
        ))
    return Div(*groups, cls="agent-browser")


def sessions_list(sessions: list[dict], current_sid: str = "", lang: str = "en"):
    """Renders the left-pane session history."""
    if not sessions:
        return Div(P(t("chat_no_sessions", lang), cls="sessions-empty"))
    items = []
    for s in sessions:
        is_active = str(s["id"]) == str(current_sid)
        title = s.get("title") or t("chat_untitled", lang)
        items.append(A(
            Span(cls=f"chat-dot{' active' if is_active else ''}"),
            Span(title[:48] + ("…" if len(title) > 48 else ""), cls="chat-session-title"),
            cls=f"chat-history-item{' active' if is_active else ''}",
            href=f"/app?sid={s['id']}",
        ))
    return Div(*items, cls="session-list")


def _config_section(current_currency: str = "USD", lang: str = "en"):
    """Configuration: currency selector (USD default) + Integrations submenu."""
    from utils.session import CURRENCIES, SYMBOLS
    from utils.config import settings

    pills = []
    for c in CURRENCIES:
        active = c == current_currency
        pills.append(Button(
            Span(SYMBOLS[c], cls="cfg-sym"),
            Span(c, cls="cfg-code"),
            cls=f"cfg-chip{' active' if active else ''}",
            hx_post="/app/config",
            hx_vals=f'{{"currency":"{c}"}}',
            hx_swap="none",
        ))

    s = settings()
    integrations = [
        ("", "CRM", "Affinity", bool(s.affinity_api_key), "BYOK"),
        ("", "CRM", "Attio", bool(s.attio_api_key), "BYOK"),
        ("", "CRM", "Pipedrive", bool(s.pipedrive_api_token), s.pipedrive_domain or "BYOK"),
        ("", "Email", "Brevo", bool(s.brevo_api_key), "BYOK"),
        ("", "Data", "Pappers", bool(s.pappers_api_key), "France"),
        ("", "Data", "Scoris", bool(s.scoris_api_key), "Europe"),
        ("", "Data", "Companies House", bool(s.companies_house_api_key), "UK"),
        ("", "Data", "SIRENE", bool(s.sirene_api_key), "France open data"),
        ("", "Data", "PRH", True, "Finland open data"),
        ("", "Research", "Tavily", bool(s.tavily_api_key), "web search"),
        ("", "Research", "EXA", bool(s.exa_api_key), "fallback"),
    ]
    integration_rows = []
    for flag, country, name, connected, note in integrations:
        status_cls = "ok" if connected else (" fallback" if note else " off")
        dot = Span(cls=f"integration-dot {'ok' if connected else ''}")
        label_text = f"{flag} {name}" if flag else name
        note_el = Span(note, cls="integration-note") if note else Span("", cls="integration-note")
        row_content = [
            dot,
            Span(label_text, cls="integration-name"),
            note_el,
            Span("connected" if connected else "off",
                 cls=f"integration-status{' ok' if connected else ''}"),
        ]
        if name in {"Affinity", "Attio", "Pipedrive", "Brevo", "Pappers", "Scoris",
                    "Companies House", "SIRENE", "PRH"}:
            integration_rows.append(A(
                *row_content,
                href="/app/integrations",
                cls="integration-row integration-link",
            ))
        else:
            integration_rows.append(Div(
                *row_content,
                cls="integration-row",
            ))

    return Div(
        # Currency block
        Div(Span(t("cfg_currency", lang), cls="cfg-label"),
            Span(t("cfg_currency_help", lang), cls="cfg-help"),
            cls="cfg-row"),
        Div(*pills, cls="cfg-pills"),
        # Integrations submenu
        Details(
            Summary(
                Span("▸", cls="cfg-arrow"),
                Span(t("cfg_integrations", lang), cls="cfg-label"),
                Span(f"{sum(1 for i in integrations if i[3])}/{len(integrations)}",
                     cls="cfg-count"),
                cls="cfg-integrations-toggle",
            ),
            Div(*integration_rows, cls="integration-list"),
            cls="config-integrations",
        ),
        A("Credentials", href="/app/integrations#credentials",
          cls="integration-row integration-link"),
        A(
            Span(cls="integration-dot ok"),
            Span("News sources", cls="integration-name"),
            Span("RSS", cls="integration-note"),
            Span("configure", cls="integration-status ok"),
            href="/app/news-sources", cls="integration-row integration-link",
        ),
        cls="config-section",
    )


def _bottom_nav(current_path: str = "", lang: str = "en"):
    items = [
        ("Discovery",                    "/app/discovery",    "⌕"),
        ("Signals",                      "/app/signals",      "∿"),
        ("Market Map",                   "/app/market-map",   "⊙"),
        ("Founders",                     "/app/founders",     "♙"),
        (t("chat_pipeline", lang),     "/app/pipeline",     "◆"),
        (t("chat_companies", lang),    "/app/companies",    "⊞"),
        (t("chat_investors", lang),    "/app/investors",    "👤"),
        (t("dr_title", lang),          "/app/dataroom",     "📁"),
        (t("chat_instructions", lang), "/app/instructions", "✎"),
        (t("chat_analytics", lang),    "/app/analytics",    "∑"),
        (t("val_title", lang),          "/app/valuation",    "◎"),
        (t("port_title", lang),         "/app/portfolio",    "◈"),
    ]
    links = []
    for label, href, icon in items:
        active = current_path.startswith(href)
        links.append(A(
            Span(icon, cls="bottom-nav-icon"),
            Span(label, cls="bottom-nav-label"),
            href=href,
            cls=f"bottom-nav-link{' active' if active else ''}",
        ))

    int_active = current_path.startswith("/app/integrations")
    int_subs = [
        ("Affinity",  "/app/integrations#affinity",  "◎"),
        ("Attio",     "/app/integrations#attio",     "◫"),
        ("Pipedrive", "/app/integrations#pipedrive", "⇄"),
        ("Brevo",     "/app/integrations#brevo",     "✉"),
        ("Pappers",    "/app/integrations#pappers",    "FR"),
        ("Scoris",     "/app/integrations#scoris",     "EU"),
        ("Companies House", "/app/integrations#companies_house", "UK"),
        ("SIRENE",     "/app/integrations#sirene",     "FR"),
        ("PRH",        "/app/integrations#prh",        "FI"),
        ("Public Directories", "/app/integrations#public_directories", "◎"),
    ]
    sub_links = [A(
        Span(ic, cls="bottom-nav-icon"),
        Span(lb, cls="bottom-nav-label"),
        href=hr, cls="bottom-nav-link sub",
    ) for lb, hr, ic in int_subs]

    integrations_menu = Details(
        Summary(A(
            Span("⇄", cls="bottom-nav-icon"),
            Span("Integrations", cls="bottom-nav-label"),
            href="/app/integrations",
            cls=f"bottom-nav-link{' active' if int_active else ''}",
        )),
        Div(*sub_links, cls="bottom-nav-sub"),
        open=int_active,
        cls="bottom-nav-details",
    )
    links.append(integrations_menu)

    return Div(*links, cls="bottom-nav")


def left_pane(*, user_email: str | None, sessions: list[dict], current_sid: str = "",
              current_path: str = "", current_currency: str = "USD", lang: str = "en"):
    """The full left pane composition."""
    signin_block = (
        Div(
            Span("◇", cls="user-mark"),
            Span(user_email, cls="user-email"),
            A("Profile", href="/app/profile", cls="profile-link"),
            Button(t("chat_sign_out", lang), cls="sign-out-btn",
                   onclick="signOut()"),
            cls="signed-in-bar",
        )
        if user_email else None
    )

    return Div(
        Div(
            A(Span("◆", cls="brand-mark"), Span("FastVC"),
              href="/", cls="brand-link"),
            Span(t("chat_beta", lang), cls="brand-badge"),
            Span(f"v{__version__}", cls="brand-version"),
            cls="left-header",
        ),
        Div(
            Div(
                A(t("chat_new", lang), cls="new-chat-btn", href="/app"),
                Div(Span(t("chat_sessions", lang), cls="section-label")),
                sessions_list(sessions, current_sid, lang=lang),
                cls="sessions-section",
            ),
            Hr(cls="left-hr"),
            Div(
                Div(Span(t("chat_agents", lang), cls="section-label")),
                agent_browser(lang=lang),
                cls="agents-section",
            ),
            Hr(cls="left-hr"),
            Div(
                Div(Span(t("chat_workspace", lang), cls="section-label")),
                _bottom_nav(current_path, lang=lang),
                cls="workspace-section",
            ),
            Hr(cls="left-hr"),
            Details(
                Summary(A(
                    Span("🎓", cls="bottom-nav-icon"),
                    Span("Training", cls="bottom-nav-label"),
                    href="/app/help",
                    cls=f"bottom-nav-link{' active' if current_path.startswith('/app/help') or current_path.startswith('/app/training') else ''}",
                )),
                Div(
                    A(Span("📖", cls="bottom-nav-icon"),
                      Span("User Guide", cls="bottom-nav-label"),
                      href="/app/help", cls="bottom-nav-link sub"),
                    A(Span("🏈", cls="bottom-nav-icon"),
                      Span("FastVC Game", cls="bottom-nav-label"),
                      href="/app/training", cls="bottom-nav-link sub"),
                    cls="bottom-nav-sub",
                ),
                open=current_path.startswith("/app/help") or current_path.startswith("/app/training"),
                cls="bottom-nav-details",
            ),
            Hr(cls="left-hr"),
            Div(
                Div(Span(t("chat_config", lang), cls="section-label")),
                _config_section(current_currency=current_currency, lang=lang),
                cls="config-wrap",
            ),
            cls="left-body",
        ),
        Div(signin_block, cls="left-footer") if signin_block else None,
        cls="left-pane", id="left-pane",
    )


def sample_cards(current_agent_slug: str | None = None, lang: str = "en",
                 prompt_map: dict[str, list[str]] | None = None):
    """Gemini-style contextual sample-question cards below the chat input.

    Renders the current agent's example_prompts (or a curated 6-pack when no
    agent is bound yet). Client-side, `updateSampleCards(slug)` refreshes the
    list whenever the user types a prefix or the router picks a new agent.
    """
    if prompt_map is None:
        from chat.suggestions import agent_prompt_map
        prompt_map = agent_prompt_map()
    if current_agent_slug and current_agent_slug in AGENTS_BY_SLUG:
        agent = AGENTS_BY_SLUG[current_agent_slug]
        prompts = prompt_map.get(current_agent_slug, [])[:6]
        label = t("js_try_with", lang) + agent_t(agent.slug, "name", lang)
    else:
        from chat.suggestions import welcome_suggestions
        prompts = [text for text, _ in welcome_suggestions(prompt_map)]
        label = t("js_try_prompt", lang)

    chips = [
        Button(
            Span(p, cls="sample-card-text"),
            cls="sample-card",
            onclick=f"fillChat({p!r}); sendMessage(null);",
            title=p,
        )
        for p in prompts
    ]
    return Div(
        Div(
            Span(label, cls="sample-cards-label"),
            id="sample-cards-label",
        ),
        Div(*chips, id="sample-cards-row", cls="sample-cards-row"),
        id="sample-cards",
        cls="sample-cards",
    )


def center_pane(*, messages: list[dict], current_agent_slug: str | None = None,
                selected_agent_slug: str | None = None,
                readonly: bool = False, lang: str = "en"):
    has_messages = bool(messages)
    bubbles = [message_bubble(m["role"], m["content"], m.get("agent_slug")) for m in messages]

    input_placeholder = t("chat_placeholder", lang)

    from chat.suggestions import agent_prompt_map
    prompt_map = agent_prompt_map()

    # Embed all agents' grounded prompts as JSON for the client so we can
    # refresh sample cards without a round-trip whenever the router picks a
    # different slug.
    import json
    prompts_lookup = prompt_map
    names_lookup = {a.slug: agent_t(a.slug, "name", lang) for a in AGENTS}

    # Language dropdown for the header — only the active flag is visible
    current_flag = LANGUAGES.get(lang, LANGUAGES["en"])["flag"]
    lang_options = [
        Button(
            Span(info["flag"], cls="lang-dd-flag"),
            Span(info["native"], cls="lang-dd-label"),
            cls=f"lang-dd-item{' active' if code == lang else ''}",
            hx_post="/app/config",
            hx_vals=f'{{"lang":"{code}"}}',
            hx_swap="none",
        )
        for code, info in LANGUAGES.items()
    ]
    lang_dropdown = Div(
        Button(current_flag, cls="lang-trigger", onclick="toggleLangDropdown(event)"),
        Div(*lang_options, cls="lang-dd-menu", id="lang-dd-menu"),
        cls="lang-dropdown",
    )

    return Div(
        Div(
            Div(
                Button("☰", cls="mobile-menu-btn", onclick="toggleLeftPane()"),
                Span("FastVC", cls="chat-header-title"),
                Span("·", cls="chat-header-dot"),
                Span(
                    agent_t(current_agent_slug, "name", lang) if current_agent_slug and current_agent_slug in AGENTS_BY_SLUG else t("chat_auto_routed", lang),
                    cls="chat-header-agent",
                    id="current-agent-label",
                ),
                cls="chat-header-left",
            ),
            Div(
                lang_dropdown,
                Button(t("chat_copy", lang), id="copy-chat-btn", cls="chat-action-btn",
                       onclick="copyChat()"),
                Button(t("chat_share", lang), id="share-chat-btn", cls="chat-action-btn",
                       onclick="shareChat()"),
                Button(t("news_title", lang), id="news-btn", cls="news-toggle-btn active",
                       onclick="toggleNewsPane()"),
                cls="chat-header-actions",
            ),
            cls="chat-header",
        ),
        Div(*bubbles, id="messages", cls="messages"),
        welcome_hero(prompt_map, lang=lang) if not has_messages else Div(id="welcome-hero", style="display:none"),
        *([] if readonly else [
            Form(
                Input(type="hidden", id="selected-agent", name="agent",
                      value=selected_agent_slug or ""),
                Textarea(
                    id="chat-input", name="msg",
                    cls="chat-textarea",
                    placeholder=input_placeholder,
                    rows="2",
                    onkeydown="handleKey(event)",
                    oninput="autoResize(this)",
                ),
                *([Button(
                    NotStr(_VOICE_ICON),
                    id="voice-btn", type="button", onclick="toggleVoice()",
                    cls="voice-btn", title=t("voice_title", lang),
                )] if settings().xai_voice_agent_id else []),
                Button(t("chat_send", lang), type="submit", cls="chat-send", id="send-btn"),
                id="chat-form",
                cls="chat-form",
                onsubmit="sendMessage(event)",
            ),
            sample_cards(current_agent_slug, lang=lang, prompt_map=prompt_map),
        ]),
        # JSON blobs the client reads
        NotStr(f'<script id="agent-prompts-data" type="application/json">{json.dumps(prompts_lookup)}</script>'),
        NotStr(f'<script id="agent-names-data" type="application/json">{json.dumps(names_lookup)}</script>'),
        NotStr(f'<script id="i18n-data" type="application/json">{json.dumps(js_translations(lang))}</script>'),
        cls="center-pane",
    )


def right_pane(lang: str = "en"):
    """News feed pane — loaded via HTMX."""
    return Div(
        Div(
            Div(H3(t("news_title", lang), cls="right-title"),
                Span("", id="news-subtitle", cls="right-subtitle"),
                cls="right-header-left"),
            Button("✕", cls="right-close", onclick="toggleNewsPane()"),
            cls="right-header",
        ),
        Div(
            Div(
                Div("◌", cls="news-loading-icon"),
                P(t("news_loading", lang), cls="news-loading-text"),
                id="news-loading",
                cls="news-loading htmx-indicator",
            ),
            Div(id="news-body", cls="news-body",
                hx_get="/app/news/html",
                hx_trigger="load, every 600s",
                hx_swap="innerHTML",
                hx_indicator="#news-loading"),
            cls="right-body",
        ),
        id="right-pane", cls="right-pane open",
    )


COPILOT_PROMPTS: dict[str, list[str]] = {
    "Pipeline": [
        "Which startups should move to screening next?",
        "Summarize the top companies by momentum and thesis fit",
        "Which opportunities have less than 12 months runway?",
        "Draft a founder outreach note using the strongest warm path",
    ],
    "Companies": [
        "Top Seed and Series A companies by momentum",
        "Find European developer-tool startups above $1M ARR",
        "Compare growth and burn multiple across sectors",
        "Which companies are likely to raise next?",
    ],
    "Investors": [
        "Rank family offices by venture mandate and likely check size",
        "Which LP relationships have gone stale?",
        "Find LPs with a warm path and early-stage appetite",
        "Prepare a first-meeting brief for the highest-fit allocator",
    ],
    "Investor Detail": [
        "Summarize this LP's mandate, check size and relationship history",
        "What is the strongest warm path?",
        "Which portfolio evidence best fits this allocator?",
        "Draft a relationship-led intro email",
    ],
    "Analytics": [
        "ARR distribution by startup stage",
        "Company count by deal stage",
        "Average burn multiple by sector",
        "Top 20 companies by momentum score",
    ],
    "Valuation": [
        "Model a $6M Series A at $24M pre-money",
        "What check gets us to 15% post-round ownership?",
        "Show dilution through Series C with pro rata",
        "What exit outcome returns 1x of the fund?",
    ],
    "Data Room": [
        "What documents are missing for due diligence?",
        "Summarize the uploaded pitch deck",
        "Are there any red flags in the legal docs?",
        "What's in the data room for this company?",
    ],
    "Instructions": [
        "How should I customize the startup screening prompt?",
        "What does the round model agent do?",
        "Help me write a system prompt for sector-specific analysis",
        "Which agent handles value creation planning?",
    ],
    "Help": [
        "How do I use the valuation simulator?",
        "What agents are available for due diligence?",
        "How does the pipeline kanban work?",
        "How do I upload documents to the data room?",
    ],
    "Integrations": [
        "How would Affinity company fields map into FastVC?",
        "Which CRM and outreach adapters are configured?",
        "Show startups not yet linked to a CRM record",
        "What capabilities does each BYOK adapter expose?",
    ],
    "Portfolio": [
        "What's the total portfolio ARR?",
        "Which sectors are overweight in the portfolio?",
        "Summarize portfolio health — any companies at risk?",
        "Which companies have less than 12 months runway?",
    ],
    "Portfolio Analytics": [
        "Compare growth and burn multiple across portfolio companies",
        "Which country has the highest concentration?",
        "Which portfolio company has the highest growth rate?",
        "Show revenue vs profitability for all holdings",
    ],
    "Portfolio KPIs": [
        "How has portfolio ARR grown year over year?",
        "Which companies are below the gross-margin target?",
        "Which portfolio companies improved NRR this quarter?",
        "Compare growth rates across the portfolio companies",
    ],
    "Training": [
        "How does the FastVC scoring system work?",
        "What deal scenarios can I practice?",
        "Give me tips for negotiating better terms",
        "What skills should I focus on improving?",
    ],
}


def copilot_pane(*, page_name: str, page_context: dict | None = None,
                 company_slug: str = "", lang: str = "en"):
    """Right-pane copilot chat — page-scoped AI assistant."""
    import json as _json
    context_json = _json.dumps(page_context or {})

    from chat.suggestions import copilot_suggestions
    prompts = copilot_suggestions(page_name)
    sample_chips = [
        Button(
            Span(p, cls="copilot-chip-text"),
            cls="copilot-chip",
            onclick=f"copilotFillAndSend({p!r})",
        )
        for p in prompts
    ]

    return Div(
        Div(
            Div(H3("Copilot", cls="right-title"),
                Span(page_name, id="copilot-subtitle", cls="right-subtitle"),
                cls="right-header-left"),
            Button("»", cls="right-close copilot-collapse", onclick="toggleCopilotPane()"),
            cls="right-header",
        ),
        Div(
            Div(id="copilot-messages", cls="copilot-messages"),
            cls="right-body copilot-body",
        ),
        Form(
            Input(type="hidden", id="copilot-context", value=context_json),
            Input(type="hidden", id="copilot-page", value=page_name),
            Input(type="hidden", id="copilot-company", value=company_slug),
            Div(
                Textarea(
                    id="copilot-input", name="msg",
                    cls="copilot-textarea",
                    placeholder=f"Ask about {page_name.lower()}...",
                    rows="2",
                    onkeydown="copilotHandleKey(event)",
                ),
                Button("Send", type="submit", cls="copilot-send", id="copilot-send-btn"),
                cls="copilot-input-row",
            ),
            Div(*sample_chips, id="copilot-chips", cls="copilot-chips"),
            id="copilot-form",
            cls="copilot-form",
            onsubmit="copilotSend(event)",
        ),
        id="right-pane", cls="right-pane copilot-pane open",
    )


def copilot_toggle_btn(lang: str = "en"):
    """Toggle button for the copilot pane, used in workspace page headers."""
    return Button("«", id="copilot-btn", cls="copilot-expand-btn",
                  onclick="toggleCopilotPane()", title="Open Copilot")


def signin_overlay(lang: str = "en"):
    google_svg = '<svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg"><path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z" fill="#4285F4"/><path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="#34A853"/><path d="M3.964 10.71c-.18-.54-.282-1.117-.282-1.71s.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9s.348 1.452.957 2.042l3.007-2.332z" fill="#FBBC05"/><path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/></svg>'
    return Div(
        Div(
            Div(
                Button("Sign In", id="auth-tab-login", cls="auth-tab active",
                       onclick="switchAuthTab('login')"),
                Button("Register", id="auth-tab-register", cls="auth-tab",
                       onclick="switchAuthTab('register')"),
                cls="auth-tabs",
            ),
            # Login form
            Div(
                P("Sign in to your FastVC account", cls="signin-sub"),
                A(
                    Span(NotStr(google_svg), cls="google-btn-icon"),
                    Span("Continue with Google", cls="google-btn-text"),
                    href="/auth/google",
                    cls="google-btn",
                ),
                Div(Span(cls="google-divider-line"), Span("or", cls="google-divider-text"), Span(cls="google-divider-line"), cls="google-divider"),
                Input(type="email", id="login-email", placeholder="Email",
                      onkeydown="if(event.key==='Enter')document.getElementById('login-password').focus()"),
                Input(type="password", id="login-password", placeholder="Password",
                      onkeydown="if(event.key==='Enter')doLogin()"),
                A("Forgot password?", href="#", onclick="showForgotPassword(event)",
                  cls="forgot-link"),
                Div(id="login-error", cls="auth-error"),
                Div(
                    Button("Sign In", onclick="doLogin()", cls="auth-primary-btn"),
                    Button("Cancel", onclick="document.getElementById('signin-overlay').classList.remove('visible')",
                           cls="auth-cancel-btn"),
                    cls="auth-btn-row",
                ),
                id="auth-form-login",
            ),
            # Register form
            Div(
                P("Create a FastVC account", cls="signin-sub"),
                Input(type="text", id="reg-name", placeholder="Name (optional)"),
                Input(type="email", id="reg-email", placeholder="Email"),
                Input(type="password", id="reg-password", placeholder="Password (min 6 chars)",
                      onkeydown="if(event.key==='Enter')doRegister()"),
                Div(id="reg-error", cls="auth-error"),
                Div(id="reg-success", cls="auth-success"),
                Div(
                    Button("Register", onclick="doRegister()", cls="auth-primary-btn"),
                    Button("Cancel", onclick="document.getElementById('signin-overlay').classList.remove('visible')",
                           cls="auth-cancel-btn"),
                    cls="auth-btn-row",
                ),
                id="auth-form-register",
                style="display:none",
            ),
            # Forgot password form
            Div(
                P("Enter your email to receive a reset link", cls="signin-sub"),
                Input(type="email", id="forgot-email", placeholder="Email",
                      onkeydown="if(event.key==='Enter')doForgot()"),
                Div(id="forgot-msg", cls="auth-msg"),
                Div(
                    Button("Send Reset Link", onclick="doForgot()", cls="auth-primary-btn"),
                    A("Back to login", href="#", onclick="switchAuthTab('login');return false",
                      cls="forgot-link", style="margin-left:12px"),
                    cls="auth-btn-row",
                ),
                id="auth-form-forgot",
                style="display:none",
            ),
            cls="signin-box",
        ),
        cls="signin-overlay", id="signin-overlay",
        onclick="if(event.target===this)this.classList.remove('visible')",
    )
