"""Plain-English chat suggestions grounded in the live FastVC company data."""

from __future__ import annotations

from functools import lru_cache

from agents.registry import AGENTS
from db import fetch_all


@lru_cache(maxsize=1)
def real_company_examples(limit: int = 6) -> tuple[dict, ...]:
    """Return high-quality, non-synthetic companies with filed financial history."""
    try:
        rows = fetch_all(
            """SELECT c.id,c.slug,c.name,c.country,c.sector,c.data_source,
                      count(f.id) AS financial_periods,max(f.period_end) AS latest_period,
                      (array_agg(f.currency ORDER BY f.period_end DESC))[1] AS currency,
                      (array_agg(f.revenue ORDER BY f.period_end DESC))[1] AS latest_revenue
               FROM fastvc.companies c
               JOIN fastvc.company_financial_periods f ON f.company_id=c.id
               WHERE COALESCE(c.data_source,'') NOT ILIKE 'synthetic%%'
                 AND f.revenue IS NOT NULL
               GROUP BY c.id
               ORDER BY (c.website IS NOT NULL AND c.website NOT ILIKE '%%kreedix%%') DESC,
                        CASE WHEN c.name ~* '(tech|soft|digital|labs|systems|snabb|amlyze|bitdegree|cujo)'
                             THEN 0 ELSE 1 END,
                        c.source_quality DESC NULLS LAST,count(f.id) DESC,
                        max(f.period_end) DESC,length(c.name),c.name
               LIMIT %s""",
            (limit,),
        )
        return tuple(rows)
    except Exception:
        return ()


def _company_names(companies: tuple[dict, ...]) -> tuple[str, str, str]:
    names = [row["name"] for row in companies[:3]]
    fallbacks = ["a company with recent registry filings", "another company in FastVC", "a third company in FastVC"]
    names.extend(fallbacks[len(names):])
    return names[0], names[1], names[2]


