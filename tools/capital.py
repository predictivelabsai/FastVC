"""Capital / LP tools: IC memo briefs, LP CRM, fund portfolio snapshot."""

from __future__ import annotations

import json
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from db import fetch_all, fetch_one


class CompanyArgs(BaseModel):
    slug_or_id: str = Field(description="Company slug or id.")


def _resolve_cid(slug_or_id):
    try:
        return int(slug_or_id)
    except (TypeError, ValueError):
        row = fetch_one("SELECT id FROM fastvc.companies WHERE slug = %s", (slug_or_id,))
        return row["id"] if row else None


def _deal_brief(slug_or_id: str) -> str:
    """Compact structured dump of everything the memo/teaser writers need."""
    cid = _resolve_cid(slug_or_id)
    if not cid:
        return "Company not found."
    co = fetch_one("SELECT * FROM fastvc.companies WHERE id = %s", (cid,))
    founders = fetch_all(
        """SELECT f.name,f.title,f.repeat_founder,f.technical,f.founder_score,l.role
           FROM fastvc.founders f
           JOIN fastvc.founder_company_links l ON l.founder_id=f.id
           WHERE l.company_id=%s ORDER BY f.founder_score DESC NULLS LAST""",
        (cid,),
    )
    rounds = fetch_all(
        """SELECT announced_date,round_type,amount_raised,pre_money,post_money,
                  lead_investor,instrument,source
           FROM fastvc.funding_rounds WHERE company_id=%s
           ORDER BY announced_date DESC NULLS LAST""",
        (cid,),
    )
    model = fetch_one(
        """SELECT round_type,pre_money,raise_amount,option_pool_pre_pct,
                  option_pool_post_pct,ownership,dilution
           FROM fastvc.round_models WHERE company_id=%s ORDER BY id DESC LIMIT 1""",
        (cid,),
    )
    outcome = fetch_one(
        """SELECT scenarios,fund_returns FROM fastvc.outcome_models
           WHERE company_id=%s ORDER BY id DESC LIMIT 1""",
        (cid,),
    )
    findings = fetch_all(
        """SELECT agent_slug,category,severity,summary,source_doc,source_page
           FROM fastvc.dd_findings WHERE company_id=%s
           ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3 WHEN 'low' THEN 4 ELSE 5 END,id DESC
           LIMIT 30""",
        (cid,),
    )
    brief = {
        "company": {
            "name": co["name"], "hq_city": co["hq_city"], "hq_state": co["hq_state"],
            "country": co["country"], "sector": co["sector"], "sub_sector": co["sub_sector"],
            "employees": co["employees"], "founded_year": co["founded_year"],
            "startup_stage": co["startup_stage"], "business_model": co["business_model"],
            "ownership": co["ownership"], "deal_stage": co["deal_stage"],
            "fundraising_status": co["fundraising_status"],
            "description": co["description"],
        },
        "operating_metrics": {
            key: float(co[key]) if co[key] is not None else None
            for key in (
                "arr", "mrr", "growth_rate", "gross_margin", "net_burn",
                "runway_months", "burn_multiple", "net_retention",
                "gross_retention", "momentum_score", "thesis_score",
            )
        },
        "financing": {
            "total_funding": float(co["total_funding"]) if co["total_funding"] else None,
            "last_round_type": co["last_round_type"],
            "last_round_amount": float(co["last_round_amount"]) if co["last_round_amount"] else None,
            "pre_money_valuation": float(co["pre_money_valuation"]) if co["pre_money_valuation"] else None,
            "post_money_valuation": float(co["post_money_valuation"]) if co["post_money_valuation"] else None,
            "target_check_size": float(co["target_check_size"]) if co["target_check_size"] else None,
            "target_ownership_pct": float(co["target_ownership_pct"]) if co["target_ownership_pct"] else None,
        },
        "founders": founders,
        "funding_rounds": rounds,
        "latest_round_model": model,
        "latest_outcome_model": outcome,
        "diligence_findings": findings,
    }
    return json.dumps(brief, default=str)


deal_brief = StructuredTool.from_function(
    func=_deal_brief,
    name="deal_brief",
    description="Pull a compact venture dossier — team, startup metrics, funding history, round and outcome models, and diligence findings — for IC writers.",
    args_schema=CompanyArgs,
)


