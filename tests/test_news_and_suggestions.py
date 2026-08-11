from agents.router import route_intent
from chat.suggestions import agent_prompt_map, welcome_suggestions
from utils.news import (
    DEFAULT_SOURCE_IDS, _is_relevant, _limit_with_source_coverage,
    _parse_html_fallback, available_sources, normalise_source_ids,
)
from utils.news_preferences import _saved_selection_or_defaults


EUROPE_DEFAULTS = (
    "sifted", "tech_eu", "eu_startups", "tech_funding_news",
    "silicon_canals", "techcrunch_europe", "startus_magazine",
    "peak_capital", "deutsche_startups", "invest_europe",
)


def test_news_catalogue_is_focused_and_configurable():
    sources = available_sources()
    ids = {source["id"] for source in sources}
    assert {"ft_private_equity", "bloomberg_private_markets", "techcrunch_startups"} <= ids
    assert DEFAULT_SOURCE_IDS == EUROPE_DEFAULTS
    assert all(next(source for source in sources if source["id"] == source_id)["default"]
               for source_id in EUROPE_DEFAULTS)
    assert not {"bbc_business", "reuters_business", "wsj_world"} & ids
    assert normalise_source_ids(["saastr", "not-a-source"]) == ("saastr",)
    assert normalise_source_ids([]) == DEFAULT_SOURCE_IDS


def test_saved_former_defaults_rotate_but_custom_choices_remain():
    former_defaults = [
        "techcrunch_startups", "eu_startups", "sifted", "crunchbase_news",
        "tech_eu", "arctic_startup", "seedcamp", "pe_hub",
        "private_equity_international", "ft_private_equity",
        "bloomberg_private_markets",
    ]
    assert _saved_selection_or_defaults(former_defaults) == EUROPE_DEFAULTS
    assert _saved_selection_or_defaults(["sifted", "tech_eu"]) == ("sifted", "tech_eu")


def test_news_limit_reserves_a_slot_for_every_selected_source():
    articles = [
        {
            "source_id": "fast", "url": f"https://fast.example/{index}",
            "published": f"2026-08-11T12:{59 - index:02d}:00+00:00",
        }
        for index in range(5)
    ] + [{
        "source_id": "slow", "url": "https://slow.example/latest",
        "published": "2026-07-01T12:00:00+00:00",
    }]
    limited = _limit_with_source_coverage(articles, ("fast", "slow"), limit=3)
    assert len(limited) == 3
    assert {article["source_id"] for article in limited} == {"fast", "slow"}


def test_official_news_page_fallback_parses_and_deduplicates_cards():
    source = {
        "id": "invest_europe", "name": "Invest Europe",
        "category": "European private capital", "icon": "IE",
    }
    card = '''
      <a href="/news/newsroom/european-private-capital/"
         class="m-listing-item-module m-news-opinion-module">
        <h4>European private capital &amp; venture news</h4><h6>23 Jul 2026</h6>
      </a>
    '''
    articles = _parse_html_fallback(source, card + card)
    assert len(articles) == 1
    assert articles[0]["title"] == "European private capital & venture news"
    assert articles[0]["published"].startswith("2026-07-23")


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
