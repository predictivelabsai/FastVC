"""Venture-native tools for startup discovery, ownership and outcomes."""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import execute, fetch_all, fetch_one


def _json(value) -> str:
    return json.dumps(value, default=str)


class SearchStartupsArgs(BaseModel):
    query: Optional[str] = Field(
        default=None, description="Name, description, sector or sub-sector keyword."
    )
    stage: Optional[str] = Field(
        default=None,
        description="stealth | pre_seed | seed | series_a | series_b | series_c | growth",
    )
    sector: Optional[str] = None
    country: Optional[str] = None
    fundraising_status: Optional[str] = None
    min_momentum: float = Field(default=0, ge=0, le=100)
    min_thesis_score: float = Field(default=0, ge=0, le=100)
    limit: int = Field(default=20, ge=1, le=100)


def _search_startups(**kw) -> str:
    args = SearchStartupsArgs(**kw)
    sql = [
        """SELECT id,slug,name,hq_city,country,sector,sub_sector,startup_stage,
                  business_model,employees,arr,growth_rate,gross_margin,net_burn,
                  runway_months,burn_multiple,net_retention,total_funding,
                  last_round_type,last_round_amount,post_money_valuation,
                  fundraising_status,momentum_score,thesis_score,source_quality,
                  data_source,deal_stage
           FROM fastvc.companies WHERE TRUE"""
    ]
    params: list = []
    if args.query:
        sql.append(
            "AND (name ILIKE %s OR description ILIKE %s OR sector ILIKE %s "
            "OR sub_sector ILIKE %s)"
        )
        params.extend([f"%{args.query}%"] * 4)
    if args.stage:
        sql.append("AND startup_stage=%s")
        params.append(args.stage.lower())
    if args.sector:
        sql.append("AND sector=%s")
        params.append({
            "enterprise_ai": "software", "devtools": "software", "deeptech": "software",
            "fintech": "fintech", "healthtech": "healthtech",
        }.get(args.sector.lower(), args.sector.lower()))
    if args.country:
        sql.append("AND country ILIKE %s")
        params.append(args.country)
    if args.fundraising_status:
        sql.append("AND fundraising_status=%s")
        params.append(args.fundraising_status.lower())
    if args.min_momentum:
        sql.append("AND momentum_score >= %s")
        params.append(args.min_momentum)
    if args.min_thesis_score:
        sql.append("AND thesis_score >= %s")
        params.append(args.min_thesis_score)
    sql.append(
        "ORDER BY COALESCE(thesis_score,source_quality) DESC NULLS LAST, "
        "COALESCE(momentum_score,source_quality) DESC NULLS LAST LIMIT %s"
    )
    params.append(args.limit)
    rows = fetch_all(" ".join(sql), tuple(params))
    return _json({"count": len(rows), "startups": rows})


search_startups = StructuredTool.from_function(
    func=_search_startups,
    name="search_startups",
    description=(
        "Search FastVC's startup universe by thesis keyword, company stage, sector, "
        "country, fundraising state, momentum and thesis fit."
    ),
    args_schema=SearchStartupsArgs,
)


class GetStartupArgs(BaseModel):
    slug_or_id: str = Field(description="Startup slug or numeric company ID.")


def _company_id(slug_or_id: str) -> int | None:
    try:
        row = fetch_one("SELECT id FROM fastvc.companies WHERE id=%s", (int(slug_or_id),))
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM fastvc.companies WHERE slug=%s", (slug_or_id,))
    return int(row["id"]) if row else None


def _get_startup(slug_or_id: str) -> str:
    company_id = _company_id(slug_or_id)
    if company_id is None:
        return _json({"error": "Startup not found"})
    company = fetch_one("SELECT * FROM fastvc.companies WHERE id=%s", (company_id,))
    founders = fetch_all(
        """SELECT f.id,f.name,f.title,f.location,f.repeat_founder,f.technical,
                  f.founder_score,l.role,l.ownership_pct
           FROM fastvc.founders f
           JOIN fastvc.founder_company_links l ON l.founder_id=f.id
           WHERE l.company_id=%s ORDER BY f.founder_score DESC NULLS LAST""",
        (company_id,),
    )
    rounds = fetch_all(
        """SELECT announced_date,round_type,amount_raised,pre_money,post_money,
                  lead_investor,participating_investors,instrument,source
           FROM fastvc.funding_rounds WHERE company_id=%s
           ORDER BY announced_date DESC NULLS LAST""",
        (company_id,),
    )
    signals = fetch_all(
        """SELECT signal_type,title,detail,signal_date,strength,source
           FROM fastvc.startup_signals WHERE company_id=%s
           ORDER BY signal_date DESC,strength DESC LIMIT 20""",
        (company_id,),
    )
    identifiers = fetch_all(
        """SELECT identifier_type,identifier_value,country_code,source,is_primary
           FROM fastvc.company_identifiers WHERE company_id=%s
           ORDER BY is_primary DESC,source,identifier_type""",
        (company_id,),
    )
    annual_financials = fetch_all(
        """SELECT period_end,currency,revenue,gross_profit,profit_before_tax,net_profit,
                  total_assets,liabilities,equity,employees,source
           FROM fastvc.company_financial_periods WHERE company_id=%s
           ORDER BY period_end DESC LIMIT 8""",
        (company_id,),
    )
    source_records = fetch_all(
        """SELECT source,external_id,fetched_at,license
           FROM fastvc.company_source_records WHERE company_id=%s
           ORDER BY fetched_at DESC""",
        (company_id,),
    )
    return _json(
        {
            "company": company,
            "identifiers": identifiers,
            "annual_financials": annual_financials,
            "source_records": source_records,
            "founders": founders,
            "funding_rounds": rounds,
            "signals": signals,
        }
    )


