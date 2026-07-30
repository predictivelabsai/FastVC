"""Monthly financial statements per company — deterministic growth trajectory.

Kept under the legacy filename `t12s.py` for import compatibility. Returns
24 months of monthly P&L data for each company, suitable for LTM + trailing
normalization.
"""

from __future__ import annotations

import math
import random
from datetime import date
from dateutil.relativedelta import relativedelta


OPEX_SPLIT_BY_SECTOR = {
    "enterprise_ai": {"sales": 0.22, "marketing": 0.12, "rnd": 0.48, "ga": 0.13, "other": 0.05},
    "devtools": {"sales": 0.24, "marketing": 0.13, "rnd": 0.46, "ga": 0.12, "other": 0.05},
    "fintech": {"sales": 0.24, "marketing": 0.14, "rnd": 0.36, "ga": 0.18, "other": 0.08},
    "healthtech": {"sales": 0.19, "marketing": 0.10, "rnd": 0.42, "ga": 0.18, "other": 0.11},
    "climate": {"sales": 0.16, "marketing": 0.08, "rnd": 0.46, "ga": 0.14, "other": 0.16},
    "consumer": {"sales": 0.15, "marketing": 0.22, "rnd": 0.04, "ga": 0.09, "other": 0.50},
    "deeptech": {"sales": 0.10, "marketing": 0.05, "rnd": 0.58, "ga": 0.12, "other": 0.15},
}

COGS_RATIO_BY_SECTOR = {
    "enterprise_ai": 0.24,
    "devtools": 0.18,
    "fintech": 0.28,
    "healthtech": 0.35,
    "climate": 0.46,
    "consumer": 0.48,
    "deeptech": 0.50,
}


def _seasonal(month: int, sector: str) -> float:
    if sector == "consumer":
        return 1.0 + 0.10 * math.sin((month - 10) / 12 * 2 * math.pi)  # Q4 spike
    if sector in {"enterprise_ai", "devtools"}:
        return 1.0 + 0.04 * math.sin((month - 11) / 12 * 2 * math.pi)  # year-end deal rush
    if sector == "healthtech":
        return 1.0 + 0.03 * math.sin((month - 1) / 12 * 2 * math.pi)
    return 1.0


def generate_for_property(company: dict, end_month: date, rng: random.Random) -> list[dict]:
    """Return 24 months of monthly financials. (Name kept for back-compat.)"""
    return generate_for_company(company, end_month, rng, months=24)


def generate_for_company(company: dict, end_month: date, rng: random.Random,
                          *, months: int = 24) -> list[dict]:
    sector = company["sector"]
    annual_rev = float(company["revenue_ltm"])
    annual_ebitda = float(company["ebitda_ltm"])
    growth = float(company["growth_rate"]) / 100
    base_margin = annual_ebitda / max(1, annual_rev)
    cogs_ratio = COGS_RATIO_BY_SECTOR[sector]
    opex_split = OPEX_SPLIT_BY_SECTOR[sector]

    base_monthly = annual_rev / 12 / (1 + growth / 2)  # mid-period for LTM
    rows: list[dict] = []

    for i in range(months - 1, -1, -1):
        m = end_month - relativedelta(months=i)
        # monthly revenue grows on trend; months further from end have smaller trend
        trend_factor = (1 + growth) ** ((months - 1 - i) / 12)
        seasonal = _seasonal(m.month, sector)
        noise = rng.uniform(0.93, 1.07)
        revenue = base_monthly * trend_factor * seasonal * noise
        cogs = revenue * cogs_ratio * rng.uniform(0.96, 1.04)
        gp = revenue - cogs

        opex_total = revenue * (1 - base_margin - cogs_ratio) * rng.uniform(0.94, 1.07)
        opex = {k: round(opex_total * v, 2) for k, v in opex_split.items()}

        ebitda = gp - sum(opex.values())

        # Add back adjustments (one-time items, owner comp)
        adjustments = {}
        if rng.random() < 0.25:
            adjustments["owner_comp"] = round(revenue * rng.uniform(0.005, 0.015), 2)
        if rng.random() < 0.12:
            adjustments["one_time_legal"] = round(revenue * rng.uniform(0.002, 0.008), 2)
        if rng.random() < 0.08:
            adjustments["discontinued_product"] = round(revenue * rng.uniform(0.005, 0.015), 2)
        adj_total = sum(adjustments.values())
        adj_ebitda = ebitda + adj_total

        # Optional SaaS metrics
        arr = None
        gross_retention = None
        net_retention = None
        if company.get("business_model") in {"b2b_saas", "usage_based", "fintech"}:
            arr = round(revenue * 12, 2)
            gross_retention = round(rng.uniform(88.0, 95.0), 2)
            net_retention = round(gross_retention + rng.uniform(6.0, 18.0), 2)

        rows.append({
            "month": m.replace(day=1).isoformat(),
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "gross_profit": round(gp, 2),
            "opex": opex,
            "ebitda": round(ebitda, 2),
            "adjustments": adjustments,
            "adj_ebitda": round(adj_ebitda, 2),
            "arr": arr,
            "gross_retention": gross_retention,
            "net_retention": net_retention,
        })
    return rows
