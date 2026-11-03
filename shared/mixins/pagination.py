from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


# class CustomPageNumberPagination(PageNumberPagination):
#     # Default page size
#     page_size = 20
#     # Allow client to override via ?page_size=XX
#     page_size_query_param = "page_size"
#     # Optional: limit the maximum page size client can request
#     max_page_size = 100
#     # Page number param (default is already 'page')
#     page_query_param = "page"

class CustomPageNumberPagination(PageNumberPagination):

    page_size = 20

    page_size_query_param = "page_size"

    max_page_size = 100

    page_query_param = "page"

    def get_paginated_response(self, data):

        return Response(

            {

                "success": True,

                "data": data,

                "total": self.page.paginator.count,

                "description": "Request Successful",

            }

        )