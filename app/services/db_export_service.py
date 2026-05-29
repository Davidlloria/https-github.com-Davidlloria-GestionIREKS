from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.core.database import engine


class DbExportService:
    def list_tables(self) -> list[str]:
        with engine.begin() as conn:
            rows = conn.exec_driver_sql(
                """
                SELECT name
                FROM sqlite_master
                WHERE type IN ('table', 'view')
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [str(row[0]) for row in rows if row and row[0]]

    def list_columns(self, table_name: str) -> list[str]:
        table = self._validate_table(table_name)
        with engine.begin() as conn:
            rows = conn.exec_driver_sql(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()
        return [str(row[1]) for row in rows if len(row) > 1 and row[1]]

    def count_rows(self, table_name: str) -> int:
        table = self._validate_table(table_name)
        with engine.begin() as conn:
            row = conn.exec_driver_sql(
                f"SELECT COUNT(*) FROM {self._quote_identifier(table)}"
            ).fetchone()
        return int((row[0] if row else 0) or 0)

    def export_data(
        self,
        *,
        table_name: str,
        columns: list[str],
        destination: Path,
        output_format: str,
    ) -> dict[str, Any]:
        table = self._validate_table(table_name)
        available_columns = self.list_columns(table)
        selected = self._validate_columns(columns, available_columns)
        fmt = str(output_format or "").strip().lower()
        if fmt not in {"csv", "xlsx", "json"}:
            raise ValueError(f"Formato no soportado: {output_format}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "csv":
            count = self._write_csv(table=table, columns=selected, destination=destination)
        elif fmt == "xlsx":
            count = self._write_xlsx(table=table, columns=selected, destination=destination)
        else:
            count = self._write_json(table=table, columns=selected, destination=destination)
        return {"rows_exported": count, "path": str(destination), "table": table, "columns": selected, "format": fmt}

    def _write_csv(self, *, table: str, columns: list[str], destination: Path) -> int:
        query = self._build_select_query(table=table, columns=columns)
        count = 0
        with engine.begin() as conn, destination.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            result = conn.exec_driver_sql(query)
            for row in result:
                writer.writerow([self._normalize_value(value) for value in row])
                count += 1
        return count

    def _write_xlsx(self, *, table: str, columns: list[str], destination: Path) -> int:
        query = self._build_select_query(table=table, columns=columns)
        workbook = Workbook()
        sheet = cast(Worksheet, workbook.active)
        sheet.title = (table[:31] or "Export")
        sheet.append(columns)
        count = 0
        with engine.begin() as conn:
            result = conn.exec_driver_sql(query)
            for row in result:
                sheet.append([self._normalize_value(value) for value in row])
                count += 1
        workbook.save(destination)
        return count

    def _write_json(self, *, table: str, columns: list[str], destination: Path) -> int:
        query = self._build_select_query(table=table, columns=columns)
        payload: list[dict[str, Any]] = []
        with engine.begin() as conn:
            result = conn.exec_driver_sql(query)
            for row in result:
                payload.append(
                    {columns[idx]: self._normalize_value(value) for idx, value in enumerate(row)}
                )
        with destination.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        return len(payload)

    def _build_select_query(self, *, table: str, columns: list[str]) -> str:
        col_clause = ", ".join(self._quote_identifier(name) for name in columns)
        return f"SELECT {col_clause} FROM {self._quote_identifier(table)}"

    def _validate_table(self, table_name: str) -> str:
        name = str(table_name or "").strip()
        if not name:
            raise ValueError("Debes seleccionar una tabla.")
        tables = self.list_tables()
        if name not in tables:
            raise ValueError(f"Tabla no valida: {name}")
        return name

    def _validate_columns(self, selected: list[str], available: list[str]) -> list[str]:
        picked = [str(col or "").strip() for col in selected if str(col or "").strip()]
        if not picked:
            raise ValueError("Debes seleccionar al menos un campo.")
        invalid = [col for col in picked if col not in available]
        if invalid:
            raise ValueError(f"Campos no validos: {', '.join(invalid)}")
        return picked

    def _quote_identifier(self, value: str) -> str:
        return '"' + str(value).replace('"', '""') + '"'

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                return str(value)
        return value