get_startup = StructuredTool.from_function(
    func=_get_startup,
    name="get_startup",
    description=(
        "Fetch a company dossier including source identifiers, annual filings, "
        "provenance, founders, financing history and recent signals."
    ),
    args_schema=GetStartupArgs,
)


def _cap_table_snapshot(slug_or_id: str) -> str:
    company_id = _company_id(slug_or_id)
    if company_id is None:
        return _json({"error": "Startup not found"})
    snapshot = fetch_one(
        """SELECT id,as_of_date,holders,total_shares,post_money
           FROM fastvc.cap_tables WHERE company_id=%s
           ORDER BY as_of_date DESC LIMIT 1""",
        (company_id,),
    )
    recent_models = fetch_all(
        """SELECT id,name,round_type,pre_money,raise_amount,option_pool_pre_pct,
                  option_pool_post_pct,ownership,dilution,created_at
           FROM fastvc.round_models WHERE company_id=%s
           ORDER BY created_at DESC LIMIT 5""",
        (company_id,),
    )
    return _json(
        {
            "company_id": company_id,
            "latest_cap_table": snapshot,
            "recent_round_models": recent_models,
        }
    )


cap_table_snapshot = StructuredTool.from_function(
    func=_cap_table_snapshot,
    name="cap_table_snapshot",
    description=(
        "Fetch the latest fully diluted cap table and recent round-model ownership "
        "bridges for a startup."
    ),
    args_schema=GetStartupArgs,
)


def _summarize_startup_metrics(slug_or_id: str) -> str:
    company_id = _company_id(slug_or_id)
    if company_id is None:
        return _json({"error": "Startup not found"})
    company = fetch_one(
        """SELECT name,startup_stage,business_model,arr,mrr,growth_rate,gross_margin,
                  net_burn,runway_months,burn_multiple,net_retention,gross_retention,
                  employees,total_funding,last_round_type,last_round_amount,
                  post_money_valuation
           FROM fastvc.companies WHERE id=%s""",
        (company_id,),
    )
    history = fetch_all(
        """SELECT month,revenue,arr,gross_profit,ebitda,gross_retention,net_retention
           FROM fastvc.financials WHERE company_id=%s
           ORDER BY month DESC LIMIT 18""",
        (company_id,),
    )
    annual_history = fetch_all(
        """SELECT period_end,currency,revenue,gross_profit,profit_before_tax,net_profit,
                  total_assets,liabilities,equity,employees,source
           FROM fastvc.company_financial_periods WHERE company_id=%s
           ORDER BY period_end DESC LIMIT 8""",
        (company_id,),
    )
    warnings = []
    if company:
        if company["runway_months"] is not None and float(company["runway_months"]) < 12:
            warnings.append("Runway is below 12 months.")
        if company["burn_multiple"] is not None and float(company["burn_multiple"]) > 2:
            warnings.append("Burn multiple is above 2.0x.")
        if company["net_retention"] is not None and float(company["net_retention"]) < 100:
            warnings.append("Net revenue retention is below 100%.")
    return _json(
        {
            "company_id": company_id,
            "metrics": company,
            "monthly_history": history,
            "annual_filing_history": annual_history,
            "data_quality": {
                "months_available": len(history),
                "annual_periods_available": len(annual_history),
                "warnings": warnings,
                "note": "Verify period definitions, currency and cohort methodology before IC.",
            },
        }
    )


summarize_startup_metrics = StructuredTool.from_function(
    func=_summarize_startup_metrics,
    name="summarize_startup_metrics",
    description=(
        "Return investor-grade ARR, growth, margin, burn, runway and retention "
        "metrics with monthly history and stage-aware data-quality warnings."
    ),
    args_schema=GetStartupArgs,
)


