"""
AWS Bedrock LLM factory helpers.

Central location for Bedrock-specific concerns:
  - Provider name inference from model/ARN identifiers
  - ChatBedrockConverse keyword-argument construction
  - Chat and title LLM instantiation

Both ``nodes.py`` and ``llm_service.py`` import from here. Do not duplicate
Bedrock logic in those modules.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from langchain_aws import ChatBedrockConverse

from apps.assistant.intents.registry import LLMConfig

# AWS cross-region inference profile IDs use a two-letter region prefix before
# the provider segment, e.g. ``us.amazon.nova-pro-v1:0`` or
# ``eu.anthropic.claude-3-haiku-20240307-v1:0``.
_CROSS_REGION_PREFIXES = frozenset({"us", "eu", "ap", "sa", "ca", "me", "af"})
# Minimum number of dot-separated parts to identify a cross-region prefix
_CROSS_REGION_MIN_PARTS = 2
_DEFAULT_LANGSMITH_BEDROCK_PROVIDER = "amazon_bedrock"


def get_active_bedrock_chat_model_id() -> str | None:
    """Return the configured Bedrock model/profile for chat flows."""
    return getattr(settings, "AWS_BEDROCK_CHAT_INFERENCE_PROFILE_ID", None) or getattr(
        settings, "AWS_BEDROCK_INFERENCE_PROFILE_ID", getattr(settings, "LLM_MODEL", None)
    )


def get_active_bedrock_title_model_id() -> str | None:
    """Return the configured Bedrock model/profile for title generation."""
    return getattr(settings, "AWS_BEDROCK_TITLE_INFERENCE_PROFILE_ID", None) or getattr(
        settings, "AWS_BEDROCK_INFERENCE_PROFILE_ID", None
    )


def get_bedrock_model_display_name(raw_model: str | None) -> str | None:
    """Return a display-safe Bedrock model name for API payloads and persistence."""
    if not raw_model:
        return None
    if raw_model.startswith("arn:aws:bedrock"):
        return raw_model.rsplit("/", maxsplit=1)[-1].split(":", maxsplit=1)[0]
    return raw_model


def infer_bedrock_provider(model_id: str | None) -> str | None:
    """Infer the model provider from a non-ARN Bedrock model ID.

    Bedrock IDs follow one of two patterns:
    - ``<provider>.<model>``          e.g. ``anthropic.claude-3-haiku-20240307-v1:0``
    - ``<region>.<provider>.<model>`` e.g. ``us.amazon.nova-pro-v1:0``

    Returns ``None`` for ARN-based identifiers and empty/None inputs.
    """
    if not model_id or model_id.startswith("arn:"):
        return None
    parts = model_id.split(".")
    if len(parts) >= _CROSS_REGION_MIN_PARTS and parts[0] in _CROSS_REGION_PREFIXES:
        return parts[1]
    return parts[0] if parts else None


def normalize_bedrock_langsmith_model_name(model_id: str | None) -> str | None:
    """Normalize Bedrock model identifiers into a stable LangSmith pricing key.

    Bedrock inference profiles often use cross-region aliases (for example,
    ``us.amazon.nova-pro-v1:0``) or ARNs that are not suitable as LangSmith
    pricing keys. This helper strips the cross-region prefix when possible and
    falls back to the terminal ARN segment for opaque identifiers.
    """
    if not model_id:
        return None

    if model_id.startswith("arn:"):
        return model_id.rsplit("/", maxsplit=1)[-1]

    parts = model_id.split(".")
    if len(parts) >= _CROSS_REGION_MIN_PARTS and parts[0] in _CROSS_REGION_PREFIXES:
        return ".".join(parts[1:])

    return model_id


def build_bedrock_trace_metadata(
    *,
    model_id: str,
    provider_override: str | None,
    langsmith_model_name: str | None = None,
) -> dict[str, str]:
    """Build metadata for LangChain/LangSmith traces of Bedrock model calls."""
    resolved_model_name = (
        langsmith_model_name
        or getattr(settings, "AWS_BEDROCK_LANGSMITH_MODEL_NAME", None)
        or normalize_bedrock_langsmith_model_name(model_id)
        or model_id
    )
    return {
        "provider": provider_override or "AWS",
        "ls_provider": getattr(
            settings,
            "AWS_BEDROCK_LANGSMITH_PROVIDER",
            _DEFAULT_LANGSMITH_BEDROCK_PROVIDER,
        ),
        "ls_model_name": resolved_model_name,
    }


def _build_bedrock_kwargs(
    *,
    model_id: str,
    region_name: str,
    temperature: float,
    max_tokens: int,
    provider_hint: str | None,
    provider_override: str | None,
) -> dict[str, Any]:
    """Return the keyword arguments dict for ``ChatBedrockConverse``.

    For ARN-based model identifiers the ``provider`` field is required by the
    AWS SDK; this helper resolves that value from settings or caller-supplied hints.
    """
    kwargs: dict[str, Any] = {
        "model": model_id,
        "region_name": region_name,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if model_id.startswith("arn:"):
        intent_classifier_profile = getattr(settings, "AWS_BEDROCK_INTENT_CLASSIFIER_INFERENCE_PROFILE_ID", None)
        intent_classifier_provider = getattr(settings, "AWS_BEDROCK_INTENT_CLASSIFIER_MODEL_PROVIDER", None)

        provider = (
            provider_override
            or (intent_classifier_provider if model_id == intent_classifier_profile else None)
            or getattr(settings, "AWS_BEDROCK_MODEL_PROVIDER", None)
            or provider_hint
            or infer_bedrock_provider(getattr(settings, "AWS_BEDROCK_INFERENCE_PROFILE_ID", None))
        )
        if provider:
            kwargs["provider"] = provider
    return kwargs


def build_chat_llm(
    llm_config: LLMConfig | None = None,
    *,
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> ChatBedrockConverse:
    """Instantiate ``ChatBedrockConverse`` for chat, routing, and handling nodes.

    The active chat inference profile (``AWS_BEDROCK_CHAT_INFERENCE_PROFILE_ID``
    or ``AWS_BEDROCK_INFERENCE_PROFILE_ID``) always takes precedence over the
    config's ``model_id``, so a single settings change reroutes all traffic
    without touching intent configurations.

    When *llm_config* is ``None``, falls back entirely to global settings —
    useful for ad-hoc calls that have no specific config context.

    Raises ``ValueError`` for unsupported LLM providers.
    """
    chat_profile = get_active_bedrock_chat_model_id()
    chat_provider_override = getattr(settings, "AWS_BEDROCK_CHAT_MODEL_PROVIDER", None)
    chat_langsmith_model_name = getattr(settings, "AWS_BEDROCK_CHAT_LANGSMITH_MODEL_NAME", None) or getattr(
        settings, "AWS_BEDROCK_LANGSMITH_MODEL_NAME", None
    )
    bedrock_region = getattr(settings, "AWS_BEDROCK_REGION", "us-east-1")

    if llm_config is None:
        model_id = chat_profile or getattr(settings, "AWS_BEDROCK_INFERENCE_PROFILE_ID", "us.amazon.nova-pro-v1:0")
        return ChatBedrockConverse(
            **_build_bedrock_kwargs(
                model_id=model_id,
                region_name=bedrock_region,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_hint=None,
                provider_override=chat_provider_override,
            ),
            metadata=build_bedrock_trace_metadata(
                model_id=model_id,
                provider_override=chat_provider_override,
                langsmith_model_name=chat_langsmith_model_name,
            ),
        )

    if llm_config.provider.upper() != "AWS_BEDROCK":
        raise ValueError(f"Unsupported LLM provider: {llm_config.provider!r}")

    intent_classifier_profile = getattr(settings, "AWS_BEDROCK_INTENT_CLASSIFIER_INFERENCE_PROFILE_ID", None)
    if llm_config.model_id == intent_classifier_profile and intent_classifier_profile:
        model_id = intent_classifier_profile
    else:
        model_id = chat_profile or llm_config.model_id
    # Inference profiles are region-scoped resources; ignore per-intent region
    # overrides when a profile ARN/ID is active.
    region_name = bedrock_region if chat_profile else (llm_config.region or bedrock_region)

    intent_classifier_provider = getattr(settings, "AWS_BEDROCK_INTENT_CLASSIFIER_MODEL_PROVIDER", None)
    provider_override = (
        intent_classifier_provider
        if model_id == intent_classifier_profile and intent_classifier_provider
        else chat_provider_override
    )
    langsmith_model_name = (
        getattr(settings, "AWS_BEDROCK_INTENT_CLASSIFIER_LANGSMITH_MODEL_NAME", None)
        if model_id == intent_classifier_profile and intent_classifier_profile
        else chat_langsmith_model_name
    ) or getattr(settings, "AWS_BEDROCK_LANGSMITH_MODEL_NAME", None)

    return ChatBedrockConverse(
        **_build_bedrock_kwargs(
            model_id=model_id,
            region_name=region_name,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_hint=infer_bedrock_provider(llm_config.model_id),
            provider_override=provider_override,
        ),
        metadata=build_bedrock_trace_metadata(
            model_id=model_id,
            provider_override=provider_override,
            langsmith_model_name=langsmith_model_name,
        ),
    )


def build_title_llm(*, temperature: float = 0.0, max_tokens: int = 64) -> ChatBedrockConverse | None:
    """Instantiate ``ChatBedrockConverse`` for thread title generation.

    Uses ``AWS_BEDROCK_TITLE_INFERENCE_PROFILE_ID`` (falling back to the global
    ``AWS_BEDROCK_INFERENCE_PROFILE_ID``).  Returns ``None`` when no profile is
    configured so callers can skip the Bedrock round-trip entirely.
    """
    title_profile = get_active_bedrock_title_model_id()
    if not title_profile:
        return None

    title_provider_override = getattr(settings, "AWS_BEDROCK_TITLE_MODEL_PROVIDER", None) or getattr(
        settings, "AWS_BEDROCK_MODEL_PROVIDER", None
    )
    title_langsmith_model_name = getattr(settings, "AWS_BEDROCK_TITLE_LANGSMITH_MODEL_NAME", None) or getattr(
        settings, "AWS_BEDROCK_LANGSMITH_MODEL_NAME", None
    )
    bedrock_region = getattr(settings, "AWS_BEDROCK_REGION", "us-east-1")

    return ChatBedrockConverse(
        **_build_bedrock_kwargs(
            model_id=title_profile,
            region_name=bedrock_region,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_hint=None,
            provider_override=title_provider_override,
        ),
        metadata=build_bedrock_trace_metadata(
            model_id=title_profile,
            provider_override=title_provider_override,
            langsmith_model_name=title_langsmith_model_name,
        ),
    )
