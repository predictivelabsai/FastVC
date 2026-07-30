from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.search import web_search
from tools.venture import get_startup, recent_startup_signals, search_startups

SPEC = AGENTS_BY_SLUG["seller_intent"]
TOOLS = [search_startups, get_startup, recent_startup_signals, web_search]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
