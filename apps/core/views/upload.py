import os

from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.mixins.drf_views import CustomResponse
from shared.utils.files import save_uploaded_file


class FileUploadView(CustomResponse, APIView):
    """
    Common file upload endpoint.

    Accepts file uploads and stores them in temp/{user_id}/ folder.
    Sanitizes filenames and adds UUID for uniqueness.
    Returns the path of uploaded file to use in subsequent API calls.

    Usage:
        POST /api/v1/upload/
        Content-Type: multipart/form-data

        file: <file data>

    Returns:
        {
            "success": true,
            "data": {
                "path": "temp/{user_id}/filename_12345678.jpg",
                "filename": "filename_12345678.jpg"
            }
        }
    """

    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Upload files to temp folder scoped to the authenticated user."""

        # NOTE: Path is always temp/{user_id}/ and does not accept custom paths
        # from request parameters to prevent directory traversal attacks.

        # Support both 'file' (singular) and 'files' (plural) fields
        files = request.FILES.getlist("files")
        if not files and "file" in request.FILES:
            files = [request.FILES["file"]]

        if not files:
            return self.build_response(
                success=False,
                error={
                    "code": "MISSING_FILE",
                    "message": "No files provided",
                    "details": None,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uploaded_files = []
        user_temp_folder = f"temp/{request.user.id}"

        try:
            for file in files:
                file_path = save_uploaded_file(file, folder=user_temp_folder)

                uploaded_files.append(
                    {
                        "path": file_path,
                        "filename": os.path.basename(file_path),
                    }
                )

            # Return single file for test compatibility if only one uploaded
            data = uploaded_files[0] if len(uploaded_files) == 1 else uploaded_files

            return self.build_response(
                success=True,
                message="File uploaded successfully.",
                data=data,
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return self.build_response(
                success=False,
                error={
                    "code": "UPLOAD_FAILED",
                    "message": str(e),
                    "details": None,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
