import datetime

from shared.mixins.drf_views import CustomResponse

_VALID_SCOPES = {"all", "this", "this_and_future"}


def parse_query_date(raw_value: str | None, field_name: str):
    if not raw_value:
        return None

    try:
        return datetime.date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError({field_name: f"{field_name} must be a valid YYYY-MM-DD date."}) from exc


def parse_occurrence_date(raw_value: str | None):
    return parse_query_date(raw_value, "occurrence_date")


def validate_query_date_window(from_date, to_date):
    if from_date and to_date and to_date < from_date:
        raise ValueError({"to_date": "to_date must be on or after from_date."})


def paginate_results(results: list, page: int, page_size: int):
    total = len(results)
    offset = (page - 1) * page_size
    page_results = results[offset : offset + page_size]
    total_pages = (total + page_size - 1) // page_size if total else 0
    meta = {"total": total, "page": page, "page_size": page_size, "total_pages": total_pages}
    return page_results, meta


def build_validation_error_details(exc: ValueError):
    detail = exc.args[0] if exc.args else str(exc)
    return CustomResponse._format_validation_errors(detail)


def validate_recurrence_scope(scope: str, occurrence_date) -> dict | None:
    if scope not in _VALID_SCOPES:
        return {"update_scope": "Must be one of: all, this, this_and_future"}
    if scope in {"this", "this_and_future"} and not occurrence_date:
        return {"occurrence_date": "occurrence_date is required for update_scope 'this' or 'this_and_future'"}
    return None
