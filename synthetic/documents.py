"""Synthetic venture diligence documents for RAG indexing."""

from __future__ import annotations

import random
from datetime import date


def metrics_pack(company: dict, rng: random.Random) -> str:
    arr = float(company["arr"])
    return f"""# Operating Metrics Pack — {company['name']}

**As of:** {date.today().isoformat()}
**Stage:** {company['startup_stage'].replace('_', ' ').title()}
**Currency:** USD

## Headline metrics
- ARR: ${arr:,.0f}
- YoY ARR growth: {company['growth_rate']:.1f}%
- Gross margin: {company['gross_margin']:.1f}%
- Net revenue retention: {company['net_retention']:.1f}%
- Gross revenue retention: {company['gross_retention']:.1f}%
- Monthly net burn: ${float(company['net_burn']):,.0f}
- Runway: {company['runway_months']:.1f} months
- Burn multiple: {company['burn_multiple']:.2f}x

## Metric definitions
ARR is recurring subscription revenue under active contracts, excluding
services, usage above committed minimums and unsigned pipeline. NRR compares
the same opening customer cohort after churn, contraction and expansion.
Monthly net burn is average cash outflow over the latest three closed months.

## Cohort and concentration notes
The top customer represents {rng.randint(7, 19)}% of ARR and the top five
represent {rng.randint(25, 48)}%. Latest-quarter logo retention was
{rng.randint(88, 98)}%. {"One enterprise renewal is under active negotiation and should be treated as at risk." if rng.random() < .35 else "No individually material renewal is currently flagged by management."}

## Data-quality checks
- Billing reconciles to the ARR bridge within {rng.uniform(.2, 1.8):.1f}%.
- Bookings and TCV are reported separately from ARR.
- Management has supplied {rng.randint(12, 30)} months of monthly history.
- Verify cohort definitions and foreign-exchange treatment before IC.
"""


def legal_dd(company: dict, rng: random.Random) -> str:
    open_issue = rng.random() < .3
    return f"""# Legal, IP & Regulatory Diligence — {company['name']}

**Counsel:** Harrison Whitmore LLP
**Date:** {date.today().isoformat()}

## Corporate and financing
Formation records, board minutes, shareholder approvals and the stock ledger
were reviewed against the fully diluted cap table. {"Two historical option grants require confirmatory board approval." if open_issue else "No material reconciliation exception was identified."}

## Intellectual property
Founder and employee invention assignments are on file. Contractor assignments
were sampled; {rng.randint(85, 100)}% of the sample contained present-tense IP
assignment language. Open-source dependencies require the normal software-bill-
of-materials review before closing.

## Employment, privacy and regulation
The company uses standard confidentiality and invention-assignment agreements.
Privacy terms cover GDPR and applicable US state law. {"A product workflow may require specialist healthcare or payments regulatory analysis." if company['sector'] in {'healthtech', 'fintech'} else "No sector-specific licence gap has been identified from the supplied evidence."}

## Material contracts
{rng.randint(1, 5)} customer contracts contain assignment or change-of-control
notice provisions. No clause should be treated as requiring consent until
confirmed against the executed agreement.

## Open items
- Reconcile all SAFEs, notes, warrants and the option reserve.
- Confirm board and shareholder authority for the proposed financing.
- Complete founder, employee and contractor IP chain-of-title review.
- Verify privacy, security and regulated-product claims with specialists.
"""


def product_gtm(company: dict, rng: random.Random) -> str:
    return f"""# Product & Go-to-Market Diligence — {company['name']}

## Product evidence
The product addresses {company['sub_sector'].lower()} workflows. Management
provided roadmap, usage and customer-reference evidence. Weekly active use is
reported across {rng.randint(58, 91)}% of contracted accounts, with the most
adopted workflow used by {rng.randint(45, 82)}% of active seats.

## Customer evidence
The diligence team completed {rng.randint(4, 9)} reference calls. Customers
most often cited time-to-value and workflow depth; the recurring objections
were implementation effort and integration coverage. Reported gross retention
is {company['gross_retention']:.1f}% and NRR is {company['net_retention']:.1f}%.

## Go-to-market
The company has {company['employees']} employees. Sales motion is
{rng.choice(['founder-led with early repeatability', 'moving from founder-led to a first sales team', 'segmented across mid-market and enterprise'])}.
Pipeline coverage is {rng.uniform(2.1, 4.6):.1f}x the next-quarter target.

## Tests before IC
- Reconcile CRM stages to signed contracts and invoiced ARR.
- Interview at least one churned customer and one implementation partner.
- Review win/loss evidence against the three closest alternatives.
- Test whether sales-cycle and expansion assumptions support the operating plan.
"""


