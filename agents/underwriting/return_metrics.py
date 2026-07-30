from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.venture import get_startup, model_venture_outcome, search_startups

SPEC = AGENTS_BY_SLUG["return_metrics"]
TOOLS = [get_startup, search_startups, model_venture_outcome]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
