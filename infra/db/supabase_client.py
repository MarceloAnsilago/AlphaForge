from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

import os
import uuid


class DatabaseClient(Protocol):
    def insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def insert_many(self, table: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...

    def select(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        ascending: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def update(self, table: str, filters: dict[str, Any], values: dict[str, Any]) -> list[dict[str, Any]]:
        ...


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SupabaseClientError(RuntimeError):
    pass


class SupabaseDatabaseClient:
    def __init__(self, url: str, key: str) -> None:
        try:
            from supabase import create_client
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise SupabaseClientError(
                "Biblioteca supabase nao encontrada. Instale a dependencia para usar persistencia real."
            ) from exc

        self._client = create_client(url, key)

    def insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._client.table(table).insert(payload).execute()
        data = getattr(result, "data", None) or []
        return dict(data[0]) if data else {}

    def insert_many(self, table: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not payloads:
            return []
        result = self._client.table(table).insert(payloads).execute()
        data = getattr(result, "data", None) or []
        return [dict(item) for item in data]

    def select(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        ascending: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query = self._client.table(table).select("*")
        for key, value in (filters or {}).items():
            query = query.eq(key, value)
        if order_by is not None:
            query = query.order(order_by, desc=not ascending)
        if limit is not None:
            query = query.limit(limit)
        result = query.execute()
        data = getattr(result, "data", None) or []
        return [dict(item) for item in data]

    def update(self, table: str, filters: dict[str, Any], values: dict[str, Any]) -> list[dict[str, Any]]:
        query = self._client.table(table).update(values)
        for key, value in filters.items():
            query = query.eq(key, value)
        result = query.execute()
        data = getattr(result, "data", None) or []
        return [dict(item) for item in data]


def build_supabase_client_from_env() -> SupabaseDatabaseClient:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        raise SupabaseClientError("SUPABASE_URL e SUPABASE_KEY sao obrigatorios para persistencia real.")
    return SupabaseDatabaseClient(url=url, key=key)


@dataclass(slots=True)
class InMemoryDatabaseClient:
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        row.setdefault("id", str(uuid.uuid4()))
        row.setdefault("created_at", utc_now_iso())
        self.tables.setdefault(table, []).append(row)
        return dict(row)

    def insert_many(self, table: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.insert(table, payload) for payload in payloads]

    def select(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        ascending: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = [dict(row) for row in self.tables.get(table, [])]
        for key, value in (filters or {}).items():
            rows = [row for row in rows if row.get(key) == value]
        if order_by is not None:
            rows = sorted(rows, key=lambda item: item.get(order_by), reverse=not ascending)
        if limit is not None:
            rows = rows[:limit]
        return rows

    def update(self, table: str, filters: dict[str, Any], values: dict[str, Any]) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for row in self.tables.get(table, []):
            if all(row.get(key) == value for key, value in filters.items()):
                row.update(values)
                row["updated_at"] = values.get("updated_at", utc_now_iso())
                updated.append(dict(row))
        return updated
