import json
import re
import time

import boto3
import structlog
from django.conf import settings

logger = structlog.getLogger("default")

# Titan V2 maximum input: 8,192 tokens / 50,000 characters
TITAN_V2_MAX_INPUT_CHARS = 50000

# Max characters of document to send for summary generation
SUMMARY_PREVIEW_CHARS = 10000

_bedrock_client = None
_bedrock_summary_client = None


def _strip_summary_header(text: str) -> str:
    """
    Strip markdown headers from the beginning of a summary.

    Claude sometimes returns summaries with markdown formatting like:
    "# Summary\\nThis is the summary text..."

    This function removes such headers to store clean text.
    """
    # Remove leading markdown headers (# Summary, ## Summary, etc.)
    # Pattern: 1+ hashes, optional whitespace, "Summary" (case-insensitive),
    # optional colon, optional whitespace, then newline
    cleaned = re.sub(r"^#+\s*Summary\s*[:]?\s*\n", "", text, flags=re.IGNORECASE)

    # If we stripped something and have content left, return the cleaned version
    if cleaned.strip() and cleaned != text:
        logger.debug("Stripped markdown header from summary", stripped_chars=len(text) - len(cleaned))
        return cleaned

    # If nothing was stripped or stripping would leave us empty, return original
    return text


def get_bedrock_summary_client():
    """Lazy-init Bedrock Runtime client for summaries."""
    global _bedrock_summary_client  # noqa: PLW0603
    if _bedrock_summary_client is None:
        region = getattr(settings, "AWS_BEDROCK_REGION", "us-west-2")
        access_key = getattr(settings, "AWS_BEDROCK_EMBEDDING_ACCESS_KEY_ID", None)
        secret_key = getattr(settings, "AWS_BEDROCK_EMBEDDING_SECRET_ACCESS_KEY", None)

        kwargs = {"region_name": region}
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        _bedrock_summary_client = boto3.client("bedrock-runtime", **kwargs)
    return _bedrock_summary_client


def generate_document_summary(text: str, file_name: str) -> str:
    """
    Generate a brief summary of the document using Bedrock Claude.

    Returns a 2-3 sentence summary, or empty string on failure.
    """
    try:
        client = get_bedrock_summary_client()
        model_id = getattr(settings, "AWS_BEDROCK_INFERENCE_PROFILE_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

        preview = text[:SUMMARY_PREVIEW_CHARS] if len(text) > SUMMARY_PREVIEW_CHARS else text

        prompt = (
            f"Summarize the following document in 2-3 sentences. "
            f"The document is named '{file_name}'.\n\n"
            f"Document content:\n{preview}\n\n"
            f"Summary:"
        )

        response = client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={"maxTokens": 300},
        )

        summary = response["output"]["message"]["content"][0]["text"].strip()
        summary = _strip_summary_header(summary)
        logger.info("Summary generated", file_name=file_name, summary_length=len(summary))
        return summary
    except Exception:
        # Log at error level — silent summary degradation is a data quality concern.
        # Files will be marked COMPLETED without a summary, which is misleading.
        logger.error(
            "Failed to generate summary — file will be embedded without summary",
            file_name=file_name,
            exc_info=True,
        )
        return ""


def _get_client():
    """Lazy-init Bedrock Runtime client for embeddings."""
    global _bedrock_client  # noqa: PLW0603
    if _bedrock_client is None:
        region = getattr(settings, "AWS_BEDROCK_EMBEDDING_REGION", "us-east-1")
        access_key = getattr(settings, "AWS_BEDROCK_EMBEDDING_ACCESS_KEY_ID", None)
        secret_key = getattr(settings, "AWS_BEDROCK_EMBEDDING_SECRET_ACCESS_KEY", None)

        kwargs = {"region_name": region}
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        _bedrock_client = boto3.client("bedrock-runtime", **kwargs)
    return _bedrock_client


def generate_embedding(text: str, max_retries: int = 2) -> list[float]:
    """
    Generate a dense embedding using Amazon Titan Text Embeddings V2.

    Retries transient errors (throttling, 5xx) with exponential backoff.

    Args:
        text: Input text (max 8,192 tokens / ~50,000 characters).
        max_retries: Number of retries for transient failures.

    Returns:
        List of floats with length == EMBEDDING_DIMENSIONS (default 1024).
    """
    client = _get_client()
    model_id = getattr(settings, "AWS_BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
    dimensions = getattr(settings, "AWS_BEDROCK_EMBEDDING_DIMENSIONS", 1024)

    # Titan V2 has a 50,000 character limit — truncate defensively
    truncated = text[:TITAN_V2_MAX_INPUT_CHARS] if len(text) > TITAN_V2_MAX_INPUT_CHARS else text

    body = json.dumps(
        {
            "inputText": truncated,
            "dimensions": dimensions,
            "normalize": True,
        }
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.invoke_model(
                body=body,
                modelId=model_id,
                accept="application/json",
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["embedding"]

        except client.exceptions.ThrottlingException:
            last_error = "ThrottlingException"
            if attempt < max_retries:
                wait = 2 ** (attempt + 1)  # 2s, 4s
                logger.warning(
                    "Bedrock throttled, retrying",
                    attempt=attempt + 1,
                    wait_seconds=wait,
                )
                time.sleep(wait)
                continue
        except Exception as e:
            # Check for transient server errors (5xx)
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code.startswith("5") and attempt < max_retries:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Bedrock server error, retrying",
                    attempt=attempt + 1,
                    wait_seconds=wait,
                    error_code=error_code,
                )
                time.sleep(wait)
                last_error = str(e)
                continue
            raise

    raise RuntimeError(f"Bedrock embedding failed after {max_retries + 1} attempts: {last_error}")


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for multiple texts.

    Titan V2 does not support batch inference, so this calls
    invoke_model once per text sequentially.

    Args:
        texts: List of input texts.

    Returns:
        List of embedding vectors (same order as input).
    """
    embeddings = []
    for text in texts:
        try:
            emb = generate_embedding(text)
            embeddings.append(emb)
        except Exception:
            logger.exception("Failed to generate embedding", text_preview=text[:100])
            raise
    return embeddings
