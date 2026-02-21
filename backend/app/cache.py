"""
In-process resolve cache.

Keyed by user_id → list of effective-permission dicts.
Invalidated by user_id (on role assign/revoke) or entirely (on any
role-structure or permission change).
"""
from typing import Any

_cache: dict[str, Any] = {}


def get_resolve(user_id: str) -> Any | None:
    return _cache.get(user_id)


def set_resolve(user_id: str, data: Any) -> None:
    _cache[user_id] = data


def invalidate_user(user_id: str) -> None:
    _cache.pop(user_id, None)


def invalidate_all() -> None:
    _cache.clear()
