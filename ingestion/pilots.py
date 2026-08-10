from __future__ import annotations

import hashlib
import json
from typing import Any

from db import connect
from utils.config import settings

from .providers import (
    CompaniesHouseClient, PappersClient, PrhClient, ScorisClient, SireneClient,
)


def _list_at(payload: Any, *keys: str) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def _deep_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key).lower())
            keys.update(_deep_keys(nested))
    elif isinstance(value, list):
        for nested in value[:10]:
            keys.update(_deep_keys(nested))
    return keys


def _identifier(provider: str, record: dict, index: int) -> str:
    candidates = {
        "pappers": ("siren", "siret"),
        "scoris": ("registration_code", "regcode", "company_number", "code"),
        "companies_house": ("company_number",),
        "sirene": ("siren",),
        "prh": ("businessId", "business_id"),
    }[provider]
    for key in candidates:
        value = record.get(key)
        if isinstance(value, dict):
            value = value.get("value") or value.get("businessId")
        if value:
            return str(value)
    digest = hashlib.sha256(json.dumps(record, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return f"sample-{index}-{digest}"


def _quality(records: list[dict]) -> dict:
    aliases = {
        "identifier": {"siren", "siret", "registration_code", "regcode", "company_number", "businessid"},
        "website": {"website", "site_internet", "url"},
        "financials": {"financials", "finances", "comptes", "turnover", "sales_revenue", "revenue"},
        "employees": {"employees", "employee_count", "number_of_employees", "effectif",
                      "trancheeffectifsunitelegale"},
        "address": {"address", "adresse", "registered_office_address", "addresses",
                    "siege", "adresse_ligne_1", "adresse_complete"},
        "founded": {"date_creation", "date_of_creation", "registrationdate",
                    "registration_date", "founded", "datecreationunitelegale"},
    }
    found = {key: 0 for key in aliases}
    for record in records:
        keys = _deep_keys(record)
        for label, candidates in aliases.items():
            found[label] += bool(keys & candidates)
    count = len(records)
    return {
        "records": count,
        "coverage_pct": {key: round(value / count * 100, 1) if count else 0 for key, value in found.items()},
    }


def _fetch(provider: str, limit: int, api_key: str = "") -> tuple[list[dict], float, dict]:
    cfg = settings()
    if provider == "pappers":
        client = PappersClient(api_key or cfg.pappers_api_key)
        search = client.search("logiciel", per_page=limit)
        hits = _list_at(search.data, "resultats", "results")[:limit]
        records, credits = [], search.credits_used
        for hit in hits:
            siren = hit.get("siren")
            if not siren:
                continue
            detail = client.company(str(siren))
            records.append(detail.data)
            credits += detail.credits_used
        return records, credits, {}
    if provider == "scoris":
        client = ScorisClient(api_key or cfg.scoris_api_key)
        response = client.filter({
            "country_code": ["FI", "SE", "GB"],
            "nace_chapter": ["INFORMATION AND COMMUNICATION"],
            "employees_min": 2, "page": 1, "page_size": limit,
        })
        hits = _list_at(response.data, "results", "companies")[:limit]
        records: list[dict] = []
        credits = response.credits_used
        credits_remaining = response.credits_remaining
        for hit in hits:
            country = hit.get("country_code") or hit.get("country")
            regcode = hit.get("regcode") or hit.get("registration_code")
            if not country or not regcode:
                records.append(hit)
                continue
            detail = client.company(str(country), str(regcode))
            records.append(detail.data if isinstance(detail.data, dict) else hit)
            credits += detail.credits_used
            credits_remaining = detail.credits_remaining or credits_remaining
        return records, credits, {"credits_remaining": credits_remaining}
    if provider == "companies_house":
        client = CompaniesHouseClient(api_key or cfg.companies_house_api_key)
        response = client.advanced_search(
            sic_codes="62012", incorporated_from="2022-01-01", size=limit,
        )
        hits = _list_at(response.data, "items", "companies")[:limit]
        records = []
        for hit in hits:
            number = hit.get("company_number")
            records.append(client.company(str(number)).data if number else hit)
        return records, 0, {}
    if provider == "sirene":
        response = SireneClient(api_key or cfg.sirene_api_key).search(
            "periode(activitePrincipaleUniteLegale:62.01Z AND "
            "etatAdministratifUniteLegale:A)",
            limit=limit,
        )
        records = _list_at(response.data, "unitesLegales", "results")[:limit]
        return records, 0, {}
    if provider == "prh":
        response = PrhClient().search(name="software")
        records = _list_at(response.data, "companies", "results")[:limit]
        return records, 0, {}
    raise ValueError(f"Unsupported provider: {provider}")


def run_quality_pilot(provider: str, *, limit: int = 5, persist: bool = True,
                      api_key: str = "") -> dict:
    if not 1 <= limit <= 25:
        raise ValueError("Pilot limit must be between 1 and 25")
    records, credits, metadata = _fetch(provider, limit, api_key=api_key)
    quality = _quality(records)
    result = {"provider": provider, **quality, "credits_used": credits, **metadata}
    if not persist:
        return result

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO fastvc.ingestion_runs
               (provider,mode,status,requested_limit,processed,inserted,credits_used,metadata,finished_at)
               VALUES (%s,'quality_pilot','completed',%s,%s,%s,%s,%s::jsonb,now()) RETURNING id""",
            (provider, limit, len(records), len(records), credits, json.dumps(result)),
        )
        run_id = cur.fetchone()[0]
        for index, record in enumerate(records):
            external_id = _identifier(provider, record, index)
            payload = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
            digest = hashlib.sha256(payload.encode()).hexdigest()
            cur.execute(
                """INSERT INTO fastvc.company_source_records
                   (company_id,source,external_id,payload,payload_hash,license)
                   VALUES (NULL,%s,%s,%s::jsonb,%s,%s)
                   ON CONFLICT (source,external_id,payload_hash) DO NOTHING""",
                (provider, external_id, payload, digest, "Provider terms apply"),
            )
        conn.commit()
    return {**result, "run_id": run_id}
