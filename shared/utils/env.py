import os
from collections.abc import Callable
from typing import Any, overload

from django.core.exceptions import ImproperlyConfigured


@overload
def get_from_env[T](
    key: str,
    default: Any = ...,
    *,
    optional: bool = ...,
    type_cast: Callable[[str], T],
) -> T: ...


@overload
def get_from_env(
    key: str,
    default: Any = ...,
    *,
    optional: bool = ...,
    type_cast: None = ...,
) -> Any: ...


def get_from_env(
    key: str,
    default: Any = None,
    *,
    optional: bool = False,
    type_cast: Callable[[str], Any] | None = None,
) -> Any:
    value = os.getenv(key)
    if value is None or value == "":
        if optional:
            return None
        if default is not None:
            return default
        else:
            raise ImproperlyConfigured(f'The environment variable "{key}" is required to run Project!')
    if type_cast is not None:
        return type_cast(value)
    return value


def get_list(text: str) -> list[str]:
    if not text:
        return []
    return [item.strip() for item in text.split(",")]


def get_set(text: str) -> set[str]:
    if not text:
        return set()
    return {item.strip() for item in text.split(",")}


def str_to_bool(s: str | bool) -> bool:
    """A converter to return a bool from a str."""
    if isinstance(s, bool):
        return s

    return s.lower() in {"true", "yes", "1"}
