"""Quota-aware bulk company discovery and provenance persistence."""

from __future__ import annotations

import hashlib
import json
import math
from contextlib import nullcontext
from datetime import date
from typing import Any

from db import connect
from utils.config import settings

from .models import FinancialPeriod, NormalizedCompany
from .normalize import clean_website, slugify
from .providers import (
    CompaniesHouseClient, PappersClient, PrhClient, ScorisClient, SireneClient,
)


SOURCE_URLS = {
    "pappers": "https://www.pappers.fr/",
    "scoris": "https://scoris.eu/",
    "companies_house": "https://find-and-update.company-information.service.gov.uk/",
    "sirene": "https://annuaire-entreprises.data.gouv.fr/",
    "prh": "https://avoindata.prh.fi/",
}
LICENSES = {
    "pappers": "Pappers API terms apply",
    "scoris": "Scoris API terms apply",
    "companies_house": "Companies House Crown copyright",
    "sirene": "INSEE open-data terms apply",
    "prh": "Creative Commons Attribution 4.0",
}


def _year(value: Any) -> int | None:
    text = str(value or "")
    for token in text.replace("/", "-").split("-"):
        if token.isdigit() and len(token) == 4:
            year = int(token)
            if 1800 <= year <= date.today().year:
                return year
    return None


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("\xa0", " ").replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _description(entries: Any, language: str = "EN") -> str:
    if not isinstance(entries, list):
        return ""
    for entry in entries:
        if isinstance(entry, dict) and str(entry.get("languageCode", "")).upper() == language:
            return str(entry.get("description") or "").strip()
    for entry in entries:
        if isinstance(entry, dict) and entry.get("description"):
            return str(entry["description"]).strip()
    return ""


def _quality(company: NormalizedCompany) -> float:
    score = 25 if company.registry_id else 0
    score += 15 if company.website else 0
    score += 10 if company.address else 0
    score += 10 if company.founded_year else 0
    score += 10 if company.employees is not None else 0
    score += 10 if company.revenue is not None else 0
    score += 10 if company.sector == "software" else 5
    score += 10 if company.description else 0
    return float(min(score, 100))


def _company(source: str, external_id: str, country: str, name: str, raw: dict,
             **values: Any) -> NormalizedCompany | None:
    name = str(name or "").strip()
    external_id = str(external_id or "").strip()
    if not name or not external_id:
        return None
    company = NormalizedCompany(
        source=source, external_id=external_id, country=country, name=name,
        registry_id=external_id, sector="software", source_url=SOURCE_URLS[source],
        description=values.pop("description", "") or
                    f"Registry-listed technology company discovered through {source.replace('_', ' ')}.",
        raw=raw, **values,
    )
    company.quality = _quality(company)
    return company


