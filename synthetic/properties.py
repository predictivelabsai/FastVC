"""Deterministic synthetic startup universe for FastVC demos and tests."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, timedelta


HQ = [
    ("San Francisco", "CA", "USA"), ("New York", "NY", "USA"),
    ("Boston", "MA", "USA"), ("Austin", "TX", "USA"), ("London", "", "GBR"),
    ("Berlin", "", "DEU"), ("Paris", "", "FRA"), ("Tallinn", "", "EST"),
    ("Helsinki", "", "FIN"), ("Stockholm", "", "SWE"), ("Amsterdam", "", "NLD"),
]
SECTORS = {
    "enterprise_ai": ["AI Infrastructure", "Vertical AI", "Agent Platforms", "MLOps"],
    "devtools": ["Developer Productivity", "Observability", "Cybersecurity", "Data Infrastructure"],
    "fintech": ["Payments", "Treasury", "Risk", "Embedded Finance"],
    "healthtech": ["Clinical Workflow", "Digital Health", "Bioinformatics", "Care Navigation"],
    "climate": ["Carbon Software", "Grid Intelligence", "Industrial Decarbonisation", "Climate Fintech"],
    "consumer": ["Consumer Subscription", "Marketplace", "Creator Tools", "Future of Work"],
    "deeptech": ["Robotics", "Semiconductors", "Advanced Materials", "Space Infrastructure"],
}
STAGES = ["stealth", "pre_seed", "seed", "series_a", "series_b", "series_c", "growth"]
PIPELINE = [
    "discovered", "screened", "first_meeting", "partner_meeting", "diligence",
    "ic", "term_sheet", "invested", "follow_on", "exited", "passed",
]
BUSINESS_MODELS = ["b2b_saas", "usage_based", "marketplace", "fintech", "consumer", "hardware"]
PREFIX = ["Northwind", "Axiom", "Lumen", "Meridian", "Cascade", "Orbital", "Arc",
          "Sentinel", "Verdant", "Parallax", "Pioneer", "Quantum", "Vertex", "Helix"]
SUFFIX = ["AI", "Labs", "Cloud", "Works", "Systems", "Health", "Flow", "Grid", "Stack", "One"]

STAGE_PROFILE = {
    "stealth":   (0, 0, 6, 0, 3_000_000, 9),
    "pre_seed":  (0, 300_000, 9, 500_000, 5_000_000, 12),
    "seed":      (250_000, 2_500_000, 18, 2_500_000, 14_000_000, 16),
    "series_a":  (1_500_000, 8_000_000, 45, 10_000_000, 40_000_000, 18),
    "series_b":  (6_000_000, 25_000_000, 110, 30_000_000, 110_000_000, 20),
    "series_c":  (18_000_000, 70_000_000, 260, 75_000_000, 260_000_000, 22),
    "growth":    (50_000_000, 180_000_000, 650, 180_000_000, 700_000_000, 24),
}


@dataclass
class Startup:
    slug: str
    name: str
    hq_city: str
    hq_state: str
    country: str
    sector: str
    sub_sector: str
    startup_stage: str
    business_model: str
    website: str
    founded_year: int
    employees: int
    revenue_ltm: float
    ebitda_ltm: float
    ebitda_margin: float
    growth_rate: float
    arr: float
    mrr: float
    gross_margin: float
    net_burn: float
    runway_months: float
    burn_multiple: float
    net_retention: float
    gross_retention: float
    total_funding: float
    last_round_date: str
    last_round_type: str
    last_round_amount: float
    pre_money_valuation: float
    post_money_valuation: float
    target_check_size: float
    target_ownership_pct: float
    fundraising_status: str
    momentum_score: float
    thesis_score: float
    ownership: str
    deal_stage: str
    deal_type: str
    enterprise_value: float
    ask_multiple: float
    description: str
    seller_intent: str
    triage_score: float
    triage_priority: str


def _slug(name: str, used: set[str]) -> str:
    base = "".join(c for c in name.lower().replace(" ", "-") if c.isalnum() or c == "-")
    candidate = base
    i = 2
    while candidate in used:
        candidate = f"{base}-{i}"
        i += 1
    used.add(candidate)
    return candidate


def _make(name: str, stage: str, sector: str, sub_sector: str, city: str,
          state: str, country: str, rng: random.Random, used: set[str],
          deal_stage: str | None = None) -> Startup:
    arr_lo, arr_hi, headcount, funding, valuation, runway_base = STAGE_PROFILE[stage]
    arr = round(rng.uniform(arr_lo, max(arr_lo + 1, arr_hi)), -3) if arr_hi else 0
    if stage == "stealth":
        arr = 0
    growth = round(rng.uniform(35, 220) if stage in {"pre_seed", "seed", "series_a"}
                   else rng.uniform(22, 110), 1)
    gross_margin = round(rng.uniform(68, 91) if sector not in {"deeptech", "climate"}
                         else rng.uniform(38, 68), 1)
    annual_burn = round(max(500_000, arr * rng.uniform(.35, 1.7) + funding * .08), -3)
    net_burn = round(annual_burn / 12, -2)
    net_new_arr = max(arr * growth / max(100 + growth, 1), 100_000)
    burn_multiple = round(annual_burn / net_new_arr, 2)
    runway = round(max(4, runway_base + rng.uniform(-4, 6)), 1)
    post = round(valuation * rng.uniform(.72, 1.35), -4)
    round_amount = round(max(750_000, post * rng.uniform(.08, .23)), -4)
    pre = max(500_000, post - round_amount)
    total_funding = round(max(funding, round_amount * rng.uniform(1, 2.2)), -4)
    target_ownership = round(rng.uniform(8, 20), 1)
    target_check = round(post * target_ownership / 100, -4)
    momentum = round(min(100, 35 + growth * .22 + max(0, 18 - burn_multiple * 3)
                         + rng.uniform(-8, 12)), 1)
    thesis = round(rng.uniform(58, 96), 1)
    score = round((momentum * .45 + thesis * .55) / 20, 2)
    priority = "High" if score >= 4 else "Medium" if score >= 3 else "Low"
    pipeline = deal_stage or rng.choice(PIPELINE)
    fundraising = rng.choices(
        ["not_raising", "preparing", "raising", "closing", "recently_funded"],
        weights=[2, 2, 5, 2, 2],
    )[0]
    heat = "hot" if fundraising in {"raising", "closing"} and momentum >= 70 else "warm" if momentum >= 55 else "cold"
    founded = date.today().year - {"stealth": 0, "pre_seed": 1, "seed": 2, "series_a": 4,
                                   "series_b": 6, "series_c": 8, "growth": 11}[stage]
    round_date = date.today() - timedelta(days=rng.randint(30, 900))
    # Keep the legacy margin compatibility column inside NUMERIC(5,2).
    # Burn and runway are the meaningful venture-native measures pre-profit.
    margin = round(max(-999.0, -annual_burn / max(arr, 1) * 100), 1) if arr else -100.0
    ev_arr = round(post / max(arr, 1), 2) if arr else 0
    slug = _slug(name, used)
    return Startup(
        slug, name, city, state, country, sector, sub_sector, stage,
        rng.choice(BUSINESS_MODELS), f"https://{slug.replace('-', '')}.example",
        founded, max(3, int(headcount * rng.uniform(.65, 1.45))),
        arr, -annual_burn, margin, growth, arr, round(arr / 12, 2),
        gross_margin, net_burn, runway, burn_multiple,
        round(rng.uniform(100, 145), 1), round(rng.uniform(82, 98), 1),
        total_funding, round_date.isoformat(), stage, round_amount, pre, post,
        target_check, target_ownership, fundraising, momentum, thesis,
        rng.choice(["founder_owned", "angel_backed", "vc_backed", "accelerator"]),
        pipeline, rng.choice(["primary", "primary", "safe", "convertible_note", "secondary"]),
        post, ev_arr,
        (f"{name} is a {stage.replace('_', ' ')} {sub_sector.lower()} startup in {city}. "
         f"It has ${arr/1_000_000:.1f}M ARR, {growth:.0f}% growth, {runway:.0f} months runway "
         f"and a {burn_multiple:.1f}x burn multiple. Pipeline stage: {pipeline.replace('_', ' ')}."),
        heat, score, priority,
    )


def generate(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    used: set[str] = set()
    rows = [
        _make("Northwind AI", "series_a", "enterprise_ai", "Vertical AI",
              "Tallinn", "", "EST", rng, used, "diligence"),
        _make("Meridian Health", "seed", "healthtech", "Clinical Workflow",
              "London", "", "GBR", rng, used, "ic"),
    ]
    for i in range(48):
        stage = STAGES[i % len(STAGES)]
        sector = list(SECTORS)[i % len(SECTORS)]
        city, state, country = rng.choice(HQ)
        name = f"{rng.choice(PREFIX)} {rng.choice(SUFFIX)}"
        rows.append(_make(name, stage, sector, rng.choice(SECTORS[sector]),
                          city, state, country, rng, used))
    return [asdict(row) for row in rows]
