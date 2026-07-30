from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.capital import deal_brief
from tools.venture import get_startup, search_startups

SPEC = AGENTS_BY_SLUG["deal_teaser"]
TOOLS = [get_startup, search_startups, deal_brief]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
