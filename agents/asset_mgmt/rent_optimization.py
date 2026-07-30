from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.asset import pricing_opt_recs
from tools.venture import get_startup, search_startups, summarize_startup_metrics

SPEC = AGENTS_BY_SLUG["rent_optimization"]
TOOLS = [get_startup, search_startups, summarize_startup_metrics, pricing_opt_recs]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
