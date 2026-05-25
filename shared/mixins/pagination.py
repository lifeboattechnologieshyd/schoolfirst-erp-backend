from rest_framework.pagination import PageNumberPagination


class CustomPageNumberPagination(PageNumberPagination):
    # Default page size
    page_size = 20
    # Allow client to override via ?page_size=XX
    page_size_query_param = "page_size"
    # Optional: limit the maximum page size client can request
    max_page_size = 100
    # Page number param (default is already 'page')
    page_query_param = "page"
