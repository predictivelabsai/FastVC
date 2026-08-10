from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

from .models import FinancialPeriod, NormalizedCompany


COUNTRY_NAMES = {"LT": "Lithuania", "EE": "Estonia", "LV": "Latvia", "GB": "United Kingdom",
                 "FR": "France", "FI": "Finland", "SE": "Sweden"}
SOURCE_URLS = {
    "LT": "https://rekvizitai.vz.lt/en/",
    "EE": "https://ariregister.rik.ee/eng",
    "LV": "https://data.gov.lv/",
}


def slugify(value: str, *, country: str = "", external_id: str = "") -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")[:55] or "company"
    suffix = re.sub(r"[^a-z0-9]+", "", f"{country}-{external_id}".lower())[:24]
    return f"{base}-{suffix}" if suffix else base


def clean_website(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"https?://[^\s]+", text)
    if match:
        return match.group(0).rstrip(".,;)")
    first = text.split()[0] if text else ""
    if first and "." in first:
        return "https://" + first.rstrip(".,;)")
    return ""


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?[\d\s.,]+", str(value).replace("\xa0", " "))
    if not match:
        return None
    text = match.group(0).strip().replace(" ", "")
    if text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _year(value: Any) -> int | None:
    if isinstance(value, int) and 1800 <= value <= date.today().year:
        return value
    text = str(value or "")
    years = re.findall(r"(?:18|19|20)\d{2}", text)
    if years:
        return int(years[-1])
    age = re.search(r"(\d+)\s*years?", text, re.I)
    if age:
        return date.today().year - int(age.group(1))
    return None


def _city(address: str, country: str) -> str:
    parts = [part.strip() for part in (address or "").split(",") if part.strip()]
    if not parts:
        return ""
    if country == "EE" and len(parts) > 1:
        return re.sub(r"\s+(vald|linn)$", "", parts[1], flags=re.I).strip()
    if country == "LV":
        return parts[0].replace(" nov.", "").strip()
    for part in reversed(parts):
        cleaned = re.sub(r"(?:LT|LV|EE)-?\d+", "", part, flags=re.I).strip()
        if cleaned and not cleaned[0].isdigit() and not re.search(r"\b(g\.|str\.|iela|al\.)\b", cleaned, re.I):
            return cleaned
    return parts[-1]


def _financial_periods(rows: list[dict]) -> list[FinancialPeriod]:
    merged: dict[int, dict] = {}
    for raw in rows or []:
        year = _integer(raw.get("year"))
        if not year or not 1900 <= year <= date.today().year + 1:
            continue
        target = merged.setdefault(year, {"year": year})
        for key in ("sales_revenue", "gross_profit", "profit_before_tax", "net_profit",
                    "total_assets", "current_assets", "non_current_assets", "liabilities",
                    "equity", "employees"):
            value = _integer(raw.get(key)) if key == "employees" else _number(raw.get(key))
            if value is not None:
                previous = target.get(key)
                if previous is None or (key == "sales_revenue" and abs(value) > abs(previous)):
                    target[key] = value
    return [FinancialPeriod(
        year=row["year"], revenue=row.get("sales_revenue"), gross_profit=row.get("gross_profit"),
        profit_before_tax=row.get("profit_before_tax"), net_profit=row.get("net_profit"),
        total_assets=row.get("total_assets"), current_assets=row.get("current_assets"),
        non_current_assets=row.get("non_current_assets"), liabilities=row.get("liabilities"),
        equity=row.get("equity"), employees=row.get("employees"),
    ) for row in sorted(merged.values(), key=lambda item: item["year"])]


def _quality(company: NormalizedCompany) -> float:
    score = 15 if company.registry_id else 0
    score += 15 if company.website else 0
    score += 12 if company.financials else 0
    score += 8 if len(company.financials) >= 3 else 0
    score += 10 if company.employees is not None else 0
    score += 8 if company.founded_year else 0
    score += {"software": 18, "financial_services": 16, "healthcare": 14,
              "business_services": 10, "consumer": 7, "industrials": 5}.get(company.sector, 4)
    if company.founded_year:
        score += 10 if company.founded_year >= 2018 else 6 if company.founded_year >= 2010 else 2
    if company.growth_rate is not None:
        score += 4 if company.growth_rate > 0 else 1
    return min(100.0, float(score))


def normalize_registry_record(raw: dict, country: str) -> NormalizedCompany | None:
    country = country.upper()
    name = str(raw.get("name") or "").strip()
    registry_id = str(raw.get("reg_code") or "").strip()
    if not name or not registry_id:
        return None
    periods = _financial_periods(raw.get("financials") or [])
    latest = periods[-1] if periods else None
    revenue = latest.revenue if latest else _number(raw.get("sales_revenue"))
    growth = None
    revenues = [period.revenue for period in periods if period.revenue and period.revenue > 0]
    if len(revenues) >= 2:
        growth = max(-999.0, min(999.0, round((revenues[-1] / revenues[-2] - 1) * 100, 1)))
    employees = _integer(raw.get("employees") or raw.get("employees_text"))
    if employees is None and latest:
        employees = latest.employees
    address = str(raw.get("address") or "").strip()
    founded = _year(raw.get("founded") or raw.get("company_age"))
    sector = str(raw.get("sector") or "business_services").strip().lower()
    sector = {"healthcare": "healthtech", "financial_services": "fintech"}.get(sector, sector)
    sub_sector = str(raw.get("sub_sector") or raw.get("categories") or "").strip()
    description = str(raw.get("activity_description") or raw.get("description") or "").strip()
    if not description or "data to your information system" in description:
        place = _city(address, country) or COUNTRY_NAMES.get(country, country)
        description = f"Registry-listed {sub_sector or sector.replace('_', ' ')} company based in {place}."
    source = f"registry_{country.lower()}"
    company = NormalizedCompany(
        source=source, external_id=registry_id, country=country, name=name,
        registry_id=registry_id, vat=str(raw.get("vat") or "").strip(),
        website=clean_website(raw.get("website")), address=address,
        hq_city=_city(address, country), founded_year=founded, sector=sector,
        sub_sector=sub_sector, employees=employees, revenue=revenue, growth_rate=growth,
        description=description, source_url=SOURCE_URLS.get(country, ""),
        financials=periods, raw=raw,
    )
    company.quality = _quality(company)
    return company