def normalize_provider_record(provider: str, raw: dict) -> NormalizedCompany | None:
    """Map a provider search result into FastVC's conservative common shape."""
    if provider == "pappers":
        office = raw.get("siege") if isinstance(raw.get("siege"), dict) else {}
        address = ", ".join(str(value).strip() for value in (
            office.get("adresse_ligne_1"), office.get("code_postal"), office.get("ville"),
        ) if value)
        financials = []
        financial_year = _integer(raw.get("annee_finances"))
        if financial_year:
            financials.append(FinancialPeriod(
                year=financial_year, revenue=_number(raw.get("chiffre_affaires")),
                net_profit=_number(raw.get("resultat")),
                employees=_integer(raw.get("effectifs_finances")),
            ))
        return _company(
            provider, raw.get("siren"), "FR",
            raw.get("nom_entreprise") or raw.get("denomination") or raw.get("nom"), raw,
            address=address, hq_city=str(office.get("ville") or "").strip(),
            founded_year=_year(raw.get("date_creation")), employees=_integer(raw.get("effectif")),
            revenue=_number(raw.get("chiffre_affaires")),
            sub_sector=str(raw.get("libelle_code_naf") or raw.get("domaine_activite") or ""),
            registry_status="inactive" if raw.get("entreprise_cessee") else "active",
            financials=financials,
        )
    if provider == "scoris":
        country = str(raw.get("country_code") or raw.get("country") or "").upper()
        return _company(
            provider, raw.get("regcode") or raw.get("registration_code"), country,
            raw.get("name") or raw.get("company_name"), raw,
        )
    if provider == "companies_house":
        office = raw.get("registered_office_address") or {}
        address = ", ".join(str(office.get(key) or "").strip() for key in (
            "address_line_1", "address_line_2", "locality", "postal_code",
        ) if office.get(key))
        return _company(
            provider, raw.get("company_number"), "GB", raw.get("company_name"), raw,
            address=address, hq_city=str(office.get("locality") or "").strip(),
            founded_year=_year(raw.get("date_of_creation")),
            sub_sector=", ".join(raw.get("sic_codes") or []),
            registry_status=str(raw.get("company_status") or "active"),
        )
    if provider == "sirene":
        periods = raw.get("periodesUniteLegale") or []
        current = next((row for row in periods if not row.get("dateFin")), periods[0] if periods else {})
        name = (current.get("denominationUniteLegale") or current.get("nomUsageUniteLegale") or
                current.get("nomUniteLegale"))
        if not name:
            name = " ".join(str(raw.get(key) or "").strip() for key in (
                "prenomUsuelUniteLegale", "nomUniteLegale",
            )).strip()
        employee_bands = {
            "00": 0, "01": 1, "02": 4, "03": 7, "11": 15, "12": 35,
            "21": 75, "22": 150, "31": 225, "32": 375, "41": 750,
            "42": 1500, "51": 3500, "52": 7500, "53": 10000,
        }
        return _company(
            provider, raw.get("siren"), "FR", name, raw,
            founded_year=_year(raw.get("dateCreationUniteLegale")),
            employees=employee_bands.get(str(raw.get("trancheEffectifsUniteLegale") or "")),
            sub_sector=str(current.get("activitePrincipaleUniteLegale") or ""),
            registry_status="active" if current.get("etatAdministratifUniteLegale") == "A" else "inactive",
        )
    if provider == "prh":
        business_id = raw.get("businessId") or {}
        names = raw.get("names") or []
        current_name = next((item for item in names if not item.get("endDate")), names[0] if names else {})
        addresses = raw.get("addresses") or []
        office = addresses[0] if addresses else {}
        post_offices = office.get("postOffices") or []
        city = _description(post_offices) or _description(post_offices, "FI")
        address = ", ".join(str(value).strip() for value in (
            office.get("street"), office.get("buildingNumber"), office.get("postCode"), city,
        ) if value)
        business_line = raw.get("mainBusinessLine") or {}
        website = raw.get("website") or {}
        return _company(
            provider, business_id.get("value"), "FI", current_name.get("name"), raw,
            website=clean_website(website.get("url")), address=address, hq_city=city,
            founded_year=_year(raw.get("registrationDate") or business_id.get("registrationDate")),
            sub_sector=_description(business_line.get("descriptions")),
            registry_status=str(raw.get("status") or raw.get("tradeRegisterStatus") or "active"),
        )
    raise ValueError(f"Unsupported provider: {provider}")


