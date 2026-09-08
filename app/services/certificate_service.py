from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, cast

import fitz

from app.core.config import BASE_DIR, DATA_DIR


class CertificateService:
    DEFAULT_CONFIG_PATH = DATA_DIR / "certificate_config.json"
    DEFAULT_OUTPUT_DIR = DATA_DIR / "exports"

    def __init__(self) -> None:
        self.DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def _default_config(self) -> dict:
        external_template = Path(r"e:\IREKS\#CURSOS\Plantilla Certificado asistencia.pdf")
        internal_template = Path("assets") / "templates" / "certificados" / "Plantilla Certificado asistencia.pdf"
        template_path = str(external_template if external_template.exists() else internal_template)
        return {
            "template_path": template_path,
            "font_name": "helv",
            "font_size": 20,
            "targets": {
                "asistente": {
                    "placeholders": ["Nombre del asistente"],
                    "baseline": 210.12,
                    "bottom": 240,
                    "center_margin": 70,
                    "box_height": 44,
                    "max_lines": 1,
                    "v_align": "middle",
                },
                "curso": {
                    "placeholders": ["Nombre del curso"],
                    "baseline": 335.29,
                    "bottom": 378,
                    "center_margin": 70,
                    "box_height": 90,
                    "max_lines": 2,
                    "v_align": "top",
                    "y_offset": 2,
                },
                "tecnicos": {
                    "placeholders": ["Jordi Ampurdan\u00e8s", "David Lloria"],
                    "replace_all": True,
                    "center_margin": 70,
                    "font_size": 16,
                    "baseline": 421.91,
                    "bottom": 477,
                    "max_lines": 5,
                },
                "fecha": {
                    "placeholders": ["Arinaga, 15 de abril de 2026"],
                    "font_size": 14,
                    "baseline": 499.56,
                    "bottom": 525,
                    "center_margin": 70,
                    "box_height": 40,
                    "max_lines": 1,
                    "v_align": "middle",
                },
            },
        }

    def ensure_default_config(self) -> Path:
        if self.DEFAULT_CONFIG_PATH.exists():
            return self.DEFAULT_CONFIG_PATH
        config = self._default_config()
        self.DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.DEFAULT_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.DEFAULT_CONFIG_PATH

    def load_config(self, config_path: Path | None = None) -> dict:
        path = config_path or self.ensure_default_config()
        if not path.exists():
            path = self.ensure_default_config()
        raw_config = json.loads(path.read_text(encoding="utf-8"))
        default = self._default_config()
        changed = False
        for key in ("template_path", "font_name", "font_size"):
            if key not in raw_config:
                raw_config[key] = default[key]
                changed = True

        # Migrate legacy coordinate-based schema.
        if "targets" not in raw_config and isinstance(raw_config.get("fields"), dict):
            raw_config["targets"] = default["targets"]
            changed = True

        if "targets" not in raw_config or not isinstance(raw_config["targets"], dict):
            raw_config["targets"] = {}
            changed = True

        for field_name, spec in default["targets"].items():
            if field_name not in raw_config["targets"] or not isinstance(raw_config["targets"][field_name], dict):
                raw_config["targets"][field_name] = spec
                changed = True
                continue
            target_cfg = raw_config["targets"][field_name]
            for key, value in spec.items():
                if key not in target_cfg:
                    target_cfg[key] = value
                    changed = True

        font_name = str(raw_config.get("font_name") or "").strip().lower()
        if font_name == "helvetica":
            raw_config["font_name"] = "helv"
            changed = True

        # Legacy key kept only for backward compatibility.
        if "fields" in raw_config:
            del raw_config["fields"]
            changed = True

        if "template_path" in raw_config and str(raw_config.get("template_path") or "").strip():
            template_path = self._resolve_template_path(str(raw_config.get("template_path") or ""))
            if not template_path.exists():
                raw_config["template_path"] = default["template_path"]
                changed = True

        if changed:
            path.write_text(json.dumps(raw_config, ensure_ascii=False, indent=2), encoding="utf-8")
        return raw_config

    def generate(
        self,
        certificates: Iterable[dict[str, str]],
        output_path: Path,
        config_path: Path | None = None,
    ) -> Path:
        config = self.load_config(config_path)
        template_path = self._resolve_template_path(str(config.get("template_path") or ""))
        if not template_path.exists():
            raise FileNotFoundError(f"No se encontro la plantilla PDF: {template_path}")

        font_name = self._normalize_font_name(str(config.get("font_name") or "helv"))
        font_size = float(config.get("font_size") or 12)
        targets = config.get("targets") or {}

        template_bytes = template_path.read_bytes()
        with fitz.open() as final_doc:
            for item in certificates:
                with fitz.open(stream=template_bytes, filetype="pdf") as doc:
                    if doc.page_count < 1:
                        raise ValueError("La plantilla PDF no contiene paginas.")
                    page = doc[0]
                    # Delete marker characters through a narrow strip at their centre.
                    # Full font bounding boxes can overlap adjacent fixed lines.
                    for field_name in ("asistente", "curso", "tecnicos", "fecha"):
                        target = targets.get(field_name) or {}
                        found = False
                        for placeholder in target.get("placeholders", []):
                            rects = page.search_for(str(placeholder).strip())
                            for rect in rects:
                                middle = (rect.y0 + rect.y1) / 2
                                page.add_redact_annot(fitz.Rect(rect.x0, middle - 0.5, rect.x1, middle + 0.5), fill=False)
                                found = True
                            if rects and not target.get("replace_all", False):
                                break
                        if not found:
                            raise ValueError(f"No se encuentra el campo en la plantilla: {target.get('placeholders')}")
                    page.apply_redactions()
                    for field_name in ("asistente", "curso", "tecnicos", "fecha"):
                        target_cfg = targets.get(field_name) or {}
                        self._replace_text_target(
                            page=page,
                            target_cfg=target_cfg,
                            new_text=str(item.get(field_name) or ""),
                            font_name=font_name,
                            font_size=float(target_cfg.get("font_size", font_size)),
                            max_lines=int(target_cfg.get("max_lines", 1)),
                        )
                    final_doc.insert_pdf(doc, from_page=0, to_page=0)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            final_doc.save(str(output_path))
        return output_path

    def _resolve_template_path(self, value: str) -> Path:
        raw = (value or "").strip()
        path = Path(raw)
        if path.is_absolute():
            return path
        return BASE_DIR / path

    def _normalize_font_name(self, font_name: str) -> str:
        name = (font_name or "").strip().lower()
        if name in {"helvetica", "helv"}:
            return "helv"
        return name or "helv"

    def _replace_text_target(
        self,
        page: fitz.Page,
        target_cfg: dict,
        new_text: str,
        font_name: str,
        font_size: float,
        max_lines: int,
    ) -> None:
        page_obj = cast(Any, page)
        margin = float(target_cfg.get("center_margin", 70))
        baseline = float(target_cfg["baseline"])
        bottom = float(target_cfg["bottom"])
        width = page.rect.width - 2 * margin
        text = (new_text or "").strip()
        font = fitz.Font(font_name)
        draw_size = float(font_size)
        lines: list[str] = []
        while draw_size >= 10:
            lines = self._wrap_lines(text, width, font_name, draw_size)
            if (len(lines) <= max_lines
                    and all(font.text_length(line, fontsize=draw_size) <= width for line in lines)
                    and baseline + max(0, len(lines) - 1) * draw_size * 1.2 + draw_size * 0.3 <= bottom):
                break
            draw_size -= 0.5
        else:
            raise ValueError("El texto del certificado no cabe en su espacio sin recortarlo.")

        for index, line in enumerate(lines):
            line_width = font.text_length(line, fontsize=draw_size)
            page_obj.insert_text(
                ((page.rect.width - line_width) / 2, baseline + index * draw_size * 1.2),
                line, fontname=font_name, fontsize=draw_size, color=(0, 0, 0),
            )

    @staticmethod
    def _wrap_lines(text: str, width: float, font_name: str, font_size: float) -> list[str]:
        lines = []
        font = fitz.Font(font_name)
        for paragraph in text.splitlines():
            line = ""
            for word in paragraph.split():
                candidate = f"{line} {word}".strip()
                if line and font.text_length(candidate, fontsize=font_size) > width:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                lines.append(line)
        return lines
