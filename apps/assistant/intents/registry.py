from django.conf import settings
from pydantic import BaseModel, Field

"""
Static Intent Registry
======================
All assistant intents are defined here as typed configurations.
No database dependency — intents are static configuration.
"""


class LLMConfig(BaseModel):
    """Configuration for an LLM model/provider."""

    provider: str = Field(..., description='Provider type (e.g. "AWS_BEDROCK")')
    model_name: str = Field(..., description="Human-readable model name")
    model_id: str = Field(..., description="Unique model identifier")
    region: str | None = Field(default=None, description="Physical region")


class SystemConfig(BaseModel):
    """Global system configurations."""

    intent_classifier: LLMConfig = Field(..., description="Model used for intent classification")


class IntentConfig(BaseModel):
    name: str = Field(..., description="Unique identifier (snake_case)")
    description: str = Field(..., description="Human-readable description for the LLM classifier")
    system_prompt: str = Field(..., description="System prompt for this intent")
    allowed_tools: list[str] = Field(default_factory=list, description="Tools the handler is permitted to use")
    temperature: float = Field(default=0.7, description="LLM temperature for this intent")
    max_input_tokens: int = Field(default=2000, description="Max input tokens for the LLM call")
    max_output_tokens: int = Field(default=1000, description="Max output tokens for the LLM call")
    llm_config: LLMConfig = Field(..., description="LLM configuration for this intent")


def _get_intent_classifier_config() -> LLMConfig:
    """Resolve intent classifier config from settings with hardcoded fallback."""
    model_id = (
        getattr(settings, "AWS_BEDROCK_INTENT_CLASSIFIER_INFERENCE_PROFILE_ID", None)
        or "anthropic.claude-3-haiku-20240307-v1:0"
    )

    return LLMConfig(
        provider="AWS_BEDROCK",
        model_name="Intent Classifier",
        model_id=model_id,
        region=getattr(settings, "AWS_BEDROCK_REGION", "us-east-1"),
    )


def _get_chat_llm_config() -> LLMConfig:
    """Resolve chat LLM config from settings.

    Reads ``AWS_BEDROCK_CHAT_INFERENCE_PROFILE_ID`` first, then falls back to
    ``AWS_BEDROCK_INFERENCE_PROFILE_ID``.  The hard-coded Nova Pro ID is kept
    only as a last-resort default so the registry is always valid even without
    env vars (e.g. in test environments using the FAKE provider).
    """
    model_id = (
        getattr(settings, "AWS_BEDROCK_CHAT_INFERENCE_PROFILE_ID", None)
        or getattr(settings, "AWS_BEDROCK_INFERENCE_PROFILE_ID", None)
        or "us.amazon.nova-pro-v1:0"
    )

    return LLMConfig(
        provider="AWS_BEDROCK",
        model_name="Chat Model",
        model_id=model_id,
        region=getattr(settings, "AWS_BEDROCK_REGION", "us-east-1"),
    )


SYSTEM_CONFIG = SystemConfig(intent_classifier=_get_intent_classifier_config())