def fetch_provider_records(provider: str, limit: int, *, max_credits: float | None = None,
                           api_key: str = "") -> tuple[list[dict], float, dict]:
    """Fetch bounded search records without purchasing per-company detail profiles."""
    if not 1 <= limit <= 5000:
        raise ValueError("Backfill limit must be between 1 and 5000")
    cfg = settings()
    records: list[dict] = []
    seen: set[str] = set()
    credits = 0.0

    def add(rows: list[dict], keys: tuple[str, ...]) -> None:
        for row in rows:
            external_id = next((str(row.get(key) or "").strip() for key in keys if row.get(key)), "")
            if not external_id or external_id in seen:
                continue
            seen.add(external_id)
            records.append(row)
            if len(records) >= limit:
                break

    if provider == "pappers":
        client = PappersClient(api_key or cfg.pappers_api_key)
        cursor = "*"
        for _ in range(math.ceil(limit / 100)):
            requested = min(100, limit - len(records))
            projected = requested * 0.1
            if max_credits is not None and credits + projected > max_credits:
                break
            response = client.search("logiciel", cursor=cursor, per_page=requested)
            rows = response.data.get("resultats") or []
            credits += response.credits_used
            add(rows, ("siren",))
            if len(rows) < requested:
                break
            cursor = str(response.data.get("curseurSuivant") or "")
            if not cursor:
                break
    elif provider == "scoris":
        client = ScorisClient(api_key or cfg.scoris_api_key)
        for page in range(1, math.ceil(limit / 100) + 1):
            if max_credits is not None and credits + 1 > max_credits:
                break
            response = client.filter({
                "country_code": ["GB", "FI", "SE", "EE", "LT", "LV"],
                "nace_chapter": ["INFORMATION AND COMMUNICATION"],
                "employees_min": 2, "page": page, "page_size": 100,
            })
            rows = response.data.get("results") or response.data.get("companies") or []
            credits += response.credits_used
            add(rows, ("regcode", "registration_code"))
            if not rows:
                break
    elif provider == "companies_house":
        response = CompaniesHouseClient(api_key or cfg.companies_house_api_key).advanced_search(
            sic_codes="62012,62020,62090,63110,63120", company_status="active", size=limit,
        )
        add(response.data.get("items") or [], ("company_number",))
    elif provider == "sirene":
        response = SireneClient(api_key or cfg.sirene_api_key).search(
            "periode(activitePrincipaleUniteLegale:62.01Z AND etatAdministratifUniteLegale:A)",
            limit=limit,
        )
        add(response.data.get("unitesLegales") or [], ("siren",))
    elif provider == "prh":
        client = PrhClient()
        for term in ("software", "tech", "digital", "data", "cloud", "cyber", "automation", "AI"):
            for page in range(1, 51):
                response = client.search(name=term, page=page)
                rows = response.data.get("companies") or []
                add(rows, ("businessId",))
                if len(records) >= limit or len(rows) < 100:
                    break
            if len(records) >= limit:
                break
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    return records[:limit], credits, {"requested": limit, "fetched": len(records[:limit])}


def _external_id(raw: dict, provider: str) -> str:
    value = {
        "pappers": raw.get("siren"),
        "scoris": raw.get("regcode") or raw.get("registration_code"),
        "companies_house": raw.get("company_number"),
        "sirene": raw.get("siren"),
        "prh": (raw.get("businessId") or {}).get("value"),
    }[provider]
    return str(value or "").strip()


