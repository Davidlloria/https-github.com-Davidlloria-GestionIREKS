from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _python_files(relative_dir: str) -> list[Path]:
    base = PROJECT_ROOT / relative_dir
    return sorted(path for path in base.rglob("*.py") if path.is_file())


def _scan_import_violations(files: list[Path], *, rule: str) -> list[str]:
    violations: list[str] = []
    for file_path in files:
        tree = ast.parse(file_path.read_text(encoding="utf-8-sig"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if rule == "ui_no_db_imports":
                        if module_name == "sqlmodel" or module_name.startswith("sqlmodel."):
                            violations.append(f"{file_path}: import {module_name}")
                        if module_name == "app.core.database" or module_name.startswith("app.core.database."):
                            violations.append(f"{file_path}: import {module_name}")
                    elif rule == "services_no_pyside6":
                        if module_name == "PySide6" or module_name.startswith("PySide6."):
                            violations.append(f"{file_path}: import {module_name}")
                    elif rule == "api_no_ui_imports":
                        if module_name == "app.ui" or module_name.startswith("app.ui."):
                            violations.append(f"{file_path}: import {module_name}")

            if isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if rule == "ui_no_db_imports":
                    if module_name == "sqlmodel" or module_name.startswith("sqlmodel."):
                        violations.append(f"{file_path}: from {module_name} import ...")
                    if module_name == "app.core.database" or module_name.startswith("app.core.database."):
                        violations.append(f"{file_path}: from {module_name} import ...")
                elif rule == "services_no_pyside6":
                    if module_name == "PySide6" or module_name.startswith("PySide6."):
                        violations.append(f"{file_path}: from {module_name} import ...")
                elif rule == "api_no_ui_imports":
                    if module_name == "app.ui" or module_name.startswith("app.ui."):
                        violations.append(f"{file_path}: from {module_name} import ...")
    return violations


def test_ui_layer_does_not_import_database_primitives() -> None:
    files = _python_files("app/ui")
    violations = _scan_import_violations(files, rule="ui_no_db_imports")
    assert not violations, "UI no debe importar sqlmodel ni app.core.database:\n" + "\n".join(violations)


def test_services_layer_does_not_import_pyside6() -> None:
    files = _python_files("app/services")
    violations = _scan_import_violations(files, rule="services_no_pyside6")
    assert not violations, "Services no debe importar PySide6:\n" + "\n".join(violations)


def test_api_layer_does_not_import_ui() -> None:
    files = _python_files("app/api")
    violations = _scan_import_violations(files, rule="api_no_ui_imports")
    assert not violations, "API no debe importar app.ui:\n" + "\n".join(violations)
