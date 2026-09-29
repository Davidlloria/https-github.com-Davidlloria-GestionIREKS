from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from app.services.document_content_index_service import (
    DocumentContentIndexService,
    DocumentContentSearchResult,
)
from app.services.document_library_service import DocumentLibraryService
from app.viewmodels import IngredientChoice


IngredientSearch = Callable[[str], list[IngredientChoice]]


@dataclass(frozen=True)
class RecipeDocumentLineDraft:
    source_name: str
    quantity_g: float
    source_quantity: str
    process_name: str
    matched_ingredient: IngredientChoice | None = None
    notes: str = ""
    source_process: str = ""

    @property
    def is_resolved(self) -> bool:
        return self.matched_ingredient is not None or bool(self.source_process)


@dataclass(frozen=True)
class RecipeDocumentDraft:
    document_id: str
    document_name: str
    relative_path: str
    page_number: int
    recipe_name: str
    process_text: str
    number_of_pieces: int
    lines: tuple[RecipeDocumentLineDraft, ...]
    warnings: tuple[str, ...] = ()

    @property
    def unresolved_count(self) -> int:
        return sum(not line.is_resolved for line in self.lines)


class RecipeDocumentImportService:
    """Search and parse recipe documents without writing application data."""

    _QUANTITY_RE = re.compile(
        r"^\s*(?P<number>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|kgs|g|gr|l|ml|ud|uds|unidad|unidades)\.?\s*$",
        re.IGNORECASE,
    )
    _PIECES_RE = re.compile(r"\b(?:para\s+)?(\d+)\s+(?:unidades|uds?\.?|piezas)\b", re.IGNORECASE)
    _PROCESS_PREFIXES = (
        "masa",
        "mezcla",
        "relleno",
        "crema",
        "compota",
        "cobertura",
        "decoracion",
        "acabado",
        "glaseado",
        "bano",
        "topping",
        "fermento",
        "esponja",
        "poolish",
        "remojo",
    )
    _REVIEW_ASSOCIATION_NOTE = "Revisar asociación con el catálogo de ingredientes"

    def __init__(
        self,
        *,
        library_service: DocumentLibraryService | None = None,
        content_service: DocumentContentIndexService | None = None,
        ingredient_search: IngredientSearch | None = None,
    ) -> None:
        self.library_service = library_service or DocumentLibraryService()
        self.content_service = content_service or DocumentContentIndexService(self.library_service)
        self.ingredient_search = ingredient_search or (lambda _term: [])

    def refresh_documents(self) -> str:
        """Discover new files and incrementally index only recipe PDFs."""
        scan = self.library_service.refresh_catalog()
        if not scan.available or not scan.scan_complete:
            detail = "; ".join(scan.errors) or "La carpeta de documentos no está disponible."
            raise RuntimeError(detail)
        documents = self.browse_documents()
        result = self.content_service.update_index(document_ids={item.document_id for item in documents})
        warnings = list(scan.errors) + list(result.errors)
        if result.no_text:
            warnings.append(f"{result.no_text} PDF sin texto extraíble; están disponibles en Explorar carpetas.")
        return "\n".join(warnings)

    def search(self, query: str, *, limit: int = 50) -> list[DocumentContentSearchResult]:
        return self.content_service.search(
            query,
            area="TECNICO",
            category_prefix="RECETAS",
            limit=limit,
        )

    def browse_documents(self) -> list[DocumentContentSearchResult]:
        """List catalogued recipe PDFs without requiring indexed text."""
        results = []
        for item in self.library_service.list_documents(area="TECNICO", extension=".pdf", active=True):
            parts = Path(item.relative_path).parts
            if len(parts) < 3 or tuple(part.casefold() for part in parts[:2]) != ("tecnico", "recetas"):
                continue
            results.append(DocumentContentSearchResult(
                document_id=item.document_id, name=item.name, relative_path=item.relative_path,
                area=item.area, category=item.category, page_number=1,
                fragment="Seleccionado por carpetas", score=0.0,
            ))
        return sorted(results, key=lambda item: item.relative_path.casefold())

    def search_raw_materials(self, query: str) -> list[IngredientChoice]:
        return [
            ingredient
            for ingredient in self.ingredient_search(str(query or "").strip())
            if ingredient.tipo_origen == "std"
        ]

    def apply_raw_material_match(
        self,
        draft: RecipeDocumentDraft,
        line_index: int,
        ingredient: IngredientChoice,
    ) -> RecipeDocumentDraft:
        if ingredient.tipo_origen != "std":
            raise ValueError("La selección debe proceder de Materias primas.")
        if line_index < 0 or line_index >= len(draft.lines):
            raise IndexError("La línea seleccionada no existe.")
        lines = list(draft.lines)
        source_line = lines[line_index]
        notes = "; ".join(
            note.strip()
            for note in source_line.notes.split(";")
            if note.strip() and note.strip() != self._REVIEW_ASSOCIATION_NOTE
        )
        lines[line_index] = replace(
            source_line,
            matched_ingredient=ingredient,
            notes=notes,
        )
        warnings = [
            warning
            for warning in draft.warnings
            if not re.fullmatch(r"\d+ ingrediente\(s\) necesitan revisión manual\.", warning)
        ]
        unresolved = sum(not line.is_resolved for line in lines)
        if unresolved:
            warnings.append(f"{unresolved} ingrediente(s) necesitan revisión manual.")
        return replace(draft, lines=tuple(lines), warnings=tuple(warnings))

    def build_draft(
        self,
        result: DocumentContentSearchResult,
        *,
        page_number: int | None = None,
    ) -> RecipeDocumentDraft:
        target_page = max(1, int(page_number or result.page_number))
        page_text = self.content_service.get_page_text(result.document_id, target_page) or ""
        draft = self.parse_page(
            page_text,
            document_id=result.document_id,
            document_name=result.name,
            relative_path=result.relative_path,
            page_number=target_page,
        )

        if draft.lines and not draft.process_text:
            # Recipe sheets often put the instructions on the following page.
            # Require the heading at its start to avoid absorbing another recipe.
            following_text = self.content_service.get_page_text(result.document_id, target_page + 1) or ""
            following_rows = [self._clean_line(row) for row in following_text.splitlines() if row.strip()]
            if following_rows and self._is_process_marker(following_rows[0]):
                instructions = self._format_process_steps(following_rows[1:])
                if instructions:
                    draft = replace(draft, process_text=instructions, warnings=draft.warnings + (
                        f"Proceso de elaboración tomado de la página {target_page + 1} del documento.",
                    ))

        if not page_text.strip():
            draft = replace(draft, warnings=draft.warnings + (
                "Esta página no tiene texto indexado disponible. Puedes consultar el PDF, pero no extraer una fórmula de esta página.",
            ))
        return draft

    def resolve_document(self, document_id: str) -> Path:
        return self.library_service.resolve_document(document_id)

    def parse_page(
        self,
        page_text: str,
        *,
        document_id: str,
        document_name: str,
        relative_path: str,
        page_number: int,
    ) -> RecipeDocumentDraft:
        rows = [self._clean_line(line) for line in str(page_text or "").splitlines()]
        rows = [line for line in rows if line]
        recipe_name = self._recipe_name(rows, document_name)
        number_of_pieces = self._number_of_pieces(rows)
        process_start = next(
            (index for index, line in enumerate(rows) if self._is_process_marker(line)),
            len(rows),
        )
        ingredient_rows = rows[:process_start]
        process_rows = rows[process_start + 1 :] if process_start < len(rows) else []
        process_text = self._format_process_steps(process_rows)

        lines: list[RecipeDocumentLineDraft] = []
        warnings: list[str] = []
        current_process = "Masa final"
        headings_seen: dict[str, str] = {}
        previous_quantity_index = -1
        for index, raw_quantity in enumerate(ingredient_rows):
            parsed_quantity = self._parse_quantity(raw_quantity)
            if parsed_quantity is None or index <= 0:
                continue
            source_name = ingredient_rows[index - 1]
            if self._normalized(source_name) == "total":
                previous_quantity_index = index
                continue
            between = ingredient_rows[previous_quantity_index + 1 : index - 1]
            headings = [line for line in between if self._is_process_heading(line)]
            if headings:
                current_process = self._process_name(headings[-1])
                headings_seen[self._normalized(headings[-1])] = current_process
            quantity_g, quantity_note = parsed_quantity
            matched = self._match_ingredient(source_name)
            notes = quantity_note
            if matched is None:
                notes = self._join_notes(notes, self._REVIEW_ASSOCIATION_NOTE)
            lines.append(
                RecipeDocumentLineDraft(
                    source_name=source_name,
                    quantity_g=quantity_g,
                    source_quantity=raw_quantity,
                    process_name=current_process,
                    matched_ingredient=matched,
                    notes=notes,
                )
            )
            previous_quantity_index = index

        # A final assembly can refer to previously prepared mixtures by name.
        references = {self._normalized(line.source_name) for line in lines} & headings_seen.keys()
        if "masa" in references:
            lines = [replace(line, process_name="Masa" if line.process_name == "Masa final" else line.process_name)
                     for line in lines]
            headings_seen["masa"] = "Masa"
        lines = [replace(line, process_name="Masa final", source_process=headings_seen[self._normalized(line.source_name)],
                         matched_ingredient=None, notes="Preparación incorporada a la masa final")
                 if self._normalized(line.source_name) in references else line for line in lines]

        inline_quantities = [
            line
            for line in ingredient_rows
            if ":" in line and re.search(r"\d+(?:[.,]\d+)?\s*(?:kg|g|ml|l)\b", line, re.IGNORECASE)
        ]
        if inline_quantities:
            warnings.append(
                "Hay cantidades incluidas dentro de frases; deben revisarse en el documento original."
            )
        if not lines:
            warnings.append("No se detectaron líneas de ingredientes en esta página.")
        unresolved = sum(not line.is_resolved for line in lines)
        if unresolved:
            warnings.append(f"{unresolved} ingrediente(s) necesitan revisión manual.")

        return RecipeDocumentDraft(
            document_id=str(document_id),
            document_name=str(document_name),
            relative_path=str(relative_path),
            page_number=max(1, int(page_number)),
            recipe_name=recipe_name,
            process_text=process_text,
            number_of_pieces=number_of_pieces,
            lines=tuple(lines),
            warnings=tuple(warnings),
        )

    def _match_ingredient(self, source_name: str) -> IngredientChoice | None:
        search_name = re.sub(r"\([^)]*\)", " ", source_name).strip() or source_name
        candidates = list(self.ingredient_search(search_name) or [])
        target = self._normalized(search_name)
        exact = [
            item
            for item in candidates
            if target in {self._normalized(item.nombre), self._normalized(item.codigo)}
        ]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            ireks = [item for item in exact if item.tipo_origen == "ireks"]
            return ireks[0] if len(ireks) == 1 else None
        return None

    @classmethod
    def _parse_quantity(cls, value: str) -> tuple[float, str] | None:
        normalized = cls._normalized(value).replace(" ", "")
        if normalized in {"c/s", "cs", "c.s"}:
            return 0.0, "Cantidad indicada como C/S en el documento"
        match = cls._QUANTITY_RE.match(value)
        if match is None:
            return None
        number = float(match.group("number").replace(",", "."))
        unit = match.group("unit").casefold()
        if unit in {"kg", "kgs"}:
            return number * 1000.0, ""
        if unit in {"g", "gr"}:
            return number, ""
        if unit == "l":
            return number * 1000.0, "Conversión provisional de litros a gramos (1:1)"
        if unit == "ml":
            return number, "Conversión provisional de mililitros a gramos (1:1)"
        return number, "Cantidad expresada en unidades; revisar equivalencia en gramos"

    @classmethod
    def _is_process_heading(cls, value: str) -> bool:
        normalized = cls._normalized(value)
        return len(value) <= 90 and any(
            normalized == prefix or normalized.startswith(f"{prefix} ")
            for prefix in cls._PROCESS_PREFIXES
        )

    @classmethod
    def _is_process_marker(cls, value: str) -> bool:
        return cls._normalized(value).startswith("proceso de elaboraci")

    @classmethod
    def _process_name(cls, value: str) -> str:
        return "Masa final" if cls._normalized(value) == "masa" else value

    @classmethod
    def _recipe_name(cls, rows: list[str], document_name: str) -> str:
        for line in rows[:6]:
            normalized = cls._normalized(line)
            if (
                normalized
                and not normalized.startswith("receta para")
                and not normalized.startswith("con ")
                and not cls._is_process_heading(line)
                and cls._parse_quantity(line) is None
            ):
                return line
        return Path(document_name).stem

    @classmethod
    def _number_of_pieces(cls, rows: list[str]) -> int:
        for line in rows[:12]:
            match = cls._PIECES_RE.search(line)
            if match:
                return max(1, int(match.group(1)))
        return 1

    @staticmethod
    def _clean_line(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @staticmethod
    def _is_bullet(value: str) -> bool:
        return not any(character.isalnum() for character in value)

    @classmethod
    def _format_process_steps(cls, rows: list[str]) -> str:
        steps: list[str] = []
        current_parts: list[str] = []
        saw_bullet = False
        for row in rows:
            if cls._is_bullet(row):
                saw_bullet = True
                if current_parts:
                    steps.append(" ".join(current_parts))
                    current_parts = []
                continue
            if saw_bullet:
                current_parts.append(row)
            else:
                steps.append(row)
        if current_parts:
            steps.append(" ".join(current_parts))
        return "\n".join(
            f"{index}. {step.strip()}"
            for index, step in enumerate(steps, start=1)
            if step.strip()
        )

    @staticmethod
    def _join_notes(first: str, second: str) -> str:
        return "; ".join(part for part in (first.strip(), second.strip()) if part)

    @staticmethod
    def _normalized(value: str) -> str:
        text = unicodedata.normalize("NFD", str(value or ""))
        text = "".join(character for character in text if unicodedata.category(character) != "Mn")
        text = re.sub(r"[^a-zA-Z0-9/]+", " ", text).strip().casefold()
        return text
