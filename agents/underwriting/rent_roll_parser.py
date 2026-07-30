from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.venture import build_round_model, cap_table_snapshot, get_startup

SPEC = AGENTS_BY_SLUG["rent_roll_parser"]
TOOLS = [get_startup, cap_table_snapshot, build_round_model]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
