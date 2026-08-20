"""Full Diligence Run — the parallel diligence orchestrator.

Unlike every other agent module, this one does not return a `create_react_agent`.
It fans out the five venture-diligence specialists concurrently on a single
target, then synthesizes their findings into one ranked memo.

Two entry points:

- ``diligence_stream(target)`` — the async generator the chat route drives.
  Sub-agents run via ``ainvoke`` *outside* any parent ``astream_events`` context,
  so their intermediate reasoning never leaks into the streamed answer; only the
  final synthesis is streamed to the user. This is the intended path.
- ``build()`` — returns a ``RunnableLambda`` so ``cached_agent("super_analyst")``
  resolves like any other agent (smoke test + route fallback). It runs the same
  fan-out and returns the finished memo as a single ``AIMessage``.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda

from agents.base import _load_system_prompt, cached_agent
from agents.registry import AGENTS_BY_SLUG
from utils.llm import build_agent_llm

log = logging.getLogger(__name__)

SPEC = AGENTS_BY_SLUG["super_analyst"]
TOOLS: list = []  # orchestrator delegates to specialist agents, not tools directly

# (display label, specialist slug) — the five venture-diligence workstreams.
WORKSTREAMS: list[tuple[str, str]] = [
    ("Data room",            "doc_room_auditor"),
    ("Legal, IP & reg",      "title_zoning"),
    ("Product & GTM",        "physical_condition"),
    ("Technology & security", "environmental_risk"),
    ("Commercial contracts", "lease_abstractor"),
]

# Five ReAct agents each making several LLM + tool calls is a real burst on the
# xAI key; cap how many workstreams run at once.
_MAX_CONCURRENT = 3
_SEMAPHORE = asyncio.Semaphore(_MAX_CONCURRENT)


async def _run_one(label: str, slug: str, target: str) -> tuple[str, str]:
    """Run a single specialist workstream to completion and return its finding."""
    async with _SEMAPHORE:
        graph = cached_agent(slug)
        prompt = (
            f"Perform your {label} diligence workstream on: {target}.\n"
            "Use FastVC tools and retrieve records before asserting facts. Return concise "
            "findings, each with a severity (High/Medium/Low) and the source you relied on. "
            "State data gaps plainly instead of inventing evidence."
        )
        res = await graph.ainvoke({"messages": [HumanMessage(content=prompt)]})
        return label, res["messages"][-1].content


def _synthesis_messages(target: str, sections: list[tuple[str, str]]) -> list:
    joined = "\n\n".join(f"## {label}\n{text}" for label, text in sections)
    system = _load_system_prompt(SPEC)
    human = (
        f"Synthesize the five diligence workstreams below on {target} into ONE ranked "
        "diligence memo. Structure it as:\n"
        "1. A one-line recommendation (Proceed / Deepen / Pass) with the single biggest reason.\n"
        "2. A risk table: each workstream, its top finding, severity, and your confidence "
        "(High/Medium/Low) in that read given the evidence available.\n"
        "3. The three open questions that would most change the decision.\n\n"
        "Do not invent facts beyond the workstreams. Where a workstream reported thin evidence, "
        "say so and lower the confidence rather than filling the gap.\n\n"
        f"{joined}"
    )
    return [SystemMessage(content=system), HumanMessage(content=human)]


async def diligence_stream(target: str):
    """Async generator: yields orchestration events for the chat route.

    Event tuples:
      ("start", [labels])        — all workstreams launched
      ("section_done", label)    — one workstream finished (or failed)
      ("memo", delta)            — a streamed chunk of the synthesized memo
    """
    coros = [_run_one(label, slug, target) for label, slug in WORKSTREAMS]
    yield ("start", [label for label, _ in WORKSTREAMS])

    sections: list[tuple[str, str]] = []
    for fut in asyncio.as_completed(coros):
        try:
            label, text = await fut
            sections.append((label, text))
            yield ("section_done", label)
        except Exception as exc:  # noqa: BLE001 — never let one lane abort the run
            log.warning("diligence workstream failed: %s", exc)
            sections.append(("A workstream (failed)", f"This workstream errored: {exc}"))
            yield ("section_done", "a workstream (failed)")

    llm = build_agent_llm()
    async for chunk in llm.astream(_synthesis_messages(target, sections)):
        if chunk.content:
            yield ("memo", chunk.content)


async def _run_and_synthesize(target: str) -> str:
    """Non-streaming fan-out + synthesis, used by the RunnableLambda fallback."""
    results = await asyncio.gather(
        *[_run_one(label, slug, target) for label, slug in WORKSTREAMS],
        return_exceptions=True,
    )
    sections: list[tuple[str, str]] = []
    for item in results:
        if isinstance(item, Exception):
            sections.append(("A workstream (failed)", f"This workstream errored: {item}"))
        else:
            sections.append(item)
    llm = build_agent_llm()
    return (await llm.ainvoke(_synthesis_messages(target, sections))).content


@lru_cache(maxsize=1)
def build():
    """Return a Runnable compatible with cached_agent()/astream_events.

    The chat route special-cases ``super_analyst`` and drives ``diligence_stream``
    directly; this lambda is the fallback so the slug still resolves everywhere
    (smoke test, generalist fallback path) and produces the finished memo.
    """
    async def _invoke(state: dict) -> dict:
        messages = state.get("messages") or []
        target = messages[-1].content if messages else ""
        memo = await _run_and_synthesize(target)
        return {"messages": [AIMessage(content=memo)]}

    return RunnableLambda(_invoke)
