"""Tests for config loading and the multi-provider LLM registry."""

import pytest

from src.core.config import Config, get_api_key, get_config
from src.core.llm_registry import LLMRegistryError, get_llm_for_agent, get_provider


@pytest.fixture(autouse=True)
def clear_provider_cache():
    """get_provider is lru_cached; isolate tests from each other."""
    get_provider.cache_clear()
    yield
    get_provider.cache_clear()


@pytest.fixture
def no_api_keys(monkeypatch):
    for var in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)


class TestConfig:
    def test_dotted_path_access(self):
        cfg = Config({"a": {"b": {"c": 42}}})
        assert cfg.get("a.b.c") == 42
        assert cfg["a.b.c"] == 42

    def test_missing_path_returns_default(self):
        cfg = Config({"a": 1})
        assert cfg.get("a.b.c") is None
        assert cfg.get("nope", "fallback") == "fallback"

    def test_missing_key_raises(self):
        with pytest.raises(KeyError, match="nope"):
            Config({})["nope"]

    def test_project_config_has_required_sections(self):
        cfg = get_config()
        assert cfg.get("llm.providers") is not None
        assert cfg.get("llm.agents") is not None
        assert cfg.get("rag.top_k") >= 1
        # 30-minute cache TTL is a project FAQ requirement.
        assert cfg.get("market_data.cache_ttl_seconds") == 1800

    def test_every_agent_maps_to_a_configured_provider(self):
        cfg = get_config()
        providers = set(cfg.get("llm.providers", {}))
        for agent, provider in cfg.get("llm.agents", {}).items():
            assert provider in providers, f"{agent} maps to unknown provider {provider}"

    def test_get_api_key_empty_is_none(self, monkeypatch):
        monkeypatch.setenv("SOME_TEST_KEY", "")
        assert get_api_key("SOME_TEST_KEY") is None
        monkeypatch.setenv("SOME_TEST_KEY", "abc")
        assert get_api_key("SOME_TEST_KEY") == "abc"


class TestLLMRegistry:
    def test_unknown_provider_raises(self):
        with pytest.raises(LLMRegistryError, match="Unknown LLM provider"):
            get_provider("watson")

    def test_missing_key_raises(self, no_api_keys):
        with pytest.raises(LLMRegistryError, match="GROQ_API_KEY"):
            get_provider("groq")

    def test_unmapped_agent_raises(self):
        with pytest.raises(LLMRegistryError, match="No LLM mapping"):
            get_llm_for_agent("nonexistent_agent")

    def test_no_keys_at_all_raises_helpful_error(self, no_api_keys):
        with pytest.raises(LLMRegistryError, match="at least one API key"):
            get_llm_for_agent("router")

    def test_builds_provider_when_key_present(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")
        llm = get_provider("groq")
        assert llm is get_provider("groq")  # cached singleton

    def test_fallback_to_available_provider(self, monkeypatch, no_api_keys):
        # Router maps to groq; only OpenAI has a key -> falls back to OpenAI.
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
        llm = get_llm_for_agent("router")
        assert type(llm).__name__ == "ChatOpenAI"
