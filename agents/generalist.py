"""Generalist fallback agent — used for prompts that don't match a specialist,
and as the safety net while Phase 6 agents are being built out.

Has access to the company search + RAG retrieval tools, so it can answer most
VC questions meaningfully even without a specialist routing.
"""

from __future__ import annotations

from functools import lru_cache

from agents.registry import AgentSpec
from agents.base import build_agent
from tools.rag import retrieve_documents
from tools.venture import get_startup, search_startups


SPEC = AgentSpec(
    slug="generalist",
    name="Generalist",
    category="sourcing",  # nominal; not shown in UI
    icon="◆",
    one_liner="Falls back when no specialist matches.",
    description="Catch-all agent with access to the startup universe and the RAG index.",
    prefix="ask:",
    example_prompts=(),
)

SYSTEM_PROMPT = """You are FastVC, an AI assistant for venture investment teams. You have access to:
- A startup universe spanning stealth and pre-seed through Series C and growth
- A RAG index of pitch decks, metrics, cap tables, MSAs, legal, product and technology diligence

When answering, favor tool calls over guessing. When you cite documents, always name the document title.
Be concise. Use markdown bullets for lists. Use **bold** for key figures.
"""


TOOLS = [search_startups, get_startup, retrieve_documents]


@lru_cache(maxsize=1)
def build():
    return build_agent(SPEC, TOOLS)
