from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import portrait
from reportlab.pdfgen import canvas

from app.core.config import BASE_DIR, DATA_DIR


class SignatureSheetService:
    DEFAULT_CONFIG_PATH = DATA_DIR / "signature_sheet_config.json"
    DEFAULT_OUTPUT_DIR = DATA_DIR / "exports"

    def __init__(self) -> None:
        self.DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def _default_config(self) -> dict:
        template_dir = Path("assets") / "templates" / "consentimientos"
        return {
            "templates": {
                "imagenes": {
                    "template_path": str(template_dir / "Plantilla Consentimiento tratamiento de imagenes.pdf"),
                    "font_name": "Helvetica",
                    "font_size": 13,
                    "fields": {
                        "fecha": {"x": 190, "y": 964, "max_chars": 24},
                        "nombre": {"x": 250, "y": 160, "max_chars": 56},
                        "nif": {"x": 620, "y": 160, "max_chars": 18},
                        "empresa": {"x": 250, "y": 138, "max_chars": 44},
                    },
                },
                "datos": {
                    "template_path": str(template_dir / "Plantilla Consentimiento tratamiento de datos.pdf"),
                    "font_name": "Helvetica",
                    "font_size": 13,
                    "fields": {
                        # Despues de "ARINAGA, en fecha"
                        "fecha": {"x": 245, "y": 948, "max_chars": 24},
                        # Despues de "Nombre y Apellidos"
                        "nombre": {"x": 235, "y": 254, "max_chars": 58},
                        # Debajo de "Nombre y Apellidos"
                        "nif": {"x": 220, "y": 236, "max_chars": 22},
                    },
                },
            }
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
        defaults = self._default_config()

        # Migrate old single-template schema to new "templates" schema.
        if "templates" not in raw_config:
            old = raw_config
            raw_config = {"templates": {"imagenes": old}}

        templates = raw_config.get("templates")
        if not isinstance(templates, dict):
            templates = {}
            raw_config["templates"] = templates

        changed = False
        for template_key, default_template in defaults["templates"].items():
            tpl = templates.get(template_key)
            if not isinstance(tpl, dict):
                templates[template_key] = default_template
                changed = True
                continue
            if "template_path" not in tpl:
                tpl["template_path"] = default_template["template_path"]
                changed = True
            if "font_name" not in tpl:
                tpl["font_name"] = default_template["font_name"]
                changed = True
            if "font_size" not in tpl:
                tpl["font_size"] = default_template["font_size"]
                changed = True
            if "fields" not in tpl or not isinstance(tpl["fields"], dict):
                tpl["fields"] = {}
                changed = True
            for field_name, field_spec in default_template["fields"].items():
                if field_name not in tpl["fields"]:
                    tpl["fields"][field_name] = field_spec
                    changed = True

        if changed:
            path.write_text(json.dumps(raw_config, ensure_ascii=False, indent=2), encoding="utf-8")
        return raw_config

    def generate(
        self,
        attendees: Iterable[dict[str, str]],
        output_path: Path,
        template_key: str = "imagenes",
        config_path: Path | None = None,
    ) -> Path:
        config = self.load_config(config_path)
        templates = config.get("templates") or {}
        template_cfg = templates.get(template_key)
        if not isinstance(template_cfg, dict):
            raise ValueError(f"Plantilla no configurada: {template_key}")

        template_path = self._resolve_template_path(str(template_cfg.get("template_path") or ""))
        if not template_path.exists():
            raise FileNotFoundError(f"No se encontro la plantilla PDF: {template_path}")

        template_bytes = template_path.read_bytes()
        template_reader = PdfReader(BytesIO(template_bytes))
        if not template_reader.pages:
            raise ValueError("La plantilla PDF no contiene paginas.")
        template_page = template_reader.pages[0]
        page_width = float(template_page.mediabox.width)
        page_height = float(template_page.mediabox.height)

        font_name = str(template_cfg.get("font_name") or "Helvetica")
        font_size = float(template_cfg.get("font_size") or 11)
        fields = template_cfg.get("fields") or {}

        writer = PdfWriter()
        for attendee in attendees:
            overlay = self._build_overlay(
                page_width=page_width,
                page_height=page_height,
                font_name=font_name,
                font_size=font_size,
                fields=fields,
                attendee=attendee,
            )
            page = PdfReader(BytesIO(template_bytes)).pages[0]
            page.merge_page(overlay.pages[0])
            writer.add_page(page)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as fh:
            writer.write(fh)
        return output_path

    def _resolve_template_path(self, value: str) -> Path:
        raw = (value or "").strip()
        path = Path(raw)
        if path.is_absolute():
            return path
        return BASE_DIR / path

    def _build_overlay(
        self,
        page_width: float,
        page_height: float,
        font_name: str,
        font_size: float,
        fields: dict,
        attendee: dict[str, str],
    ) -> PdfReader:
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=portrait((page_width, page_height)))
        c.setFont(font_name, font_size)

        def draw_field(key: str, value: str) -> None:
            spec = fields.get(key) or {}
            x = float(spec.get("x", 0))
            y = float(spec.get("y", 0))
            max_chars = int(spec.get("max_chars", 0) or 0)
            text = (value or "").strip()
            if max_chars > 0:
                text = text[:max_chars]
            c.drawString(x, y, text)

        for key in ("fecha", "nombre", "nif", "empresa"):
            if key in fields:
                draw_field(key, attendee.get(key) or "")
        c.save()
        packet.seek(0)
        return PdfReader(packet)
