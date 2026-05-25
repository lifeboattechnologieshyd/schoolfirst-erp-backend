from typing import Any

import structlog
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.docusafe.serializers.search import SearchQuerySerializer, SearchResultSerializer
from apps.docusafe.services.vector_search_service import DocusafeSearchService
from apps.docusafe.views.base import CustomAPIView
from shared.enums import GlobalAPIMessageCodes

logger = structlog.getLogger("default")


class DocusafeSearchView(CustomAPIView):
    """
    POST /v1/docusafe/search/

    Hybrid semantic + keyword search across the user's Docusafe files.
    Combines Titan V2 dense embeddings with BM25 sparse vectors
    using Reciprocal Rank Fusion (RRF) for best-of-both-worlds ranking.

    Request body:
        - query (str, required): The search query.
        - folder_id (uuid, optional): Filter results to a specific folder.
        - limit (int, optional): Maximum results (default 10, max 50).

    Returns ranked list of matching files with relevance scores and snippets.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = SearchQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["query"]
        folder_id = serializer.validated_data.get("folder_id")
        limit = serializer.validated_data.get("limit", 10)

        user_id = str(request.user.id)

        try:
            search_service = DocusafeSearchService()
            results = search_service.hybrid_search(
                user_id=user_id,
                query=query,
                folder_id=str(folder_id) if folder_id else None,
                limit=limit,
            )
        except ValidationError as e:
            return self.build_response(
                success=False,
                error={
                    "code": GlobalAPIMessageCodes.VALIDATION_ERROR,
                    "message": GlobalAPIMessageCodes.VALIDATION_ERROR.label,
                    "details": self._format_validation_errors(e.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Search failed", user_id=user_id, query=query)
            return self.build_response(
                success=False,
                message="Search is temporarily unavailable. Please try again later.",
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        result_serializer = SearchResultSerializer(results, many=True)

        return self.build_response(
            success=True,
            data=result_serializer.data,
            message=f"Found {len(results)} result(s).",
            status=status.HTTP_200_OK,
        )
