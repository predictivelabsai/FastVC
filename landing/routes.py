"""Marketing routes including the product, open-source and contact surfaces."""

from __future__ import annotations

from fasthtml.common import (
    Div, H1, H2, H3, H4, P, Ul, Li, Section, Article, Span, A, Img, Form, Input, Textarea, Label, Button, NotStr,
    Table, Thead, Tbody, Tr, Th, Td,
)

from starlette.responses import RedirectResponse

from app import rt
from agents.registry import AGENTS, AGENTS_BY_CATEGORY, AGENTS_BY_SLUG, CATEGORIES
from landing.components import (
    page, Hero, ProductTour, CategoryPillar, AgentCard, CategorySection, CaseStudyStrip, PENewsSection, CTASection,
    Eyebrow, Heading, Body_, Button_, Pill, Section_, PartnersSection, SITE_NAME, SITE_TAGLINE,
    GITHUB_URL,
)
from utils.i18n import t, agent_t, category_t, get_lang, set_lang, LANGUAGES


# ── Language switch ────────────────────────────────────────────────────
@rt("/set-lang/{code}")
def set_language(code: str, sess):
    if code in LANGUAGES:
        set_lang(sess, code)
    return RedirectResponse("/", status_code=303)


# ── / ────────────────────────────────────────────────────────────────
@rt("/")
def home(sess):
    lang = get_lang(sess)
    pillars = Section_(
        Div(
            Eyebrow(t("pillars_eyebrow", lang)),
            Heading(2, t("pillars_heading", lang), cls="mt-3 max-w-4xl mb-10"),
            cls="mb-6",
        ),
        Div(
            *[CategoryPillar(c, lang=lang) for c in CATEGORIES],
            cls="grid md:grid-cols-2 lg:grid-cols-5 gap-4",
        ),
        cls="border-t border-line",
    )

    how = Section_(
        Div(
            Eyebrow(t("how_eyebrow", lang)),
            Heading(2, t("how_heading", lang), cls="mt-3 max-w-3xl mb-10"),
            cls="mb-6",
        ),
        Div(
            *[Article(
                P(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim mb-3"),
                H3(title, cls="text-ink text-xl font-medium mb-3"),
                P(body, cls="text-ink-muted text-sm leading-relaxed"),
                cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
            ) for (num, title, body) in [
                ("01", t("how_01_title", lang), t("how_01_body", lang)),
                ("02", t("how_02_title", lang), t("how_02_body", lang)),
                ("03", t("how_03_title", lang), t("how_03_body", lang)),
            ]],
            cls="grid md:grid-cols-3 gap-4",
        ),
        cls="border-t border-line",
    )

    open_source = Section_(
        Div(
            Eyebrow(t("oss_badge", lang)),
            Heading(2, "Your fund's operating system should become your edge — not your vendor's.",
                    cls="mt-3 max-w-4xl"),
            P("FastVC is free and fully open source under Apache 2.0. Run it on your "
              "infrastructure, keep confidential deal data in your security boundary, and "
              "adapt the agents, ranking logic and workflows to how your firm invests.",
              cls="mt-5 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            Div(
                Button_(t("oss_explore", lang), href="/open-source", primary=True),
                Button_(t("oss_view_source", lang), href=GITHUB_URL, primary=False),
                cls="mt-8 flex items-center gap-3 flex-wrap",
            ),
            cls="md:col-span-2",
        ),
        Div(
            *[Article(
                P(title, cls="text-ink font-medium mb-2"),
                P(body, cls="text-ink-muted text-sm leading-relaxed"),
                cls="p-6 rounded-2xl border border-line bg-bg-elevated h-full",
            ) for title, body in [
                ("Data sovereignty", "Your database, infrastructure and model endpoint remain under your control."),
                ("Private by design", "Pipeline, data-room and IC context need not leave your chosen security boundary."),
                ("Auditable", "Inspect every prompt, tool, scoring rule and source before trusting an answer."),
                ("Built for differentiation", "Fork the workflow into a proprietary information system tailored to your thesis."),
            ]],
            cls="grid sm:grid-cols-2 gap-4 mt-10",
        ),
        cls="border-t border-line bg-accent/5",
    )

    return page(
        t("hero_eyebrow", lang),
        Hero(lang=lang),
        ProductTour(lang=lang),
        open_source,
        pillars,
        how,
        CaseStudyStrip(lang=lang),
        PENewsSection(lang=lang),
        PartnersSection(),
        CTASection(lang=lang),
        current_path="/",
        lang=lang,
    )


# ── /open-source ────────────────────────────────────────────────────
@rt("/open-source")
def open_source_page(sess):
    lang = get_lang(sess)
    advantages = [
        ("Data sovereignty", "Deploy FastVC in infrastructure you control. Your pipeline, "
         "company intelligence, data-room documents and investment history stay in your "
         "database and under your retention policies."),
        ("Privacy without a black box", "Choose the model endpoint and data providers. "
         "Audit credential handling and retrieval paths in source instead of relying on "
         "a vendor's assurances."),
        ("Logic you can inspect", "Every agent instruction, tool, routing decision and "
         "scoring rule is readable. Your team can challenge the reasoning and change it."),
        ("A compounding information advantage", "Encode your thesis, sourcing heuristics, "
         "diligence playbooks and portfolio pattern recognition. The system becomes more "
         "specific to your firm instead of converging on the same SaaS workflow as every peer."),
    ]
    return page(
        t("nav_open_source", lang),
        Section_(
            Eyebrow(t("oss_badge", lang)),
            Heading(1, "Own the system that compounds your venture intelligence.",
                    cls="mt-4 max-w-5xl"),
            P("FastVC's complete application source is available under Apache 2.0. There are "
              "no software licence or per-seat fees: use it, self-host it, audit it and modify "
              "it into an operating system that reflects how your fund actually wins.",
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            Div(
                Button_(t("oss_view_source", lang), href=GITHUB_URL, primary=True),
                Button_(t("oss_cta_start", lang), href="/signin", primary=False),
                cls="mt-8 flex items-center gap-3 flex-wrap",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                *[Article(
                    Span(f"0{index}", cls="font-mono text-[11px] tracking-widest text-accent"),
                    Heading(3, title, cls="mt-4"),
                    P(body, cls="mt-3 text-ink-muted text-sm leading-relaxed"),
                    cls="p-7 rounded-2xl border border-line bg-bg-elevated h-full",
                ) for index, (title, body) in enumerate(advantages, start=1)],
                cls="grid md:grid-cols-2 gap-4",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Eyebrow("What free means"),
            Heading(2, "No licence fee. No per-seat gate. No lock-in.", cls="mt-4 max-w-3xl"),
            P("The FastVC software is free under Apache 2.0. Infrastructure, commercial model "
              "APIs and paid data providers can still have their own costs, but you choose each "
              "one and can replace it without rebuilding the venture workflow.",
              cls="mt-5 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line bg-accent/5",
        ),
        CTASection(lang=lang),
        current_path="/open-source",
        lang=lang,
    )


# ── /platform ────────────────────────────────────────────────────────
@rt("/platform")
def platform(sess):
    lang = get_lang(sess)
    return page(
        t("platform_title", lang),
        Section_(
            Eyebrow(t("platform_title", lang)),
            Heading(1, t("platform_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("platform_body", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                *[Article(
                    Div(Span(c["icon"], cls="text-accent text-xl"),
                        Span(t("agents_count", lang).format(n=len(AGENTS_BY_CATEGORY[c['key']])),
                             cls="ml-auto font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                        cls="flex items-center mb-4"),
                    H3(category_t(c["key"], "name", lang), cls="text-ink text-xl font-medium mb-2"),
                    P(category_t(c["key"], "blurb", lang), cls="text-ink-muted leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for c in CATEGORIES],
                cls="grid md:grid-cols-2 lg:grid-cols-5 gap-4",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Eyebrow(t("platform_hood", lang)),
            Heading(2, t("platform_not_wrap", lang), cls="mt-3 max-w-3xl mb-10"),
            Div(
                *[Article(
                    P(k, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
                    P(v, cls="text-ink leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for (k, v) in [
                    ("Squad", t("platform_squad", lang)),
                    ("Tools", t("platform_tools", lang)),
                    ("RAG",   t("platform_rag", lang)),
                    ("Memory", t("platform_memory", lang)),
                ]],
                cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
            ),
            cls="border-t border-line",
        ),
        CTASection(lang=lang),
        current_path="/platform",
        lang=lang,
    )


# ── /agents ──────────────────────────────────────────────────────────
@rt("/agents")
def agents_page(sess):
    lang = get_lang(sess)
    return page(
        t("nav_agents", lang),
        Section_(
            Eyebrow(t("agents_eyebrow", lang)),
            Heading(1, t("agents_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("agents_body", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        *[CategorySection(c, lang=lang) for c in CATEGORIES],
        CTASection(lang=lang),
        current_path="/agents",
        lang=lang,
    )


# ── /agents/<slug> ───────────────────────────────────────────────────
@rt("/agents/{slug}")
def agent_detail(slug: str, sess):
    lang = get_lang(sess)
    agent = AGENTS_BY_SLUG.get(slug)
    if agent is None:
        return page(
            t("agent_not_found", lang),
            Section_(
                H1(t("agent_not_found", lang), cls="text-ink text-3xl"),
                P(t("agent_no_url", lang), A(t("agent_full_squad", lang), href="/agents", cls="text-accent underline"), ".",
                  cls="text-ink-muted mt-4"),
            ),
            current_path="/agents",
            lang=lang,
        )
    cat = next(c for c in CATEGORIES if c["key"] == agent.category)
    agent_name = agent_t(slug, "name", lang)
    from chat.suggestions import agent_prompt_map
    public_prompts = agent_prompt_map().get(slug, [])
    return page(
        agent_name,
        Section_(
            Div(
                A(t("agent_all", lang), href="/agents", cls="text-ink-dim text-xs hover:text-accent"),
                cls="mb-6",
            ),
            Div(
                Span(agent.icon, cls="text-accent text-4xl"),
                Span(category_t(cat["key"], "name", lang), cls="ml-4 font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                cls="flex items-center mb-4",
            ),
            Heading(1, agent_name, cls="max-w-4xl"),
            P(agent_t(slug, "one_liner", lang), cls="mt-5 text-ink-muted text-lg max-w-3xl"),
            Div(Pill(f"category: {cat['key']}"),
                Pill("plain-English routing"),
                cls="mt-6 flex flex-wrap gap-2"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                Div(
                    Eyebrow(t("agent_what", lang)),
                    P(agent.description, cls="mt-4 text-ink leading-relaxed"),
                    cls="md:col-span-2",
                ),
                Div(
                    Eyebrow(t("agent_examples", lang)),
                    Ul(
                        *[Li(
                            Div(f'"{p}"', cls="px-4 py-3 rounded-xl bg-bg-elevated border border-line text-sm text-ink leading-relaxed"),
                            cls="mb-2",
                        ) for p in public_prompts],
                        cls="mt-4 space-y-2",
                    ),
                    cls="",
                ),
                cls="grid md:grid-cols-3 gap-10",
            ),
            cls="border-t border-line",
        ),
        CTASection(headline=t("agent_try", lang).format(name=agent_name),
                   body=t("agent_try_body", lang),
                   cta_label=t("hero_cta_open", lang), cta_href="/signin", lang=lang),
        current_path="/agents",
        lang=lang,
    )


# ── /how-it-works ────────────────────────────────────────────────────
@rt("/how-it-works")
def how_it_works(sess):
    lang = get_lang(sess)
    return page(
        t("hiw_title", lang),
        Section_(
            Eyebrow(t("hiw_title", lang)),
            Heading(1, t("hiw_h1", lang), cls="mt-4 max-w-4xl"),
            cls="border-t border-line",
        ),
        *[Section_(
            Div(
                Span(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                Heading(2, title, cls="mt-3 max-w-3xl"),
                P(body, cls="mt-5 text-ink-muted text-lg max-w-3xl leading-relaxed"),
                cls="mb-8",
            ),
            Div(*[Pill(name) for name in agents], cls="flex flex-wrap gap-2"),
            cls="border-t border-line",
        ) for (num, title, body, agents) in [
            (t("hiw_01_num", lang), t("hiw_01_title", lang), t("hiw_01_body", lang),
             ["Startup Discovery", "Startup Screener", "Venture Comps", "Fundraising Signal"]),
            (t("hiw_02_num", lang), t("hiw_02_title", lang), t("hiw_02_body", lang),
             ["Cap Table Parser", "Startup Metrics", "Round & Ownership", "Financing Strategy", "Venture Outcomes"]),
            (t("hiw_03_num", lang), t("hiw_03_title", lang), t("hiw_03_body", lang),
             ["Data Room Auditor", "Contract Abstractor", "Legal & IP", "Product & GTM", "Technology & Security"]),
            (t("hiw_04_num", lang), t("hiw_04_title", lang), t("hiw_04_body", lang),
             ["IC Memo Writer", "Deal Brief", "LP Update Generator", "LP Fundraising Copilot"]),
            (t("hiw_05_num", lang), t("hiw_05_title", lang), t("hiw_05_body", lang),
             ["Pricing & Monetization", "KPI / Burn / Runway", "Portfolio Support", "Retention & Expansion"]),
        ]],
        CTASection(lang=lang),
        current_path="/how-it-works",
        lang=lang,
    )


# ── /pricing ─────────────────────────────────────────────────────────
@rt("/pricing")
def pricing():
    """Retired in favour of /features. Kept so existing inbound links survive."""
    return RedirectResponse("/features", status_code=301)


# ── /features ────────────────────────────────────────────────────────
# Capability groups. Each maps to real product surface — the workspace
# routes in chat/ and the agent categories in agents/registry.py.
FEATURE_GROUPS = [
    ("Discovery & signals", "⌕", [
        ("Thesis-led discovery",
         "Describe the thesis in plain language — stage, sector, geography, founder "
         "background, momentum — and get an explainable match list, not a keyword dump."),
        ("Startup & founder signals",
         "Hiring velocity, funding events, product launches and founder moves, tracked "
         "continuously and surfaced against your saved searches."),
        ("Market maps",
         "Generate a category map on demand and keep it live as the sector moves."),
        ("Saved searches & alerts",
         "Persist a thesis once; new matches arrive by alert and in the daily digest."),
    ]),
    ("Conversational analysis", "◆", [
        ("An agent squad, not a chatbot",
         "Specialists across sourcing, round modelling, diligence, IC/LP and portfolio "
         "support. An intent router reads each plain-English request and selects the right specialist."),
        ("Grounded in your data",
         "Answers cite the company record, financials, cap table and indexed documents "
         "behind them, with the tool calls shown inline."),
        ("Editable instructions",
         "Every agent's operating prompt is editable in-app and versioned, so the squad "
         "reflects how your fund actually underwrites."),
        ("Text-to-SQL analytics",
         "Ask a question of the portfolio in English; get guarded SELECT SQL and a chart."),
    ]),
    ("Round & ownership modelling", "◈", [
        ("Round construction",
         "Model pre/post money, option pool shuffle, dilution and the check size that "
         "gets you to a target ownership."),
        ("Outcome modelling",
         "Probability-weighted exit outcomes from your entry through later rounds."),
        ("Cap table parsing",
         "Turn a messy cap table into fully diluted ownership you can reason about."),
        ("Comps",
         "Comparable financings and operating benchmarks by stage, model and geography."),
    ]),
    ("Diligence & IC", "◼", [
        ("Data room with citations",
         "Upload a data room, index it, and get retrieval with the source passage attached."),
        ("Diligence findings & risks",
         "Track findings, risks and milestones per deal, kept next to the deal workspace."),
        ("IC memo drafting",
         "Draft the memo from the record, then export to PDF or Word."),
        ("LP relations",
         "LP/family-office CRM and LP-update workflows off the same underlying data."),
    ]),
]

# Integration surface. Grouped by the job each one does for a fund — the CRM
# adapters here are the providers in tools/integrations.py PROVIDERS.
INTEGRATION_GROUPS = [
    ("Relationship & CRM", "Where the fund's system of record lives.", [
        ("Affinity", "VC relationship CRM — companies, people, interaction history, warm paths, pipeline."),
        ("Attio", "Flexible CRM — map startup, founder, LP and activity objects into your workspace."),
        ("Pipedrive", "Pipeline CRM — companies, contacts, deals, activities and LP pipeline."),
        ("Brevo", "Outreach and lifecycle email for founder and LP sequences."),
    ]),
    ("Where your team already works", "Push signal to the surface people read.", [
        ("Slack", "Deal alerts, new-match notifications and digest delivery into the channel that owns the thesis."),
        ("Email digest", "A daily brief of new matches, signals and pipeline movement."),
        ("Calendar & inbox", "Meeting and thread context for warm-path mapping."),
    ]),
    ("Public signal sources", "The open web, read continuously.", [
        ("LinkedIn", "Headcount by function, hiring velocity, founder and operator moves."),
        ("X / Twitter", "Investor follow-graph convergence and founder activity ahead of a round."),
        ("Company registries", "UK, French, Finnish, Estonian, Latvian and Lithuanian identity and filing data."),
        ("News & RSS", "Sector and portfolio news, deduplicated into the workspace."),
    ]),
    ("Agentic & developer surface", "FastVC as a component, not a silo.", [
        ("MCP server", "Expose FastVC data to Claude and other agents over Model Context Protocol."),
        ("REST API", "Query companies, founders, rounds and signals programmatically."),
        ("Zapier / n8n", "Wire FastVC into existing automation without writing glue."),
        ("Bring your own LLM", "Point the squad at your own model endpoint."),
    ]),
]


COMPANY_DATA_SOURCES = [
    {
        "name": "Pappers API", "flags": "🇫🇷", "kind": "Commercial API",
        "logo": "https://www.pappers.fr/favicon.ico", "url": "https://www.pappers.fr/",
        "coverage": "France, with expanding European coverage",
        "data": "Legal identity, officers, filings and financial statements",
    },
    {
        "name": "Scoris API", "flags": "🇬🇧 🇫🇮 🇪🇪 🇱🇹 🇱🇻 🇸🇪", "kind": "Commercial API",
        "logo": "https://www.google.com/s2/favicons?domain=scoris.eu&sz=128", "url": "https://scoris.eu/",
        "coverage": "United Kingdom, Finland, Estonia, Lithuania, Latvia and Sweden",
        "data": "Registry search, financials, contacts and company enrichment",
    },
    {
        "name": "Companies House", "flags": "🇬🇧", "kind": "Official public API",
        "logo": "https://www.google.com/s2/favicons?domain=find-and-update.company-information.service.gov.uk&sz=128",
        "url": "https://find-and-update.company-information.service.gov.uk/",
        "coverage": "United Kingdom",
        "data": "Company profiles, officers, significant control and SIC codes",
    },
    {
        "name": "INSEE SIRENE", "flags": "🇫🇷", "kind": "Official open-data API",
        "logo": "https://www.insee.fr/favicon.ico", "url": "https://portail-api.insee.fr/",
        "coverage": "France",
        "data": "SIREN/SIRET identity, NAF activity, status and establishments",
    },
    {
        "name": "PRH / Finnish Business Information System", "flags": "🇫🇮", "kind": "Official open-data API",
        "logo": "https://www.google.com/s2/favicons?domain=prh.fi&sz=128", "url": "https://avoindata.prh.fi/",
        "coverage": "Finland",
        "data": "Business IDs, industry, registered names, addresses and websites",
    },
    {
        "name": "Estonian e-Business Register", "flags": "🇪🇪", "kind": "Business registry",
        "logo": "https://ariregister.rik.ee/favicon.ico", "url": "https://ariregister.rik.ee/eng",
        "coverage": "Estonia",
        "data": "Registry identity and multi-period statutory financials",
    },
    {
        "name": "Lithuanian company registry data", "flags": "🇱🇹", "kind": "Registry directory",
        "logo": "https://rekvizitai.vz.lt/favicon.ico", "url": "https://rekvizitai.vz.lt/en/",
        "coverage": "Lithuania",
        "data": "Registration, VAT, company status, employees and annual financials",
    },
    {
        "name": "Latvian Open Data Portal", "flags": "🇱🇻", "kind": "Official open data",
        "logo": "https://data.gov.lv/favicon.ico", "url": "https://data.gov.lv/",
        "coverage": "Latvia",
        "data": "Enterprise-register identity and long-run annual financial history",
    },
]


def DataSourcesSection():
    """Implemented company APIs and registries, with coverage and provenance."""
    return Section_(
        Eyebrow("Company data sources"),
        Heading(2, "Registry-backed company intelligence across Europe.", cls="mt-4 max-w-4xl"),
        P("FastVC combines official APIs, licensed company-data providers and provenance-preserving "
          "registry imports. Every record retains its source identifier, source URL, retrieval time "
          "and applicable licence so the investment team can distinguish a filing from an inference.",
          cls="mt-6 text-ink-muted text-lg max-w-4xl leading-relaxed mb-10"),
        Div(
            *[A(
                Article(
                    Div(
                        Div(
                            Img(src=source["logo"], alt=f"{source['name']} logo",
                                cls="w-8 h-8 object-contain rounded",
                                onerror="this.style.display='none';this.nextElementSibling.style.display='inline'"),
                            Span(source["name"][:3].upper(),
                                 cls="font-mono text-[10px] text-accent", style="display:none"),
                            cls="w-11 h-11 rounded-xl border border-line bg-bg-raised flex items-center justify-center overflow-hidden",
                        ),
                        Div(
                            P(source["name"], cls="text-ink font-medium leading-snug"),
                            P(source["kind"], cls="text-accent text-[11px] font-mono uppercase tracking-wider mt-1"),
                        ),
                        Span(source["flags"], cls="ml-auto text-lg tracking-wide text-right"),
                        cls="flex items-center gap-3 mb-5",
                    ),
                    P(source["coverage"], cls="text-ink text-sm mb-2"),
                    P(source["data"], cls="text-ink-muted text-sm leading-relaxed"),
                    cls="p-6 rounded-2xl border border-line bg-bg-elevated h-full hover:border-accent/60 transition-colors",
                ),
                href=source["url"], target="_blank", rel="noopener noreferrer",
                cls="block no-underline group",
            ) for source in COMPANY_DATA_SOURCES],
            cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
        ),
        Div(
            Pill("Source IDs retained"), Pill("Annual periods normalized"),
            Pill("Real registry and API records"), Pill("BYOK and open-data adapters"),
            cls="mt-8 flex flex-wrap gap-2",
        ),
        cls="border-t border-line",
    )


@rt("/features")
def features(sess):
    lang = get_lang(sess)
    return page(
        t("nav_features", lang),
        Section_(
            Eyebrow("What FastVC does"),
            Heading(1, "Everything between a thesis and a signed term sheet.",
                    cls="mt-4 max-w-4xl"),
            P("FastVC is a working venture system, not a prompt pack. Discovery, signals, "
              "screening, round and ownership modelling, cited diligence, IC and LP work — "
              "on one data model, driven by conversation.",
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        *[Section_(
            Div(
                Span(icon, cls="text-accent text-2xl"),
                Heading(2, group, cls="mt-3"),
                cls="mb-8",
            ),
            Div(
                *[Article(
                    P(name, cls="text-ink font-medium mb-2"),
                    P(body, cls="text-ink-muted text-sm leading-relaxed"),
                    cls="p-6 rounded-2xl border border-line bg-bg-elevated h-full",
                ) for name, body in items],
                cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
            ),
            cls="border-t border-line",
        ) for group, icon, items in FEATURE_GROUPS],
        DataSourcesSection(),
        IntegrationsSection(),
        CTASection(lang=lang),
        current_path="/features",
        lang=lang,
    )


def IntegrationsSection():
    """Integrations block — also reusable on the home page."""
    return Section_(
        Eyebrow("Integrations"),
        Heading(2, "Fits the stack you already run.", cls="mt-4 max-w-3xl"),
        P("Most funds run a sourcing engine, a relationship CRM, a financial database and "
          "an automation layer. FastVC is built to sit across them rather than replace them — "
          "your data stays yours, and the squad reads from wherever it already lives.",
          cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed mb-10"),
        Div(
            *[Article(
                P(group, cls="text-ink font-medium"),
                P(blurb, cls="text-ink-dim text-xs mt-1 mb-5"),
                Ul(
                    *[Li(
                        Span("→ ", cls="text-accent mr-1"),
                        Span(name, cls="text-ink text-sm font-medium"),
                        Span(f" — {desc}", cls="text-ink-muted text-sm"),
                        cls="mb-3 flex items-baseline flex-wrap",
                    ) for name, desc in items],
                ),
                cls="p-6 rounded-2xl border border-line bg-bg-elevated h-full",
            ) for group, blurb, items in INTEGRATION_GROUPS],
            cls="grid md:grid-cols-2 gap-4",
        ),
        P("Adapters validate and store credentials today; live sync is opt-in per provider. "
          "Keys are encrypted at rest and never rendered back to the browser.",
          cls="mt-8 text-ink-dim text-xs max-w-3xl"),
        section_id="integrations",
        cls="border-t border-line",
    )


# ── /compare ─────────────────────────────────────────────────────────
# Scope is deliberately narrow: the early / signal-based deal sourcing and
# company discovery category. Financial-depth databases (PitchBook, CB
# Insights) and relationship CRMs (Affinity) are a different job and are
# treated as complements in the gap analysis below, not competitors.
COMPARE_ROWS = [
    ("Licence",
     "Open source — Apache 2.0, the whole system",
     "Proprietary SaaS",
     "Proprietary SaaS",
     "Proprietary SaaS",
     "Proprietary SaaS"),
    ("Self-host",
     "Yes — your infrastructure, your database",
     "Vendor cloud only",
     "Vendor cloud only",
     "Vendor cloud only",
     "Vendor cloud only"),
    ("Auditable logic",
     "Every agent prompt, tool and scoring rule is readable and editable",
     "Scoring and ranking are closed",
     "Signal weighting is closed",
     "Convergence logic is closed",
     "Classification model is closed"),
    ("Primary edge",
     "Open-source agentic workflow over your own fund data",
     "Breadth of proprietary company + people index",
     "Cross-channel growth signals",
     "Investor follow-graph convergence on X",
     "AI reading of company websites at scale"),
    ("Core dataset",
     "Bring your own — your pipeline, cap tables, data room, plus public registries",
     "35M+ companies, 195M+ people profiles",
     "Company, web traffic, hiring and product signals",
     "1,000+ venture investors' following behaviour",
     "28M+ company profiles, website-derived"),
    ("Earliest signal",
     "Depends on the sources you connect",
     "Formation and stealth, talent movement",
     "Growth inflection across web / hiring / product",
     "Pre-round — months before announcement",
     "What a company actually does, not its SIC code"),
    ("AI agent",
     "Specialist squad across the whole lifecycle",
     "Scout — research, market maps, outreach drafts",
     "AI search and scoring",
     "Prompt-to-founder-contact flow",
     "AI search and list building"),
    ("Beyond sourcing",
     "Round modelling, diligence, IC memos, LP relations, portfolio ops",
     "Primarily discovery and research",
     "Primarily discovery and signals",
     "Primarily discovery and outreach",
     "Discovery plus M&A/PE workflows"),
    ("Best fit",
     "Funds that want one system from thesis to IC and LP reporting",
     "Institutional VCs with dedicated sourcing teams",
     "Emerging managers on consumer and SaaS",
     "Solo GPs and small funds wanting early edge cheaply",
     "M&A, PE and mid-market corporate development"),
    ("Pricing shape",
     "BYOD; self-host or hosted",
     "Enterprise / quote-based",
     "Mid-market subscription",
     "From ~$49/mo",
     "Subscription, not publicly listed"),
]

COMPARE_COLS = ["FastVC", "Harmonic.ai", "Specter", "Frontrun", "Inven"]

GAP_ROWS = [
    ("Where FastVC is strong",
     ["Open source under Apache 2.0. Every one of the alternatives is a closed "
      "proprietary platform — you can read FastVC's sourcing logic, fork it, and run "
      "it on your own infrastructure.",
      "No vendor lock-in: your data stays in your database, and you can point the "
      "squad at your own LLM endpoint.",
      "The whole lifecycle in one place — discovery through round modelling, cited "
      "diligence, IC memo and LP update, on a single data model.",
      "Agents whose operating instructions you can read and edit, so the system "
      "underwrites the way your fund does — not how a vendor's black box scores.",
      "Answers grounded in your own records with the tool calls shown, rather than "
      "an opaque score."]),
    ("Where the specialists are stronger",
     ["Proprietary coverage at formation and in stealth — Harmonic's 35M company / "
      "195M people index is a data moat FastVC does not try to replicate.",
      "Frontrun's investor follow-graph is a genuinely earlier signal than anything "
      "derivable from public filings.",
      "Specter's cross-channel growth history is deeper on consumer and SaaS traction.",
      "Inven's multilingual website reading is stronger for mid-market and M&A search."]),
    ("How they fit together",
     ["The honest answer is that most funds run a stack. FastVC is designed to be the "
      "workflow and reasoning layer on top of whichever sourcing index you trust.",
      "Connect a specialist sourcing feed for earliest-signal coverage; keep Affinity "
      "or Attio as the relationship system of record.",
      "Use FastVC where those tools stop — the modelling, diligence, IC and LP work "
      "that still happens in spreadsheets and documents.",
      "Everything is reachable over API and MCP so the squad can read from all of it."]),
]


@rt("/compare")
def compare(sess):
    lang = get_lang(sess)
    return page(
        t("nav_compare", lang),
        Section_(
            Eyebrow("Comparison"),
            Heading(1, "The open-source alternative to closed sourcing platforms.",
                    cls="mt-4 max-w-4xl"),
            P("This compares FastVC against the early / signal-based deal sourcing and "
              "company discovery category. Every alternative below is proprietary SaaS "
              "running on a vendor's infrastructure; FastVC is Apache 2.0 and runs on yours. "
              "Financial-depth databases and relationship CRMs do a different job — they "
              "appear in the gap analysis as complements, not rivals.",
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            Div(
                A("★ Apache 2.0 on GitHub ↗", href=GITHUB_URL, target="_blank",
                  rel="noopener noreferrer",
                  cls="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs "
                      "font-medium text-accent border border-accent/40 hover:bg-accent/5 "
                      "transition-colors no-underline"),
                cls="mt-8",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                Table(
                    Thead(Tr(
                        Th("", cls="text-left p-4 text-xs font-mono uppercase tracking-widest text-ink-dim"),
                        *[Th(c, cls=("text-left p-4 text-sm font-medium " +
                                     ("text-accent" if c == "FastVC" else "text-ink")))
                          for c in COMPARE_COLS],
                    )),
                    Tbody(*[Tr(
                        Th(row[0], cls="text-left p-4 align-top text-sm font-medium text-ink whitespace-nowrap"),
                        *[Td(cell, cls=("p-4 align-top text-sm leading-relaxed " +
                                        ("text-ink bg-accent/5" if i == 0 else "text-ink-muted")))
                          for i, cell in enumerate(row[1:])],
                        cls="border-t border-line",
                    ) for row in COMPARE_ROWS]),
                    cls="w-full min-w-[64rem] border-collapse",
                ),
                cls="overflow-x-auto rounded-2xl border border-line bg-bg-elevated",
            ),
            P("Competitor details reflect publicly published positioning as of August 2026 "
              "and change often — treat them as a starting point, not a datasheet.",
              cls="mt-4 text-ink-dim text-xs"),
            cls="border-t border-line",
        ),
        Section_(
            Eyebrow("Gap analysis"),
            Heading(2, "An honest read of the trade-offs.", cls="mt-4 max-w-3xl"),
            Div(
                *[Article(
                    P(title, cls="text-ink font-medium mb-4"),
                    Ul(*[Li(
                        Span("• ", cls="text-accent mr-2"),
                        Span(point, cls="text-ink-muted text-sm leading-relaxed"),
                        cls="mb-3 flex items-baseline",
                    ) for point in points]),
                    cls="p-6 rounded-2xl border border-line bg-bg-elevated h-full",
                ) for title, points in GAP_ROWS],
                cls="grid md:grid-cols-3 gap-4 mt-10",
            ),
            cls="border-t border-line",
        ),
        CTASection(lang=lang),
        current_path="/compare",
        lang=lang,
    )


# ── /contact ─────────────────────────────────────────────────────────
@rt("/contact")
def contact(sess, sent: bool = False):
    lang = get_lang(sess)
    form = Form(
        Div(
            Label(t("contact_name", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="name", type="text", required=True,
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_email", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="email", type="email", required=True,
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_firm", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="firm", type="text",
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_pipeline", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Textarea(name="message", rows="5", required=True,
                     cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-8",
        ),
        Button(t("contact_send", lang), type="submit",
               cls="inline-flex items-center gap-2 px-5 py-3 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all"),
        method="post",
        action="/contact",
    )

    success = Div(
        Div(
            Span("✓", cls="text-accent text-2xl"),
            cls="mb-4",
        ),
        H3(t("contact_thanks", lang), cls="text-ink text-xl mb-2"),
        P(t("contact_usually", lang), cls="text-ink-muted"),
        cls="p-8 rounded-2xl bg-bg-elevated border border-line",
    )

    return page(
        t("contact_eyebrow", lang),
        Section_(
            Eyebrow(t("contact_eyebrow", lang)),
            Heading(1, t("contact_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("contact_body", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            Div(
                success if sent else form,
                cls="mt-12 max-w-xl",
            ),
            cls="border-t border-line",
        ),
        current_path="/contact",
        lang=lang,
    )


@rt("/contact", methods=["POST"])
def contact_post(sess, name: str = "", email: str = "", firm: str = "", message: str = ""):
    lang = get_lang(sess)
    import logging
    logging.getLogger(__name__).info("contact form submitted: %s (%s) %s chars",
                                     name, email, len(message or ""))
    return page(
        t("contact_thanks", lang),
        Section_(
            Eyebrow(t("contact_eyebrow", lang)),
            Heading(1, t("contact_thanks", lang), cls="mt-4 max-w-4xl"),
            P(t("contact_usually", lang), " ", t("contact_meanwhile", lang),
              A(t("contact_open_app", lang), href="/signin", cls="text-accent underline"),
              t("contact_byod_post", lang),
              cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        current_path="/contact",
        lang=lang,
    )
