from typing import TYPE_CHECKING, Any

import structlog
from django.conf import settings
from langchain_core.runnables import RunnableConfig

if TYPE_CHECKING:
    from apps.assistant.services.llm_service import LLMService

from apps.assistant.intents.registry import LLMConfig
from apps.assistant.services.providers.bedrock import (
    build_chat_llm as build_bedrock_chat_llm,
    build_title_llm as build_bedrock_title_llm,
    get_active_bedrock_chat_model_id,
    get_active_bedrock_title_model_id,
    get_bedrock_model_display_name,
)

logger = structlog.get_logger("default")


def _get_configured_llm_provider(provider: str | None = None) -> str:
    """Return the active LLM provider in normalized form."""
    return (provider or getattr(settings, "LLM_PROVIDER", "AWS_BEDROCK")).upper()


def get_llm_service() -> LLMService:
    """Return a cached LLMService instance (builds the graph once per process)."""
    from apps.assistant.services.llm_service import get_llm_service as _get_llm_service  # noqa: PLC0415

    return _get_llm_service()


def get_active_chat_model_id() -> str | None:
    """Return the active chat model ID for the configured provider."""
    provider = _get_configured_llm_provider()
    if provider == "AWS_BEDROCK":
        return get_active_bedrock_chat_model_id()
    return getattr(settings, "LLM_MODEL", None)


def get_active_title_model_id() -> str | None:
    """Return the active title model ID for the configured provider."""
    provider = _get_configured_llm_provider()
    if provider == "AWS_BEDROCK":
        return get_active_bedrock_title_model_id()
    return getattr(settings, "LLM_MODEL", None)


def format_model_display_name(raw_model: str | None, provider: str | None = None) -> str | None:
    """Return a provider-appropriate display name for a model identifier."""
    if not raw_model:
        return None

    resolved_provider = _get_configured_llm_provider(provider)
    if resolved_provider == "AWS_BEDROCK":
        return get_bedrock_model_display_name(raw_model)
    return raw_model


def get_active_chat_model_display_name() -> str | None:
    """Return the display-safe model name for the active chat provider."""
    return format_model_display_name(get_active_chat_model_id())


def get_active_title_model_display_name() -> str | None:
    """Return the display-safe model name for the active title provider."""
    return format_model_display_name(get_active_title_model_id())


def build_chat_llm(llm_config: LLMConfig | None = None, **kwargs: Any) -> Any:
    """
    Vendor-agnostic factory for chat LLMs.
    Currently defaults to Bedrock but can be extended for Vertex, etc.
    """
    provider = _get_configured_llm_provider(llm_config.provider if llm_config else None)

    if provider == "AWS_BEDROCK":
        return build_bedrock_chat_llm(llm_config, **kwargs)

    # TODO: Add more providers here (e.g., Vertex AI)
    raise ValueError(f"Unsupported LLM provider: {provider}")


def build_title_llm(**kwargs: Any) -> Any:
    """
    Vendor-agnostic factory for title LLMs.
    """
    provider = _get_configured_llm_provider()

    if provider == "AWS_BEDROCK":
        return build_bedrock_title_llm(**kwargs)

    raise ValueError(f"Unsupported LLM provider: {provider}")


def generate_thread_title(message_content: str, config: RunnableConfig | dict[str, object] | None = None) -> str:
    """
    Generate a concise thread title from the first message content.

    Extracted as a standalone function (not a method on LLMService) so that
    graph nodes can import it directly without introducing a circular dependency
    through LLMService → build_graph → nodes → LLMService.
    """
    from shared.utils import strip_thinking_blocks  # noqa: PLC0415 — avoids circular at module init

    llm = build_title_llm(temperature=0.0, max_tokens=64)
    if llm is None:
        return message_content[:47] + "..."

    prompt = (
        f"Generate a very short title (3 to 5 words) for a conversation "
        f'that starts with this message: "{message_content[:200]}"\n'
        f"Respond with only the title, no punctuation or quotes."
    )
    try:
        response = llm.invoke(prompt, config=config)
        return strip_thinking_blocks(response.content.strip())[:50]
    except Exception as e:
        logger.exception("Error generating thread title", error=str(e))
        return message_content[:47] + "..."
