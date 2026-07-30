from __future__ import annotations
from functools import lru_cache

from agents.base import build_agent
from agents.registry import AGENTS_BY_SLUG
from tools.diligence import audit_doc_room
from tools.rag import retrieve_documents
from tools.venture import get_startup, search_startups

SPEC = AGENTS_BY_SLUG["doc_room_auditor"]
TOOLS = [get_startup, search_startups, audit_doc_room, retrieve_documents]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
