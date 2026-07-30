"""Shared helpers for building LangGraph ReAct agents.

Every agent module exports `build()` that returns a cached graph. This module
provides the canonical factory so agents stay consistent in shape.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from agents.registry import AgentSpec
from utils.llm import build_agent_llm

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts" / "system"
SHARED_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "shared" / "vc_context.md"


def _load_system_prompt(spec: AgentSpec) -> str:
    shared = SHARED_PROMPT_FILE.read_text() if SHARED_PROMPT_FILE.exists() else ""
    specific_file = PROMPTS_DIR / f"{spec.slug}.md"
    specific = specific_file.read_text() if specific_file.exists() else ""
    if not specific:
        log.warning("no system prompt for %s — using shared context only", spec.slug)
    mandate = (
        f"# Your FastVC role\n\n"
        f"You are the **{spec.name}**. {spec.description}\n\n"
        f"Primary capability: {spec.one_liner}\n\n"
        "Use the venture-capital vocabulary and workflow in the shared context. "
        "Any legacy PEHero terminology in the operational notes below is an "
        "implementation detail: translate it into venture-native analysis and "
        "never expose legacy product names or buyout-specific assumptions. "
        "Retrieve before asserting facts and label assumptions clearly."
    )
    return (shared + "\n\n" + mandate + "\n\n# Operational tool notes\n\n" + specific).strip()


def build_agent(spec: AgentSpec, tools: list[BaseTool]):
    """Build a LangGraph ReAct agent with Grok + the provided tools.

    Intentionally NOT cached here — caller may want different tool sets per
    session. Agent module-level `build()` functions own their own caching.
    """
    system = _load_system_prompt(spec)
    llm = build_agent_llm()
    return create_react_agent(llm, tools, prompt=system or None)


@lru_cache(maxsize=64)
def cached_agent(slug: str):
    """Fetch a cached agent by slug. Looks up the module and calls its build()."""
    from agents import registry
    spec = registry.by_slug(slug)
    if spec is None:
        raise ValueError(f"unknown agent slug: {slug}")

    # Convention: agents/<category>/<slug>.py exports build()
    import importlib
    module = importlib.import_module(f"agents.{spec.category}.{spec.slug}")
    return module.build()
