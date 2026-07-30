from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.diligence import abstract_leases
from tools.rag import retrieve_documents
from tools.venture import get_startup, search_startups

SPEC = AGENTS_BY_SLUG["lease_abstractor"]
TOOLS = [get_startup, search_startups, abstract_leases, retrieve_documents]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