def persist_backfill(provider: str, records: list[dict], *, requested_limit: int,
                     credits_used: float = 0, metadata: dict | None = None,
                     connection=None) -> dict:
    companies = [company for raw in records
                 if (company := normalize_provider_record(provider, raw)) is not None]
    inserted = updated = source_records = financial_periods = 0
    manager = connect() if connection is None else nullcontext(connection)
    with manager as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO fastvc.ingestion_runs
               (provider,mode,status,requested_limit,credits_used,metadata)
               VALUES (%s,'backfill','running',%s,%s,%s::jsonb) RETURNING id""",
            (provider, requested_limit, credits_used, json.dumps(metadata or {})),
        )
        run_id = cur.fetchone()[0]
        try:
            for company in companies:
                cur.execute(
                    """SELECT company_id FROM fastvc.company_identifiers
                       WHERE country_code=%s AND identifier_value=%s
                       ORDER BY is_primary DESC,last_seen_at DESC LIMIT 1""",
                    (company.country, company.registry_id),
                )
                match = cur.fetchone()
                company_id = match[0] if match else None
                if company_id:
                    cur.execute(
                        """UPDATE fastvc.companies SET
                             website=COALESCE(website,NULLIF(%s,'')),
                             hq_city=COALESCE(hq_city,NULLIF(%s,'')),
                             founded_year=COALESCE(founded_year,%s),
                             employees=COALESCE(employees,%s),
                             revenue_ltm=COALESCE(revenue_ltm,%s),
                             sub_sector=COALESCE(sub_sector,NULLIF(%s,'')),
                             description=COALESCE(NULLIF(description,''),%s),
                             source_quality=GREATEST(COALESCE(source_quality,0),%s),
                             source_updated_at=now(), registry_status=%s
                           WHERE id=%s""",
                        (company.website, company.hq_city, company.founded_year,
                         company.employees, company.revenue, company.sub_sector,
                         company.description, company.quality, company.registry_status, company_id),
                    )
                    updated += 1
                else:
                    cur.execute(
                        """INSERT INTO fastvc.companies
                           (slug,name,hq_city,country,sector,sub_sector,website,founded_year,
                            employees,revenue_ltm,deal_stage,description,data_source,
                            source_quality,source_updated_at,registry_status)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'discovered',%s,%s,%s,now(),%s)
                           RETURNING id""",
                        (slugify(company.name, country=company.country,
                                 external_id=f"{provider}-{company.external_id}"),
                         company.name, company.hq_city or None, company.country,
                         company.sector, company.sub_sector or None, company.website or None,
                         company.founded_year, company.employees, company.revenue,
                         company.description, company.source, company.quality,
                         company.registry_status),
                    )
                    company_id = cur.fetchone()[0]
                    inserted += 1
                cur.execute(
                    """INSERT INTO fastvc.company_identifiers
                       (company_id,source,country_code,identifier_type,identifier_value,
                        is_primary,source_url)
                       VALUES (%s,%s,%s,'registry_number',%s,TRUE,%s)
                       ON CONFLICT (source,country_code,identifier_type,identifier_value)
                       DO UPDATE SET last_seen_at=now()""",
                    (company_id, provider, company.country, company.registry_id, company.source_url),
                )
                payload = json.dumps(company.raw, ensure_ascii=False, sort_keys=True, default=str)
                digest = hashlib.sha256(payload.encode()).hexdigest()
                cur.execute(
                    """INSERT INTO fastvc.company_source_records
                       (company_id,source,external_id,source_url,payload,payload_hash,license)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)
                       ON CONFLICT (source,external_id,payload_hash) DO UPDATE SET
                         company_id=EXCLUDED.company_id,fetched_at=now()""",
                    (company_id, provider, company.external_id, company.source_url,
                     payload, digest, LICENSES[provider]),
                )
                source_records += 1
                for period in company.financials:
                    cur.execute(
                        """INSERT INTO fastvc.company_financial_periods
                           (company_id,period_end,period_type,currency,revenue,net_profit,
                            employees,source,source_external_id)
                           VALUES (%s,%s::date,'annual','EUR',%s,%s,%s,%s,%s)
                           ON CONFLICT (company_id,period_end,period_type,source) DO UPDATE SET
                             revenue=COALESCE(EXCLUDED.revenue,fastvc.company_financial_periods.revenue),
                             net_profit=COALESCE(EXCLUDED.net_profit,fastvc.company_financial_periods.net_profit),
                             employees=COALESCE(EXCLUDED.employees,fastvc.company_financial_periods.employees),
                             fetched_at=now()""",
                        (company_id, f"{period.year}-12-31", period.revenue,
                         period.net_profit, period.employees, provider, company.external_id),
                    )
                    financial_periods += 1
            result = {
                "provider": provider, "requested": requested_limit, "fetched": len(records),
                "processed": len(companies), "inserted_companies": inserted,
                "updated_companies": updated, "source_records": source_records,
                "financial_periods": financial_periods, "credits_used": credits_used,
            }
            cur.execute(
                """UPDATE fastvc.ingestion_runs SET status='completed',processed=%s,
                   inserted=%s,updated=%s,credits_used=%s,metadata=metadata || %s::jsonb,
                   finished_at=now() WHERE id=%s""",
                (len(companies), inserted, updated, credits_used, json.dumps(result), run_id),
            )
            conn.commit()
            return {**result, "run_id": run_id}
        except Exception as exc:
            conn.rollback()
            raise RuntimeError(f"Backfill persistence failed before commit: {exc}") from exc


def run_backfill(provider: str, *, limit: int = 1000, max_credits: float | None = None,
                 api_key: str = "", dry_run: bool = False) -> dict:
    if dry_run:
        records, credits, metadata = fetch_provider_records(
            provider, limit, max_credits=max_credits, api_key=api_key,
        )
        normalized = [item for raw in records
                      if (item := normalize_provider_record(provider, raw)) is not None]
        return {
            "provider": provider, **metadata, "normalizable": len(normalized),
            "credits_used": credits, "sample_ids": [item.external_id for item in normalized[:3]],
        }
    # Acquire the database slot before making paid provider calls. Holding the
    # same connection through persistence prevents credit spend followed by a
    # second connection-acquisition failure on a busy shared database.
    with connect() as conn:
        records, credits, metadata = fetch_provider_records(
            provider, limit, max_credits=max_credits, api_key=api_key,
        )
        return persist_backfill(
            provider, records, requested_limit=limit, credits_used=credits,
            metadata=metadata, connection=conn,
        )
