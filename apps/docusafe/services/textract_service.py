import time
from typing import Any

import boto3
import structlog
from django.conf import settings

from apps.docusafe.services.file_storage_service import DocusafeFileStorageService

logger = structlog.getLogger("default")

_textract_client = None


def _get_textract_client() -> Any:
    """Lazy-init Textract client."""
    global _textract_client  # noqa: PLW0603
    if _textract_client is None:
        region = getattr(settings, "AWS_BEDROCK_EMBEDDING_TEXTRACT_REGION", "ap-south-1")
        access_key = getattr(
            settings, "AWS_BEDROCK_EMBEDDING_ACCESS_KEY_ID", getattr(settings, "AWS_ACCESS_KEY_ID", None)
        )
        secret_key = getattr(
            settings, "AWS_BEDROCK_EMBEDDING_SECRET_ACCESS_KEY", getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
        )

        kwargs = {"region_name": region}
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        _textract_client = boto3.client("textract", **kwargs)
    return _textract_client


def _poll_textract_job(client: Any, job_id: str, max_wait_seconds: int = 300) -> list[dict[str, Any]]:
    """
    Poll a Textract async job until completion.

    Args:
        client: Textract boto3 client.
        job_id: The job ID from start_document_analysis.
        max_wait_seconds: Maximum time to wait before giving up.

    Returns:
        List of all Block dicts from all pages.
    """
    poll_interval = 5  # seconds
    elapsed = 0

    while elapsed < max_wait_seconds:
        result = client.get_document_analysis(JobId=job_id)
        status = result["JobStatus"]

        if status == "SUCCEEDED":
            # Collect blocks from first page of results
            all_blocks = list(result.get("Blocks", []))

            # Handle pagination
            next_token = result.get("NextToken")
            while next_token:
                result = client.get_document_analysis(JobId=job_id, NextToken=next_token)
                all_blocks.extend(result.get("Blocks", []))
                next_token = result.get("NextToken")

            logger.info("Textract job completed", job_id=job_id, block_count=len(all_blocks))
            return all_blocks

        if status == "FAILED":
            error_msg = result.get("StatusMessage", "Unknown error")
            logger.error("Textract job failed", job_id=job_id, error=error_msg)
            raise RuntimeError(f"Textract job {job_id} failed: {error_msg}")

        # Still IN_PROGRESS
        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Textract job {job_id} did not complete within {max_wait_seconds}s")


def extract_structured_blocks(file_path: str, use_async: bool = False) -> list[dict[str, Any]]:
    """
    Extract raw Textract blocks preserving full structure.

    Returns raw block dicts with BlockType, Page, Text,
    Confidence, and Relationships intact.

    Used by pdf_parser.py and image_ocr_parser.py to build
    DocumentBlock objects with page/layout awareness.

    Args:
        file_path: S3 object key.
        use_async: If True, use async Textract for multi-page docs.

    Returns:
        List of raw Textract Block dicts.
    """
    if use_async:
        return _extract_blocks_async(file_path)
    return _extract_blocks_sync(file_path)


def _extract_blocks_sync(file_path: str) -> list[dict[str, Any]]:
    """Sync Textract: returns raw blocks (not parsed text)."""
    client = _get_textract_client()
    file_bytes = DocusafeFileStorageService.read_file_bytes(file_path)

    try:
        response = client.analyze_document(
            Document={"Bytes": file_bytes},
            FeatureTypes=["TABLES", "FORMS", "LAYOUT"],
        )
        return response.get("Blocks", [])
    except Exception:
        logger.exception("Textract sync block extraction failed", file_path=file_path)
        raise


def _extract_blocks_async(file_path: str) -> list[dict[str, Any]]:
    """Async Textract: returns raw blocks (not parsed text)."""
    client = _get_textract_client()
    bucket = getattr(settings, "AWS_S3_BUCKET", "schoolfirst")

    try:
        start_response = client.start_document_analysis(
            DocumentLocation={
                "S3Object": {
                    "Bucket": bucket,
                    "Name": file_path,
                }
            },
            FeatureTypes=["TABLES", "FORMS", "LAYOUT"],
        )

        job_id = start_response["JobId"]
        logger.info("Started Textract async job (structured)", job_id=job_id, file_path=file_path)

        return _poll_textract_job(client, job_id)
    except Exception:
        logger.exception("Textract async block extraction failed", file_path=file_path)
        raise