class StartupSignalsArgs(BaseModel):
    signal_type: Optional[str] = None
    company_stage: Optional[str] = None
    days: int = Field(default=180, ge=1, le=1095)
    min_strength: float = Field(default=0, ge=0, le=100)
    limit: int = Field(default=30, ge=1, le=100)


def _recent_startup_signals(**kw) -> str:
    args = StartupSignalsArgs(**kw)
    sql = [
        """SELECT s.signal_type,s.title,s.detail,s.signal_date,s.strength,s.source,
                  c.id AS company_id,c.slug,c.name,c.startup_stage,c.sector,
                  c.momentum_score,c.fundraising_status
           FROM fastvc.startup_signals s
           JOIN fastvc.companies c ON c.id=s.company_id
           WHERE s.signal_date >= current_date - %s"""
    ]
    params: list = [args.days]
    if args.signal_type:
        sql.append("AND s.signal_type=%s")
        params.append(args.signal_type)
    if args.company_stage:
        sql.append("AND c.startup_stage=%s")
        params.append(args.company_stage)
    if args.min_strength:
        sql.append("AND s.strength >= %s")
        params.append(args.min_strength)
    sql.append("ORDER BY s.signal_date DESC,s.strength DESC LIMIT %s")
    params.append(args.limit)
    rows = fetch_all(" ".join(sql), tuple(params))
    return _json({"count": len(rows), "signals": rows})


recent_startup_signals = StructuredTool.from_function(
    func=_recent_startup_signals,
    name="recent_startup_signals",
    description=(
        "Find recent formation, founder, hiring, product, traction and fundraising "
        "signals, with company context and evidence sources."
    ),
    args_schema=StartupSignalsArgs,
)


class WarmPathsArgs(BaseModel):
    slug_or_id: str = Field(description="Startup slug or numeric company ID.")
    user_id: Optional[int] = Field(
        default=None, description="Optional FastVC user ID to restrict paths to one team member."
    )


def _find_warm_paths(slug_or_id: str, user_id: int | None = None) -> str:
    company_id = _company_id(slug_or_id)
    if company_id is None:
        return _json({"error": "Startup not found"})
    where = "AND tc.user_id=%s" if user_id is not None else ""
    params = (company_id, user_id) if user_id is not None else (company_id,)
    rows = fetch_all(
        f"""SELECT tc.connector_name,tc.connector_email,tc.relationship,tc.strength,
                   tc.last_interaction,tc.notes,f.name AS founder_name,f.title
            FROM fastvc.team_connections tc
            LEFT JOIN fastvc.founders f ON f.id=tc.founder_id
            WHERE tc.company_id=%s {where}
            ORDER BY tc.strength DESC,tc.last_interaction DESC NULLS LAST""",
        params,
    )
    return _json({"company_id": company_id, "count": len(rows), "warm_paths": rows})


find_warm_paths = StructuredTool.from_function(
    func=_find_warm_paths,
    name="find_warm_paths",
    description=(
        "Find explainable relationship paths from the investment team, portfolio "
        "network or LP network to a startup's founders."
    ),
    args_schema=WarmPathsArgs,
)


class RoundModelArgs(BaseModel):
    slug_or_id: str
    round_type: str = "series_a"
    pre_money: float = Field(gt=0, description="Pre-money valuation in whole currency units.")
    raise_amount: float = Field(gt=0, description="Total primary round size.")
    our_check: float = Field(gt=0, description="FastVC fund investment.")
    option_pool_pre_pct: float = Field(default=8, ge=0, le=50)
    option_pool_post_pct: float = Field(default=12, ge=0, le=50)
    persist: bool = True


