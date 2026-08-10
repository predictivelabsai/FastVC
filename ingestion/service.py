from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

from db import connect, fetch_all

from .models import NormalizedCompany
from .normalize import normalize_registry_record, slugify


DEFAULT_REGISTRY_DIRS = (
    Path(__file__).resolve().parents[2] / "FastPE" / "data",
    Path("/home/julian/dev/fastco/FastPE/data"),
    Path("/home/julian/dev/plai/liquidround/data"),
)
COUNTRY_QUOTAS = {"LT": 200, "EE": 150, "LV": 150}

SYNTHETIC_TABLES = (
    "fastvc.agent_invocations", "fastvc.deal_risks", "fastvc.deal_milestones",
    "fastvc.dd_findings", "fastvc.portfolio_kpis", "fastvc.startup_signals",
    "fastvc.team_connections", "fastvc.founder_company_links", "fastvc.founders",
    "fastvc.funding_rounds", "fastvc.outcome_models", "fastvc.round_models",
    "fastvc.market_signals", "fastvc.investor_crm", "fastvc.debt_stacks",
    "fastvc.lbo_models", "fastvc.trading_comps", "fastvc.transaction_comps",
    "fastvc.contracts", "fastvc.financials", "fastvc.cap_tables",
    "fastvc.company_financial_periods", "fastvc.company_source_records",
    "fastvc.company_identifiers", "fastvc.companies",
)
RAG_TABLES = (
    "fastvc_rag.rag_queries", "fastvc_rag.embeddings", "fastvc_rag.chunks",
    "fastvc_rag.documents",
)


def registry_dir(candidate: str | Path | None = None) -> Path:
    candidates = (Path(candidate),) if candidate else DEFAULT_REGISTRY_DIRS
    for path in candidates:
        if path and all((path / f"{country}_companies.json").exists() for country in ("lt", "ee", "lv")):
            return path
    raise FileNotFoundError("Could not find LT/EE/LV registry JSON files; pass --registry-dir")


def load_registry_candidates(source_dir: str | Path | None = None) -> list[NormalizedCompany]:
    base = registry_dir(source_dir)
    companies: list[NormalizedCompany] = []
    for country in ("LT", "EE", "LV"):
        rows = json.loads((base / f"{country.lower()}_companies.json").read_text())
        for raw in rows:
            company = normalize_registry_record(raw, country)
            if company and company.revenue and company.revenue > 0:
                companies.append(company)
    return companies


def select_registry_cohort(companies: list[NormalizedCompany], limit: int = 500,
                           quotas: dict[str, int] | None = None) -> list[NormalizedCompany]:
    quotas = dict(quotas or COUNTRY_QUOTAS)
    grouped: dict[str, list[NormalizedCompany]] = defaultdict(list)
    for company in companies:
        grouped[company.country].append(company)
    for rows in grouped.values():
        rows.sort(key=lambda company: (
            company.quality,
            company.growth_rate if company.growth_rate is not None else -1000,
            company.founded_year or 0,
            company.revenue or 0,
        ), reverse=True)

    selected: list[NormalizedCompany] = []
    seen: set[tuple[str, str]] = set()
    for country, quota in quotas.items():
        for company in grouped.get(country, [])[:quota]:
            key = (company.country, company.registry_id)
            if key not in seen:
                selected.append(company)
                seen.add(key)
    if len(selected) < limit:
        remainder = sorted(companies, key=lambda company: company.quality, reverse=True)
        for company in remainder:
            key = (company.country, company.registry_id)
            if key in seen:
                continue
            selected.append(company)
            seen.add(key)
            if len(selected) == limit:
                break
    return selected[:limit]


def cohort_summary(companies: list[NormalizedCompany]) -> dict:
    countries: dict[str, int] = defaultdict(int)
    sectors: dict[str, int] = defaultdict(int)
    periods = websites = 0
    for company in companies:
        countries[company.country] += 1
        sectors[company.sector] += 1
        periods += len(company.financials)
        websites += bool(company.website)
    quality = sum(company.quality for company in companies) / len(companies) if companies else 0
    return {
        "companies": len(companies), "countries": dict(sorted(countries.items())),
        "sectors": dict(sorted(sectors.items(), key=lambda item: item[1], reverse=True)),
        "financial_periods": periods, "with_website": websites,
        "average_quality": round(quality, 1),
    }


