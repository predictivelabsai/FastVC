"""Light smoke tests.

These do NOT hit the LLM — they verify that every agent module builds, that
the router dispatches sensibly, and that key tools return real data against
the synthetic corpus.

Run with:  pytest -q tests
"""

from __future__ import annotations

import json

import pytest

from agents.base import cached_agent
from agents.registry import AGENTS, AGENTS_BY_SLUG
from agents import router as agent_router


def test_health_endpoint():
    from starlette.testclient import TestClient
    from app import app

    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "fastvc"}


@pytest.mark.parametrize("spec", AGENTS, ids=lambda s: s.slug)
def test_every_agent_builds(spec):
    graph = cached_agent(spec.slug)
    assert graph is not None


@pytest.mark.parametrize("message,expected_slug", [
    ("screen: Northwind AI at Series A", "deal_triage"),
    ("round: model an $8M Series A", "pro_forma_builder"),
    ("metrics: normalize Meridian Health's ARR", "t12_normalizer"),
    ("memo: IC memo for Northwind AI", "investor_memo"),
    ("contracts: change-of-control terms across MSAs", "lease_abstractor"),
    ("support: rank initiatives for Northwind AI", "capex_prioritizer"),
    ("burn: what's driving runway variance?", "opex_variance"),
    ("retention: which customers are at risk?", "tenant_churn"),
    ("pricing: where is packaging below market?", "rent_optimization"),
    ("discover: European Seed developer-tool startups", "market_scanner"),
    ("comps: Series A vertical AI rounds", "comp_finder"),
    ("outcomes: model dilution through Series C", "return_metrics"),
])
def test_prefix_routing(message, expected_slug):
    assert agent_router.route(message) == expected_slug


def test_free_form_routing_falls_back_sensibly():
    slug = agent_router.route("what ARR multiple are Series A SaaS rounds using?")
    assert slug in AGENTS_BY_SLUG


def test_startup_search_returns_data():
    from tools.venture import search_startups
    out = json.loads(search_startups.invoke({"sector": "healthtech", "limit": 5}))
    assert out["count"] >= 1
    assert out["startups"][0]["sector"] == "healthtech"


def test_rag_retrieval_returns_citations():
    from rag.retriever import retrieve
    chunks = retrieve("change of control customer msa", k=3, doc_types=["msa"])
    assert len(chunks) >= 1
    assert all(c.doc_type == "msa" for c in chunks)


def test_startup_dossier_has_venture_context():
    from tools.venture import get_startup
    payload = json.loads(get_startup.invoke({"slug_or_id": "northwind-ai"}))
    assert payload["company"]["startup_stage"] == "series_a"
    assert payload["founders"]
    assert payload["funding_rounds"]


def test_round_and_outcome_models():
    from tools.venture import build_round_model, model_venture_outcome
    round_payload = json.loads(build_round_model.invoke({
        "slug_or_id": "northwind-ai", "round_type": "series_a",
        "pre_money": 32_000_000, "raise_amount": 8_000_000,
        "our_check": 5_000_000, "persist": False,
    }))
    assert round_payload["post_money"] == 40_000_000
    assert round_payload["fastvc_post_round_pct"] == 12.5
    outcome = json.loads(model_venture_outcome.invoke({
        "slug_or_id": "northwind-ai", "invested_capital": 5_000_000,
        "current_ownership_pct": 12.5, "future_dilution_pct": 35,
        "downside_exit": 50_000_000, "base_exit": 500_000_000,
        "upside_exit": 1_500_000_000, "persist": False,
    }))
    assert outcome["expected_gross_moic"] > 0


def test_integration_secrets_round_trip_without_plaintext():
    from tools.integrations import decrypt_secret, encrypt_secret, mask_secret, test_stub
    value = "vc-provider-test-key"
    encrypted = encrypt_secret(value)
    assert value not in encrypted
    assert decrypt_secret(encrypted) == value
    assert mask_secret(value).endswith("-key")
    assert test_stub("affinity", value)["ok"] is True