def _build_round_model(**kw) -> str:
    args = RoundModelArgs(**kw)
    company_id = _company_id(args.slug_or_id)
    if company_id is None:
        return _json({"error": "Startup not found"})
    if args.our_check > args.raise_amount:
        return _json({"error": "Our check cannot exceed the total raise"})
    post_money = args.pre_money + args.raise_amount
    investor_pct = args.raise_amount / post_money * 100
    our_pct = args.our_check / post_money * 100
    pool_top_up = max(0.0, args.option_pool_post_pct - args.option_pool_pre_pct)
    existing_pct = max(0.0, 100.0 - investor_pct - pool_top_up)
    ownership = [
        {"holder": "Existing fully diluted holders", "post_round_pct": existing_pct},
        {"holder": "FastVC fund", "post_round_pct": our_pct},
        {
            "holder": "Other new investors",
            "post_round_pct": max(0.0, investor_pct - our_pct),
        },
        {"holder": "Incremental option pool", "post_round_pct": pool_top_up},
    ]
    model_id = None
    if args.persist:
        row = fetch_one(
            """INSERT INTO fastvc.round_models
               (company_id,name,round_type,pre_money,raise_amount,new_money,
                option_pool_pre_pct,option_pool_post_pct,ownership,dilution)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb)
               RETURNING id""",
            (
                company_id,
                f"{args.round_type.replace('_', ' ').title()} scenario",
                args.round_type,
                args.pre_money,
                args.raise_amount,
                _json(
                    [
                        {"investor": "FastVC fund", "amount": args.our_check},
                        {
                            "investor": "Other new investors",
                            "amount": args.raise_amount - args.our_check,
                        },
                    ]
                ),
                args.option_pool_pre_pct,
                args.option_pool_post_pct,
                _json(ownership),
                _json({"existing_holder_dilution_pct": 100 - existing_pct}),
            ),
        )
        model_id = row["id"] if row else None
    return _json(
        {
            "round_model_id": model_id,
            "company_id": company_id,
            "round_type": args.round_type,
            "pre_money": args.pre_money,
            "raise_amount": args.raise_amount,
            "post_money": post_money,
            "new_investor_pct": investor_pct,
            "fastvc_post_round_pct": our_pct,
            "ownership": ownership,
        }
    )


build_round_model = StructuredTool.from_function(
    func=_build_round_model,
    name="build_round_model",
    description=(
        "Build and optionally persist a venture financing ownership bridge from "
        "pre-money valuation, raise, FastVC check and option-pool assumptions."
    ),
    args_schema=RoundModelArgs,
)


class OutcomeModelArgs(BaseModel):
    slug_or_id: str
    invested_capital: float = Field(gt=0)
    current_ownership_pct: float = Field(gt=0, le=100)
    future_dilution_pct: float = Field(default=35, ge=0, lt=100)
    downside_exit: float = Field(gt=0)
    base_exit: float = Field(gt=0)
    upside_exit: float = Field(gt=0)
    downside_probability: float = Field(default=30, ge=0, le=100)
    base_probability: float = Field(default=50, ge=0, le=100)
    upside_probability: float = Field(default=20, ge=0, le=100)
    years: int = Field(default=7, ge=1, le=20)
    persist: bool = True


def _model_venture_outcome(**kw) -> str:
    args = OutcomeModelArgs(**kw)
    company_id = _company_id(args.slug_or_id)
    if company_id is None:
        return _json({"error": "Startup not found"})
    total_probability = (
        args.downside_probability + args.base_probability + args.upside_probability
    )
    if abs(total_probability - 100) > 0.01:
        return _json({"error": "Scenario probabilities must total 100%"})
    exit_ownership = args.current_ownership_pct * (1 - args.future_dilution_pct / 100)
    definitions = [
        ("downside", args.downside_exit, args.downside_probability),
        ("base", args.base_exit, args.base_probability),
        ("upside", args.upside_exit, args.upside_probability),
    ]
    scenarios = []
    expected_proceeds = 0.0
    for name, exit_value, probability in definitions:
        proceeds = exit_value * exit_ownership / 100
        moic = proceeds / args.invested_capital
        irr = (moic ** (1 / args.years) - 1) * 100 if moic > 0 else -100
        expected_proceeds += proceeds * probability / 100
        scenarios.append(
            {
                "scenario": name,
                "probability_pct": probability,
                "exit_value": exit_value,
                "ownership_pct": exit_ownership,
                "proceeds": proceeds,
                "gross_moic": moic,
                "gross_irr_pct": irr,
            }
        )
    expected_moic = expected_proceeds / args.invested_capital
    expected_irr = (
        (expected_moic ** (1 / args.years) - 1) * 100 if expected_moic > 0 else -100
    )
    fund_returns = {
        "invested_capital": args.invested_capital,
        "expected_proceeds": expected_proceeds,
        "expected_gross_moic": expected_moic,
        "expected_gross_irr_pct": expected_irr,
        "exit_ownership_pct": exit_ownership,
    }
    if args.persist:
        execute(
            """INSERT INTO fastvc.outcome_models (company_id,scenarios,fund_returns)
               VALUES (%s,%s::jsonb,%s::jsonb)""",
            (company_id, _json(scenarios), _json(fund_returns)),
        )
    return _json({"company_id": company_id, "scenarios": scenarios, **fund_returns})


model_venture_outcome = StructuredTool.from_function(
    func=_model_venture_outcome,
    name="model_venture_outcome",
    description=(
        "Model dilution-adjusted downside, base and upside venture outcomes, "
        "including probability-weighted proceeds, gross MOIC and gross IRR."
    ),
    args_schema=OutcomeModelArgs,
)
