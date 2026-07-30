"""24 months of sector-level market signals for VC."""

from __future__ import annotations

import math
import random
from datetime import date
from dateutil.relativedelta import relativedelta

METRICS = ["arr_multiple_median", "round_size_median", "round_volume",
           "fundraising_time", "down_round_rate", "exit_arr_multiple"]


def _baseline(sector: str) -> dict[str, float]:
    arr_multiple = {
        "enterprise_ai": 18.0, "devtools": 14.0, "fintech": 11.0,
        "healthtech": 10.0, "climate": 8.0, "consumer": 7.0, "deeptech": 9.0,
    }[sector]
    round_size = {
        "enterprise_ai": 12.0, "devtools": 10.0, "fintech": 14.0,
        "healthtech": 12.0, "climate": 18.0, "consumer": 8.0, "deeptech": 20.0,
    }[sector]
    round_volume = {
        "enterprise_ai": 75, "devtools": 42, "fintech": 48,
        "healthtech": 46, "climate": 31, "consumer": 38, "deeptech": 24,
    }[sector]
    return {
        "arr_multiple_median": arr_multiple,
        "round_size_median": round_size,
        "round_volume": round_volume,
        "fundraising_time": 5.0,
        "down_round_rate": 12.0,
        "exit_arr_multiple": max(3.0, arr_multiple - 3.0),
    }


def generate(companies: list[dict], months: int = 24, seed: int = 42) -> list[dict]:
    rng = random.Random(seed + 7)
    rows: list[dict] = []
    seen: set[tuple] = set()

    sectors = {c["sector"] for c in companies}
    sub_sectors_by_sector: dict[str, set[str]] = {}
    for c in companies:
        sub_sectors_by_sector.setdefault(c["sector"], set()).add(c["sub_sector"])

    today = date.today().replace(day=1)

    for sector in sectors:
        base = _baseline(sector)
        for sub in sub_sectors_by_sector.get(sector, {""}):
            for metric in METRICS:
                for i in range(months, 0, -1):
                    m = today - relativedelta(months=i)
                    t = i / months
                    seasonal = 0.05 * math.sin(i / 6 * math.pi)
                    trend = {
                        "arr_multiple_median": -1.5 * (1 - t),
                        "round_size_median": -1.0 * (1 - t),
                        "round_volume": -10 * (1 - t),
                        "fundraising_time": 1.5 * (1 - t),
                        "down_round_rate": 4.0 * (1 - t),
                        "exit_arr_multiple": -1.0 * (1 - t),
                    }[metric]
                    value = base[metric] * (1 + seasonal) + trend + rng.uniform(-0.2, 0.2)
                    key = (sector, sub, metric, m)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append({
                        "sector": sector,
                        "sub_sector": sub,
                        "metric": metric,
                        "value": round(value, 3),
                        "as_of_date": m.isoformat(),
                        "source": rng.choice(["PitchBook", "Crunchbase", "Carta",
                                              "Cambridge Associates", "Company announcements"]),
                    })
    return rows
