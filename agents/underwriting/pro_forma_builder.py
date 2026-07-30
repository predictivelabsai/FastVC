from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.venture import build_round_model, get_startup, search_startups

SPEC = AGENTS_BY_SLUG["pro_forma_builder"]
TOOLS = [get_startup, search_startups, build_round_model]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