def _hash_payload(payload: dict) -> tuple[str, str]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return text, hashlib.sha256(text.encode()).hexdigest()


def replace_company_universe(companies: list[NormalizedCompany], *, dry_run: bool = False) -> dict:
    summary = cohort_summary(companies)
    if dry_run:
        return summary
    if not companies:
        raise ValueError("Refusing to replace the company universe with an empty cohort")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO fastvc.ingestion_runs (provider,mode,requested_limit,metadata) "
            "VALUES ('registry_cache','replace',%s,%s::jsonb) RETURNING id",
            (len(companies), json.dumps(summary)),
        )
        run_id = cur.fetchone()[0]
        try:
            for table in SYNTHETIC_TABLES:
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
            for table in RAG_TABLES:
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")

            period_count = 0
            for company in companies:
                cur.execute(
                    """INSERT INTO fastvc.companies
                       (slug,name,hq_city,country,sector,sub_sector,website,founded_year,
                        employees,revenue_ltm,growth_rate,deal_stage,description,
                        data_source,source_quality,source_updated_at,registry_status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'discovered',%s,
                               %s,%s,now(),%s) RETURNING id""",
                    (slugify(company.name, country=company.country, external_id=company.external_id),
                     company.name, company.hq_city or None, company.country, company.sector,
                     company.sub_sector or None, company.website or None, company.founded_year,
                     company.employees, company.revenue, company.growth_rate,
                     company.description, company.source, company.quality,
                     company.registry_status),
                )
                company_id = cur.fetchone()[0]
                identifiers = [("registry_number", company.registry_id, True)]
                if company.vat:
                    identifiers.append(("vat", company.vat, False))
                for identifier_type, identifier_value, primary in identifiers:
                    cur.execute(
                        """INSERT INTO fastvc.company_identifiers
                           (company_id,source,country_code,identifier_type,identifier_value,
                            is_primary,source_url)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                        (company_id, company.source, company.country, identifier_type,
                         identifier_value, primary, company.source_url or None),
                    )
                payload, payload_hash = _hash_payload(company.raw)
                cur.execute(
                    """INSERT INTO fastvc.company_source_records
                       (company_id,source,external_id,source_url,payload,payload_hash,license)
                       VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                    (company_id, company.source, company.external_id, company.source_url or None,
                     payload, payload_hash, "Original source terms apply"),
                )
                for period in company.financials:
                    cur.execute(
                        """INSERT INTO fastvc.company_financial_periods
                           (company_id,period_end,period_type,currency,revenue,gross_profit,
                            profit_before_tax,net_profit,total_assets,current_assets,
                            non_current_assets,liabilities,equity,employees,source,
                            source_external_id)
                           VALUES (%s,%s::date,'annual','EUR',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (company_id, f"{period.year}-12-31", period.revenue,
                         period.gross_profit, period.profit_before_tax, period.net_profit,
                         period.total_assets, period.current_assets, period.non_current_assets,
                         period.liabilities, period.equity, period.employees, company.source,
                         company.external_id),
                    )
                    period_count += 1
            cur.execute(
                """UPDATE fastvc.ingestion_runs SET status='completed',processed=%s,
                   inserted=%s,metadata=metadata || %s::jsonb,finished_at=now() WHERE id=%s""",
                (len(companies), len(companies), json.dumps({"financial_periods": period_count}), run_id),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            with connect() as error_conn, error_conn.cursor() as error_cur:
                error_cur.execute(
                    """UPDATE fastvc.ingestion_runs SET status='failed',errors=1,
                       error_detail=%s,finished_at=now() WHERE id=%s""",
                    (str(exc)[:2000], run_id),
                )
                error_conn.commit()
            raise
    return {**summary, "financial_periods": period_count, "run_id": run_id}


def source_status() -> list[dict]:
    return fetch_all(
        """SELECT source AS provider,count(DISTINCT company_id) AS companies,
                  count(*) AS snapshots,max(fetched_at) AS last_sync
           FROM fastvc.company_source_records GROUP BY source ORDER BY source"""
    )
