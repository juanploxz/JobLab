from rest_framework.pagination import PageNumberPagination


class PlanPageNumberPagination(PageNumberPagination):
    """Bounded collection pagination suitable for an API Gateway."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50
