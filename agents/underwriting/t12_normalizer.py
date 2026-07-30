from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.venture import get_startup, summarize_startup_metrics

SPEC = AGENTS_BY_SLUG["t12_normalizer"]
TOOLS = [get_startup, summarize_startup_metrics]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
