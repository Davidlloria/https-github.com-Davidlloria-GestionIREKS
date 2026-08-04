from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.database import engine


@dataclass(frozen=True)
class SalesToolsHistoryRow:
    created_at: str
    action: str
    detail: str
    status: str
    message: str
    warnings_json: str


class SalesToolsService:
    def ensure_history_table(self) -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS sales_tools_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    warnings_json TEXT NOT NULL DEFAULT '[]'
                )
                """
            )
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(sales_tools_history)").fetchall()}
            if "warnings_json" not in columns:
                conn.exec_driver_sql("ALTER TABLE sales_tools_history ADD COLUMN warnings_json TEXT NOT NULL DEFAULT '[]'")
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_sales_tools_history_created_at
                ON sales_tools_history (created_at DESC, id DESC)
                """
            )

    def record_history(
        self,
        *,
        created_at: str,
        action: str,
        detail: str,
        status: str,
        message: str,
        warnings_json: str,
    ) -> None:
        self.ensure_history_table()
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                INSERT INTO sales_tools_history (created_at, action, detail, status, message, warnings_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (created_at, action, detail, status, message, warnings_json),
            )

    def load_history_rows(self, *, limit: int, action_filter: str = "all") -> list[SalesToolsHistoryRow]:
        self.ensure_history_table()
        safe_limit = max(1, min(int(limit), 200))
        clean_action_filter = str(action_filter or "all").strip().lower()
        where_clause = ""
        params: list[object] = [safe_limit]
        if clean_action_filter in {"export", "import", "revert"}:
            where_clause = "WHERE action = ?"
            params = [clean_action_filter, safe_limit]
        query = f"""
            SELECT created_at, action, detail, status, message, warnings_json
            FROM sales_tools_history
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """
        with engine.begin() as conn:
            rows = conn.exec_driver_sql(query, tuple(params)).fetchall()
        return [
            SalesToolsHistoryRow(
                created_at=str(row[0] or ""),
                action=str(row[1] or ""),
                detail=str(row[2] or ""),
                status=str(row[3] or ""),
                message=str(row[4] or ""),
                warnings_json=str(row[5] or "[]"),
            )
            for row in rows
        ]

    def read_table_rows(self, table_name: str, columns: list[str]) -> list[tuple[Any, ...]]:
        query = self._build_export_query(table_name, columns)
        with engine.begin() as conn:
            return list(conn.exec_driver_sql(query).fetchall())

    def _build_export_query(self, table_name: str, columns: list[str]) -> str:
        quoted_cols = ", ".join(self._quote_identifier(col) for col in columns)
        return f"SELECT {quoted_cols} FROM {self._quote_identifier(table_name)}"

    def _quote_identifier(self, value: str) -> str:
        return '"' + str(value).replace('"', '""') + '"'
