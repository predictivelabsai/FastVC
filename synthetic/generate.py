"""Seed the FastVC databases with synthetic VC data.

Usage:
    python -m synthetic.generate                  # seed=42, ~40 companies, indexes RAG
    python -m synthetic.generate --seed 7
    python -m synthetic.generate --skip-rag       # OLTP only
    python -m synthetic.generate --limit 5        # small subset for quick testing
    python -m synthetic.generate --fresh          # truncates tables first (safer than --drop)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from datetime import date

from dateutil.relativedelta import relativedelta

from db import connect
from rag.indexer import DocIn, upsert_documents, build_ann_index
from synthetic import properties as P       # companies
from synthetic import rent_rolls as RR      # cap tables
from synthetic import t12s as T12           # monthly financials
from synthetic import comps as CMP          # txn + trading comps
from synthetic import market_signals as MS
from synthetic import lps as LP
from synthetic import leases as LEASE       # customer MSA bodies
from synthetic import documents as DOC

log = logging.getLogger(__name__)

TRUNCATE_TABLES = [
    "fastvc.agent_invocations",
    "fastvc.deal_risks",
    "fastvc.deal_milestones",
    "fastvc.dd_findings",
    "fastvc.portfolio_kpis",
    "fastvc.startup_signals",
    "fastvc.team_connections",
    "fastvc.founder_company_links",
    "fastvc.founders",
    "fastvc.funding_rounds",
    "fastvc.outcome_models",
    "fastvc.round_models",
    "fastvc.market_signals",
    "fastvc.investor_crm",
    "fastvc.debt_stacks",
    "fastvc.lbo_models",
    "fastvc.trading_comps",
    "fastvc.transaction_comps",
    "fastvc.contracts",
    "fastvc.financials",
    "fastvc.cap_tables",
    "fastvc.companies",
    # chat left alone to preserve user sessions across reseed
]


def _truncate():
    with connect() as conn, conn.cursor() as cur:
        for t in TRUNCATE_TABLES:
            cur.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE fastvc_rag.rag_queries RESTART IDENTITY")
        cur.execute("TRUNCATE TABLE fastvc_rag.embeddings RESTART IDENTITY")
        cur.execute("TRUNCATE TABLE fastvc_rag.chunks RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE fastvc_rag.documents RESTART IDENTITY CASCADE")
        conn.commit()


def _insert_companies(specs: list[dict]) -> dict[str, int]:
    slug_to_id: dict[str, int] = {}
    with connect() as conn, conn.cursor() as cur:
        for s in specs:
            cur.execute(
                """
                INSERT INTO fastvc.companies
                  (slug, name, hq_city, hq_state, country, sector, sub_sector, website,
                   founded_year, employees, revenue_ltm, ebitda_ltm, ebitda_margin,
                   growth_rate, ownership, deal_stage, deal_type, enterprise_value,
                   ask_multiple, description, seller_intent, triage_score, triage_priority,
                   startup_stage, business_model, arr, mrr, gross_margin, net_burn,
                   runway_months, burn_multiple, net_retention, gross_retention,
                   total_funding, last_round_date, last_round_type, last_round_amount,
                   pre_money_valuation, post_money_valuation, target_check_size,
                   target_ownership_pct, fundraising_status, momentum_score, thesis_score)
                VALUES (%(slug)s, %(name)s, %(hq_city)s, %(hq_state)s, %(country)s,
                        %(sector)s, %(sub_sector)s, %(website)s,
                        %(founded_year)s, %(employees)s, %(revenue_ltm)s, %(ebitda_ltm)s,
                        %(ebitda_margin)s, %(growth_rate)s, %(ownership)s, %(deal_stage)s,
                        %(deal_type)s, %(enterprise_value)s, %(ask_multiple)s,
                        %(description)s, %(seller_intent)s, %(triage_score)s, %(triage_priority)s,
                        %(startup_stage)s, %(business_model)s, %(arr)s, %(mrr)s,
                        %(gross_margin)s, %(net_burn)s, %(runway_months)s,
                        %(burn_multiple)s, %(net_retention)s, %(gross_retention)s,
                        %(total_funding)s, %(last_round_date)s::date, %(last_round_type)s,
                        %(last_round_amount)s, %(pre_money_valuation)s,
                        %(post_money_valuation)s, %(target_check_size)s,
                        %(target_ownership_pct)s, %(fundraising_status)s,
                        %(momentum_score)s, %(thesis_score)s)
                ON CONFLICT (slug) DO UPDATE SET
                  name = EXCLUDED.name, description = EXCLUDED.description,
                  startup_stage = EXCLUDED.startup_stage, arr = EXCLUDED.arr,
                  momentum_score = EXCLUDED.momentum_score,
                  thesis_score = EXCLUDED.thesis_score
                RETURNING id, slug
                """,
                s,
            )
            row = cur.fetchone()
            slug_to_id[row[1]] = row[0]
        conn.commit()
    return slug_to_id


def _insert_cap_tables(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    n = 0
    as_of = date.today().replace(day=1)
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            ct = RR.generate_for_company(co, as_of, rng)
            cur.execute(
                """
                INSERT INTO fastvc.cap_tables (company_id, as_of_date, holders, total_shares, post_money)
                VALUES (%s, %s::date, %s::jsonb, %s, %s)
                ON CONFLICT (company_id, as_of_date) DO UPDATE SET
                  holders = EXCLUDED.holders,
                  total_shares = EXCLUDED.total_shares,
                  post_money = EXCLUDED.post_money
                """,
                (cid, ct["as_of_date"], json.dumps(ct["holders"]),
                 ct["total_shares"], ct["post_money"]),
            )
            n += 1
        conn.commit()
    return n


def _insert_venture_intelligence(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> dict:
    """Seed funding rounds, founders, warm paths and fresh startup signals."""
    first_names = ["Maya", "Elena", "Sofia", "Amir", "Noah", "Lucas", "Aino", "Karl", "Priya", "Jonas"]
    last_names = ["Chen", "Kask", "Patel", "Niemi", "Andersson", "Meyer", "Martin", "Taylor", "Rao", "Lepp"]
    employers = ["Stripe", "Wise", "DeepMind", "Datadog", "Shopify", "Revolut", "Nvidia", "HubSpot"]
    schools = ["Stanford", "MIT", "Cambridge", "ETH Zurich", "Aalto", "Imperial College"]
    connectors = ["Alex Partner", "Sam Principal", "Taylor Founder", "Jordan LP", "Morgan Operator"]
    signal_templates = [
        ("key_hire", "Added a first senior go-to-market leader"),
        ("headcount", "Engineering headcount accelerated over the last quarter"),
        ("launch", "Released a major product capability"),
        ("traction", "Customer and usage momentum increased"),
        ("founder_move", "Founder profile showed new company-building activity"),
        ("funding", "Entered an active fundraising window"),
    ]
    counts = {"rounds": 0, "founders": 0, "connections": 0, "signals": 0}
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            # One canonical latest round plus a prior round for Series A+.
            rounds = [(co["last_round_date"], co["last_round_type"],
                       co["last_round_amount"], co["pre_money_valuation"],
                       co["post_money_valuation"])]
            if co["startup_stage"] in {"series_a", "series_b", "series_c", "growth"}:
                prior_amount = max(500_000, co["last_round_amount"] * .28)
                prior_post = max(prior_amount * 2.5, co["pre_money_valuation"] * .35)
                prior_type = {"series_a": "seed", "series_b": "series_a",
                              "series_c": "series_b", "growth": "series_c"}[co["startup_stage"]]
                prior_date = (date.fromisoformat(co["last_round_date"]) - relativedelta(months=20)).isoformat()
                rounds.append((prior_date, prior_type, prior_amount, prior_post - prior_amount, prior_post))
            for announced, round_type, amount, pre, post in rounds:
                cur.execute(
                    """INSERT INTO fastvc.funding_rounds
                       (company_id, announced_date, round_type, amount_raised, pre_money,
                        post_money, lead_investor, participating_investors, instrument, source)
                       VALUES (%s,%s::date,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (company_id, announced_date, round_type) DO NOTHING""",
                    (cid, announced, round_type, amount, pre, post,
                     rng.choice(["Northstar Ventures", "Foundry Capital", "Altitude", "Seedline"]),
                     [rng.choice(["Operator Fund", "Frontier Angels", "Arc Ventures"])],
                     "preferred_equity" if round_type not in {"pre_seed", "seed"} else rng.choice(["safe", "preferred_equity"]),
                     "Synthetic company update"),
                )
                counts["rounds"] += 1

            for founder_idx in range(rng.choice([1, 2, 2, 3])):
                full_name = f"{rng.choice(first_names)} {rng.choice(last_names)}"
                founder_slug = f"{co['slug']}-{founder_idx + 1}"
                cur.execute(
                    """INSERT INTO fastvc.founders
                       (slug, name, title, email, linkedin_url, location, education,
                        prior_companies, repeat_founder, technical, founder_score)
                       VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
                       ON CONFLICT (slug) DO UPDATE SET name=EXCLUDED.name
                       RETURNING id""",
                    (founder_slug, full_name, "Co-founder",
                     f"{full_name.lower().replace(' ', '.')}@{co['slug']}.example",
                     f"https://linkedin.example/in/{founder_slug}", co["hq_city"],
                     json.dumps([rng.choice(schools)]), json.dumps([rng.choice(employers)]),
                     rng.random() < .28, rng.random() < .68, round(rng.uniform(62, 96), 1)),
                )
                founder_id = cur.fetchone()[0]
                cur.execute(
                    """INSERT INTO fastvc.founder_company_links
                       (founder_id, company_id, role, started_at, ownership_pct)
                       VALUES (%s,%s,%s,%s::date,%s)
                       ON CONFLICT (founder_id, company_id) DO NOTHING""",
                    (founder_id, cid, "co_founder", f"{co['founded_year']}-01-01",
                     round(rng.uniform(12, 48), 1)),
                )
                counts["founders"] += 1
                if founder_idx == 0 and rng.random() < .7:
                    cur.execute(
                        """INSERT INTO fastvc.team_connections
                           (founder_id, company_id, connector_name, relationship, strength,
                            last_interaction, notes)
                           VALUES (%s,%s,%s,%s,%s,%s::date,%s)""",
                        (founder_id, cid, rng.choice(connectors),
                         rng.choice(["emailed", "met", "linkedin", "portfolio", "lp"]),
                         rng.randint(2, 5),
                         (date.today() - relativedelta(days=rng.randint(5, 500))).isoformat(),
                         "Synthetic warm path for product demonstration"),
                    )
                    counts["connections"] += 1

            for signal_type, title in rng.sample(signal_templates, k=3):
                signal_date = date.today() - relativedelta(days=rng.randint(1, 120))
                cur.execute(
                    """INSERT INTO fastvc.startup_signals
                       (company_id, signal_type, title, detail, signal_date, strength, source, metadata)
                       VALUES (%s,%s,%s,%s,%s::date,%s,%s,%s::jsonb)
                       ON CONFLICT (company_id, signal_type, title, signal_date) DO NOTHING""",
                    (cid, signal_type, title,
                     f"{co['name']}: {title.lower()}; verify in diligence before relying on it.",
                     signal_date.isoformat(), round(rng.uniform(55, 96), 1),
                     "Synthetic signal feed", json.dumps({"demo": True})),
                )
                counts["signals"] += 1
        conn.commit()
    return counts


def _insert_financials(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    n = 0
    end_month = date.today().replace(day=1) - relativedelta(months=1)
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            rows = T12.generate_for_company(co, end_month, rng)
            for r in rows:
                cur.execute(
                    """
                    INSERT INTO fastvc.financials
                      (company_id, month, revenue, cogs, gross_profit, opex, ebitda,
                       adjustments, adj_ebitda, arr, gross_retention, net_retention)
                    VALUES (%s, %s::date, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s)
                    ON CONFLICT (company_id, month) DO UPDATE SET
                      revenue = EXCLUDED.revenue, cogs = EXCLUDED.cogs,
                      gross_profit = EXCLUDED.gross_profit, opex = EXCLUDED.opex,
                      ebitda = EXCLUDED.ebitda, adjustments = EXCLUDED.adjustments,
                      adj_ebitda = EXCLUDED.adj_ebitda,
                      arr = EXCLUDED.arr, gross_retention = EXCLUDED.gross_retention,
                      net_retention = EXCLUDED.net_retention
                    """,
                    (cid, r["month"], r["revenue"], r["cogs"], r["gross_profit"],
                     json.dumps(r["opex"]), r["ebitda"], json.dumps(r["adjustments"]),
                     r["adj_ebitda"], r["arr"], r["gross_retention"], r["net_retention"]),
                )
                n += 1
        conn.commit()
    return n


def _insert_contracts(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    """Insert synthetic customer MSAs (and a handful of supplier + employment) per company."""
    n = 0
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            # customer MSAs
            n_customers = rng.randint(8, 20)
            for _ in range(n_customers):
                start = date.today() - relativedelta(days=rng.randint(180, 1200))
                term_years = rng.choice([1, 2, 3, 3, 5])
                end = start + relativedelta(years=term_years)
                annual_value = rng.randint(60_000, 3_500_000)
                cur.execute(
                    """
                    INSERT INTO fastvc.contracts
                      (company_id, counterparty, contract_type, start_date, end_date,
                       annual_value, auto_renew, change_of_control_trigger,
                       termination_notice_days, exclusivity, status)
                    VALUES (%s, %s, %s, %s::date, %s::date, %s, %s, %s, %s, %s, %s)
                    """,
                    (cid,
                     rng.choice([
                         "Acme Industrial", "Vector Logistics", "Harborlight Holdings",
                         "Cascade Retail", "Northwind Distributors", "Meridian Hospitals",
                         "Alpine Foods", "Orbit Communications", "Brightline Logistics",
                         "Summit Health Systems", "Wavecrest Retail", "Keystone Partners",
                     ]) + " " + rng.choice(["Inc", "LLC", "Corp", "Co"]),
                     "customer_msa", start.isoformat(), end.isoformat(), annual_value,
                     rng.random() < 0.7, rng.random() < 0.35,
                     rng.choice([30, 60, 90, 90, 120]),
                     rng.random() < 0.12,
                     "active" if end > date.today() else "expired"),
                )
                n += 1
            # a few suppliers
            for _ in range(rng.randint(2, 6)):
                start = date.today() - relativedelta(days=rng.randint(90, 900))
                end = start + relativedelta(years=rng.choice([2, 3, 5]))
                cur.execute(
                    """
                    INSERT INTO fastvc.contracts
                      (company_id, counterparty, contract_type, start_date, end_date,
                       annual_value, auto_renew, change_of_control_trigger,
                       termination_notice_days, exclusivity, status)
                    VALUES (%s, %s, %s, %s::date, %s::date, %s, %s, %s, %s, %s, %s)
                    """,
                    (cid,
                     rng.choice(["Global Components", "Rising Sun Manufacturing",
                                 "Pinecrest Services", "Nimbus Cloud Infra",
                                 "Westbridge Logistics", "Twin Cities Staffing"])
                     + " " + rng.choice(["Inc", "LLC", "Corp"]),
                     "supplier", start.isoformat(), end.isoformat(),
                     rng.randint(80_000, 1_500_000),
                     rng.random() < 0.5, rng.random() < 0.2,
                     rng.choice([30, 60, 90]), rng.random() < 0.2,
                     "active"),
                )
                n += 1
        conn.commit()
    return n


RISK_POOL = [
    ("financial", "Customer concentration risk", "Validate top accounts and diversify pipeline"),
    ("financial", "Runway below next-round threshold", "Agree a milestone-based operating plan"),
    ("financial", "ARR definition or recognition uncertainty", "Reconcile contracts, billing and revenue"),
    ("financial", "Burn multiple above stage benchmark", "Identify hiring and infrastructure efficiency levers"),
    ("team", "Founder or key-person dependency", "Build succession, hiring and retention plans"),
    ("technology", "Architecture scalability risk", "Run targeted architecture and load review"),
    ("technology", "Third-party model or platform dependency", "Model cost, availability and substitution risk"),
    ("operational", "Hiring plan exceeds recruiting capacity", "Sequence critical roles and map talent channels"),
    ("legal", "Pending litigation exposure", "Obtain legal opinion and reserve estimate"),
    ("legal", "IP ownership ambiguity", "Complete founder, employee and contractor IP chain of title"),
    ("legal", "GDPR compliance gaps", "Engage privacy counsel for gap assessment"),
    ("legal", "Financing approval or consent gap", "Map board, shareholder and contractual approvals"),
    ("market", "Category demand may be cyclical", "Model downside growth and financing scenarios"),
    ("market", "Regulatory change risk", "Monitor pending legislation and model impact"),
    ("market", "Competitive entry threat", "Benchmark product moat and distribution against leaders"),
    ("product", "Product-market fit evidence is shallow", "Expand usage analysis and customer references"),
    ("gtm", "Sales motion is not repeatable", "Reconcile pipeline, win rates and rep productivity"),
    ("portfolio", "Retention deterioration", "Prioritize activation, success and expansion experiments"),
]

MILESTONE_POOL = [
    ("Founder meeting", "Deal lead"),
    ("Startup screening note", "Deal lead"),
    ("Data-room access and audit", "Operations"),
    ("Metrics and cap-table reconciliation", "Finance"),
    ("Product and market diligence", "Deal lead"),
    ("Legal due diligence memo", "Legal"),
    ("Technology and security assessment", "Operations"),
    ("Term sheet review", "Legal"),
    ("IC memo submitted", "Deal lead"),
    ("Round and ownership model", "Finance"),
    ("Closing conditions complete", "Legal"),
    ("Portfolio support plan agreed", "Operations"),
]


def _insert_risks(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    n = 0
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            k = rng.randint(3, 6)
            picks = rng.sample(RISK_POOL, min(k, len(RISK_POOL)))
            for cat, title, mitigation in picks:
                cur.execute(
                    "INSERT INTO fastvc.deal_risks "
                    "(company_id, title, probability, impact, category, mitigation) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (cid, title, rng.randint(1, 5), rng.randint(1, 5), cat, mitigation),
                )
                n += 1
        conn.commit()
    return n


def _insert_milestones(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    n = 0
    today = date.today()
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            stage = co.get("deal_stage") or "sourced"
            if stage in ("exited", "passed"):
                continue
            k = rng.randint(4, 7)
            picks = rng.sample(MILESTONE_POOL, min(k, len(MILESTONE_POOL)))
            base_offset = rng.randint(-30, 30)
            for i, (title, owner) in enumerate(picks):
                due = today + relativedelta(days=base_offset + i * rng.randint(15, 35))
                pct = rng.choice([0, 0, 20, 40, 60, 80, 100, 100])
                if pct == 100:
                    status = "done"
                elif due < today and pct < 100:
                    status = "overdue"
                elif pct > 0 and rng.random() < 0.08:
                    status = "blocked"
                else:
                    status = "open"
                cur.execute(
                    "INSERT INTO fastvc.deal_milestones "
                    "(company_id, title, due_date, owner, pct_complete, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (cid, title, due.isoformat(), owner, pct, status),
                )
                n += 1
        conn.commit()
    return n


def _insert_txn_comps(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> tuple[int, int]:
    s = r = 0
    with connect() as conn, conn.cursor() as cur:
        for cid, co in cos_with_ids:
            for c in CMP.generate_transaction_comps(co, rng):
                cur.execute(
                    """
                    INSERT INTO fastvc.transaction_comps
                      (company_id, target_name, acquirer, sector, sub_sector, country,
                       announce_date, close_date, enterprise_value, revenue, ebitda,
                       ev_revenue, ev_ebitda, deal_type, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::date, %s::date, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (cid, c["target_name"], c["acquirer"], c["sector"], c["sub_sector"],
                     c["country"], c["announce_date"], c["close_date"], c["enterprise_value"],
                     c["revenue"], c["ebitda"], c["ev_revenue"], c["ev_ebitda"],
                     c["deal_type"], c["source"]),
                )
                s += 1
            for c in CMP.generate_trading_comps(co, rng):
                cur.execute(
                    """
                    INSERT INTO fastvc.trading_comps
                      (company_id, ticker, peer_name, sector, market_cap, ev,
                       revenue_ltm, ebitda_ltm, ev_revenue, ev_ebitda, rev_growth,
                       ebitda_margin, as_of_date, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::date, %s)
                    """,
                    (cid, c["ticker"], c["peer_name"], c["sector"], c["market_cap"], c["ev"],
                     c["revenue_ltm"], c["ebitda_ltm"], c["ev_revenue"], c["ev_ebitda"],
                     c["rev_growth"], c["ebitda_margin"], c["as_of_date"], c["source"]),
                )
                r += 1
        conn.commit()
    return s, r


def _insert_market_signals(rows: list[dict]) -> int:
    with connect() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO fastvc.market_signals
                  (sector, sub_sector, metric, value, as_of_date, source)
                VALUES (%s, %s, %s, %s, %s::date, %s)
                ON CONFLICT (sector, sub_sector, metric, as_of_date) DO UPDATE SET
                  value = EXCLUDED.value, source = EXCLUDED.source
                """,
                (r["sector"], r["sub_sector"], r["metric"], r["value"], r["as_of_date"], r["source"]),
            )
        conn.commit()
    return len(rows)


def _insert_lps(rows: list[dict]) -> int:
    with connect() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                """
                INSERT INTO fastvc.investor_crm
                  (name, firm, lp_type, email, commitment_size, stage, focus, geography,
                   aum, last_touch, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::date, %s)
                """,
                (r["name"], r["firm"], r["lp_type"], r["email"], r["commitment_size"],
                 r["stage"], r["focus"], r["geography"], r["aum"],
                 r["last_touch"], r["notes"]),
            )
        conn.commit()
    return len(rows)


def _index_rag(cos_with_ids: list[tuple[int, dict]], rng: random.Random) -> int:
    """Index DD docs per company + top-2 customer MSAs per company + industry reports."""
    docs: list[DocIn] = []

    # Sample customer MSAs per company (top 2)
    for cid, co in cos_with_ids:
        with connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT counterparty, start_date, end_date, annual_value "
                "FROM fastvc.contracts WHERE company_id = %s AND contract_type = 'customer_msa' "
                "ORDER BY annual_value DESC LIMIT 2",
                (cid,),
            )
            msas = cur.fetchall()
        for (counterparty, start_d, end_d, av) in msas:
            av_f = float(av) if av is not None else 0
            unit = {"holder": counterparty, "lease_start": str(start_d),
                    "lease_end": str(end_d), "rent": int(av_f)}
            body = LEASE.generate_lease_body(prop=co, unit=unit, rng=rng)
            docs.append(DocIn(
                title=f"MSA — {co['name']} / {counterparty}",
                doc_type="msa",
                text=body,
                company_id=cid,
                metadata={"counterparty": counterparty, "annual_value": av_f,
                          "sector": co["sector"]},
            ))

    # DD docs per company
    for cid, co in cos_with_ids:
        for d in DOC.generate_all_for_property(co, rng):
            docs.append(DocIn(
                title=d["title"],
                doc_type=d["doc_type"],
                text=d["text"],
                company_id=cid,
                metadata={"sector": co["sector"], "sub_sector": co["sub_sector"]},
            ))

    # Industry reports by sector / sub_sector
    for d in DOC.generate_market_reports([c for _, c in cos_with_ids], rng):
        docs.append(DocIn(
            title=d["title"],
            doc_type=d["doc_type"],
            text=d["text"],
            metadata={},
        ))

    log.info("embedding + upserting %d documents", len(docs))
    ids = upsert_documents(docs, replace=False)
    return len(ids)


def run(seed: int = 42, skip_rag: bool = False, limit: int | None = None, fresh: bool = False) -> None:
    if fresh:
        print("truncating fastvc tables (preserving chat history)…")
        _truncate()

    rng = random.Random(seed)
    specs = P.generate(seed=seed)
    if limit:
        specs = specs[:limit]
    print(f"generated {len(specs)} companies")

    slug_to_id = _insert_companies(specs)
    cos_with_ids = [(slug_to_id[s["slug"]], s) for s in specs]

    venture_counts = _insert_venture_intelligence(cos_with_ids, rng)
    print("inserted venture intelligence: " + ", ".join(
        f"{value} {key}" for key, value in venture_counts.items()))

    n = _insert_cap_tables(cos_with_ids, rng)
    print(f"inserted cap tables for {n} companies")

    n = _insert_financials(cos_with_ids, rng)
    print(f"inserted {n} monthly financial rows")

    n = _insert_contracts(cos_with_ids, rng)
    print(f"inserted {n} contracts (customer MSAs + suppliers)")

    n = _insert_risks(cos_with_ids, rng)
    print(f"inserted {n} deal risks")

    n = _insert_milestones(cos_with_ids, rng)
    print(f"inserted {n} deal milestones")

    s, r = _insert_txn_comps(cos_with_ids, rng)
    print(f"inserted {s} transaction comps, {r} trading comps")

    ms_rows = MS.generate([c for _, c in cos_with_ids], seed=seed)
    n = _insert_market_signals(ms_rows)
    print(f"inserted {n} market signal rows")

    n = _insert_lps(LP.generate(count=60, seed=seed))
    print(f"inserted {n} LP contacts")

    if not skip_rag:
        n = _index_rag(cos_with_ids, rng)
        print(f"indexed {n} RAG documents")
        build_ann_index()

    print("done")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-rag", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--fresh", action="store_true", help="truncate tables before seeding")
    args = ap.parse_args()
    run(seed=args.seed, skip_rag=args.skip_rag, limit=args.limit, fresh=args.fresh)