def agent_prompt_map(companies: tuple[dict, ...] | None = None) -> dict[str, list[str]]:
    """Build natural-language prompts; named examples always come from the live database."""
    companies = companies if companies is not None else real_company_examples()
    first, second, third = _company_names(companies)
    shared = [
        f"Summarize the verified company and financial data available for {first}.",
        f"Compare the latest filed financials for {first} and {second}.",
        "Find companies with recent registry financials and explain the source quality.",
    ]
    prompts: dict[str, list[str]] = {agent.slug: list(shared) for agent in AGENTS}
    prompts.update({
        "market_scanner": [
            "Find software companies with recent registry financials in FastVC.",
            f"Find companies similar to {first} using only the data already loaded.",
            "Show high-quality company records from Lithuania, Latvia and Estonia.",
        ],
        "deal_triage": [
            f"Screen {first} using the evidence available in FastVC.",
            f"Compare {first} and {second} and tell me which merits deeper research.",
            "Rank companies with recent financial filings and explain every score.",
        ],
        "comp_finder": [
            f"Compare {first}, {second} and {third} using their latest filed financials.",
            f"Find the closest company records to {first} in FastVC.",
            "Build a comparison set from companies with at least two financial periods.",
        ],
        "seller_intent": [
            f"Review the available signals and data gaps for {first}.",
            "Find companies whose latest filings suggest a material change in performance.",
            "Show which companies need fresh fundraising-signal research.",
        ],
        "outreach_email": [
            f"Draft a research-led introduction to {first} using only verified FastVC facts.",
            f"Write a concise meeting request to {second} without inventing founder details.",
            "Choose a company with strong source coverage and draft a factual outreach note.",
        ],
        "outreach_sequencer": [
            f"Create a three-step research-led outreach plan for {first}.",
            f"Plan a follow-up sequence for {second} using only verified facts.",
            "Build an outreach sequence for one well-documented company in FastVC.",
        ],
        "loi_writer": [
            f"List the missing information required before drafting terms for {first}.",
            f"Prepare a non-binding term-sheet checklist for {second} without inventing economics.",
            "Find a company with good filing coverage and outline a counsel-ready terms process.",
        ],
        "rent_roll_parser": [
            f"Explain what ownership data is available and missing for {first}.",
            f"Prepare a cap-table data request for {second} based on its current dossier.",
            "Find company records that still need cap-table enrichment.",
        ],
        "t12_normalizer": [
            f"Review the available annual financial history for {first} and flag data gaps.",
            f"Compare revenue and profit trends for {first} and {second}.",
            "Find companies with at least three annual periods and summarize their trends.",
        ],
        "pro_forma_builder": [
            f"Use {first} as context and list what is still needed to model a financing round.",
            f"Explain which filed figures for {second} can support a round model and which cannot.",
            "Find a well-documented company and prepare a financing-model input checklist.",
        ],
        "debt_stack_modeler": [
            f"Assess which available financials for {first} are relevant to financing capacity.",
            f"Compare the filed profit and balance-sheet history of {first} and {second}.",
            "Find companies with liabilities and equity data suitable for financing review.",
        ],
        "return_metrics": [
            f"List the missing ownership and valuation inputs needed to model outcomes for {first}.",
            f"Prepare an outcome-model data checklist for {second}.",
            "Find a company with good financial history and identify the additional return-model inputs.",
        ],
        "doc_room_auditor": [
            f"Audit the evidence currently available for {first} and list missing diligence documents.",
            f"Compare source coverage for {first} and {second}.",
            "Find companies with financial filings but no uploaded diligence documents.",
        ],
        "lease_abstractor": [
            f"Check whether FastVC has contracts for {first} and prepare a missing-document request.",
            f"List the commercial evidence available for {second} without inventing contract terms.",
            "Find a documented company and outline the contracts needed for diligence.",
        ],
        "title_zoning": [
            f"Summarize the legal identifiers and provenance available for {first}.",
            f"Compare the registry evidence for {first} and {second}.",
            "Find companies whose legal or ownership records need enrichment.",
        ],
        "physical_condition": [
            f"Summarize the product and go-to-market evidence actually available for {first}.",
            f"Create a customer-reference plan for {second} based on its current data gaps.",
            "Find companies that have financial records but need product diligence.",
        ],
        "environmental_risk": [
            f"Summarize the technology and security evidence available for {first}.",
            f"Prepare a technology diligence request for {second} without assuming its architecture.",
            "Find software companies that still need technology-risk enrichment.",
        ],
        "investor_memo": [
            f"Draft an evidence-led investment brief for {first} and clearly mark every data gap.",
            f"Compare {first} and {second} in a short investment committee pre-read.",
            "Choose a company with strong financial coverage and draft a sourced preliminary memo.",
        ],
        "deal_teaser": [
            f"Create a factual one-page company brief for {first}.",
            f"Summarize the verified strengths and open questions for {second}.",
            "Choose a company with recent filings and create a sourced deal snapshot.",
        ],
        "lp_update": [
            f"Use {first} as an example and explain which verified updates could appear in an LP note.",
            f"Summarize recent filed changes for {first} and {second} without treating them as portfolio holdings.",
            "Find material company-data changes that could inform a research update.",
        ],
        "fundraising_crm": [
            f"Explain which investor or relationship data is available for {first}.",
            f"Prepare a research plan to identify relevant investors for {second}.",
            "Find companies with good financial coverage but missing investor links.",
        ],
        "rent_optimization": [
            f"Explain what pricing evidence is available and missing for {first}.",
            f"Prepare a pricing diligence request for {second} based on current data gaps.",
            "Find software companies with financial history that need pricing enrichment.",
        ],
        "opex_variance": [
            f"Review revenue, profit and employee changes in the filed history for {first}.",
            f"Compare operating trends for {first} and {second}.",
            "Find the largest year-over-year changes in companies with recent filings.",
        ],
        "capex_prioritizer": [
            f"Use the verified data for {first} to identify the next three research priorities.",
            f"Compare the evidence gaps for {first} and {second} and prioritize follow-up work.",
            "Rank company records by the value of their next enrichment step.",
        ],
        "tenant_churn": [
            f"Explain whether FastVC has retention data for {first} and what is missing.",
            f"Prepare a retention-data request for {second} without inventing customer metrics.",
            "Find software companies with financial filings but no cohort or retention evidence.",
        ],
    })
    return prompts


def welcome_suggestions(prompt_map: dict[str, list[str]]) -> list[tuple[str, str]]:
    choices = (
        "deal_triage", "t12_normalizer", "comp_finder",
        "investor_memo", "market_scanner", "opex_variance",
    )
    return [(prompt_map[slug][0], slug) for slug in choices]


def copilot_suggestions(page_name: str) -> list[str]:
    prompts = agent_prompt_map()
    mapping = {
        "Pipeline": "deal_triage", "Companies": "market_scanner",
        "Analytics": "opex_variance", "Valuation": "pro_forma_builder",
        "Data Room": "doc_room_auditor", "Portfolio": "opex_variance",
        "Portfolio Analytics": "comp_finder", "Portfolio KPIs": "t12_normalizer",
        "Investor Detail": "fundraising_crm", "Investors": "fundraising_crm",
        "Integrations": "market_scanner", "News": "market_scanner",
    }
    return prompts.get(mapping.get(page_name, "deal_triage"), prompts["deal_triage"])
