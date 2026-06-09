from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, cast

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Circle, Drawing, String
from reportlab.platypus import Image as RLImage
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.database import engine
from app.models import Cliente, IngredienteIreks, IngredienteStd, MateriaPrimaValorNutricional, Receta, RecetaLinea
from app.services.recipe_calculation_service import RecipeCalculationService
from app.services.recipe_service import RecipeService


class PdfService:
    def __init__(self) -> None:
        self.icons_dir = Path("assets") / "icons"
        self.badges_dir = Path("assets") / "templates" / "badges"
        self.header_elaboracion_path = Path("assets") / "templates" / "recetas" / "imagen_cabecera_receta_elaboracion.png"
        self.header_costes_path = Path("assets") / "templates" / "recetas" / "imagen_cabecera_receta_costes.png"
        self.ireks_logo_path = Path("assets") / "logos" / "corporativos" / "IREKS_Logo_transparente.png"

        self.icon_map = {
            "etiqueta": "icon_etiqueta.png",
            "usuario": "icon_usuario.png",
            "calendario": "icon_calendario.png",
            "amasadora": "icon_amasadora.png",
            "bol": "icon_bol.png",
            "masa": "icon_masa.png",
            "fermentacion": "icon_fermentacion.png",
            "horno": "icon_horno.png",
            "gota": "icon_gota.png",
            "termometro": "icon_termometro.png",
            "reloj": "icon_reloj.png",
            "pan": "icon_pan.png",
            "monedas": "icon_monedas.png",
            "pastel": "icon_pastel.png",
            "hoja": "icon_hoja.png",
        }

        styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            "title",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=25,
            textColor=colors.HexColor("#1A1A1A"),
        )
        self.subtitle_style = ParagraphStyle(
            "subtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=15,
            leading=17,
            textColor=colors.HexColor("#2B2B2B"),
        )
        self.section_style = ParagraphStyle(
            "section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11.7,
            leading=13,
            textColor=colors.HexColor("#212121"),
        )
        self.label_style = ParagraphStyle(
            "label",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.2,
            leading=9.7,
            textColor=colors.HexColor("#3D3D3D"),
        )
        self.label_right_style = ParagraphStyle(
            "label_right",
            parent=self.label_style,
            alignment=2,
        )
        self.value_style = ParagraphStyle(
            "value",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.9,
            leading=10.3,
            textColor=colors.HexColor("#151515"),
        )
        self.body_style = ParagraphStyle(
            "body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor("#151515"),
        )
        self.body_right_style = ParagraphStyle(
            "body_right",
            parent=self.body_style,
            alignment=2,
        )
        self.small_style = ParagraphStyle(
            "small",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.9,
            leading=9.5,
            textColor=colors.HexColor("#4C4C4C"),
        )
        self.kpi_label_style = ParagraphStyle(
            "kpi_label",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.9,
            leading=9,
            textColor=colors.HexColor("#232323"),
            alignment=1,
        )
        self.kpi_value_style = ParagraphStyle(
            "kpi_value",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.7,
            leading=10,
            textColor=colors.HexColor("#151515"),
            alignment=1,
        )
        self.cost_kpi_label_style = ParagraphStyle(
            "cost_kpi_label",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.4,
            leading=8.4,
            textColor=colors.HexColor("#232323"),
            alignment=1,
        )
        self.cost_kpi_value_style = ParagraphStyle(
            "cost_kpi_value",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.3,
            leading=9.3,
            textColor=colors.HexColor("#151515"),
            alignment=1,
        )

    def _normalize_process_name(self, value: str | None) -> str:
        text = str(value or "").strip()
        return text if text else "Masa final"

    def _group_lines_by_process(self, lineas: list[RecetaLinea]) -> list[tuple[str, list[RecetaLinea]]]:
        grouped: dict[str, list[RecetaLinea]] = {}
        order: list[str] = []
        for line in lineas:
            name = self._normalize_process_name(getattr(line, "proceso_nombre", "") or "Masa final")
            if name not in grouped:
                grouped[name] = []
                order.append(name)
            grouped[name].append(line)
        if not grouped:
            return [("Masa final", [])]
        return [(name, grouped.get(name, [])) for name in order]

    def _parse_process_sections(self, raw_text: str, process_names: list[str]) -> dict[str, str]:
        raw = str(raw_text or "").strip()
        if not raw:
            return {}
        lines = [line.rstrip() for line in raw.splitlines()]
        sections: dict[str, list[str]] = {}
        current: str | None = None
        seen_heading = False
        known = {name.lower(): name for name in process_names}

        def resolve_heading(text: str) -> str:
            cleaned = text.strip().strip(":").strip()
            if not cleaned:
                return "Masa final"
            key = cleaned.lower()
            if key in known:
                return known[key]
            for known_key, known_name in known.items():
                if key == known_key or key in known_key or known_key in key:
                    return known_name
            return self._normalize_process_name(cleaned)

        for line in lines:
            stripped = line.strip()
            heading_candidate = None
            if stripped.startswith("## "):
                heading_candidate = stripped[3:].strip()
            elif stripped.startswith("@"):
                heading_candidate = stripped[1:].strip()
            elif stripped.startswith("[") and stripped.endswith("]") and len(stripped) <= 80:
                heading_candidate = stripped[1:-1].strip()
            if heading_candidate is not None:
                current = resolve_heading(heading_candidate)
                sections.setdefault(current, [])
                seen_heading = True
                continue
            if current is None:
                current = "Masa final"
                sections.setdefault(current, [])
            sections[current].append(stripped)

        if not seen_heading:
            return {"Masa final": raw}

        normalized: dict[str, str] = {}
        for name, content_lines in sections.items():
            text = "\n".join([x for x in content_lines if x.strip()]).strip()
            normalized[name] = text
        return normalized

    def _json_to_obj(self, raw_value: str):
        text = (raw_value or "").strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _resolve_elab_by_process(
        self,
        elab_obj: dict,
        elab_flat: dict[str, str],
        process_names: list[str],
    ) -> dict[str, dict[str, str]]:
        fields = [
            "peso_pieza",
            "am1_lenta",
            "am1_rapida",
            "am1_temp",
            "rep_bloque_1",
            "rep_bloque_2",
            "fermentacion_temp",
            "rep_fermentacion",
            "fermentacion_humedad",
            "precalentamiento_coc",
            "temp_coccion_coc",
            "tiempo_coccion_coc",
            "vapor_coc",
        ]
        base = {k: str(elab_flat.get(k, "") or "").strip() for k in fields}
        result: dict[str, dict[str, str]] = {name: dict(base) for name in process_names}

        procesos_obj = elab_obj.get("procesos") if isinstance(elab_obj, dict) else None
        if isinstance(procesos_obj, dict):
            for name in process_names:
                cfg = procesos_obj.get(name)
                if not isinstance(cfg, dict):
                    continue
                for key in fields:
                    if key in cfg:
                        result[name][key] = str(cfg.get(key, "") or "").strip()
                if not result[name].get("rep_fermentacion", "").strip():
                    legacy_ferment = str(cfg.get("fermentacion", "") or cfg.get("tiempo_fermentacion", "") or "").strip()
                    if legacy_ferment:
                        result[name]["rep_fermentacion"] = legacy_ferment
                if not result[name].get("rep_bloque_1", "").strip():
                    result[name]["rep_bloque_1"] = str(cfg.get("am2_lenta", "") or "").strip()
                if not result[name].get("rep_bloque_2", "").strip():
                    result[name]["rep_bloque_2"] = str(cfg.get("am2_rapida", "") or "").strip()
                if not result[name].get("fermentacion_temp", "").strip():
                    result[name]["fermentacion_temp"] = str(cfg.get("am2_temp", "") or "").strip()

        # Flat override format: proceso::<nombre>::<campo>
        for raw_key, raw_val in elab_flat.items():
            key = str(raw_key or "")
            if not key.startswith("proceso::"):
                continue
            parts = key.split("::", 2)
            if len(parts) != 3:
                continue
            proc_name, field = parts[1].strip(), parts[2].strip()
            if not proc_name or field not in fields:
                continue
            for name in process_names:
                if name.lower() == proc_name.lower():
                    result[name][field] = str(raw_val or "").strip()
                    break
        for name in process_names:
            if result[name].get("rep_fermentacion", "").strip():
                pass
            else:
                for legacy_key in ("fermentacion", "tiempo_fermentacion"):
                    flat_key = f"proceso::{name}::{legacy_key}"
                    v = str(elab_flat.get(flat_key, "") or "").strip()
                    if v:
                        result[name]["rep_fermentacion"] = v
                        break
            if not result[name].get("rep_bloque_1", "").strip():
                v = str(elab_flat.get(f"proceso::{name}::am2_lenta", "") or "").strip()
                if v:
                    result[name]["rep_bloque_1"] = v
            if not result[name].get("rep_bloque_2", "").strip():
                v = str(elab_flat.get(f"proceso::{name}::am2_rapida", "") or "").strip()
                if v:
                    result[name]["rep_bloque_2"] = v
            if not result[name].get("fermentacion_temp", "").strip():
                v = str(elab_flat.get(f"proceso::{name}::am2_temp", "") or "").strip()
                if v:
                    result[name]["fermentacion_temp"] = v
        return result

    def export_recipe_to_pdf(self, recipe_id: int, output_path: Path, layout_mode: str = "extended") -> None:
        receta, cliente, lineas = self._load_recipe_data(recipe_id)
        if not receta:
            raise ValueError("Receta no encontrada.")
        # Recalcular al exportar para evitar porcentajes panaderos obsoletos en BD.
        # Esto garantiza que el PDF refleje los datos actuales de la formula.
        calc = RecipeService().calculate(receta, lineas, sync_categories=True)
        receta = calc.receta
        lineas = calc.lineas

        esc = self._json_to_dict(receta.escandallo_detalle_json)
        elab = self._json_to_dict(receta.parametros_elaboracion_json)
        elab_obj = self._json_to_obj(receta.parametros_elaboracion_json)
        process_names = [name for name, _items in self._group_lines_by_process(lineas)]
        elab_by_process = self._resolve_elab_by_process(elab_obj, elab, process_names)
        masa_total = float(receta.masa_total_g or 0.0)
        peso_pieza = self._to_float(esc.get("peso_pieza")) or float(receta.peso_pieza_g or 0.0)
        piezas = (masa_total / peso_pieza) if peso_pieza > 0 else float(receta.numero_piezas or 0.0)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        story: list = []
        story.extend(self._build_header(receta, cliente, header_kind="elaboracion"))
        story.append(Spacer(1, 1.5 * mm))

        is_simple_layout = str(layout_mode or "").strip().lower() == "simple"
        ingredients_block = self._build_ingredients_block(receta, lineas)
        if is_simple_layout:
            right_top_block_flowables = self._build_process_block(
                elab_by_process,
                include_title=True,
                section_number=3,
                section_title="PROCESO TECNICO",
            )
            # Align title baseline with left "1 INGREDIENTES" in simple layout.
            right_top_block_flowables = [Spacer(1, 1.6 * mm), *right_top_block_flowables]
        else:
            right_top_block_flowables = self._build_process_block(
                elab_by_process,
                include_title=True,
                section_number=2,
                section_title="PROCESO TECNICO",
            )

        left_top_block = self._stack_cell(ingredients_block, 94)
        right_top_block = self._stack_cell(right_top_block_flowables, 94)
        top_h = max(self._flowable_height(left_top_block, 94), self._flowable_height(right_top_block, 94))
        top_row = Table(
            [[left_top_block, right_top_block]],
            colWidths=[94 * mm, 94 * mm],
            rowHeights=[top_h],
            hAlign="LEFT",
        )
        top_row.setStyle(self._two_col_style())
        story.append(top_row)

        story.append(Spacer(1, 1.6 * mm))
        full_process_flowables = self._build_proceso_text_block(receta, lineas, width_mm=194)
        story.append(
            KeepTogether(
                [
                    self._section_title(3, "PROCESO DE ELABORACION", None, total_width_mm=194),
                    Spacer(1, 1 * mm),
                    *full_process_flowables,
                ]
            )
        )

        if not is_simple_layout:

            story.append(Spacer(1, 1.8 * mm))
            right_nutri_block = self._stack_cell(
                self._build_nutrition_block(receta, lineas, section_number=5, section_title="VALORES NUTRICIONALES", width_mm=95),
                94,
            )
            right_nutri_h_pt = self._flowable_height(right_nutri_block, 94)
            left_obs_block = self._stack_cell(
                self._build_observations_block(
                    receta,
                    section_number=4,
                    section_title="OBSERVACIONES",
                    width_mm=95,
                    min_total_height_pt=right_nutri_h_pt,
                ),
                94,
            )
            obs_nutri_h = max(self._flowable_height(left_obs_block, 94), self._flowable_height(right_nutri_block, 94))
            obs_nutri_row = Table(
                [[left_obs_block, right_nutri_block]],
                colWidths=[94 * mm, 94 * mm],
                rowHeights=[obs_nutri_h],
                hAlign="LEFT",
            )
            obs_nutri_row.setStyle(self._two_col_style())
            story.append(obs_nutri_row)

            story.append(PageBreak())
            story.extend(self._build_header(receta, cliente, header_kind="costes"))
            story.append(Spacer(1, 1.5 * mm))
            left_bottom_flowables = self._build_cost_block(
                receta,
                lineas,
                esc,
                piezas_elaboradas=piezas,
                include_kpi=False,
                include_detail_kpis=False,
                section_title="COSTES / ESCANDALLO",
                section_number=1,
            )
            right_bottom_flowables = self._build_production_block(
                receta,
                masa_total,
                peso_pieza,
                piezas,
                section_number=2,
                section_title="DATOS DE PRODUCCION",
                top_offset_mm=0.0,
            )
            left_bottom_block = self._stack_cell(left_bottom_flowables, 94)
            right_bottom_block = self._stack_cell(right_bottom_flowables, 94)
            bottom_h = max(self._flowable_height(left_bottom_block, 94), self._flowable_height(right_bottom_block, 94))
            bottom_row = Table(
                [[left_bottom_block, right_bottom_block]],
                colWidths=[94 * mm, 94 * mm],
                rowHeights=[bottom_h],
                hAlign="LEFT",
            )
            bottom_row.setStyle(self._two_col_style())
            story.append(bottom_row)

            total_coste = 0.0
            for line in lineas:
                eur_kg = float(getattr(line, "precio_kg_snapshot", 0.0) or 0.0)
                qty_g = float(getattr(line, "cantidad_base_g", 0.0) or 0.0)
                total_coste += (qty_g / 1000.0) * eur_kg
            precio_venta = self._to_float(esc.get("precio_venta"))
            igic_pct = self._to_float(esc.get("igic"))
            rendimiento = float(piezas or 0.0)
            if rendimiento <= 0:
                rendimiento = float(receta.numero_piezas or 0.0)
            costes_fijos = self._to_float(esc.get("costes_fijos"))
            costes_variables = self._to_float(esc.get("costes_variables"))
            otros_costes = self._to_float(esc.get("otros_costes"))
            total_costes = total_coste + costes_fijos + costes_variables + otros_costes
            coste_unitario = (total_costes / rendimiento) if rendimiento > 0 else 0.0
            calc_igic = precio_venta * igic_pct / 100.0
            precio_neto = precio_venta + calc_igic
            coste_mp_unitario = (total_coste / rendimiento) if rendimiento > 0 else 0.0
            pct_coste_mp = (coste_mp_unitario / precio_venta * 100.0) if precio_venta > 0 else 0.0
            pct_margen_pv = ((precio_venta - coste_unitario) / precio_venta * 100.0) if precio_venta > 0 else 0.0
            detail_kpis = self._build_cost_detail_kpis(
                coste_mp=total_coste,
                costes_fijos=costes_fijos,
                costes_variables=costes_variables,
                otros_costes=otros_costes,
                total_costes=total_costes,
                unidades_totales=rendimiento,
                coste_unitario=coste_unitario,
                precio_venta=precio_venta,
                igic_pct=igic_pct,
                calc_igic=calc_igic,
                precio_neto=precio_neto,
                pct_coste_mp=pct_coste_mp,
                pct_margen_pv=pct_margen_pv,
            )

            coste_pieza = (total_coste / rendimiento) if rendimiento > 0 else 0.0
            margen = ((precio_venta - coste_pieza) / precio_venta * 100.0) if precio_venta > 0 else 0.0
            summary_kpi = Table(
                [[
                    self._kpi_card("masa", "TOTAL MASA", f"{self._fmt(masa_total, 2)} g", 31.7),
                    self._kpi_card("monedas", "COSTE TOTAL", f"{self._fmt(total_costes, 2)} €", 31.7),
                    self._kpi_card("pan", "PESO PIEZA", f"{self._fmt(peso_pieza, 2)} g", 31.7),
                    self._kpi_card("monedas", "COSTE PIEZA", f"{self._fmt(coste_pieza, 2)} €", 31.7),
                    self._kpi_card("etiqueta", "PVP", f"{self._fmt(precio_venta, 2)} €", 31.7),
                    self._kpi_card("pastel", "MARGEN ESTIMADO", f"{self._fmt(margen, 2)}%", 31.7),
                ]],
                colWidths=[31.7 * mm, 31.7 * mm, 31.7 * mm, 31.7 * mm, 31.7 * mm, 31.7 * mm],
                hAlign="LEFT",
            )
            summary_kpi.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D2D2D2")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E8E8E8")),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )

            right_bottom_flowables.extend([Spacer(1, 1.2 * mm), *detail_kpis["costes_produccion"]])
            right_bottom_block = self._stack_cell(right_bottom_flowables, 94)
            bottom_h = max(self._flowable_height(left_bottom_block, 94), self._flowable_height(right_bottom_block, 94))
            bottom_row = Table(
                [[left_bottom_block, right_bottom_block]],
                colWidths=[94 * mm, 94 * mm],
                rowHeights=[bottom_h],
                hAlign="LEFT",
            )
            bottom_row.setStyle(self._two_col_style())
            story[-1] = bottom_row

            story.append(Spacer(1, 1.8 * mm))
            left_kpi8_block = self._stack_cell(detail_kpis["costes_unidad"], 94)
            right_kpi9_block = self._stack_cell(detail_kpis["precios_margenes"], 94)
            kpi89_h = max(self._flowable_height(left_kpi8_block, 94), self._flowable_height(right_kpi9_block, 94))
            kpi89_row = Table(
                [[left_kpi8_block, right_kpi9_block]],
                colWidths=[94 * mm, 94 * mm],
                rowHeights=[kpi89_h],
                hAlign="LEFT",
            )
            kpi89_row.setStyle(self._two_col_style())
            story.append(kpi89_row)

            story.append(Spacer(1, 1.2 * mm))
            summary_row = Table([[summary_kpi]], colWidths=[194 * mm], hAlign="LEFT")
            summary_row.setStyle(
                TableStyle(
                    [
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            story.append(summary_row)
        story.append(Spacer(1, 2 * mm))

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=6 * mm,
            rightMargin=6 * mm,
            topMargin=6 * mm,
            bottomMargin=6 * mm,
            title=f"Ficha tecnica - {receta.nombre}",
            author="Gestion IREKS",
        )
        doc.build(story, onFirstPage=self._draw_page_bg, onLaterPages=self._draw_page_bg)

    def _two_col_style(self) -> TableStyle:
        return TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm),
                ("LEFTPADDING", (1, 0), (1, 0), 4 * mm),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )

    def _stack_cell(self, flowables: list, width_mm: float) -> Table:
        box = Table([[flowables]], colWidths=[width_mm * mm], hAlign="LEFT")
        box.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return box

    def _flowable_height(self, flowable, width_mm: float) -> float:
        _w, h = flowable.wrap(width_mm * mm, 10000 * mm)
        return h

    def _sync_parallel_table_row_heights(
        self,
        left_flowables: list,
        left_cols: int,
        right_flowables: list,
        right_cols: int,
        left_key: str | None = None,
        right_key: str | None = None,
    ) -> None:
        left_table = self._find_table_by_key(left_flowables, left_key) if left_key else None
        right_table = self._find_table_by_key(right_flowables, right_key) if right_key else None
        if not left_table:
            left_table = self._find_table_by_cols(left_flowables, left_cols, min_rows=3)
        if not right_table:
            right_table = self._find_table_by_cols(right_flowables, right_cols, min_rows=3)
        if not left_table or not right_table:
            return

        left_width = sum(float(w) for w in getattr(left_table, "_colWidths", []) or [])
        right_width = sum(float(w) for w in getattr(right_table, "_colWidths", []) or [])
        if left_width <= 0 or right_width <= 0:
            return

        left_table.wrap(left_width, 10000 * mm)
        right_table.wrap(right_width, 10000 * mm)

        left_heights = list(getattr(left_table, "_rowHeights", []) or [])
        right_heights = list(getattr(right_table, "_rowHeights", []) or [])
        if not left_heights or not right_heights:
            return

        max_len = max(len(left_heights), len(right_heights))
        shared: list[float] = []
        for i in range(max_len):
            lh = left_heights[i] if i < len(left_heights) else 0.0
            rh = right_heights[i] if i < len(right_heights) else 0.0
            shared.append(max(float(lh or 0.0), float(rh or 0.0)))

        left_table_any = left_table  # reportlab uses dynamic internal attrs
        right_table_any = right_table
        setattr(left_table_any, "_argH", list(shared))
        setattr(right_table_any, "_argH", list(shared))
        setattr(left_table_any, "_rowHeights", list(shared))
        setattr(right_table_any, "_rowHeights", list(shared))

    def _find_table_by_key(self, flowables: list, key: str | None):
        if not key:
            return None
        for flowable in flowables:
            if not isinstance(flowable, Table):
                continue
            if getattr(flowable, "_ireks_sync_key", None) == key:
                return flowable
        return None

    def _find_table_by_cols(self, flowables: list, cols: int, min_rows: int = 1):
        candidates = []
        for flowable in flowables:
            if not isinstance(flowable, Table):
                continue
            ncols = int(getattr(flowable, "_ncols", 0) or 0)
            nrows = int(getattr(flowable, "_nrows", 0) or 0)
            if ncols == cols and nrows >= min_rows:
                candidates.append(flowable)
        if not candidates:
            return None
        # Pick the largest table (data table), avoiding tiny header/section tables.
        candidates.sort(key=lambda t: int(getattr(t, "_nrows", 0) or 0), reverse=True)
        return candidates[0]

    def _build_header(self, receta: Receta, cliente: Cliente | None, header_kind: str = "elaboracion") -> list:
        cliente_name = ""
        if cliente:
            cliente_name = (
                (cliente.cliente_nombre_comercial or "").strip()
                or (cliente.cliente_nombre_fiscal or "").strip()
                or (cliente.cliente_nombre_interno or "").strip()
            )
        today = datetime.now().strftime("%d/%m/%Y")

        header_path = self.header_elaboracion_path if str(header_kind).strip().lower() == "elaboracion" else self.header_costes_path

        if header_path.exists() and self.ireks_logo_path.exists():
            logo_img = RLImage(str(self.ireks_logo_path), width=39 * mm, height=24 * mm)
            right_banner = RLImage(str(header_path), width=145 * mm, height=35 * mm)
            separator = Table([[""]], colWidths=[0.6 * mm], rowHeights=[23 * mm], hAlign="CENTER")
            separator.setStyle(
                TableStyle(
                    [
                        ("LINEBEFORE", (0, 0), (0, 0), 0.8, colors.HexColor("#A5A5A5")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )
            banner = Table([[logo_img, separator, right_banner]], colWidths=[45 * mm, 2 * mm, 143 * mm], rowHeights=[35 * mm], hAlign="LEFT")
            banner.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (0, 0), "CENTER"),
                        ("ALIGN", (1, 0), (1, 0), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#C7AA89")),
                    ]
                )
            )
            info = self._build_header_info_strip(receta, cliente_name, today, show_client=not bool(receta.es_base))
            return [banner, Spacer(1, 1.2 * mm), info]

        title = Table(
            [
                [Paragraph("FICHA TECNICA", self.title_style)],
                [Paragraph("DE ELABORACION", self.subtitle_style)],
            ],
            colWidths=[190 * mm],
            hAlign="LEFT",
        )
        title.setStyle(
            TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#C7AA89")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        info = self._build_header_info_strip(receta, cliente_name, today, show_client=not bool(receta.es_base))
        return [title, Spacer(1, 1.2 * mm), info]

    def _build_header_info_strip(self, receta: Receta, cliente_name: str, today: str, show_client: bool = True) -> Table:
        producto_rows = [
            [self._icon("etiqueta", 5, 5), Paragraph("PRODUCTO", self.label_style)],
            ["", Paragraph((receta.nombre or "SIN NOMBRE").upper(), self.section_style)],
            ["", Spacer(1, 0.5 * mm)],
        ]
        if show_client:
            producto_rows.extend(
                [
                    [self._icon("usuario", 5, 5), Paragraph("CLIENTE", self.label_style)],
                    ["", Paragraph(cliente_name, self.value_style)],
                ]
            )
        producto = Table(
            producto_rows,
            colWidths=[8 * mm, 104 * mm],
        )
        producto.setStyle(self._compact_cell_style())

        users = Table(
            [
                [self._icon("reloj", 5, 5), Paragraph("CODIGO", self.label_style), Paragraph(str(receta.id or ""), self.value_style)],
                [self._icon("hoja", 5, 5), Paragraph("VERSION", self.label_style), Paragraph((receta.version or "1.0").strip(), self.value_style)],
                [self._icon("calendario", 5, 5), Paragraph("FECHA", self.label_style), Paragraph(today, self.value_style)],
                [self._icon("usuario", 5, 5), Paragraph("ELABORADO&nbsp;POR", self.label_style), Paragraph("", self.value_style)],
            ],
            colWidths=[8 * mm, 39 * mm, 27 * mm],
        )
        users.setStyle(self._compact_cell_style(padding=1.0))

        row = Table([[producto, users]], colWidths=[116 * mm, 74 * mm], hAlign="LEFT")
        row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEAFTER", (0, 0), (0, 0), 0.5, colors.HexColor("#D8D8D8")),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D8D8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        return row

    def _section_title(self, number: int, title: str, icon: str | None = None, total_width_mm: float = 95) -> Table:
        badge_size = 8 * mm
        badge = Drawing(badge_size, badge_size)
        badge.add(
            Circle(
                badge_size / 2,
                badge_size / 2,
                badge_size / 2 - 0.4,
                fillColor=colors.HexColor("#EBC4A1"),
                strokeColor=colors.HexColor("#DEA176"),
                strokeWidth=0.6,
            )
        )
        badge.add(
            String(
                badge_size / 2,
                badge_size / 2 - 3.2,
                str(number),
                fontName="Helvetica-Bold",
                fontSize=8.8,
                fillColor=colors.HexColor("#6C4B32"),
                textAnchor="middle",
            )
        )
        if icon:
            icon_cell = self._icon(icon, 6, 6)
            icon_col_w = 8
        else:
            icon_cell = Spacer(0, 6 * mm)
            icon_col_w = 0
        title_w = max(total_width_mm - (10 + icon_col_w), 20)
        t = Table([[badge, icon_cell, Paragraph(title, self.section_style)]], colWidths=[10 * mm, icon_col_w * mm, title_w * mm], hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return t

    def _build_ingredients_block(self, receta: Receta, lineas: list[RecetaLinea]) -> list:
        data = [[Paragraph("INGREDIENTE", self.label_style), Paragraph("% PANADERO", self.label_right_style), Paragraph("CANT. (g)", self.label_right_style)]]
        process_rows: list[int] = []
        for process_name, process_lines in self._group_lines_by_process(lineas):
            named_lines = [line for line in process_lines if str(getattr(line, "nombre_mostrado", "") or "").strip()]
            if not named_lines:
                continue
            process_rows.append(len(data))
            data.append(
                [
                    Paragraph(f"<b>{escape(process_name.upper())}</b>", self.label_style),
                    Paragraph("", self.body_right_style),
                    Paragraph("", self.body_right_style),
                ]
            )
            for line in named_lines:
                name = (line.nombre_mostrado or "").strip()
                data.append(
                    [
                        Paragraph(name, self.body_style),
                        Paragraph(f"{self._fmt(line.porcentaje_panadero, 2)} %", self.body_right_style),
                        Paragraph(f"{self._fmt(line.cantidad_base_g, 2)} g", self.body_right_style),
                    ]
                )

        data.append(
            [
                Paragraph("<b>TOTAL MASA</b>", self.label_style),
                Paragraph(f"<b>{self._fmt(receta.total_porcentaje_panadero, 2)} %</b>", self.label_right_style),
                Paragraph(f"<b>{self._fmt(receta.masa_total_g, 2)} g</b>", self.label_right_style),
            ]
        )

        table = Table(data, colWidths=[50 * mm, 24 * mm, 21 * mm], hAlign="LEFT")
        setattr(table, "_ireks_sync_key", "ingredients_main")
        styles = [
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E2E2")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFE9E2")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F7F3EE")),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ALIGN", (1, 0), (2, -1), "RIGHT"),
        ]
        for row_idx in process_rows:
            styles.append(("SPAN", (0, row_idx), (2, row_idx)))
            styles.append(("ALIGN", (0, row_idx), (2, row_idx), "LEFT"))
            styles.append(("BACKGROUND", (0, row_idx), (2, row_idx), colors.HexColor("#F2F4F7")))
        table.setStyle(TableStyle(styles))

        elab = self._json_to_dict(receta.parametros_elaboracion_json)
        temp_masa = str(elab.get("am1_temp", "") or "").strip() or "-"
        tiempo_total_min = sum(
            self._to_float(elab.get(key))
            for key in ("am1_lenta", "am1_rapida", "rep_bloque_1", "rep_bloque_2", "rep_fermentacion", "tiempo_coccion_coc")
        )
        rendimiento_kg = float(receta.masa_total_g or 0.0) / 1000.0

        hidratacion = self._kpi_card("gota", "HIDRATACION", f"{self._fmt(receta.hidratacion_pct, 2)}%", 23.75)
        temp = self._kpi_card("termometro", "TEMP. MASA", f"{temp_masa} C", 23.75)
        tiempo = self._kpi_card("reloj", "TIEMPO TOTAL", f"{self._fmt(tiempo_total_min, 0)} min", 23.75)
        rend = self._kpi_card("pan", "RENDIMIENTO", f"{self._fmt(rendimiento_kg, 2)} kg", 23.75)

        kpi = Table([[hidratacion, temp, tiempo, rend]], colWidths=[23.75 * mm, 23.75 * mm, 23.75 * mm, 23.75 * mm], hAlign="LEFT")
        kpi.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D2D2D2")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E8E8E8")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return [Spacer(1, 1.6 * mm), self._section_title(1, "INGREDIENTES", None), Spacer(1, 1 * mm), table, Spacer(1, 1 * mm), kpi]

    def _kpi_card(self, icon_name: str, label: str, value: str, width_mm: float) -> Table:
        text = Table(
            [
                [Paragraph(label, self.kpi_label_style)],
                [Paragraph(value, self.kpi_value_style)],
            ],
            colWidths=[width_mm * mm],
        )
        text.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        card = Table(
            [
                [self._icon(icon_name, 8.5, 8.5)],
                [Spacer(1, 0.4 * mm)],
                [text],
            ],
            colWidths=[width_mm * mm],
            hAlign="CENTER",
        )
        card.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return card

    def _build_process_block(
        self,
        elab_by_process: dict[str, dict[str, str]],
        include_title: bool = True,
        section_number: int = 2,
        section_title: str = "PROCESO DE ELABORACION",
    ) -> list:
        def val(elab: dict[str, str], key: str) -> str:
            raw = str(elab.get(key, "") or "").strip()
            return raw if raw else "-"

        def val_any(elab: dict[str, str], keys: tuple[str, ...]) -> str:
            for key in keys:
                raw = str(elab.get(key, "") or "").strip()
                if raw:
                    return raw
            return ""

        rows = []
        header_rows: list[int] = []
        process_items = list(elab_by_process.items()) if elab_by_process else [("Masa final", {})]
        for process_name, elab in process_items:
            header_rows.append(len(rows))
            rows.append(
                [
                    Paragraph(f"<b>{escape(process_name.upper())}</b>", self.label_style),
                    Paragraph("", self.body_style),
                ]
            )
            rows.extend(
                [
                    [
                        self._icon("amasadora", 9.5, 9.5),
                        Paragraph(
                            f"<b>1. AMASADO</b><br/>Tiempo: {val(elab, 'am1_lenta')} min (lento) + {val(elab, 'am1_rapida')} min (rapido)<br/>Temp. masa: {val(elab, 'am1_temp')} C",
                            self.body_style,
                        ),
                    ],
                    [
                        self._icon("bol", 9.5, 9.5),
                        Paragraph(
                            f"<b>2. REPOSOS</b><br/>Reposo en bloque: {val_any(elab, ('rep_bloque_1', 'am2_lenta'))} min<br/>Reposo en pieza: {val_any(elab, ('rep_bloque_2', 'am2_rapida'))} min",
                            self.body_style,
                        ),
                    ],
                    [
                        self._icon("fermentacion", 9.5, 9.5),
                        Paragraph(
                            f"<b>3. FERMENTACION</b><br/>Temperatura: {val_any(elab, ('fermentacion_temp', 'am2_temp'))} C<br/>Tiempo: {val_any(elab, ('rep_fermentacion', 'fermentacion', 'tiempo_fermentacion'))} min<br/>Humedad: {val(elab, 'fermentacion_humedad')} %",
                            self.body_style,
                        ),
                    ],
                    [
                        self._icon("horno", 9.5, 9.5),
                        Paragraph(
                            f"<b>4. COCCION</b><br/>Temp. inicial: {val(elab, 'precalentamiento_coc')} C<br/>Temp. coccion: {val(elab, 'temp_coccion_coc')} C<br/>Tiempo: {val(elab, 'tiempo_coccion_coc')} min<br/>Vapor: {val(elab, 'vapor_coc')}",
                            self.body_style,
                        ),
                    ],
                ]
            )
        table = Table(rows, colWidths=[12 * mm, 83 * mm], hAlign="LEFT")
        styles = [
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E3E3E3")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (0, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        for row_idx in header_rows:
            styles.append(("SPAN", (0, row_idx), (1, row_idx)))
            styles.append(("ALIGN", (0, row_idx), (1, row_idx), "LEFT"))
            styles.append(("BACKGROUND", (0, row_idx), (1, row_idx), colors.HexColor("#F2F4F7")))
        table.setStyle(TableStyle(styles))
        if include_title:
            return [Spacer(1, 1.6 * mm), self._section_title(section_number, section_title, None), Spacer(1, 1 * mm), table]
        return [table]

    def _build_cost_block(
        self,
        receta: Receta,
        lineas: list[RecetaLinea],
        esc: dict[str, str],
        piezas_elaboradas: float | None = None,
        include_kpi: bool = True,
        include_detail_kpis: bool = True,
        section_title: str = "COSTES / ESCANDALLO",
        section_number: int = 3,
    ) -> list:
        data = [[
            Paragraph("INGREDIENTE", self.label_style),
            Paragraph("CANT.&nbsp;(g)", self.label_right_style),
            Paragraph("€/kg", self.label_right_style),
            Paragraph("COSTE&nbsp;(€)", self.label_right_style),
        ]]
        total_coste = 0.0
        process_header_rows: list[int] = []
        process_subtotal_rows: list[int] = []

        for process_name, process_lines in self._group_lines_by_process(lineas):
            named_lines = [line for line in process_lines if str(getattr(line, "nombre_mostrado", "") or "").strip()]
            if not named_lines:
                continue

            process_header_rows.append(len(data))
            data.append(
                [
                    Paragraph(f"<b>{escape(process_name.upper())}</b>", self.label_style),
                    Paragraph("", self.body_right_style),
                    Paragraph("", self.body_right_style),
                    Paragraph("", self.body_right_style),
                ]
            )

            process_total = 0.0
            for line in named_lines:
                name = (line.nombre_mostrado or "").strip()
                eur_kg = float(line.precio_kg_snapshot or 0.0)
                coste = (float(line.cantidad_base_g or 0.0) / 1000.0) * eur_kg
                total_coste += coste
                process_total += coste
                data.append(
                    [
                        Paragraph(name, self.body_style),
                        Paragraph(f"{self._fmt(line.cantidad_base_g, 2)} g", self.body_right_style),
                        Paragraph(f"{self._fmt(eur_kg, 2)} €", self.body_right_style),
                        Paragraph(f"{self._fmt(coste, 2)} €", self.body_right_style),
                    ]
                )

            process_subtotal_rows.append(len(data))
            data.append(
                [
                    Paragraph(f"<b>Subtotal {escape(process_name)}</b>", self.label_right_style),
                    Paragraph("", self.body_right_style),
                    Paragraph("", self.body_right_style),
                    Paragraph(f"<b>{self._fmt(process_total, 2)} €</b>", self.label_right_style),
                ]
            )

        data.append(
            [
                Paragraph("<b>COSTE TOTAL MASA</b>", self.label_right_style),
                Paragraph("", self.body_right_style),
                Paragraph("", self.body_right_style),
                Paragraph(f"<b>{self._fmt(total_coste, 2)} €</b>", self.label_right_style),
            ]
        )

        # Keep total width at 94 mm, but widen right headers to avoid wraps that break row alignment.
        table = Table(data, colWidths=[43 * mm, 19 * mm, 12 * mm, 20 * mm], hAlign="LEFT")
        setattr(table, "_ireks_sync_key", "costs_main")
        styles = [
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E2E2")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFE9E2")),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F7F3EE")),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (3, -1), "RIGHT"),
            ("SPAN", (0, -1), (2, -1)),
            ("ALIGN", (0, -1), (2, -1), "LEFT"),
            ("VALIGN", (0, -1), (-1, -1), "MIDDLE"),
        ]
        for row_idx in process_header_rows:
            styles.append(("SPAN", (0, row_idx), (3, row_idx)))
            styles.append(("ALIGN", (0, row_idx), (3, row_idx), "LEFT"))
            styles.append(("BACKGROUND", (0, row_idx), (3, row_idx), colors.HexColor("#F2F4F7")))
        for row_idx in process_subtotal_rows:
            styles.append(("SPAN", (0, row_idx), (2, row_idx)))
            styles.append(("ALIGN", (0, row_idx), (2, row_idx), "LEFT"))
            styles.append(("BACKGROUND", (0, row_idx), (3, row_idx), colors.HexColor("#FAFAFA")))
            styles.append(("VALIGN", (0, row_idx), (3, row_idx), "MIDDLE"))
        table.setStyle(TableStyle(styles))

        precio_venta = self._to_float(esc.get("precio_venta"))
        igic_pct = self._to_float(esc.get("igic"))
        rendimiento = float(piezas_elaboradas or 0.0)
        if rendimiento <= 0:
            rendimiento = float(receta.numero_piezas or 0.0)
        costes_fijos = self._to_float(esc.get("costes_fijos"))
        costes_variables = self._to_float(esc.get("costes_variables"))
        otros_costes = self._to_float(esc.get("otros_costes"))
        total_costes = total_coste + costes_fijos + costes_variables + otros_costes
        coste_pieza = (total_coste / rendimiento) if rendimiento > 0 else 0.0
        margen = ((precio_venta - coste_pieza) / precio_venta * 100.0) if precio_venta > 0 else 0.0
        coste_unitario = (total_costes / rendimiento) if rendimiento > 0 else 0.0
        calc_igic = precio_venta * igic_pct / 100.0
        precio_neto = precio_venta + calc_igic
        coste_mp_unitario = (total_coste / rendimiento) if rendimiento > 0 else 0.0
        pct_coste_mp = (coste_mp_unitario / precio_venta * 100.0) if precio_venta > 0 else 0.0
        pct_margen_pv = ((precio_venta - coste_unitario) / precio_venta * 100.0) if precio_venta > 0 else 0.0

        kpi = Table(
            [[
                self._kpi_card("monedas", "COSTE POR PIEZA", f"{self._fmt(coste_pieza, 2)} €", 31.5),
                self._kpi_card("etiqueta", "PVP RECOMENDADO", f"{self._fmt(precio_venta, 2)} €", 31.5),
                self._kpi_card("pastel", "MARGEN ESTIMADO", f"{self._fmt(margen, 2)}%", 32),
            ]],
            colWidths=[31.5 * mm, 31.5 * mm, 32 * mm],
            hAlign="LEFT",
        )
        kpi.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D2D2D2")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E8E8E8")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        block = [self._section_title(section_number, section_title, None), Spacer(1, 1 * mm), table]
        if include_kpi:
            detail_kpis = self._build_cost_detail_kpis(
                coste_mp=total_coste,
                costes_fijos=costes_fijos,
                costes_variables=costes_variables,
                otros_costes=otros_costes,
                total_costes=total_costes,
                unidades_totales=rendimiento,
                coste_unitario=coste_unitario,
                precio_venta=precio_venta,
                igic_pct=igic_pct,
                calc_igic=calc_igic,
                precio_neto=precio_neto,
                pct_coste_mp=pct_coste_mp,
                pct_margen_pv=pct_margen_pv,
            )
            block.extend([Spacer(1, 1 * mm), kpi])
            if include_detail_kpis:
                block.extend(
                    [
                        Spacer(1, 1 * mm),
                        *detail_kpis["costes_produccion"],
                        Spacer(1, 1.6 * mm),
                        *detail_kpis["costes_unidad"],
                        Spacer(1, 1.6 * mm),
                        *detail_kpis["precios_margenes"],
                    ]
                )
        return block

    def _build_cost_detail_kpis(
        self,
        *,
        coste_mp: float,
        costes_fijos: float,
        costes_variables: float,
        otros_costes: float,
        total_costes: float,
        unidades_totales: float,
        coste_unitario: float,
        precio_venta: float,
        igic_pct: float,
        calc_igic: float,
        precio_neto: float,
        pct_coste_mp: float,
        pct_margen_pv: float,
    ) -> dict[str, list]:
        panel_costes_produccion = self._build_kpi_panel_table(
            [
                ("Coste materias primas", f"{self._fmt(coste_mp, 2)} €", ""),
                ("Costes fijos", f"{self._fmt(costes_fijos, 2)} €", ""),
                ("Costes variables", f"{self._fmt(costes_variables, 2)} €", ""),
                ("Otros costes", f"{self._fmt(otros_costes, 2)} €", ""),
                ("Total costes", f"{self._fmt(total_costes, 2)} €", "danger"),
            ],
        )
        panel_costes_unidad = self._build_kpi_panel_table(
            [
                ("Nº de piezas", f"{self._fmt(unidades_totales, 0)} Uds", ""),
                ("<b>Coste unitario</b>", f"<b>{self._fmt(coste_unitario, 2)} €</b>", "danger"),
            ],
        )
        panel_precios_margenes = self._build_kpi_panel_table(
            [
                ("Precio de venta", f"{self._fmt(precio_venta, 2)} €", ""),
                (f"IGIC % - {self._fmt(igic_pct, 0)}%", f"{self._fmt(calc_igic, 2)} €", ""),
                ("Precio neto", f"{self._fmt(precio_neto, 2)} €", ""),
                ("% Coste de Materia Primas", f"{self._fmt(pct_coste_mp, 2)} %", "danger"),
                ("% Margen sobre PV", f"{self._fmt(pct_margen_pv, 2)} %", "good"),
            ],
        )
        return {
            "costes_produccion": [
                self._section_title(3, "COSTES DE PRODUCCION", None),
                Spacer(1, 1 * mm),
                panel_costes_produccion,
            ],
            "costes_unidad": [
                self._section_title(4, "COSTES POR UNIDAD", None),
                Spacer(1, 1 * mm),
                panel_costes_unidad,
            ],
            "precios_margenes": [
                self._section_title(5, "PRECIOS Y MARGENES", None),
                Spacer(1, 1 * mm),
                panel_precios_margenes,
            ],
        }

    def _build_kpi_panel_table(self, rows: list[tuple[str, str, str]]) -> Table:
        data = []
        for label, value, kind in rows:
            data.append([Paragraph(label, self.small_style), Paragraph(value, self.body_right_style)])
        panel = Table(data, colWidths=[60 * mm, 34 * mm], hAlign="LEFT")
        styles = [
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E3E3E3")),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for idx, (_label, _value, kind) in enumerate(rows, start=0):
            if kind in {"danger", "good"}:
                styles.append(("BACKGROUND", (0, idx), (1, idx), colors.HexColor("#F7F3EE")))
                styles.append(("FONTNAME", (0, idx), (1, idx), "Helvetica-Bold"))
        panel.setStyle(TableStyle(styles))
        return panel

    def _build_production_block(
        self,
        receta: Receta,
        masa_total: float,
        peso_pieza: float,
        piezas: float,
        section_number: int = 4,
        section_title: str = "DATOS DE PRODUCCION",
        top_offset_mm: float = 1.6,
    ) -> list:
        rows = [
            [Paragraph("Peso total de la masa", self.body_style), Paragraph(f"{self._fmt(masa_total, 2)} g", self.body_right_style)],
            [Paragraph("Nº de piezas", self.body_style), Paragraph(f"{self._fmt(piezas, 0)} uds", self.body_right_style)],
            [Paragraph("Peso por unidad", self.body_style), Paragraph(f"{self._fmt(peso_pieza, 2)} g", self.body_right_style)],
            [Paragraph("Merma estimada", self.body_style), Paragraph(f"{self._fmt(receta.merma_pct, 2)}%", self.body_right_style)],
        ]
        table = Table(rows, colWidths=[54 * mm, 41 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E3E3E3")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ]
            )
        )
        blocks: list = []
        if top_offset_mm > 0:
            blocks.append(Spacer(1, top_offset_mm * mm))
        blocks.extend([self._section_title(section_number, section_title, None), Spacer(1, 1 * mm), table])
        return blocks

    def _build_observations_block(
        self,
        receta: Receta,
        section_number: int = 5,
        section_title: str = "OBSERVACIONES",
        width_mm: float = 95,
        min_total_height_pt: float | None = None,
    ) -> list:
        lines = [x.strip() for x in (receta.observaciones or "").splitlines() if x.strip()]
        if not lines:
            lines = ["Sin observaciones."]
        text = "<br/>".join(f"- {line}" for line in lines)
        title = self._section_title(section_number, section_title, None, total_width_mm=width_mm)
        box = Table([[Paragraph(text, self.body_style)]], colWidths=[width_mm * mm], hAlign="LEFT")
        box.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        if min_total_height_pt and min_total_height_pt > 0:
            natural_total = self._flowable_height(title, width_mm) + self._flowable_height(Spacer(1, 1 * mm), width_mm) + self._flowable_height(box, width_mm)
            if natural_total < min_total_height_pt:
                extra = min_total_height_pt - natural_total
                min_box_h = self._flowable_height(box, width_mm) + extra
                stretched_box = Table([[Paragraph(text, self.body_style)]], colWidths=[width_mm * mm], rowHeights=[min_box_h], hAlign="LEFT")
                stretched_box.setStyle(
                    TableStyle(
                        [
                            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
                        ]
                    )
                )
                box = stretched_box
        return [title, Spacer(1, 1 * mm), box]

    def _build_nutrition_block(
        self,
        receta: Receta,
        lineas: list[RecetaLinea],
        section_number: int = 5,
        section_title: str = "VALORES NUTRICIONALES",
        width_mm: float = 95,
    ) -> list:
        values = self._compute_recipe_nutrition_per_100(receta, lineas)
        rows = [
            ("Valor energético", f"{self._fmt(values['energia_kj'], 2)} kJ / {self._fmt(values['energia_kcal'], 2)} kcal"),
            ("Grasas", f"{self._fmt(values['grasas_g'], 2)} g"),
            ("&nbsp;&nbsp;&nbsp;de las cuales saturadas", f"{self._fmt(values['saturadas_g'], 2)} g"),
            ("Hidratos de carbono", f"{self._fmt(values['hidratos_g'], 2)} g"),
            ("&nbsp;&nbsp;&nbsp;de los cuales azúcares", f"{self._fmt(values['azucares_g'], 2)} g"),
            ("Fibra alimentaria", f"{self._fmt(values['fibra_g'], 2)} g"),
            ("Proteínas", f"{self._fmt(values['proteinas_g'], 2)} g"),
            ("Sal", f"{self._fmt(values['sal_g'], 2)} g"),
        ]
        data = [[Paragraph("<b>Información nutricional Por 100 g</b>", self.small_style), ""]]
        data.extend([[Paragraph(lbl, self.small_style), Paragraph(val, self.body_right_style)] for lbl, val in rows])
        table = Table(data, colWidths=[58 * mm, 37 * mm], hAlign="LEFT")
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E3E3E3")),
                    ("SPAN", (0, 0), (1, 0)),
                    ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#EFE9E2")),
                    ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (1, 0), colors.HexColor("#2F3A4A")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return [self._section_title(section_number, section_title, None, total_width_mm=width_mm), Spacer(1, 1 * mm), table]

    def _compute_recipe_nutrition_per_100(self, receta: Receta, lineas: list[RecetaLinea]) -> dict[str, float]:
        totals = {
            "energia_kj": 0.0,
            "energia_kcal": 0.0,
            "grasas_g": 0.0,
            "saturadas_g": 0.0,
            "hidratos_g": 0.0,
            "azucares_g": 0.0,
            "fibra_g": 0.0,
            "proteinas_g": 0.0,
            "sal_g": 0.0,
        }
        valid_lines: list[RecetaLinea] = []
        ireks_codes: set[str] = set()
        std_codes: set[str] = set()
        unknown_codes: set[str] = set()
        ireks_names: set[str] = set()
        std_names: set[str] = set()
        for line in lineas:
            if str(getattr(line, "tipo_linea", "ingrediente") or "ingrediente").strip().lower() != "ingrediente":
                continue
            cantidad = float(getattr(line, "cantidad_base_g", 0.0) or 0.0)
            if cantidad <= 0:
                continue
            code = str(getattr(line, "codigo_ingrediente", "") or "").strip()
            name = str(getattr(line, "nombre_mostrado", "") or "").strip()
            if not code and not name:
                continue
            valid_lines.append(line)
            source = str(getattr(line, "tipo_origen", "") or "").strip().lower()
            if source == "ireks":
                if code:
                    ireks_codes.add(code)
                if name:
                    ireks_names.add(name)
            elif source == "std":
                if code:
                    std_codes.add(code)
                if name:
                    std_names.add(name)
            else:
                if code:
                    unknown_codes.add(code)

        if not valid_lines:
            return totals

        masa_total_g = float(getattr(receta, "masa_total_g", 0.0) or 0.0)
        if masa_total_g <= 0:
            masa_total_g = sum(float(getattr(line, "cantidad_base_g", 0.0) or 0.0) for line in valid_lines)
        if masa_total_g <= 0:
            return totals

        ireks_by_code: dict[str, str] = {}
        std_by_code: dict[str, str] = {}
        nutrition_by_articulo: dict[str, MateriaPrimaValorNutricional] = {}
        with Session(engine) as session:
            all_ireks_codes = set(ireks_codes) | set(unknown_codes)
            if all_ireks_codes:
                rows = list(
                    session.exec(
                        select(IngredienteIreks).where(
                            func.lower(cast(Any, IngredienteIreks.articulo_referencia)).in_(
                                {code.lower() for code in all_ireks_codes}
                            )
                        )
                    )
                )
                ireks_by_code = {
                    str(getattr(row, "articulo_referencia", "") or "").strip().lower(): str(getattr(row, "articulo_id", "") or "").strip()
                    for row in rows
                    if str(getattr(row, "articulo_referencia", "") or "").strip()
                    and str(getattr(row, "articulo_id", "") or "").strip()
                }
            if ireks_names:
                rows = list(
                    session.exec(
                        select(IngredienteIreks).where(
                            func.lower(cast(Any, IngredienteIreks.articulo_descripcion)).in_(
                                {name.lower() for name in ireks_names}
                            )
                        )
                    )
                )
                for row in rows:
                    name_key = str(getattr(row, "articulo_descripcion", "") or "").strip().lower()
                    articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
                    if name_key and articulo_id and name_key not in ireks_by_code:
                        ireks_by_code[name_key] = articulo_id

            all_std_codes = set(std_codes) | set(unknown_codes)
            if all_std_codes:
                rows = list(
                    session.exec(
                        select(IngredienteStd).where(
                            func.lower(cast(Any, IngredienteStd.articulo_referencia_distribuidor)).in_(
                                {code.lower() for code in all_std_codes}
                            )
                        )
                    )
                )
                std_by_code = {
                    str(getattr(row, "articulo_referencia_distribuidor", "") or "").strip().lower(): str(getattr(row, "articulo_id", "") or "").strip()
                    for row in rows
                    if str(getattr(row, "articulo_referencia_distribuidor", "") or "").strip()
                    and str(getattr(row, "articulo_id", "") or "").strip()
                }
            if std_names:
                rows = list(
                    session.exec(
                        select(IngredienteStd).where(
                            func.lower(cast(Any, IngredienteStd.articulo_descripcion)).in_(
                                {name.lower() for name in std_names}
                            )
                        )
                    )
                )
                for row in rows:
                    name_key = str(getattr(row, "articulo_descripcion", "") or "").strip().lower()
                    articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
                    if name_key and articulo_id and name_key not in std_by_code:
                        std_by_code[name_key] = articulo_id

            articulo_ids: set[str] = set()
            for line in valid_lines:
                source = str(getattr(line, "tipo_origen", "") or "").strip().lower()
                code = str(getattr(line, "codigo_ingrediente", "") or "").strip().lower()
                name = str(getattr(line, "nombre_mostrado", "") or "").strip().lower()
                aid = ""
                if source == "ireks":
                    aid = ireks_by_code.get(code, "") or ireks_by_code.get(name, "")
                elif source == "std":
                    aid = std_by_code.get(code, "") or std_by_code.get(name, "")
                else:
                    aid = (
                        ireks_by_code.get(code, "")
                        or std_by_code.get(code, "")
                        or ireks_by_code.get(name, "")
                        or std_by_code.get(name, "")
                    )
                if aid:
                    articulo_ids.add(aid)

            if articulo_ids:
                nutrition_rows = list(
                    session.exec(
                        select(MateriaPrimaValorNutricional).where(cast(Any, MateriaPrimaValorNutricional.articulo_id).in_(articulo_ids))
                    )
                )
                nutrition_by_articulo = {
                    str(getattr(row, "articulo_id", "") or "").strip(): row
                    for row in nutrition_rows
                    if str(getattr(row, "articulo_id", "") or "").strip()
                }

        for line in valid_lines:
            source = str(getattr(line, "tipo_origen", "") or "").strip().lower()
            code = str(getattr(line, "codigo_ingrediente", "") or "").strip().lower()
            name = str(getattr(line, "nombre_mostrado", "") or "").strip().lower()
            aid = ""
            if source == "ireks":
                aid = ireks_by_code.get(code, "") or ireks_by_code.get(name, "")
            elif source == "std":
                aid = std_by_code.get(code, "") or std_by_code.get(name, "")
            else:
                aid = (
                    ireks_by_code.get(code, "")
                    or std_by_code.get(code, "")
                    or ireks_by_code.get(name, "")
                    or std_by_code.get(name, "")
                )
            if not aid:
                continue
            nutrition = nutrition_by_articulo.get(aid)
            if nutrition is None:
                continue
            cantidad_g = float(getattr(line, "cantidad_base_g", 0.0) or 0.0)
            factor = cantidad_g / 100.0
            totals["energia_kj"] += float(getattr(nutrition, "energia_kj", 0.0) or 0.0) * factor
            totals["energia_kcal"] += float(getattr(nutrition, "energia_kcal", 0.0) or 0.0) * factor
            totals["grasas_g"] += float(getattr(nutrition, "grasas_g", 0.0) or 0.0) * factor
            totals["saturadas_g"] += float(getattr(nutrition, "saturadas_g", 0.0) or 0.0) * factor
            totals["hidratos_g"] += float(getattr(nutrition, "hidratos_g", 0.0) or 0.0) * factor
            totals["azucares_g"] += float(getattr(nutrition, "azucares_g", 0.0) or 0.0) * factor
            totals["fibra_g"] += float(getattr(nutrition, "fibra_g", 0.0) or 0.0) * factor
            totals["proteinas_g"] += float(getattr(nutrition, "proteinas_g", 0.0) or 0.0) * factor
            totals["sal_g"] += float(getattr(nutrition, "sal_g", 0.0) or 0.0) * factor

        return {k: (v * 100.0 / masa_total_g) for k, v in totals.items()}

    def _build_proceso_text_block(
        self,
        receta: Receta,
        lineas: list[RecetaLinea],
        width_mm: float = 95,
        min_height_pt: float | None = None,
    ) -> list:
        grouped = self._group_lines_by_process(lineas)
        process_names = [name for name, _items in grouped]
        section_map = self._parse_process_sections((receta.proceso or "").strip(), process_names)
        if not section_map:
            section_map = {"Masa final": "Sin proceso."}

        chunks: list[str] = []
        for name in process_names:
            body = (section_map.get(name) or "").strip()
            if not body and len(process_names) > 1:
                body = "Sin descripciÃ³n especÃ­fica."
            elif not body:
                body = "Sin proceso."
            escaped_body_lines = [escape(line.strip()) for line in body.splitlines() if line.strip()]
            escaped_body = "<br/>".join(escaped_body_lines) if escaped_body_lines else "Sin proceso."
            chunks.append(f"<b>{escape(name)}</b><br/>{escaped_body}")
        text = "<br/><br/>".join(chunks) if chunks else "Sin proceso."
        paragraph = Paragraph(text, self.body_style)
        natural_box = Table([[paragraph]], colWidths=[width_mm * mm], hAlign="LEFT")
        natural_box.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        natural_box.wrap(width_mm * mm, 10000 * mm)
        natural_height = float((getattr(natural_box, "_rowHeights", [0.0]) or [0.0])[0] or 0.0)
        row_height = max(natural_height, float(min_height_pt or 0.0))
        box = Table([[paragraph]], colWidths=[width_mm * mm], rowHeights=[row_height], hAlign="LEFT")
        box.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return [box]

    def _build_proceso_kpi(self, receta: Receta) -> list:
        raw = (receta.proceso or "").strip()
        if not raw:
            raw = "Sin proceso."
        lines = [escape(line.strip()) for line in raw.splitlines() if line.strip()]
        if not lines:
            lines = ["Sin proceso."]
        text = "<br/>".join(lines)
        title = self._section_title(2, "PROCESO DE ELABORACION", None, total_width_mm=196)
        box = Table([[Paragraph(text, self.body_style)]], colWidths=[196 * mm], hAlign="LEFT")
        box.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBCBCB")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        return [title, Spacer(1, 1 * mm), box]

    def _build_footer(self) -> list:
        notes = Table(
            [
                [Paragraph("<b>NOTAS</b>", self.small_style)],
                [Paragraph(" ", self.small_style)],
                [Paragraph(" ", self.small_style)],
            ],
            colWidths=[94 * mm],
            rowHeights=[8 * mm, 7 * mm, 7 * mm],
            hAlign="LEFT",
        )
        notes.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                    ("LINEBELOW", (0, 1), (0, 1), 0.8, colors.HexColor("#626262")),
                    ("LINEBELOW", (0, 2), (0, 2), 0.8, colors.HexColor("#626262")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        sign = Table(
            [[Paragraph("<b>FIRMA</b>", self.small_style)]],
            colWidths=[94 * mm],
            rowHeights=[22 * mm],
            hAlign="LEFT",
        )
        sign.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D0D0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        row = Table([[notes, sign]], colWidths=[94 * mm, 94 * mm], hAlign="LEFT")
        row.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm),
                    ("LEFTPADDING", (1, 0), (1, 0), 4 * mm),
                    ("RIGHTPADDING", (1, 0), (1, 0), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return [row]

    def _compact_cell_style(self, padding: float = 0) -> TableStyle:
        return TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), padding),
                ("RIGHTPADDING", (0, 0), (-1, -1), padding),
                ("TOPPADDING", (0, 0), (-1, -1), padding),
                ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ]
        )

    def _draw_page_bg(self, canvas, _doc) -> None:
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#FCFCFC"))
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    def _icon(self, name: str | None, width_mm: float, height_mm: float | None = None):
        if not name:
            return Spacer(width_mm * mm, (height_mm or width_mm) * mm)
        filename = self.icon_map.get(name)
        if not filename:
            return Spacer(width_mm * mm, (height_mm or width_mm) * mm)
        path = self.icons_dir / filename
        if not path.exists():
            return Spacer(width_mm * mm, (height_mm or width_mm) * mm)
        h = height_mm if height_mm is not None else width_mm
        return RLImage(str(path), width=width_mm * mm, height=h * mm)

    def _load_recipe_data(self, recipe_id: int) -> tuple[Receta | None, Cliente | None, list[RecetaLinea]]:
        with Session(engine) as session:
            receta = session.get(Receta, recipe_id)
            if not receta:
                return None, None, []
            cliente = session.get(Cliente, receta.cliente_id)
            lineas = list(
                session.exec(
                    select(RecetaLinea).where(RecetaLinea.receta_id == recipe_id).order_by(col(RecetaLinea.orden))
                )
            )
        return receta, cliente, lineas

    def _json_to_dict(self, raw: str) -> dict[str, str]:
        text = (raw or "").strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(k): str(v) for k, v in payload.items()}

    def _to_float(self, value: str | None) -> float:
        raw = (value or "").strip().replace("€", "").replace("%", "").replace("EUR", "").strip()
        if not raw:
            return 0.0
        normalized = raw.replace(".", "").replace(",", ".")
        try:
            return float(normalized)
        except Exception:
            return 0.0

    def _fmt(self, value: float | int | None, decimals: int = 2) -> str:
        number = float(value or 0.0)
        text = f"{number:,.{decimals}f}"
        return text.replace(",", "_").replace(".", ",").replace("_", ".")


