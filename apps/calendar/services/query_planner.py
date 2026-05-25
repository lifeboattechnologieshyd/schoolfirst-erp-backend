import functools
from dataclasses import dataclass

from django.db.models import F

from apps.calendar.services.query_common import paginate_results


@dataclass(frozen=True)
class CalendarListQueryResult:
    items: list
    meta: dict


def paginate_queryset(qs, page: int, page_size: int):
    total = qs.count()
    offset = (page - 1) * page_size
    items = list(qs[offset : offset + page_size])
    total_pages = (total + page_size - 1) // page_size if total else 0
    return items, {"total": total, "page": page, "page_size": page_size, "total_pages": total_pages}


def parse_query_bool(raw_value: str | None):
    if raw_value is None:
        return None
    return raw_value.lower() == "true"


def sort_items_by_field(items: list, field_name: str, sort: str = "asc") -> list:
    non_null_items = [item for item in items if getattr(item, field_name, None) is not None]
    null_items = [item for item in items if getattr(item, field_name, None) is None]
    non_null_items.sort(key=lambda item: getattr(item, field_name), reverse=(sort == "desc"))
    return non_null_items + null_items


def parse_sort_param(
    raw: str | None,
    allowed_fields: frozenset[str],
    default: list[str],
) -> list[str]:
    """Parse ?sort=field,-field2 into ordering tokens like ["field", "-field2"].

    Follows the convention: plain name = ascending, "-" prefix = descending.
    Multiple comma-separated fields are supported.
    Raises ValueError with a "sort" key if a requested field is not in allowed_fields.
    """
    if not raw:
        return list(default)
    tokens: list[str] = []
    for raw_token in raw.split(","):
        token = raw_token.strip()
        if not token:
            continue
        field = token.lstrip("-")
        if field not in allowed_fields:
            raise ValueError({"sort": (f"Invalid sort field '{field}'. Allowed: {', '.join(sorted(allowed_fields))}.")})
        tokens.append(token)
    return tokens or list(default)


def sort_items_by_fields(items: list, order_tokens: list[str]) -> list:
    """Sort a Python list by multiple ordering tokens (e.g. ["start_at", "-priority"]).

    Nulls are placed last regardless of sort direction.
    """
    if not order_tokens:
        return items

    def _compare(a: object, b: object) -> int:
        for token in order_tokens:
            descending = token.startswith("-")
            field = token.lstrip("-")
            va = getattr(a, field, None)
            vb = getattr(b, field, None)
            if va is None and vb is None:
                continue
            if va is None:
                return 1
            if vb is None:
                return -1
            if va < vb:  # type: ignore[operator]
                result = -1
            elif va > vb:  # type: ignore[operator]
                result = 1
            else:
                continue
            return -result if descending else result
        return 0

    return sorted(items, key=functools.cmp_to_key(_compare))


def build_queryset_ordering(order_tokens: list[str]) -> list:
    """Convert ordering tokens to Django F() expressions with nulls_last=True."""
    result = []
    for token in order_tokens:
        descending = token.startswith("-")
        field = token.lstrip("-")
        result.append(F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True))
    return result


class BaseCalendarListQuery:
    def __init__(self, service):
        self.service = service

    @staticmethod
    def _page_params(params) -> tuple[int, int]:
        return int(params.get("page", 1)), int(params.get("page_size", 20))

    def _build_result(self, items: list, params) -> CalendarListQueryResult:
        page, page_size = self._page_params(params)
        paged_items, meta = paginate_results(items, page=page, page_size=page_size)
        return CalendarListQueryResult(items=paged_items, meta=meta)

    def _build_queryset_result(self, qs, params) -> CalendarListQueryResult:
        page, page_size = self._page_params(params)
        items, meta = paginate_queryset(qs, page=page, page_size=page_size)
        return CalendarListQueryResult(items=items, meta=meta)

    def execute(self, params, from_date, to_date) -> CalendarListQueryResult:
        if from_date and to_date:
            return self._build_result(self.build_ranged_items(params, from_date, to_date), params)
        return self._build_queryset_result(self.build_queryset(params, from_date, to_date), params)

    def build_ranged_items(self, params, from_date, to_date) -> list:
        raise NotImplementedError

    def build_queryset(self, params, from_date, to_date):
        raise NotImplementedError
