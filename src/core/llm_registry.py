"""Multi-provider LLM registry.

Maps each agent to its configured provider (OpenAI / Gemini / Groq) per
config.yaml. Providers are swappable in config without code changes:

    groq   -> routing/classification (lowest latency)
    gemini -> high-volume RAG-grounded agents (free tier)
    openai -> calculation-heavy reasoning agents
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from src.core.config import get_api_key, get_config
from src.core.logging import get_logger

logger = get_logger(__name__)


class LLMRegistryError(RuntimeError):
    """Raised when a provider cannot be constructed (e.g. missing API key)."""


def _build_provider(name: str) -> BaseChatModel:
    cfg = get_config()
    spec = cfg.get(f"llm.providers.{name}")
    if spec is None:
        raise LLMRegistryError(f"Unknown LLM provider '{name}' (not in config.yaml)")

    api_key = get_api_key(spec["api_key_env"])
    if not api_key:
        raise LLMRegistryError(
            f"Provider '{name}' requires env var {spec['api_key_env']} to be set"
        )

    model = spec["model"]
    temperature = spec.get("temperature", 0.3)

    if name == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)
    if name == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model, temperature=temperature, google_api_key=api_key
        )
    if name == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=model, temperature=temperature, api_key=api_key)

    raise LLMRegistryError(f"No constructor implemented for provider '{name}'")


@lru_cache(maxsize=8)
def get_provider(name: str) -> BaseChatModel:
    """Return a cached chat model instance for a provider name."""
    llm = _build_provider(name)
    logger.info("Initialized LLM provider '%s'", name)
    return llm


def get_llm_for_agent(agent_name: str) -> BaseChatModel:
    """Return the chat model assigned to an agent, with provider fallback.

    If the configured provider's API key is missing, fall back to any other
    configured provider so a partially-configured environment still works.
    """
    cfg = get_config()
    provider_name = cfg.get(f"llm.agents.{agent_name}")
    if provider_name is None:
        raise LLMRegistryError(f"No LLM mapping for agent '{agent_name}' in config.yaml")

    try:
        return get_provider(provider_name)
    except LLMRegistryError as exc:
        logger.warning("Provider '%s' unavailable for agent '%s': %s", provider_name, agent_name, exc)
        for fallback in cfg.get("llm.providers", {}):
            if fallback == provider_name:
                continue
            try:
                llm = get_provider(fallback)
                logger.warning("Agent '%s' falling back to provider '%s'", agent_name, fallback)
                return llm
            except LLMRegistryError:
                continue
        raise LLMRegistryError(
            f"No usable LLM provider for agent '{agent_name}'. "
            "Set at least one API key in .env (see .env.example)."
        ) from exc