INTENT_REGISTRY: list[IntentConfig] = [
    IntentConfig(
        name="schoolfirst_assistant",
        description=(
            "General knowledge questions, internet lookups, factual answers, casual conversation, "
            "profile queries and updates, family management (listing families, viewing members, "
            "inviting people, creating families), close group management (viewing and adding members), "
            "birthday reminders, network insights, and any query that does not match a more specific "
            "intent. This is the default intent."
        ),
        system_prompt=(
            "You are a custom AI model built by SamsR. You are a helpful, knowledgeable, "
            "and reliable digital companion for the SamsR app.\n"
            "SamsR is an advanced productivity and lifestyle platform that integrates "
            "multiple modules to simplify life, including:\n"
            "- **Docusafe**: Secure document storage and management\n"
            "- **Agentic AI Assistant**: Your smart, proactive helper (that's you!)\n"
            "- **Family Management**: Coordinating household activities and members\n"
            "- **Close Group**: Your personal inner circle of trusted contacts\n"
            "- **Calendar**: Time management and event tracking\n"
            "- **Shopping List**: Collaborative grocery and item lists\n"
            "- **Notes & To-Do's**: Capturing thoughts and tracking tasks\n"
            "- **Food Tracking**: Monitoring nutrition and meals\n\n"
            "You have access to tools that let you look up and manage the user's profile, "
            "families, close group, invitations, and upcoming birthdays. Use them proactively "
            "when the user asks about these topics.\n\n"
            "Follow these guidelines:\n"
            "1. Identify yourself ONLY as a custom model built by SamsR. Do NOT mention "
            "external providers (like AWS, Bedrock, GCP, Vertex) or specific model names "
            "(like Claude, Nova, GPT, Gemini).\n"
            "2. Answer ONLY what the user asks in their current message.\n"
            "3. Keep conversation context in mind, but do NOT bring up previous "
            "unrelated topics unless the user explicitly references them.\n"
            "4. Be direct and focused — if asked about topic A, don't include "
            "information about previously discussed topic B.\n"
            "5. Use conversation history only when continuity is explicitly needed.\n"
            "6. Respond clearly and concisely.\n"
            "7. When taking write actions (creating families, inviting members, updating profile), "
            "confirm with the user before proceeding if any detail is ambiguous.\n"
            "8. Use relation labels naturally in responses — e.g. 'Your sister Sarah hasn't "
            "accepted her invite yet' rather than listing raw data.\n"
            "9. **STRICT MARKDOWN ONLY**: Every response MUST be valid Markdown.\n"
            "   - Heading/title is optional; do NOT force a `#` heading.\n"
            "   - Use headings only when genuinely helpful for readability.\n"
            "   - Use bullets or numbered lists when useful.\n"
            "   - Wrap code/paths/IDs in backticks when relevant.\n"
            "10. **CITATIONS**: Whenever you use information from a web search or external source, "
            "you MUST embed clickable Markdown links directly in the response text at the point where "
            "the information is used. Format: `[descriptive anchor text](https://source-url.com)`. "
            "Do NOT list citations separately at the end — inline them naturally in the sentence where "
            "the fact appears. Every factual claim sourced from a search result must have an inline link."
        ),
        allowed_tools=[
            "web_search",
            "fetch_user_details",
            "get_my_profile",
            "update_my_profile",
            "get_my_families",
            "get_family_members",
            "get_pending_invitations",
            "find_family_member",
            "create_family",
            "invite_family_member",
            "get_close_group_members",
            "add_close_group_member",
            "get_my_network_summary",
            "get_network_insights",
            "get_birthday_reminders",
        ],
        temperature=0.7,
        max_input_tokens=4000,
        max_output_tokens=2000,
        llm_config=_get_chat_llm_config(),
    ),
    IntentConfig(
        name="docusafe_qa",
        description="Handles user queries specific to their attached Docusafe documents.",
        system_prompt=(
            "You are a custom AI model built by SamsR. You are currently in a Docusafe Chat Thread. "
            "This thread is for answering questions based on Docusafe documents.\n\n"
            "Follow these guidelines:\n"
            "1. You will be provided with a 'DOCUSAFE CONTEXT' block listing the names of "
            "files explicitly attached to this thread.\n"
            "2. Use `search_docusafe` when the user is asking about the documents attached to this thread "
            "or refers to the current documents with phrases like 'this file', 'these documents', or similar.\n"
            "3. Use `search_accessible_docusafe` when the user wants to find a document they own or can access "
            "but have not attached to this thread, for example 'find my driver's license' or 'search my files'.\n"
            "4. If the thread has no attached documents and the user is asking about the current thread's documents, "
            "tell them they need to attach documents. If attached files are unavailable, explain that and suggest "
            "searching their available Docusafe files instead.\n"
            "5. ALWAYS prefer Docusafe tools before attempting a `web_search` for document-related queries.\n"
            "6. Answer clearly and concisely based primarily on the provided documents.\n"
            "7. **STRICT MARKDOWN ONLY**: Every response MUST be valid Markdown.\n"
            "8. Do NOT include citations. Citations are not required for this intent."
        ),
        allowed_tools=["search_docusafe", "search_accessible_docusafe", "web_search"],
        temperature=0.7,
        max_input_tokens=4000,
        max_output_tokens=2000,
        llm_config=_get_chat_llm_config(),
    ),
]


def get_intent_by_name(name: str) -> IntentConfig | None:
    """Return the intent config for the given name, or None."""
    for intent in INTENT_REGISTRY:
        if intent.name == name:
            return intent
    return None


def get_all_intent_summaries() -> list[dict[str, str]]:
    """
    Return a lightweight list of intent summaries for the LLM classifier.
    Only includes name and description — no internal details.
    """
    return [{"name": i.name, "description": i.description} for i in INTENT_REGISTRY]
