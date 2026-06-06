from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import app.services.order_document_ocr_runtime_service as ocr_runtime_service
from app.services.order_document_ocr_runtime_service import OrderDocumentOcrRuntimeService


def _install_pytesseract_stub(monkeypatch, *, version_ok: bool = True) -> SimpleNamespace:
    def get_tesseract_version() -> str:
        if not version_ok:
            raise RuntimeError("tesseract unavailable")
        return "5.4.0"

    stub = SimpleNamespace(
        pytesseract=SimpleNamespace(tesseract_cmd=""),
        get_tesseract_version=get_tesseract_version,
    )
    monkeypatch.setitem(sys.modules, "pytesseract", stub)
    return stub


def test_resolve_runtime_prefers_tesseract_cmd_env(monkeypatch, tmp_path: Path) -> None:
    env_bin = tmp_path / "env" / "tesseract.exe"
    env_bin.parent.mkdir(parents=True, exist_ok=True)
    env_bin.write_text("")
    runtime_bin = tmp_path / "runtime" / "tesseract" / "tesseract.exe"
    runtime_bin.parent.mkdir(parents=True, exist_ok=True)
    runtime_bin.write_text("")

    monkeypatch.setattr(ocr_runtime_service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(ocr_runtime_service.Path, "cwd", lambda: tmp_path)
    monkeypatch.setenv("TESSERACT_CMD", str(env_bin))
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    stub = _install_pytesseract_stub(monkeypatch)

    state = OrderDocumentOcrRuntimeService().resolve_runtime()

    assert state.configured is True
    assert state.tesseract_cmd == str(env_bin)
    assert stub.pytesseract.tesseract_cmd == str(env_bin)
    assert state.ocr_lang is None
    assert OrderDocumentOcrRuntimeService().ocr_lang() is None


def test_resolve_runtime_detects_runtime_tesseract(monkeypatch, tmp_path: Path) -> None:
    runtime_bin = tmp_path / "runtime" / "tesseract" / "tesseract.exe"
    runtime_bin.parent.mkdir(parents=True, exist_ok=True)
    runtime_bin.write_text("")

    monkeypatch.setattr(ocr_runtime_service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(ocr_runtime_service.Path, "cwd", lambda: tmp_path)
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    stub = _install_pytesseract_stub(monkeypatch)

    state = OrderDocumentOcrRuntimeService().resolve_runtime()

    assert state.configured is True
    assert state.tesseract_cmd == str(runtime_bin)
    assert stub.pytesseract.tesseract_cmd == str(runtime_bin)


def test_resolve_runtime_detects_tessdata_and_language(monkeypatch, tmp_path: Path) -> None:
    runtime_bin = tmp_path / "runtime" / "tesseract" / "tesseract.exe"
    tessdata_dir = runtime_bin.parent / "tessdata"
    tessdata_dir.mkdir(parents=True, exist_ok=True)
    runtime_bin.write_text("")
    (tessdata_dir / "eng.traineddata").write_text("")
    (tessdata_dir / "spa.traineddata").write_text("")

    monkeypatch.setattr(ocr_runtime_service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(ocr_runtime_service.Path, "cwd", lambda: tmp_path)
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    stub = _install_pytesseract_stub(monkeypatch)

    state = OrderDocumentOcrRuntimeService().resolve_runtime()

    assert state.configured is True
    assert state.tessdata_prefix == str(tessdata_dir)
    assert state.ocr_lang == "eng+spa"
    assert OrderDocumentOcrRuntimeService().ocr_lang() == "eng+spa"
    assert Path(ocr_runtime_service.os.environ["TESSDATA_PREFIX"]) == tessdata_dir
    assert stub.pytesseract.tesseract_cmd == str(runtime_bin)


def test_resolve_runtime_returns_none_language_without_tessdata(monkeypatch, tmp_path: Path) -> None:
    runtime_bin = tmp_path / "runtime" / "tesseract" / "tesseract.exe"
    runtime_bin.parent.mkdir(parents=True, exist_ok=True)
    runtime_bin.write_text("")

    monkeypatch.setattr(ocr_runtime_service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(ocr_runtime_service.Path, "cwd", lambda: tmp_path)
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    _install_pytesseract_stub(monkeypatch)

    state = OrderDocumentOcrRuntimeService().resolve_runtime()

    assert state.configured is True
    assert state.tessdata_prefix is None
    assert state.ocr_lang is None
    assert OrderDocumentOcrRuntimeService().ocr_lang() is None


def test_resolve_runtime_returns_unavailable_for_invalid_candidate(monkeypatch, tmp_path: Path) -> None:
    invalid_bin = tmp_path / "missing" / "tesseract.exe"
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    monkeypatch.setattr(ocr_runtime_service.OrderDocumentOcrRuntimeService, "_candidate_paths", lambda self: [invalid_bin])
    _install_pytesseract_stub(monkeypatch, version_ok=False)

    state = OrderDocumentOcrRuntimeService().resolve_runtime()

    assert state.configured is False
    assert state.tesseract_cmd is None
    assert state.tessdata_prefix is None
    assert state.ocr_lang is None
