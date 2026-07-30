from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.search import web_search
from tools.rag import retrieve_documents
from tools.venture import recent_startup_signals, search_startups

SPEC = AGENTS_BY_SLUG["market_scanner"]
TOOLS = [search_startups, recent_startup_signals, retrieve_documents, web_search]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
