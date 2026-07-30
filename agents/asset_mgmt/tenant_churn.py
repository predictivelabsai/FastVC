from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.asset import customer_churn_scores
from tools.venture import get_startup, search_startups, summarize_startup_metrics

SPEC = AGENTS_BY_SLUG["tenant_churn"]
TOOLS = [get_startup, search_startups, summarize_startup_metrics, customer_churn_scores]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
