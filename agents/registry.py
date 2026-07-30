"""Registry for the FastVC specialist agent squad.

Module slugs stay compatible with the PEHero-derived implementation while the
public names, routing prefixes and prompts are venture-native.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    slug: str
    name: str
    category: str
    icon: str
    one_liner: str
    description: str
    prefix: str
    example_prompts: tuple[str, ...] = field(default_factory=tuple)


CATEGORIES = [
    {"key": "sourcing", "name": "Discovery & Sourcing",
     "blurb": "Find exceptional startups and founders before the round becomes consensus.", "icon": "◉"},
    {"key": "underwriting", "name": "Round & Ownership",
     "blurb": "Turn startup metrics and round terms into an ownership and outcome view.", "icon": "◈"},
    {"key": "diligence", "name": "Venture Diligence",
     "blurb": "Test team, product, market, technology, legal and commercial evidence.", "icon": "◆"},
    {"key": "capital", "name": "IC & LP Relations",
     "blurb": "Move from conviction to IC, co-investor communication and LP fundraising.", "icon": "◐"},
    {"key": "asset_mgmt", "name": "Portfolio Support",
     "blurb": "Help portfolio companies improve growth, efficiency, hiring and retention.", "icon": "◼"},
]


def A(slug, name, category, icon, prefix, one_liner, description, *prompts):
    return AgentSpec(slug, name, category, icon, one_liner, description, prefix, tuple(prompts))


AGENTS = (
    A("market_scanner", "Startup Discovery", "sourcing", "⌕", "discover:",
      "Thesis-driven startup and founder discovery with explainable matches.",
      "Searches the startup universe by stage, sector, geography, founder background, momentum and fund criteria.",
      "discover: European AI infrastructure startups at Seed or Series A",
      "Find stealth founders leaving frontier-model labs",
      "Show climate software companies with accelerating engineering hiring"),
    A("deal_triage", "Startup Screener", "sourcing", "✓", "screen:",
      "Fast go/deepen/pass screening against the fund thesis.",
      "Scores fund fit, founder-market fit, differentiation, traction, capital efficiency, round and key risks.",
      "screen: Northwind AI, Seed, $1.8M ARR, 120% growth, raising $6M",
      "Should we take a first meeting with Meridian Health?",
      "What evidence is missing before partner meeting?"),
    A("comp_finder", "Venture Comps", "sourcing", "≡", "comps:",
      "Comparable rounds, public peers and outcome benchmarks.",
      "Builds relevant financing and operating comps by stage, business model, growth and geography.",
      "comps: Series A vertical AI companies in Europe",
      "Benchmark ARR multiples for growth-stage cybersecurity",
      "Find comparable rounds for a $4M ARR developer-tools company"),
    A("seller_intent", "Fundraising Signal", "sourcing", "∿", "signal:",
      "Ranks startups by fundraising readiness and momentum.",
      "Combines runway, team movement, key hires, product launches, growth and financing history into explainable signals.",
      "signal: companies likely to raise Series A in the next six months",
      "Which portfolio-adjacent startups just hired a first CFO?",
      "Show strong founder moves in applied AI"),
    A("outreach_email", "Founder Outreach", "sourcing", "✉", "outreach:",
      "Personalized, thesis-led founder outreach.",
      "Drafts concise outreach grounded in the founder, product, market and a credible reason to meet.",
      "outreach: write to the founder of Northwind AI",
      "Draft a warm-intro request through a portfolio CEO",
      "Follow up after a first meeting without sounding generic"),
    A("outreach_sequencer", "Outreach Sequencer", "sourcing", "↗", "sequence:",
      "Multi-touch founder, co-investor and LP sequences.",
      "Plans thoughtful sequences and can hand them to Brevo, Attio, Affinity or Pipedrive when configured.",
      "sequence: three-touch founder sequence for a stealth AI company",
      "Create an LP re-engagement sequence for Fund III",
      "Plan follow-ups after a partner meeting"),
    A("loi_writer", "Term Sheet Drafter", "sourcing", "✍", "terms:",
      "Investment term-sheet first drafts and issue lists.",
      "Drafts a non-binding venture term sheet covering economics, governance, closing and diligence items for counsel review.",
      "terms: $5M Series A at $20M pre-money for 20% post",
      "Draft a SAFE side-letter issue list",
      "Compare 1x non-participating and participating preference outcomes"),

    A("rent_roll_parser", "Cap Table Parser", "underwriting", "☰", "cap:",
      "Any cap table into fully diluted ownership and preference layers.",
      "Normalizes shares, options, warrants, SAFEs, notes and preferences and flags reconciliation gaps.",
      "cap: calculate fully diluted ownership after a $6M Series A",
      "Model the option-pool shuffle pre-money",
      "Show SAFE and note conversion at the proposed price"),
    A("t12_normalizer", "Startup Metrics Normalizer", "underwriting", "∑", "metrics:",
      "Messy operating data into investor-grade startup metrics.",
      "Normalizes MRR, ARR, retention, margin, CAC, burn, runway, cohorts and headcount with period consistency checks.",
      "metrics: normalize Northwind's monthly SaaS metrics",
      "Calculate burn multiple and runway",
      "Reconcile bookings, revenue and ARR"),
    A("pro_forma_builder", "Round & Ownership Modeler", "underwriting", "▤", "round:",
      "Round construction, dilution, pro rata and ownership scenarios.",
      "Models pre/post-money, primary and secondary, option pool, investor allocations and follow-on dilution.",
      "round: model $8M Series A at $32M pre-money",
      "What check gets us to 15% ownership?",
      "Show dilution through Series C with pro rata"),
    A("debt_stack_modeler", "Financing Strategy", "underwriting", "▥", "finance:",
      "Equity, SAFE, note, venture debt and runway trade-offs.",
      "Compares financing instruments and their ownership, cash runway, covenant and refinancing implications.",
      "finance: compare a SAFE, priced seed and venture debt",
      "How much runway does a $4M raise buy?",
      "Model a bridge before Series B"),
    A("return_metrics", "Venture Outcome Model", "underwriting", "◈", "outcomes:",
      "Probability-weighted ownership, proceeds, MOIC and IRR.",
      "Builds downside, base and upside exit cases with reserves, follow-ons and future dilution.",
      "outcomes: model our Seed check through a Series C exit",
      "What exit value returns the fund?",
      "Show ownership and proceeds with and without pro rata"),

    A("doc_room_auditor", "Data Room Auditor", "diligence", "☷", "vdr:",
      "Checks the data room against stage-appropriate venture diligence.",
      "Flags missing, stale and inconsistent corporate, financial, product, security, customer and financing evidence.",
      "vdr: audit Northwind's Series A data room",
      "What is missing before IC?",
      "Cross-check the deck, KPI file and cap table"),
    A("lease_abstractor", "Contract Abstractor", "diligence", "▢", "contracts:",
      "Customer and commercial contracts into cited key terms.",
      "Extracts value, term, renewal, termination, assignment, data, IP and change-of-control provisions.",
      "contracts: abstract the top ten enterprise MSAs",
      "Show customer concentration and termination exposure",
      "Find IP assignment gaps"),
    A("title_zoning", "Legal, IP & Regulatory", "diligence", "◰", "legal:",
      "Corporate, IP, employment, privacy and regulatory issue spotting.",
      "Reviews formation, securities, IP chain of title, employment, litigation, privacy and regulated-product evidence.",
      "legal: summarize Series A legal risks",
      "Check founder and contractor IP assignment",
      "What consents are required to close?"),
    A("physical_condition", "Product & GTM Diligence", "diligence", "⌂", "product:",
      "Tests product evidence, customers, positioning and go-to-market repeatability.",
      "Synthesizes product usage, references, roadmap, pipeline, win/loss and sales efficiency into testable findings.",
      "product: assess product-market fit for Northwind",
      "Build a customer-reference interview plan",
      "Is the GTM motion repeatable yet?"),
    A("environmental_risk", "Technology & Security Risk", "diligence", "⚠", "tech:",
      "Architecture, AI, security, data and technical-team diligence.",
      "Reviews system architecture, model dependencies, security posture, privacy, technical debt and engineering execution.",
      "tech: review Northwind's AI architecture risks",
      "Assess SOC 2 readiness and data boundaries",
      "Where is the product dependent on third-party models?"),

    A("investor_memo", "IC Memo Writer", "capital", "✎", "memo:",
      "A concise venture IC memo grounded in evidence.",
      "Drafts thesis, team, product, market, traction, round, ownership, outcomes, risks and open questions.",
      "memo: draft the Series A IC memo for Northwind AI",
      "Write the team and market sections only",
      "Turn our diligence findings into an IC pre-read"),
    A("deal_teaser", "Deal Brief", "capital", "✦", "brief:",
      "One-page opportunity and co-investor brief.",
      "Creates a decision-oriented snapshot of the company, round, thesis, metrics, ownership and risks.",
      "brief: create a one-page Northwind deal brief",
      "Draft a co-investor summary",
      "Summarize this opportunity for Monday partner meeting"),
    A("lp_update", "LP Update Generator", "capital", "⇄", "lpupdate:",
      "Quarterly LP updates from fund and portfolio evidence.",
      "Drafts portfolio progress, investments, exits, valuations, reserves, DPI/TVPI and market commentary.",
      "lpupdate: draft Q2 Fund III update",
      "Summarize new investments and follow-ons",
      "Explain the change in TVPI and DPI"),
    A("fundraising_crm", "LP Fundraising Copilot", "capital", "◎", "lpcrm:",
      "Ranks LP prospects and recommends the next relationship action.",
      "Uses mandate fit, relationship path, engagement, timing, check size and staleness across family offices and institutions.",
      "lpcrm: top family offices to contact for Fund IV",
      "Prepare for an endowment first meeting",
      "Draft a re-engagement note to stale qualified LPs"),

    A("rent_optimization", "Pricing & Monetization", "asset_mgmt", "↗", "pricing:",
      "Pricing, packaging and expansion recommendations.",
      "Uses willingness-to-pay, cohorts, usage, contract and competitive evidence to identify monetization opportunities.",
      "pricing: assess Northwind's usage-based pricing",
      "Where is enterprise packaging leaving money on the table?",
      "Model a pricing change with churn sensitivity"),
    A("opex_variance", "KPI, Burn & Runway Watcher", "asset_mgmt", "Δ", "burn:",
      "Surfaces operating misses and runway risks early.",
      "Tracks ARR, growth, margin, burn, runway, hiring and plan variance across the portfolio.",
      "burn: which companies have under 12 months runway?",
      "What drove Northwind's burn multiple deterioration?",
      "Show portfolio companies missing ARR plan"),
    A("capex_prioritizer", "Portfolio Support Prioritizer", "asset_mgmt", "⚒", "support:",
      "Ranks hiring, GTM, product, capital and operating support actions.",
      "Prioritizes portfolio requests by company impact, urgency, fund leverage and execution effort.",
      "support: rank open portfolio support requests",
      "Should we prioritize a VP Sales search or pricing project?",
      "Which introductions would have the highest impact?"),
    A("tenant_churn", "Retention & Expansion", "asset_mgmt", "∠", "retention:",
      "Cohort, logo and revenue-retention diagnosis.",
      "Finds at-risk accounts and cohorts, expansion potential and the product or success actions most likely to help.",
      "retention: diagnose Northwind's NRR decline",
      "Which cohorts are failing to activate?",
      "Estimate ARR at risk in the next two quarters"),
)

AGENTS_BY_SLUG = {a.slug: a for a in AGENTS}
AGENTS_BY_CATEGORY: dict[str, list[AgentSpec]] = {}
for agent in AGENTS:
    AGENTS_BY_CATEGORY.setdefault(agent.category, []).append(agent)


def all_agents():
    return AGENTS


def by_slug(slug: str):
    return AGENTS_BY_SLUG.get(slug)
