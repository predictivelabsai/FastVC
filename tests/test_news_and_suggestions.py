from agents.router import route_intent
from chat.suggestions import agent_prompt_map, welcome_suggestions
from utils.news import (
    DEFAULT_SOURCE_IDS, _is_relevant, available_sources, normalise_source_ids,
)


def test_news_catalogue_is_focused_and_configurable():
    sources = available_sources()
    ids = {source["id"] for source in sources}
    assert {"ft_private_equity", "bloomberg_private_markets", "techcrunch_startups"} <= ids
    assert not {"bbc_business", "reuters_business", "wsj_world"} & ids
    assert normalise_source_ids(["saastr", "not-a-source"]) == ("saastr",)
    assert normalise_source_ids([]) == DEFAULT_SOURCE_IDS


def test_bloomberg_filter_admits_private_markets_not_macro_politics():
    source = {"strict": True}
    assert _is_relevant(source, "Private equity fund closes a new buyout vehicle", "")
    assert not _is_relevant(source, "Election debate shifts the economic outlook", "")


def test_chat_prompts_use_live_company_context_and_plain_english():
    companies = (
        {"name": "Real Alpha OÜ"},
        {"name": "Real Beta UAB"},
        {"name": "Real Gamma SIA"},
    )
    prompts = agent_prompt_map(companies)
    rendered = [prompt for values in prompts.values() for prompt in values]
    assert any("Real Alpha OÜ" in prompt for prompt in rendered)
    assert all(not prompt.split(" ", 1)[0].endswith(":") for prompt in rendered)
    assert "Meridian Health" not in " ".join(rendered)
    assert len(welcome_suggestions(prompts)) == 6


def test_intent_wrapper_supports_plain_english_and_hidden_agent_selection():
    selected = route_intent("Review the available annual filings.", "t12_normalizer")
    assert selected.agent_slug == "t12_normalizer"
    assert selected.intent_source == "selected_agent"
    assert selected.message == "Review the available annual filings."

    legacy = route_intent("memo: Draft a sourced pre-read")
    assert legacy.agent_slug == "investor_memo"
    assert legacy.intent_source == "legacy_shortcut"
    assert legacy.message == "Draft a sourced pre-read"
