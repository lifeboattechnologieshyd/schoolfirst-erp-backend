from rest_framework.views import APIView

from shared.mixins.drf_views import CustomResponse


class CustomAPIView(APIView, CustomResponse):
    """
    Base API view with custom response build capabilities for Docusafe.
    """

    pass