class CRMArgs(BaseModel):
    stage: Optional[str] = Field(default=None, description="cold | qualified | meeting | dd | committed | closed | passed")
    focus: Optional[str] = Field(default=None, description="venture | seed | early_stage | multi_stage | growth")
    lp_type: Optional[str] = Field(default=None, description="pension | endowment | fof | family_office | sovereign | insurance | hnw")
    min_check: Optional[float] = Field(default=None)
    days_since_touch: Optional[int] = Field(default=None, description="Filter to LPs not touched in N days.")
    limit: int = Field(default=15, ge=1, le=50)


def _crm_lookup(**kw) -> str:
    args = CRMArgs(**kw)
    sql = ["SELECT name, firm, lp_type, email, commitment_size, stage, focus, geography, aum, last_touch, notes "
           "FROM fastvc.investor_crm WHERE TRUE"]
    params: list = []
    if args.stage:
        sql.append("AND stage = %s"); params.append(args.stage)
    if args.focus:
        sql.append("AND focus = %s"); params.append(args.focus)
    if args.lp_type:
        sql.append("AND lp_type = %s"); params.append(args.lp_type)
    if args.min_check:
        sql.append("AND commitment_size >= %s"); params.append(args.min_check)
    if args.days_since_touch:
        sql.append("AND last_touch < now() - (%s || ' days')::interval"); params.append(args.days_since_touch)
    sql.append("ORDER BY commitment_size DESC NULLS LAST, last_touch DESC NULLS LAST LIMIT %s")
    params.append(args.limit)
    rows = fetch_all(" ".join(sql), tuple(params))
    if not rows:
        return "No LPs match."
    rows2 = [{**r,
              "commitment_size": float(r["commitment_size"]) if r["commitment_size"] else None,
              "aum": float(r["aum"]) if r["aum"] else None,
              "last_touch": str(r["last_touch"]) if r["last_touch"] else None}
             for r in rows]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "LP shortlist",
        "columns": ["name", "firm", "lp_type", "stage", "focus", "commitment_size", "last_touch"],
        "rows": rows2,
        "summary": {"count": len(rows2)},
    }, default=str)


rank_lps = StructuredTool.from_function(
    func=_crm_lookup,
    name="rank_lps",
    description="Filter + rank the LP CRM by stage, focus, LP type, min commitment size, and days-since-last-touch.",
    args_schema=CRMArgs,
)
# Back-compat alias
crm_lookup = rank_lps


def _portfolio_snapshot() -> str:
    """For LP updates: venture portfolio by sector, ARR, growth and ownership."""
    rows = fetch_all(
        "SELECT sector, count(*) as n, "
        "sum(arr)::numeric as total_arr, avg(growth_rate) as avg_growth, "
        "avg(gross_margin) as avg_gross_margin, avg(runway_months) as avg_runway, "
        "avg(target_ownership_pct) as avg_ownership "
        "FROM fastvc.companies "
        "WHERE deal_stage IN ('invested','follow_on','exited') "
        "GROUP BY sector ORDER BY sector"
    )
    rows2 = [{"sector": r["sector"], "companies": r["n"],
              "total_arr": float(r["total_arr"]) if r["total_arr"] else None,
              "avg_growth_pct": round(float(r["avg_growth"]), 1) if r["avg_growth"] else None,
              "avg_gross_margin_pct": round(float(r["avg_gross_margin"]), 1) if r["avg_gross_margin"] else None,
              "avg_runway_months": round(float(r["avg_runway"]), 1) if r["avg_runway"] else None,
              "avg_ownership_pct": round(float(r["avg_ownership"]), 1) if r["avg_ownership"] else None}
             for r in rows]
    return "__ARTIFACT__" + json.dumps({
        "kind": "table",
        "title": "Portfolio snapshot",
        "columns": ["sector", "companies", "total_arr", "avg_growth_pct",
                    "avg_gross_margin_pct", "avg_runway_months", "avg_ownership_pct"],
        "rows": rows2,
    })


portfolio_snapshot = StructuredTool.from_function(
    func=_portfolio_snapshot,
    name="portfolio_snapshot",
    description="Venture portfolio snapshot by sector — company count, ARR, growth, gross margin, runway and fund ownership.",
    args_schema=BaseModel,
)
