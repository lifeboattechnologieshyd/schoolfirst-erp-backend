from shared.utils import get_from_env

# --- LLM Provider Settings ---

# Which LLM provider to use.
# Options:
#   "AWS_BEDROCK"  - boto3 Converse API (recommended, native SDK)
#   "FAKE"                - In-memory stub for tests / local dev
LLM_PROVIDER = get_from_env("LLM_PROVIDER", "FAKE")

# --- AWS Bedrock (Native boto3 provider) ---
# Region where your Bedrock model is deployed.
AWS_BEDROCK_REGION = get_from_env("AWS_BEDROCK_REGION", "us-east-1")


# Optional global inference profile ID/ARN. When set, Bedrock invocations
# should use this profile instead of direct on-demand model IDs.
AWS_BEDROCK_INFERENCE_PROFILE_ID = get_from_env("AWS_BEDROCK_INFERENCE_PROFILE_ID", None, optional=True)

# Optional chat/tool-capable inference profile ID/ARN.
# If set, this takes precedence for assistant routing and generation flows.
AWS_BEDROCK_CHAT_INFERENCE_PROFILE_ID = get_from_env("AWS_BEDROCK_CHAT_INFERENCE_PROFILE_ID", None, optional=True)

# Optional title-generation inference profile ID/ARN.
# If set, this takes precedence only for thread title generation.
AWS_BEDROCK_TITLE_INFERENCE_PROFILE_ID = get_from_env("AWS_BEDROCK_TITLE_INFERENCE_PROFILE_ID", None, optional=True)

# Optional intent-classifier inference profile ID/ARN.
AWS_BEDROCK_INTENT_CLASSIFIER_INFERENCE_PROFILE_ID = get_from_env(
    "AWS_BEDROCK_INTENT_CLASSIFIER_INFERENCE_PROFILE_ID", None, optional=True
)

# Optional provider hint for ARN-based model/inference-profile invocations.
# Example values: "anthropic", "amazon", "meta", "mistral", "cohere".
AWS_BEDROCK_MODEL_PROVIDER = get_from_env("AWS_BEDROCK_MODEL_PROVIDER", None, optional=True)

# Optional provider hints for split profile usage.
AWS_BEDROCK_CHAT_MODEL_PROVIDER = get_from_env("AWS_BEDROCK_CHAT_MODEL_PROVIDER", None, optional=True)
AWS_BEDROCK_TITLE_MODEL_PROVIDER = get_from_env("AWS_BEDROCK_TITLE_MODEL_PROVIDER", None, optional=True)
AWS_BEDROCK_INTENT_CLASSIFIER_MODEL_PROVIDER = get_from_env(
    "AWS_BEDROCK_INTENT_CLASSIFIER_MODEL_PROVIDER", None, optional=True
)

# Optional LangSmith pricing metadata overrides.
# These are useful when Bedrock requests go through inference profile IDs/ARNs
# that do not match the model name configured in LangSmith's pricing table.
AWS_BEDROCK_LANGSMITH_PROVIDER = get_from_env("AWS_BEDROCK_LANGSMITH_PROVIDER", "amazon_bedrock")
AWS_BEDROCK_LANGSMITH_MODEL_NAME = get_from_env("AWS_BEDROCK_LANGSMITH_MODEL_NAME", None, optional=True)
AWS_BEDROCK_CHAT_LANGSMITH_MODEL_NAME = get_from_env("AWS_BEDROCK_CHAT_LANGSMITH_MODEL_NAME", None, optional=True)
AWS_BEDROCK_TITLE_LANGSMITH_MODEL_NAME = get_from_env("AWS_BEDROCK_TITLE_LANGSMITH_MODEL_NAME", None, optional=True)
AWS_BEDROCK_INTENT_CLASSIFIER_LANGSMITH_MODEL_NAME = get_from_env(
    "AWS_BEDROCK_INTENT_CLASSIFIER_LANGSMITH_MODEL_NAME", None, optional=True
)

# Long-term ABSK API key: boto3 reads AWS_BEARER_TOKEN_BEDROCK automatically.
# We expose it here so settings-aware code can inspect it if needed.
AWS_BEARER_TOKEN_BEDROCK = get_from_env("AWS_BEARER_TOKEN_BEDROCK", "", optional=True)

TAVILY_API_KEY = get_from_env("TAVILY_API_KEY", "", optional=True)
