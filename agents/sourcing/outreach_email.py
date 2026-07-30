from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.search import web_search
from tools.rag import retrieve_documents
from tools.venture import find_warm_paths, get_startup, search_startups

SPEC = AGENTS_BY_SLUG["outreach_email"]
TOOLS = [search_startups, get_startup, find_warm_paths, retrieve_documents, web_search]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
