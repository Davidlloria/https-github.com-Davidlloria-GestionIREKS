from __future__ import annotations

from dataclasses import dataclass
import os
import sys
from pathlib import Path

from app.core.config import BASE_DIR


@dataclass(slots=True)
class OcrRuntimeState:
    configured: bool
    tesseract_cmd: str | None
    tessdata_prefix: str | None
    ocr_lang: str | None
    message: str = ""


class OrderDocumentOcrRuntimeService:
    def resolve_runtime(self) -> OcrRuntimeState:
        try:
            import pytesseract
        except Exception:
            return OcrRuntimeState(False, None, None, None, "pytesseract no disponible.")

        candidates = self._candidate_paths()
        seen: set[Path] = set()
        for candidate in candidates:
            candidate = candidate.expanduser().resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            state = self._apply_candidate(candidate, pytesseract)
            if state.configured:
                return state

        state = self._apply_candidate(None, pytesseract)
        if state.configured:
            return state
        return OcrRuntimeState(False, None, None, None, "No se pudo configurar Tesseract.")

    def configure_tesseract(self) -> bool:
        return self.resolve_runtime().configured

    def ocr_lang(self) -> str | None:
        return self.resolve_runtime().ocr_lang

    def _candidate_paths(self) -> list[Path]:
        candidates: list[Path] = []

        env_cmd = os.environ.get("TESSERACT_CMD")
        if env_cmd:
            candidates.append(Path(env_cmd))

        runtime_dirs = [
            BASE_DIR / "runtime" / "tesseract",
            Path.cwd() / "runtime" / "tesseract",
        ]
        if getattr(sys, "frozen", False):
            runtime_dirs.insert(0, Path(sys.executable).resolve().parent / "runtime" / "tesseract")
            bundle_dir = getattr(sys, "_MEIPASS", "")
            if bundle_dir:
                runtime_dirs.insert(0, Path(bundle_dir) / "runtime" / "tesseract")

        for runtime_dir in runtime_dirs:
            candidates.append(runtime_dir / "tesseract.exe")
            candidates.append(runtime_dir / "Tesseract-OCR" / "tesseract.exe")

        candidates.extend(
            [
                Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
                Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
            ]
        )
        return candidates

    def _apply_candidate(self, candidate: Path | None, pytesseract: object) -> OcrRuntimeState:
        if candidate is None:
            tesseract_dir = None
            candidate_cmd = None
        else:
            if not candidate.exists():
                return OcrRuntimeState(False, None, None, None)
            tesseract_dir = candidate.parent
            candidate_cmd = str(candidate)
            pytesseract.pytesseract.tesseract_cmd = candidate_cmd  # type: ignore[attr-defined]

        tessdata_prefix = self._configure_tessdata_prefix(tesseract_dir)
        try:
            pytesseract.get_tesseract_version()  # type: ignore[attr-defined]
        except Exception:
            return OcrRuntimeState(False, None, None, None)
        return OcrRuntimeState(True, candidate_cmd, tessdata_prefix, self._resolve_ocr_lang(tessdata_prefix))

    def _configure_tessdata_prefix(self, tesseract_dir: Path | None) -> str | None:
        if tesseract_dir is None:
            return os.environ.get("TESSDATA_PREFIX") or None
        tessdata_dir = tesseract_dir / "tessdata"
        if tessdata_dir.exists():
            tessdata_prefix = str(tessdata_dir)
            os.environ["TESSDATA_PREFIX"] = tessdata_prefix
            return tessdata_prefix
        return os.environ.get("TESSDATA_PREFIX") or None

    def _resolve_ocr_lang(self, tessdata_prefix: str | None) -> str | None:
        if not tessdata_prefix:
            return None
        tessdata_dir = Path(tessdata_prefix)
        langs = [lang for lang in ("eng", "spa") if (tessdata_dir / f"{lang}.traineddata").exists()]
        return "+".join(langs) if langs else None
