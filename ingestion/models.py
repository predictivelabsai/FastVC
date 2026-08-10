from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FinancialPeriod:
    year: int
    revenue: float | None = None
    gross_profit: float | None = None
    profit_before_tax: float | None = None
    net_profit: float | None = None
    total_assets: float | None = None
    current_assets: float | None = None
    non_current_assets: float | None = None
    liabilities: float | None = None
    equity: float | None = None
    employees: int | None = None


@dataclass(slots=True)
class NormalizedCompany:
    source: str
    external_id: str
    country: str
    name: str
    registry_id: str
    vat: str = ""
    website: str = ""
    address: str = ""
    hq_city: str = ""
    founded_year: int | None = None
    sector: str = "business_services"
    sub_sector: str = ""
    employees: int | None = None
    revenue: float | None = None
    growth_rate: float | None = None
    description: str = ""
    registry_status: str = "active"
    source_url: str = ""
    quality: float = 0
    financials: list[FinancialPeriod] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