def tech_ddq(company: dict, rng: random.Random) -> str:
    return f"""# Technology & Security DDQ — {company['name']}

## Architecture
The primary application uses {rng.choice(['Python and TypeScript', 'Go and React', 'Java and TypeScript', 'Rust and Python'])}
with {rng.choice(['PostgreSQL', 'CockroachDB', 'DynamoDB'])}. Infrastructure is
deployed on {rng.choice(['AWS', 'GCP', 'Azure'])} using infrastructure as code.
CI/CD runs through GitHub Actions with peer review and automated tests.

## Engineering
The company reports {max(3, int(company['employees'] * rng.uniform(.35, .65)))}
engineers. Technical debt is {rng.choice(['moderate', 'typical for company stage', 'below the stage benchmark'])}.
The principal scaling concern is {rng.choice(['data-pipeline observability', 'tenant isolation', 'model inference cost', 'release-process maturity'])}.

## Security and privacy
- SOC 2: {rng.choice(['Type II complete', 'Type I complete; Type II in progress', 'readiness work in progress'])}
- Annual penetration test: {rng.choice(['complete with no open high findings', 'scheduled', 'evidence requested'])}
- Encryption: in transit and at rest for production data
- Incident response and access review: evidence supplied, sample testing pending

## AI and data dependencies
Model providers, training-data rights, prompt/data boundaries, evaluation and
fallback behaviour require explicit verification. Third-party model pricing and
availability should be included in gross-margin sensitivity.
"""


def pitch_deck(company: dict, rng: random.Random) -> str:
    return f"""# Investor Deck Summary — {company['name']}

## Company
{company['description']}

## Team
The founding team combines {rng.choice(['technical research and enterprise software', 'regulated-industry and product', 'developer tooling and go-to-market'])}
experience. Management highlights speed of product iteration and access to
early design partners as its founder-market-fit evidence.

## Traction
- ARR: ${float(company['arr']) / 1_000_000:.1f}M
- YoY growth: {company['growth_rate']:.0f}%
- Gross margin: {company['gross_margin']:.0f}%
- NRR: {company['net_retention']:.0f}%
- Customers or active accounts: {rng.randint(12, 180)}

## Financing
The company is at {company['startup_stage'].replace('_', ' ')} and is
{company['fundraising_status'].replace('_', ' ')}. Its last round was
${float(company['last_round_amount']) / 1_000_000:.1f}M. Management's proposed
use of funds is product and engineering, go-to-market hiring, and runway to the
next stage milestone.

## Claims requiring diligence
- Market size, competitive differentiation and product usage
- ARR, retention and customer concentration
- Fully diluted cap table and financing instruments
- Hiring plan, burn, runway and next-round milestones
"""


def industry_report(sector: str, sub_sector: str, rng: random.Random) -> str:
    return f"""# Venture Market Map — {sector.title()} / {sub_sector}

**Date:** {date.today().isoformat()}

## Market
The category contains a mix of formation-stage startups, early revenue
companies and scaled challengers. Current investor attention is
{rng.choice(['accelerating', 'selective', 'concentrated around category leaders'])}.

## Venture benchmarks
- Median Seed round: ${rng.uniform(2.0, 5.5):.1f}M
- Median Series A round: ${rng.uniform(8.0, 18.0):.1f}M
- Illustrative post-money / ARR range: {rng.uniform(6, 10):.1f}x–{rng.uniform(14, 24):.1f}x
- Typical runway raised for: {rng.randint(16, 24)} months

## Themes
- Founder and key-hire movement remains an early company-formation signal.
- Investors are rewarding efficient growth and evidence of repeatable demand.
- Financing dispersion is wide; stage, growth, retention and market structure
  matter more than a single headline multiple.

## Evidence warning
These are synthetic research benchmarks for product demonstration. Validate
live financing and company claims against dated primary sources before IC.
"""


def generate_all_for_property(company: dict, rng: random.Random) -> list[dict]:
    """Compatibility entry point returning venture DD documents."""
    return [
        {"title": f"Investor Deck — {company['name']}", "doc_type": "pitch_deck",
         "text": pitch_deck(company, rng)},
        {"title": f"Metrics Pack — {company['name']}", "doc_type": "metrics",
         "text": metrics_pack(company, rng)},
        {"title": f"Legal, IP & Regulatory — {company['name']}", "doc_type": "legal",
         "text": legal_dd(company, rng)},
        {"title": f"Product & GTM — {company['name']}", "doc_type": "product_gtm",
         "text": product_gtm(company, rng)},
        {"title": f"Technology & Security — {company['name']}", "doc_type": "tech_ddq",
         "text": tech_ddq(company, rng)},
    ]


def generate_market_reports(companies: list[dict], rng: random.Random) -> list[dict]:
    pairs = sorted({(c["sector"], c["sub_sector"]) for c in companies})
    return [
        {
            "title": f"{sector.title()} / {sub} Venture Market Map — {date.today().year}",
            "doc_type": "industry",
            "text": industry_report(sector, sub, rng),
        }
        for sector, sub in pairs
    ]
