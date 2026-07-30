"""Venture financing and public-company comps per startup."""

from __future__ import annotations

import random
from datetime import date, timedelta


VENTURE_INVESTORS = [
    "Northstar Ventures", "Foundry Capital", "Altitude", "Seedline",
    "Operator Fund", "Frontier Angels", "Arc Ventures", "Firstminute",
    "Balderton", "Index Ventures", "Atomico", "Accel", "General Catalyst",
    "Lightspeed", "Bessemer", "Insight Partners", "Coatue", "Eurazeo",
]
STRATEGIC_ACQUIRERS = [
    "Oracle", "Salesforce", "Microsoft", "IBM", "ServiceNow", "Adobe",
    "Siemens", "Emerson", "Honeywell", "Parker Hannifin", "Roper Technologies",
    "UnitedHealth", "HCA Healthcare", "CVS Health", "Stryker", "Medtronic",
    "Clorox", "Procter & Gamble", "Nestle", "Pepsico",
]

TARGETS_BY_SECTOR = {
    "enterprise_ai": ["AppWorks", "DataPrism", "Clarion AI", "Dataflow Labs", "NovaSoft",
                 "Acuity Analytics", "Stellar SaaS", "Crestwave", "Vantedge", "Beacon AI"],
    "devtools": ["BuildLayer", "TraceStack", "CodeArc", "Runtime Labs", "Shipyard Cloud"],
    "fintech": ["LedgerFlow", "TreasuryOne", "RiskPilot", "PayArc", "Vault Systems"],
    "healthtech": ["ClearPath Health", "Hampton Medical", "Northfield Care", "Pine Valley Health",
                   "Summit Specialty", "Meadowbrook Health"],
    "climate": ["GridPilot", "CarbonArc", "Verdant Systems", "Industrial Zero", "TerraFlow"],
    "consumer": ["Riverbend Brands", "Harbor Kitchen", "Fieldhouse Goods", "Wildroot Co"],
    "deeptech": ["Orbital Works", "Quantum Foundry", "Vector Robotics", "Helix Materials"],
}


def _sector_multiple(sector: str, rng: random.Random) -> float:
    base = {
        "enterprise_ai": 18.0, "devtools": 14.0, "fintech": 11.0,
        "healthtech": 10.0, "climate": 8.0, "consumer": 7.0, "deeptech": 9.0,
    }[sector]
    return round(base + rng.uniform(-2.5, 3.5), 2)


def generate_sales_comps(company: dict, rng: random.Random, count: int = 6) -> list[dict]:
    """Comparable venture rounds stored in the compatibility comps table."""
    return generate_transaction_comps(company, rng, count)


def generate_transaction_comps(company: dict, rng: random.Random, count: int = 6) -> list[dict]:
    sector = company["sector"]
    sub = company["sub_sector"]
    target_names = TARGETS_BY_SECTOR.get(sector, ["Acme Co"])
    rows = []
    for _ in range(count):
        delta_days = rng.randint(30, 900)
        announce_date = date.today() - timedelta(days=delta_days)
        close_date = announce_date + timedelta(days=rng.randint(30, 180))
        target_rev = rng.uniform(max(250_000, company["arr"] * .35), max(2_000_000, company["arr"] * 1.8))
        ev_rev = _sector_multiple(sector, rng)
        ev = target_rev * ev_rev
        target_ebitda = -target_rev * rng.uniform(.2, 1.2)
        ev_ebitda = None
        ev_rev = ev / target_rev
        deal_type = rng.choice(["seed", "series_a", "series_b", "series_c", "growth"])
        acquirer = rng.choice(VENTURE_INVESTORS)

        rows.append({
            "target_name": rng.choice(target_names),
            "acquirer": acquirer,
            "sector": sector,
            "sub_sector": sub,
            "country": company["country"],
            "announce_date": announce_date.isoformat(),
            "close_date": close_date.isoformat(),
            "enterprise_value": round(ev, 2),
            "revenue": round(target_rev, 2),
            "ebitda": round(target_ebitda, 2),
            "ev_revenue": round(ev_rev, 2),
            "ev_ebitda": ev_ebitda,
            "deal_type": deal_type,
            "source": rng.choice(["PitchBook", "Crunchbase", "Company announcement", "Press release"]),
        })
    return rows


# Back-compat wrapper used by synthetic/generate._insert_comps
def generate_rent_comps(company: dict, rng: random.Random, count: int = 6) -> list[dict]:
    """Trading comps (public peers) for the company's sector. Stored in fastvc.trading_comps."""
    return generate_trading_comps(company, rng, count)


def generate_trading_comps(company: dict, rng: random.Random, count: int = 6) -> list[dict]:
    sector = company["sector"]
    tickers = {
        "enterprise_ai": ["PLTR", "SNOW", "AI", "CRM", "NOW"],
        "devtools": ["DDOG", "GTLB", "MDB", "ESTC", "TEAM"],
        "fintech": ["NU", "SOFI", "AFRM", "TOST", "COIN"],
        "healthtech": ["VEEV", "TDOC", "TEM", "DOCS", "HIMS"],
        "climate": ["FLNC", "STEM", "NXT", "BE", "CHPT"],
        "consumer": ["PG", "CLX", "KHC", "GIS"],
        "deeptech": ["NVDA", "RKLB", "IONQ", "QUBT", "SYM"],
    }[sector]

    rows = []
    for _ in range(count):
        ticker = rng.choice(tickers)
        market_cap = rng.uniform(1_500_000_000, 80_000_000_000)
        ev = market_cap * rng.uniform(0.95, 1.25)
        rev_ltm = market_cap / rng.uniform(3, 12)
        ebitda_margin = rng.uniform(15, 35)
        ebitda_ltm = rev_ltm * ebitda_margin / 100
        ev_rev = ev / rev_ltm
        ev_ebitda = ev / ebitda_ltm
        rev_growth = rng.uniform(4, 24)
        rows.append({
            "comp_name": f"Trading comp — {ticker}",
            "ticker": ticker,
            "peer_name": ticker,
            "sector": sector,
            "market_cap": round(market_cap, 2),
            "ev": round(ev, 2),
            "revenue_ltm": round(rev_ltm, 2),
            "ebitda_ltm": round(ebitda_ltm, 2),
            "ev_revenue": round(ev_rev, 2),
            "ev_ebitda": round(ev_ebitda, 2),
            "rev_growth": round(rev_growth, 2),
            "ebitda_margin": round(ebitda_margin, 2),
            "as_of_date": date.today().isoformat(),
            # Legacy fields kept empty for old callers
            "unit_type": ticker,
            "sqft": None,
            "rent": None,
            "rent_per_sqft": None,
            "effective_date": date.today().isoformat(),
            "source": rng.choice(["Capital IQ", "FactSet", "Bloomberg"]),
        })
    return rows
