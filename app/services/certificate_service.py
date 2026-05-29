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
                    "center_margin": 70,
                    "box_height": 44,
                    "max_lines": 1,
                    "v_align": "middle",
                },
                "curso": {
                    "placeholders": ["Nombre del curso"],
                    "center_margin": 70,
                    "box_height": 90,
                    "max_lines": 2,
                    "v_align": "top",
                    "y_offset": 2,
                },
                "fecha": {
                    "placeholders": ["Arinaga, 15 de abril de 2026"],
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
        final_doc = fitz.open()
        for item in certificates:
            doc = fitz.open(stream=template_bytes, filetype="pdf")
            if doc.page_count < 1:
                doc.close()
                raise ValueError("La plantilla PDF no contiene paginas.")
            page = doc[0]
            self._replace_text_target(
                page=page,
                target_cfg=targets.get("asistente") or {},
                new_text=str(item.get("asistente") or ""),
                font_name=font_name,
                font_size=font_size,
                max_lines=1,
            )
            self._replace_text_target(
                page=page,
                target_cfg=targets.get("curso") or {},
                new_text=str(item.get("curso") or ""),
                font_name=font_name,
                font_size=font_size,
                max_lines=2,
            )
            self._replace_text_target(
                page=page,
                target_cfg=targets.get("fecha") or {},
                new_text=str(item.get("fecha") or ""),
                font_name=font_name,
                font_size=font_size,
                max_lines=1,
            )
            final_doc.insert_pdf(doc, from_page=0, to_page=0)
            doc.close()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_doc.save(str(output_path))
        final_doc.close()
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
        placeholder_rect = self._find_placeholder_rect(page, target_cfg)
        if placeholder_rect is None:
            return

        page_obj.add_redact_annot(placeholder_rect, fill=(1, 1, 1))
        page_obj.apply_redactions()

        margin = float(target_cfg.get("center_margin", 70) or 70)
        box_height = float(target_cfg.get("box_height", 32) or 32)
        y_offset = float(target_cfg.get("y_offset", 0) or 0)
        v_align = str(target_cfg.get("v_align") or "middle").strip().lower()
        if v_align == "top":
            box_top = placeholder_rect.y0 + y_offset
        elif v_align == "bottom":
            box_top = placeholder_rect.y1 - box_height + y_offset
        else:
            center_y = (placeholder_rect.y0 + placeholder_rect.y1) / 2.0
            box_top = center_y - box_height / 2.0 + y_offset
        insert_rect = fitz.Rect(
            margin,
            box_top,
            page_obj.rect.width - margin,
            box_top + box_height,
        )

        text = (new_text or "").strip()
        if max_lines > 1:
            text = self._wrap_text(
                text=text,
                max_width=insert_rect.width,
                font_name=font_name,
                font_size=font_size,
                max_lines=max_lines,
            )
        draw_font_size = max(10.0, float(font_size))
        result = -1.0
        while draw_font_size >= 10.0:
            result = page_obj.insert_textbox(
                insert_rect,
                text,
                fontname=font_name,
                fontsize=draw_font_size,
                align=fitz.TEXT_ALIGN_CENTER,
                color=(0, 0, 0),
            )
            if result >= 0:
                break
            draw_font_size -= 1.0

    def _find_placeholder_rect(self, page: fitz.Page, target_cfg: dict) -> fitz.Rect | None:
        page_obj = cast(Any, page)
        placeholders = target_cfg.get("placeholders") or []
        for raw in placeholders:
            text = str(raw or "").strip()
            if not text:
                continue
            rects = page_obj.search_for(text)
            if rects:
                rect = rects[0]
                for extra in rects[1:]:
                    rect |= extra
                return rect
        return None

    def _wrap_text(
        self,
        text: str,
        max_width: float,
        font_name: str,
        font_size: float,
        max_lines: int,
    ) -> str:
        value = (text or "").strip()
        if not value:
            return ""
        if fitz.get_text_length(value, fontname=font_name, fontsize=font_size) <= max_width:
            return value

        def truncate_to_width(line: str) -> str:
            txt = line.strip()
            while txt and fitz.get_text_length(txt, fontname=font_name, fontsize=font_size) > max_width:
                txt = txt[:-1].rstrip()
            return txt

        if max_lines <= 1:
            return truncate_to_width(value)

        words = value.split()
        if not words:
            return ""

        first_line = ""
        split_index = 0
        for idx, word in enumerate(words):
            candidate = word if not first_line else f"{first_line} {word}"
            if fitz.get_text_length(candidate, fontname=font_name, fontsize=font_size) <= max_width or not first_line:
                first_line = candidate
                split_index = idx + 1
                continue
            break

        second_line = " ".join(words[split_index:]).strip()
        if not second_line and split_index < len(words):
            second_line = words[split_index]

        first_line = truncate_to_width(first_line)
        second_line = truncate_to_width(second_line)
        return f"{first_line}\n{second_line}".strip()
