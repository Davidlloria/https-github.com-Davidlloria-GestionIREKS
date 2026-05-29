from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlmodel import Session, col, or_, select

from app.core.database import engine
from app.models import (
    CodigoPostal,
    IngredienteIreks,
    IngredienteStd,
    Isla,
    Localidad,
    MateriaPrimaPrecio,
    MateriaPrimaValorNutricional,
    Municipio,
    Provincia,
    Proveedor,
    TarifaPrecioIreks,
)
from app.services.import_service import ImportService


@dataclass(frozen=True)
class MaintenanceImportProfile:
    key: str
    label: str
    description: str
    schema: list[dict[str, Any]]
    aliases: dict[str, list[str]]
    required_fields: list[str]
    match_fields: list[str]
    update_fields: list[str]
    allow_blank_updates: bool = False


@dataclass
class MaintenanceImportPreview:
    total_rows: int
    valid_rows: int
    invalid_rows: int
    estimated_inserts: int
    estimated_updates: int
    errors: list[str]


@dataclass
class MaintenanceImportResult:
    job_id: str
    profile_key: str
    file_path: str
    dry_run: bool
    mode: str
    total_rows: int
    inserted: int
    updated: int
    skipped: int
    errors: list[str]
    started_at: datetime
    finished_at: datetime


class DbMaintenanceImportService:
    def __init__(self) -> None:
        self.import_service = ImportService()
        self._profiles = self._build_profiles()
        self._ensure_audit_tables()

    def list_profiles(self) -> list[MaintenanceImportProfile]:
        return list(self._profiles.values())

    def get_profile(self, key: str) -> MaintenanceImportProfile:
        profile = self._profiles.get(key)
        if profile is None:
            raise ValueError(f"Perfil de importacion no encontrado: {key}")
        return profile

    def create_excel_template(self, profile_key: str, destination: Path) -> Path:
        profile = self.get_profile(profile_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook()
        sheet = cast(Worksheet, workbook.active)
        sheet.title = "plantilla"
        headers = [str(field.get("label") or field.get("name") or "").strip() for field in profile.schema]
        sheet.append(headers)

        if profile.key == "tarifa_precios_ireks":
            sheet.append(["", 2026, 0.0, 0.0])

        workbook.save(destination)
        return destination

    def preview(self, profile_key: str, file_path: Path) -> MaintenanceImportPreview:
        profile = self.get_profile(profile_key)
        rows = self.import_service.read_rows(file_path)

        payloads, errors = self._prepare_payloads(profile=profile, rows=rows)
        estimated_inserts = 0
        estimated_updates = 0
        with Session(engine) as session:
            lookup = self._build_lookup(session=session, profile=profile, payloads=[p for _, p in payloads])
            for _, payload in payloads:
                if self._find_match(profile=profile, payload=payload, lookup=lookup) is None:
                    estimated_inserts += 1
                else:
                    estimated_updates += 1

        valid_rows = len(payloads)
        return MaintenanceImportPreview(
            total_rows=len(rows),
            valid_rows=valid_rows,
            invalid_rows=max(len(rows) - valid_rows, 0),
            estimated_inserts=estimated_inserts,
            estimated_updates=estimated_updates,
            errors=errors,
        )

    def execute(
        self,
        *,
        profile_key: str,
        file_path: Path,
        mode: str,
        dry_run: bool,
        actor: str = "",
    ) -> MaintenanceImportResult:
        normalized_mode = (mode or "upsert").strip().lower()
        if normalized_mode not in {"upsert", "insert_only", "update_only"}:
            raise ValueError(f"Modo de importacion no soportado: {mode}")

        profile = self.get_profile(profile_key)
        rows = self.import_service.read_rows(file_path)
        job_id = str(uuid4())
        started_at = datetime.now()
        start_ts = perf_counter()

        inserted = 0
        updated = 0
        skipped = 0
        errors: list[str] = []

        self._create_job(
            job_id=job_id,
            profile_key=profile.key,
            file_path=str(file_path),
            dry_run=dry_run,
            mode=normalized_mode,
            actor=actor,
            started_at=started_at,
        )

        with Session(engine) as session:
            payloads, prep_errors = self._prepare_payloads(profile=profile, rows=rows)
            errors.extend(prep_errors)
            lookup = self._build_lookup(session=session, profile=profile, payloads=[p for _, p in payloads])

            for idx, payload in payloads:
                try:
                    with session.begin_nested():
                        existing = self._find_match(profile=profile, payload=payload, lookup=lookup)
                        if existing is None:
                            if normalized_mode == "update_only":
                                skipped += 1
                                continue
                            entity = self._create_entity(session=session, profile=profile, payload=payload)
                            inserted += 1
                            self._update_lookup_after_insert(profile=profile, lookup=lookup, entity=entity)
                            continue

                        if normalized_mode == "insert_only":
                            skipped += 1
                            continue

                        changed = self._apply_updates(session=session, profile=profile, entity=existing, payload=payload)
                        if changed:
                            session.add(existing)
                            updated += 1
                        else:
                            skipped += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Fila {idx}: {exc}")

            if dry_run:
                session.rollback()
            else:
                session.commit()

        finished_at = datetime.now()
        elapsed = perf_counter() - start_ts
        self._finish_job(
            job_id=job_id,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            error_count=len(errors),
            status=self._status_for(inserted=inserted, updated=updated, skipped=skipped, error_count=len(errors), elapsed=elapsed),
            finished_at=finished_at,
            errors=errors,
        )

        return MaintenanceImportResult(
            job_id=job_id,
            profile_key=profile.key,
            file_path=str(file_path),
            dry_run=dry_run,
            mode=normalized_mode,
            total_rows=len(rows),
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            errors=errors,
            started_at=started_at,
            finished_at=finished_at,
        )

    def list_recent_jobs(self, limit: int = 25) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 200))
        with engine.begin() as conn:
            rows = conn.exec_driver_sql(
                """
                SELECT
                    job_id,
                    created_at,
                    finished_at,
                    profile_key,
                    file_path,
                    dry_run,
                    mode,
                    inserted,
                    updated,
                    skipped,
                    errors,
                    status,
                    actor,
                    error_preview
                FROM import_jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()
        jobs: list[dict[str, Any]] = []
        for row in rows:
            jobs.append(
                {
                    "job_id": str(row[0] or ""),
                    "created_at": str(row[1] or ""),
                    "finished_at": str(row[2] or ""),
                    "profile_key": str(row[3] or ""),
                    "file_path": str(row[4] or ""),
                    "dry_run": bool(row[5]),
                    "mode": str(row[6] or ""),
                    "inserted": int(row[7] or 0),
                    "updated": int(row[8] or 0),
                    "skipped": int(row[9] or 0),
                    "errors": int(row[10] or 0),
                    "status": str(row[11] or ""),
                    "actor": str(row[12] or ""),
                    "error_preview": str(row[13] or ""),
                }
            )
        return jobs

    def _prepare_payloads(
        self,
        *,
        profile: MaintenanceImportProfile,
        rows: list[dict[str, Any]],
    ) -> tuple[list[tuple[int, dict[str, Any]]], list[str]]:
        payloads: list[tuple[int, dict[str, Any]]] = []
        errors: list[str] = []
        for idx, row in enumerate(rows, start=2):
            try:
                payload = self.import_service.build_payload(row=row, schema=profile.schema, aliases=profile.aliases)
                self.import_service.validate_required_fields(payload, profile.required_fields)
                payload = self._normalize_payload(profile=profile, payload=payload)
                payloads.append((idx, payload))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Fila {idx}: {exc}")
        return payloads, errors

    def _normalize_payload(self, *, profile: MaintenanceImportProfile, payload: dict[str, Any]) -> dict[str, Any]:
        if profile.key == "productos_ireks":
            return self._normalize_ireks_payload(payload)
        if profile.key == "materias_primas":
            return self._normalize_materia_prima_payload(payload)
        if profile.key == "materias_primas_formato":
            return self._normalize_materia_prima_formato_payload(payload)
        if profile.key == "proveedores":
            return self._normalize_proveedor_payload(payload)
        if profile.key == "provincias":
            return self._normalize_provincia_payload(payload)
        if profile.key == "islas":
            return self._normalize_isla_payload(payload)
        if profile.key == "municipios":
            return self._normalize_municipio_payload(payload)
        if profile.key == "codigos_postales":
            return self._normalize_codigo_postal_payload(payload)
        if profile.key == "localidades":
            return self._normalize_localidad_payload(payload)
        if profile.key == "tarifa_precios_ireks":
            return self._normalize_tarifa_payload(payload)
        if profile.key == "precios_materias_primas":
            return self._normalize_materia_prima_precio_payload(payload)
        if profile.key == "valores_nutricionales_ireks":
            return self._normalize_nutricion_ireks_payload(payload)
        raise ValueError(f"Perfil de normalizacion no soportado: {profile.key}")

    def _build_lookup(self, *, session: Session, profile: MaintenanceImportProfile, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        if profile.key == "productos_ireks":
            return self._build_ireks_lookup(session, payloads)
        if profile.key == "materias_primas":
            return self._build_materia_prima_lookup(session, payloads)
        if profile.key == "materias_primas_formato":
            return self._build_materia_prima_formato_lookup(session, payloads)
        if profile.key == "proveedores":
            return self._build_proveedor_lookup(session, payloads)
        if profile.key == "provincias":
            return self._build_provincia_lookup(session, payloads)
        if profile.key == "islas":
            return self._build_isla_lookup(session, payloads)
        if profile.key == "municipios":
            return self._build_municipio_lookup(session, payloads)
        if profile.key == "codigos_postales":
            return self._build_codigo_postal_lookup(session, payloads)
        if profile.key == "localidades":
            return self._build_localidad_lookup(session, payloads)
        if profile.key == "tarifa_precios_ireks":
            return self._build_tarifa_lookup(session, payloads)
        if profile.key == "precios_materias_primas":
            return self._build_materia_prima_precio_lookup(session, payloads)
        if profile.key == "valores_nutricionales_ireks":
            return self._build_nutricion_ireks_lookup(session, payloads)
        return {}

    def _find_match(self, *, profile: MaintenanceImportProfile, payload: dict[str, Any], lookup: dict[str, Any]) -> Any | None:
        if profile.key == "productos_ireks":
            return self._find_ireks_match(payload, lookup)
        if profile.key == "materias_primas":
            return self._find_materia_prima_match(payload, lookup)
        if profile.key == "materias_primas_formato":
            return self._find_materia_prima_formato_match(payload, lookup)
        if profile.key == "proveedores":
            return self._find_proveedor_match(payload, lookup)
        if profile.key == "provincias":
            return self._find_provincia_match(payload, lookup)
        if profile.key == "islas":
            return self._find_isla_match(payload, lookup)
        if profile.key == "municipios":
            return self._find_municipio_match(payload, lookup)
        if profile.key == "codigos_postales":
            return self._find_codigo_postal_match(payload, lookup)
        if profile.key == "localidades":
            return self._find_localidad_match(payload, lookup)
        if profile.key == "tarifa_precios_ireks":
            return self._find_tarifa_match(payload, lookup)
        if profile.key == "precios_materias_primas":
            return self._find_materia_prima_precio_match(payload, lookup)
        if profile.key == "valores_nutricionales_ireks":
            return self._find_nutricion_ireks_match(payload, lookup)
        return None

    def _create_entity(self, *, session: Session, profile: MaintenanceImportProfile, payload: dict[str, Any]) -> Any:
        if profile.key == "productos_ireks":
            entity = IngredienteIreks(**payload)
        elif profile.key == "materias_primas":
            entity = IngredienteStd(**payload)
        elif profile.key == "materias_primas_formato":
            raise ValueError(
                "El perfil 'materias_primas_formato' solo actualiza articulos existentes. "
                "Usa modo 'Solo actualizar' y verifica articulo_id."
            )
        elif profile.key == "proveedores":
            entity = Proveedor(**payload)
        elif profile.key == "provincias":
            entity = Provincia(**payload)
        elif profile.key == "islas":
            entity = Isla(**payload)
        elif profile.key == "municipios":
            entity = Municipio(**payload)
        elif profile.key == "codigos_postales":
            entity = CodigoPostal(**payload)
        elif profile.key == "localidades":
            self._ensure_codigo_postal_link(session, str(payload.get("municipio_id") or ""), payload.get("codigo_postal"))
            entity = Localidad(**payload)
        elif profile.key == "tarifa_precios_ireks":
            entity = TarifaPrecioIreks(
                articulo_id=str(payload.get("articulo_id") or "").strip(),
                tarifa_ano=int(payload.get("tarifa_ano") or 0),
                precio_fabricante=float(payload.get("precio_fabricante") or 0.0),
                precio_distribuidor=float(payload.get("precio_distribuidor") or 0.0),
            )
        elif profile.key == "precios_materias_primas":
            entity = MateriaPrimaPrecio(
                articulo_id=str(payload.get("articulo_id") or "").strip(),
                fecha_precio=cast(date, payload["fecha_precio"]),
                costo_neto=float(payload.get("costo_neto") or 0.0),
            )
        elif profile.key == "valores_nutricionales_ireks":
            entity = MateriaPrimaValorNutricional(
                articulo_id=str(payload.get("articulo_id") or "").strip(),
                energia_kj=float(payload.get("energia_kj") or 0.0),
                energia_kcal=float(payload.get("energia_kcal") or 0.0),
                grasas_g=float(payload.get("grasas_g") or 0.0),
                saturadas_g=float(payload.get("saturadas_g") or 0.0),
                hidratos_g=float(payload.get("hidratos_g") or 0.0),
                azucares_g=float(payload.get("azucares_g") or 0.0),
                fibra_g=float(payload.get("fibra_g") or 0.0),
                proteinas_g=float(payload.get("proteinas_g") or 0.0),
                sal_g=float(payload.get("sal_g") or 0.0),
            )
        else:
            raise ValueError(f"Perfil no soportado para insercion: {profile.key}")
        session.add(entity)
        session.flush()
        return entity

    def _apply_updates(self, *, session: Session, profile: MaintenanceImportProfile, entity: Any, payload: dict[str, Any]) -> bool:
        if profile.key == "localidades":
            self._ensure_codigo_postal_link(session, str(payload.get("municipio_id") or ""), payload.get("codigo_postal"))
            return self._apply_localidad_updates(entity=entity, payload=payload, profile=profile)
        changed = False
        for field in profile.update_fields:
            if field not in payload:
                continue
            value = payload[field]
            if not profile.allow_blank_updates and isinstance(value, str) and not value.strip():
                continue
            if getattr(entity, field) != value:
                setattr(entity, field, value)
                changed = True
        return changed

    def _update_lookup_after_insert(self, *, profile: MaintenanceImportProfile, lookup: dict[str, Any], entity: Any) -> None:
        if profile.key == "productos_ireks":
            articulo_id = str(entity.articulo_id or "").strip()
            if articulo_id:
                lookup["by_id"][articulo_id] = entity
            ref_key = str(entity.articulo_referencia or "").strip().lower()
            if ref_key:
                lookup["by_ref"][ref_key] = entity
        elif profile.key == "materias_primas":
            articulo_id = str(entity.articulo_id or "").strip()
            if articulo_id:
                lookup["by_id"][articulo_id] = entity
            ref = str(entity.articulo_referencia_distribuidor or "").strip().lower()
            pid = str(entity.proveedor_id or "").strip()
            if ref and pid:
                lookup["by_ref_proveedor"][(pid, ref)] = entity
        elif profile.key == "proveedores":
            eid = str(entity.proveedor_id or "").strip()
            if eid:
                lookup["by_id"][eid] = entity
            code = int(entity.proveedor_codigo or 0)
            if code > 0:
                lookup["by_code"][code] = entity
        elif profile.key == "provincias":
            pid = str(entity.provincia_id or "").strip()
            code = str(entity.provincia_codigo or "").strip().lower()
            if pid:
                lookup["by_id"][pid] = entity
            if code:
                lookup["by_code"][code] = entity
        elif profile.key == "islas":
            eid = str(entity.isla_id or "").strip()
            code = str(entity.isla_codigo or "").strip().lower()
            if eid:
                lookup["by_id"][eid] = entity
            if code:
                lookup["by_code"][code] = entity
        elif profile.key == "municipios":
            eid = str(entity.municipio_id or "").strip()
            code = str(entity.municipio_codigo or "").strip().lower()
            if eid:
                lookup["by_id"][eid] = entity
            if code:
                lookup["by_code"][code] = entity
        elif profile.key == "codigos_postales":
            key = (str(entity.municipio_id or "").strip(), str(entity.codigo_postal or "").strip())
            lookup["by_pk"][key] = entity
        elif profile.key == "localidades":
            eid = str(entity.localidad_id or "").strip()
            if eid:
                lookup["by_id"][eid] = entity
        elif profile.key == "tarifa_precios_ireks":
            key = (str(entity.articulo_id or "").strip(), int(entity.tarifa_ano or 0))
            lookup["by_pk"][key] = entity
        elif profile.key == "precios_materias_primas":
            key = (str(entity.articulo_id or "").strip(), entity.fecha_precio)
            lookup["by_pk"][key] = entity
        elif profile.key == "valores_nutricionales_ireks":
            aid = str(entity.articulo_id or "").strip()
            if aid:
                lookup["by_articulo_id"][aid] = entity

    def _build_profiles(self) -> dict[str, MaintenanceImportProfile]:
        profiles = [
            MaintenanceImportProfile(
                key="productos_ireks",
                label="Productos IREKS (upsert)",
                description="Importa o actualiza productos IREKS por Articulo_ID o Referencia.",
                schema=[
                    {"name": "almacen_id", "label": "Almacen_ID"},
                    {"name": "fabricante_id", "label": "Fabricante_ID"},
                    {"name": "distribuidor_id", "label": "Distribuidor_ID"},
                    {"name": "articulo_id", "label": "Articulo_ID"},
                    {"name": "articulo_referencia", "label": "Articulo_Referencia"},
                    {"name": "articulo_referencia_corta", "label": "Articulo_Referencia_Corta"},
                    {"name": "articulo_descripcion", "label": "Articulo_Descripcion"},
                    {"name": "articulo_envase_id", "label": "Articulo_Envase_ID"},
                    {"name": "articulo_envase_cantidad", "label": "Articulo_Envase_Cantidad", "type": "float"},
                    {"name": "articulo_envase_peso", "label": "Articulo_Envase_Peso", "type": "float"},
                    {"name": "articulo_envase_unidad_medida", "label": "Articulo_Envase_Unidad_Medida"},
                    {"name": "articulo_envase_peso_total", "label": "Articulo_Envase_Peso_Total", "type": "float"},
                    {"name": "articulo_familia_id", "label": "Articulo_Familia_ID"},
                    {"name": "articulo_grupo_id", "label": "Articulo_Grupo_ID"},
                    {"name": "articulo_subfamilia_id", "label": "Articulo_Subfamilia_ID"},
                    {"name": "categoria", "label": "Categoria"},
                    {"name": "articulo_status_activo", "label": "Articulo_Status_Activo", "type": "bool", "default": True},
                    {"name": "articulo_status_en_lista", "label": "Articulo_Status_En_Lista", "type": "bool", "default": False},
                ],
                aliases={
                    "almacen_id": ["almacen", "almacen_id"],
                    "fabricante_id": ["fabricante", "fabricante_id", "marca_id"],
                    "distribuidor_id": ["distribuidor", "distribuidor_id"],
                    "articulo_id": ["articulo", "articulo_id", "id_articulo"],
                    "articulo_referencia": ["referencia", "ref", "codigo"],
                    "articulo_referencia_corta": ["referencia_corta", "ref_corta", "codigo_corto"],
                    "articulo_descripcion": ["descripcion", "nombre", "articulo_descripcion"],
                    "articulo_envase_id": ["envase", "envase_id", "articulo_envase_id"],
                    "articulo_envase_cantidad": ["envase_cantidad", "cantidad_envase"],
                    "articulo_envase_peso": ["envase_peso", "peso_envase"],
                    "articulo_envase_unidad_medida": ["unidad_medida", "unidad", "um"],
                    "articulo_envase_peso_total": ["peso_total", "envase_peso_total"],
                    "articulo_familia_id": ["familia", "familia_id"],
                    "articulo_grupo_id": ["grupo", "grupo_id"],
                    "articulo_subfamilia_id": ["subfamilia", "subfamilia_id"],
                    "articulo_status_activo": ["status_activo", "activo_status", "activo_producto", "estado", "habilitado", "activo"],
                    "articulo_status_en_lista": ["status_en_lista", "en_lista", "lista"],
                },
                required_fields=["almacen_id"],
                match_fields=["articulo_id", "articulo_referencia"],
                update_fields=[
                    "almacen_id",
                    "fabricante_id",
                    "distribuidor_id",
                    "articulo_referencia",
                    "articulo_referencia_corta",
                    "articulo_descripcion",
                    "articulo_envase_id",
                    "articulo_envase_cantidad",
                    "articulo_envase_peso",
                    "articulo_envase_unidad_medida",
                    "articulo_envase_peso_total",
                    "articulo_familia_id",
                    "articulo_grupo_id",
                    "articulo_subfamilia_id",
                    "categoria",
                    "articulo_status_activo",
                    "articulo_status_en_lista",
                ],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="materias_primas",
                label="Materias primas (upsert)",
                description="Importa materias primas por Articulo_ID o Referencia+Proveedor.",
                schema=[
                    {"name": "articulo_id", "label": "Articulo_ID"},
                    {"name": "articulo_referencia_distribuidor", "label": "Articulo_Referencia_Distribuidor"},
                    {"name": "proveedor_id", "label": "Proveedor_ID"},
                    {"name": "articulo_descripcion", "label": "Articulo_Descripcion"},
                    {"name": "articulo_grupo_id", "label": "Articulo_Grupo_ID"},
                    {"name": "articulo_familia_id", "label": "Articulo_Familia_ID"},
                    {"name": "articulo_subfamilia_id", "label": "Articulo_Subfamilia_ID"},
                    {"name": "categoria", "label": "Categoria"},
                    {"name": "formato", "label": "Formato"},
                    {"name": "formato_cantidad", "label": "Cantidad formato", "type": "float"},
                    {"name": "formato_unidad", "label": "Unidad formato"},
                    {"name": "pvp_formato", "label": "PVP formato", "type": "float"},
                    {"name": "pvp_unidad_medida", "label": "PVP unidad medida", "type": "float"},
                    {"name": "activo", "label": "Activo", "type": "bool", "default": True},
                ],
                aliases={
                    "articulo_id": ["id", "articuloid"],
                    "articulo_referencia_distribuidor": ["referencia", "ref", "codigo", "cod"],
                    "proveedor_id": ["proveedor", "proveedor_id", "supplier_id", "distribuidor", "distribuidor_id"],
                    "articulo_descripcion": ["descripcion", "nombre", "articulo", "producto"],
                    "articulo_grupo_id": ["grupo", "grupo_id"],
                    "articulo_familia_id": ["familia", "familia_id"],
                    "articulo_subfamilia_id": ["subfamilia", "subfamilia_id"],
                    "categoria": ["categoria", "tipo"],
                    "formato": ["formato", "envase"],
                    "formato_cantidad": ["cantidad", "cantidad_formato", "peso_formato"],
                    "formato_unidad": ["unidad", "unidad_formato"],
                    "pvp_formato": ["pvp_formato", "precio_formato"],
                    "pvp_unidad_medida": ["pvp_unidad", "pvp_unidad_medida", "precio_unidad"],
                    "activo": ["estado", "habilitado"],
                },
                required_fields=["proveedor_id", "articulo_descripcion"],
                match_fields=["articulo_id", "articulo_referencia_distribuidor", "proveedor_id"],
                update_fields=[
                    "articulo_referencia_distribuidor",
                    "proveedor_id",
                    "articulo_descripcion",
                    "articulo_grupo_id",
                    "articulo_familia_id",
                    "articulo_subfamilia_id",
                    "categoria",
                    "formato",
                    "formato_cantidad",
                    "formato_unidad",
                    "pvp_formato",
                    "pvp_unidad_medida",
                    "activo",
                ],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="provincias",
                label="Direcciones: Provincias",
                description="Importa provincias por ID o codigo unico.",
                schema=[
                    {"name": "provincia_id", "label": "Provincia_ID"},
                    {"name": "provincia_nombre", "label": "Provincia_Nombre"},
                    {"name": "provincia_codigo", "label": "Provincia_Codigo"},
                ],
                aliases={
                    "provincia_id": ["id", "uuid", "provincia_uuid"],
                    "provincia_nombre": ["nombre", "provincia"],
                    "provincia_codigo": ["codigo", "cod_provincia"],
                },
                required_fields=["provincia_nombre", "provincia_codigo"],
                match_fields=["provincia_id", "provincia_codigo"],
                update_fields=["provincia_nombre", "provincia_codigo"],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="materias_primas_formato",
                label="Materias primas: formato/unidad/cantidad",
                description="Actualiza formato, unidad y cantidad por articulo_id.",
                schema=[
                    {"name": "articulo_id", "label": "Articulo_ID"},
                    {"name": "formato", "label": "Formato"},
                    {"name": "formato_unidad", "label": "Unidad formato"},
                    {"name": "formato_cantidad", "label": "Cantidad formato", "type": "float"},
                ],
                aliases={
                    "articulo_id": ["id", "articuloid", "id_articulo", "producto_id"],
                    "formato": ["formato", "envase", "presentacion"],
                    "formato_unidad": ["unidad", "unidad_formato", "um", "u_medida"],
                    "formato_cantidad": ["cantidad", "cantidad_formato", "peso_formato", "cantidad_envase"],
                },
                required_fields=["articulo_id"],
                match_fields=["articulo_id"],
                update_fields=["formato", "formato_unidad", "formato_cantidad"],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="proveedores",
                label="Proveedores (upsert)",
                description="Importa o actualiza proveedores por ID o codigo.",
                schema=[
                    {"name": "proveedor_id", "label": "Proveedor_ID"},
                    {"name": "proveedor_razon_social", "label": "Razon social"},
                    {"name": "proveedor_nombre_comercial", "label": "Nombre comercial"},
                    {"name": "proveedor_cif", "label": "CIF"},
                    {"name": "proveedor_telefono", "label": "Telefono"},
                    {"name": "proveedor_contacto", "label": "Contacto"},
                ],
                aliases={
                    "proveedor_id": ["id", "proveedor_id", "supplier_id"],
                    "proveedor_razon_social": ["razon_social", "razon", "nombre_fiscal", "fiscal_name"],
                    "proveedor_nombre_comercial": ["nombre_comercial", "nombre", "proveedor", "supplier_name"],
                    "proveedor_cif": ["cif", "nif", "vat"],
                    "proveedor_telefono": ["telefono", "tel", "phone"],
                    "proveedor_contacto": ["contacto", "contact", "persona_contacto"],
                },
                required_fields=["proveedor_id", "proveedor_razon_social"],
                match_fields=["proveedor_id", "proveedor_codigo"],
                update_fields=[
                    "proveedor_razon_social",
                    "proveedor_nombre_comercial",
                    "proveedor_cif",
                    "proveedor_telefono",
                    "proveedor_contacto",
                ],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="islas",
                label="Direcciones: Islas",
                description="Importa islas por ID o codigo unico.",
                schema=[
                    {"name": "isla_id", "label": "Isla_ID"},
                    {"name": "provincia_id", "label": "Provincia_ID"},
                    {"name": "isla_nombre", "label": "Isla_Nombre"},
                    {"name": "isla_codigo", "label": "Isla_Codigo"},
                    {"name": "isla_iniciales", "label": "Isla_Iniciales"},
                ],
                aliases={
                    "isla_id": ["id", "uuid", "isla_uuid"],
                    "provincia_id": ["provincia_uuid", "provinciaid"],
                    "isla_nombre": ["nombre", "isla"],
                    "isla_codigo": ["codigo", "cod_isla"],
                    "isla_iniciales": ["iniciales", "siglas"],
                },
                required_fields=["provincia_id", "isla_nombre", "isla_codigo"],
                match_fields=["isla_id", "isla_codigo"],
                update_fields=["provincia_id", "isla_nombre", "isla_codigo", "isla_iniciales"],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="municipios",
                label="Direcciones: Municipios",
                description="Importa municipios por ID o codigo unico.",
                schema=[
                    {"name": "municipio_id", "label": "Municipio_ID"},
                    {"name": "isla_id", "label": "Isla_ID"},
                    {"name": "provincia_id", "label": "Provincia_ID"},
                    {"name": "municipio_nombre", "label": "Municipio_Nombre"},
                    {"name": "municipio_codigo", "label": "Municipio_Codigo"},
                ],
                aliases={
                    "municipio_id": ["id", "uuid", "municipio_uuid"],
                    "isla_id": ["isla_uuid", "islaid"],
                    "provincia_id": ["provincia_uuid", "provinciaid"],
                    "municipio_nombre": ["nombre", "municipio"],
                    "municipio_codigo": ["codigo", "cod_municipio"],
                },
                required_fields=["isla_id", "provincia_id", "municipio_nombre", "municipio_codigo"],
                match_fields=["municipio_id", "municipio_codigo"],
                update_fields=["isla_id", "provincia_id", "municipio_nombre", "municipio_codigo"],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="codigos_postales",
                label="Direcciones: Codigos postales",
                description="Importa codigos postales por PK compuesta Municipio_ID + Codigo_Postal.",
                schema=[
                    {"name": "municipio_id", "label": "Municipio_ID"},
                    {"name": "codigo_postal", "label": "Codigo_Postal"},
                ],
                aliases={
                    "municipio_id": ["municipio_uuid", "municipioid", "id_municipio"],
                    "codigo_postal": ["cp", "codigo", "postal"],
                },
                required_fields=["municipio_id", "codigo_postal"],
                match_fields=["municipio_id", "codigo_postal"],
                update_fields=[],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="localidades",
                label="Direcciones: Localidades",
                description="Importa localidades por ID y vincula/crea CodigoPostal cuando aplica.",
                schema=[
                    {"name": "localidad_id", "label": "Localidad_ID"},
                    {"name": "municipio_id", "label": "Municipio_ID"},
                    {"name": "localidad_nombre", "label": "Localidad_Nombre"},
                    {"name": "codigo_postal", "label": "Codigo_Postal"},
                ],
                aliases={
                    "localidad_id": ["id", "uuid", "localidad_uuid"],
                    "municipio_id": ["municipio_uuid", "municipioid", "id_municipio"],
                    "localidad_nombre": ["nombre", "localidad"],
                    "codigo_postal": ["cp", "codigo", "postal"],
                },
                required_fields=["municipio_id", "localidad_nombre"],
                match_fields=["localidad_id"],
                update_fields=["municipio_id", "localidad_nombre", "codigo_postal"],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="precios_materias_primas",
                label="Precios materias primas (historico)",
                description="Importa precios historicos por articulo_id + fecha_precio.",
                schema=[
                    {"name": "articulo_id", "label": "articulo_id"},
                    {"name": "fecha_precio", "label": "fecha_precio"},
                    {"name": "costo_neto", "label": "costo_neto", "type": "float"},
                ],
                aliases={
                    "articulo_id": ["id_articulo", "articuloid", "producto_id"],
                    "fecha_precio": ["fecha", "fecha_costo", "fecha_precio"],
                    "costo_neto": ["costo", "precio", "coste_neto", "costo_neto"],
                },
                required_fields=["articulo_id", "fecha_precio", "costo_neto"],
                match_fields=["articulo_id", "fecha_precio"],
                update_fields=["costo_neto"],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="tarifa_precios_ireks",
                label="Tarifa precios IREKS (anual)",
                description="Importa tarifas anuales por articulo_id (precio fabricante y distribuidor).",
                schema=[
                    {"name": "articulo_id", "label": "Articulo_ID"},
                    {"name": "tarifa_ano", "label": "Tarifa_Ano"},
                    {"name": "precio_fabricante", "label": "Precio_Fabricante", "type": "float"},
                    {"name": "precio_distribuidor", "label": "Precio_Distribuidor", "type": "float"},
                ],
                aliases={
                    "articulo_id": ["id_articulo", "articuloid", "producto_id"],
                    "tarifa_ano": ["ano", "anio", "year", "ejercicio"],
                    "precio_fabricante": ["tarifa_fabricante", "pvp_fabricante", "precio_ireks", "precio_fab"],
                    "precio_distribuidor": ["tarifa_distribuidor", "pvp_distribuidor", "precio_dist"],
                },
                required_fields=["articulo_id", "tarifa_ano"],
                match_fields=["articulo_id", "tarifa_ano"],
                update_fields=["precio_fabricante", "precio_distribuidor"],
                allow_blank_updates=False,
            ),
            MaintenanceImportProfile(
                key="valores_nutricionales_ireks",
                label="Valores nutricionales IREKS",
                description="Importa valores nutricionales para productos IREKS por Articulo_ID o Referencia.",
                schema=[
                    {"name": "articulo_id", "label": "Articulo_ID"},
                    {"name": "articulo_referencia", "label": "Articulo_Referencia"},
                    {"name": "energia_kj", "label": "Energia_kJ", "type": "float"},
                    {"name": "energia_kcal", "label": "Energia_kcal", "type": "float"},
                    {"name": "grasas_g", "label": "Grasas_g", "type": "float"},
                    {"name": "saturadas_g", "label": "Saturadas_g", "type": "float"},
                    {"name": "hidratos_g", "label": "Hidratos_g", "type": "float"},
                    {"name": "azucares_g", "label": "Azucares_g", "type": "float"},
                    {"name": "fibra_g", "label": "Fibra_g", "type": "float"},
                    {"name": "proteinas_g", "label": "Proteinas_g", "type": "float"},
                    {"name": "sal_g", "label": "Sal_g", "type": "float"},
                ],
                aliases={
                    "articulo_id": ["id_articulo", "articuloid", "producto_id"],
                    "articulo_referencia": ["referencia", "ref", "codigo", "articulo_referencia"],
                    "energia_kj": ["energia_kj", "kJ", "energia"],
                    "energia_kcal": ["energia_kcal", "kcal"],
                    "grasas_g": ["grasas_g", "grasas"],
                    "saturadas_g": ["saturadas_g", "grasas_saturadas", "saturadas"],
                    "hidratos_g": ["hidratos_g", "hidratos", "carbohidratos"],
                    "azucares_g": ["azucares_g", "azucares", "azucares_totales"],
                    "fibra_g": ["fibra_g", "fibra"],
                    "proteinas_g": ["proteinas_g", "proteinas"],
                    "sal_g": ["sal_g", "sal"],
                },
                required_fields=[],
                match_fields=["articulo_id", "articulo_referencia"],
                update_fields=[
                    "energia_kj",
                    "energia_kcal",
                    "grasas_g",
                    "saturadas_g",
                    "hidratos_g",
                    "azucares_g",
                    "fibra_g",
                    "proteinas_g",
                    "sal_g",
                ],
                allow_blank_updates=False,
            ),
        ]
        return {profile.key: profile for profile in profiles}

    def _build_ireks_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        articulo_ids = {str(payload.get("articulo_id") or "").strip() for payload in payloads}
        articulo_ids.discard("")
        references = {str(payload.get("articulo_referencia") or "").strip() for payload in payloads}
        references.discard("")
        statements = []
        if articulo_ids:
            statements.append(col(IngredienteIreks.articulo_id).in_(articulo_ids))
        if references:
            statements.append(col(IngredienteIreks.articulo_referencia).in_(references))
        rows: list[IngredienteIreks] = list(session.exec(select(IngredienteIreks).where(or_(*statements)))) if statements else []
        by_id = {str(row.articulo_id or "").strip(): row for row in rows if str(row.articulo_id or "").strip()}
        by_ref = {str(row.articulo_referencia or "").strip().lower(): row for row in rows if str(row.articulo_referencia or "").strip()}
        return {"by_id": by_id, "by_ref": by_ref}

    def _find_ireks_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> IngredienteIreks | None:
        articulo_id = str(payload.get("articulo_id") or "").strip()
        if articulo_id and articulo_id in lookup["by_id"]:
            return lookup["by_id"][articulo_id]
        ref = str(payload.get("articulo_referencia") or "").strip().lower()
        if ref and ref in lookup["by_ref"]:
            return lookup["by_ref"][ref]
        return None

    def _build_materia_prima_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        articulo_ids = {str(payload.get("articulo_id") or "").strip() for payload in payloads}
        articulo_ids.discard("")
        referencias = {str(payload.get("articulo_referencia_distribuidor") or "").strip() for payload in payloads}
        referencias.discard("")
        proveedor_ids = {str(payload.get("proveedor_id") or "").strip() for payload in payloads}
        proveedor_ids.discard("")
        statements = []
        if articulo_ids:
            statements.append(col(IngredienteStd.articulo_id).in_(articulo_ids))
        if referencias and proveedor_ids:
            statements.append(
                (col(IngredienteStd.articulo_referencia_distribuidor).in_(referencias))
                & (col(IngredienteStd.proveedor_id).in_(proveedor_ids))
            )
        rows: list[IngredienteStd] = list(session.exec(select(IngredienteStd).where(or_(*statements)))) if statements else []
        by_id = {str(row.articulo_id or "").strip(): row for row in rows if str(row.articulo_id or "").strip()}
        by_ref_proveedor = {
            (str(row.proveedor_id or "").strip(), str(row.articulo_referencia_distribuidor or "").strip().lower()): row
            for row in rows
            if str(row.proveedor_id or "").strip() and str(row.articulo_referencia_distribuidor or "").strip()
        }
        return {"by_id": by_id, "by_ref_proveedor": by_ref_proveedor}

    def _find_materia_prima_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> IngredienteStd | None:
        articulo_id = str(payload.get("articulo_id") or "").strip()
        if articulo_id and articulo_id in lookup["by_id"]:
            return lookup["by_id"][articulo_id]
        ref = str(payload.get("articulo_referencia_distribuidor") or "").strip().lower()
        pid = str(payload.get("proveedor_id") or "").strip()
        if ref and pid and (pid, ref) in lookup["by_ref_proveedor"]:
            return lookup["by_ref_proveedor"][(pid, ref)]
        return None

    def _build_materia_prima_formato_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        articulo_ids = {str(payload.get("articulo_id") or "").strip() for payload in payloads}
        articulo_ids.discard("")
        rows: list[IngredienteStd] = []
        if articulo_ids:
            rows = list(session.exec(select(IngredienteStd).where(col(IngredienteStd.articulo_id).in_(articulo_ids))))
        by_id = {str(row.articulo_id or "").strip(): row for row in rows if str(row.articulo_id or "").strip()}
        return {"by_id": by_id}

    def _find_materia_prima_formato_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> IngredienteStd | None:
        articulo_id = str(payload.get("articulo_id") or "").strip()
        if not articulo_id:
            return None
        return lookup["by_id"].get(articulo_id)

    def _build_proveedor_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        ids = {str(payload.get("proveedor_id") or "").strip() for payload in payloads}
        ids.discard("")
        codes = {int(payload.get("proveedor_codigo") or 0) for payload in payloads}
        codes.discard(0)
        statements = []
        if ids:
            statements.append(col(Proveedor.proveedor_id).in_(ids))
        if codes:
            statements.append(col(Proveedor.proveedor_codigo).in_(codes))
        rows: list[Proveedor] = list(session.exec(select(Proveedor).where(or_(*statements)))) if statements else []
        by_id = {str(row.proveedor_id or "").strip(): row for row in rows if str(row.proveedor_id or "").strip()}
        by_code = {int(row.proveedor_codigo or 0): row for row in rows if int(row.proveedor_codigo or 0) > 0}
        return {"by_id": by_id, "by_code": by_code}

    def _find_proveedor_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> Proveedor | None:
        eid = str(payload.get("proveedor_id") or "").strip()
        if eid and eid in lookup["by_id"]:
            return lookup["by_id"][eid]
        code = int(payload.get("proveedor_codigo") or 0)
        if code > 0 and code in lookup["by_code"]:
            return lookup["by_code"][code]
        return None

    def _build_provincia_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        ids = {str(payload.get("provincia_id") or "").strip() for payload in payloads}
        ids.discard("")
        codes = {str(payload.get("provincia_codigo") or "").strip() for payload in payloads}
        codes.discard("")
        statements = []
        if ids:
            statements.append(col(Provincia.provincia_id).in_(ids))
        if codes:
            statements.append(col(Provincia.provincia_codigo).in_(codes))
        rows: list[Provincia] = list(session.exec(select(Provincia).where(or_(*statements)))) if statements else []
        by_id = {str(row.provincia_id or "").strip(): row for row in rows if str(row.provincia_id or "").strip()}
        by_code = {str(row.provincia_codigo or "").strip().lower(): row for row in rows if str(row.provincia_codigo or "").strip()}
        return {"by_id": by_id, "by_code": by_code}

    def _find_provincia_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> Provincia | None:
        pid = str(payload.get("provincia_id") or "").strip()
        if pid and pid in lookup["by_id"]:
            return lookup["by_id"][pid]
        code = str(payload.get("provincia_codigo") or "").strip().lower()
        if code and code in lookup["by_code"]:
            return lookup["by_code"][code]
        return None

    def _build_isla_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        ids = {str(payload.get("isla_id") or "").strip() for payload in payloads}
        ids.discard("")
        codes = {str(payload.get("isla_codigo") or "").strip() for payload in payloads}
        codes.discard("")
        statements = []
        if ids:
            statements.append(col(Isla.isla_id).in_(ids))
        if codes:
            statements.append(col(Isla.isla_codigo).in_(codes))
        rows: list[Isla] = list(session.exec(select(Isla).where(or_(*statements)))) if statements else []
        by_id = {str(row.isla_id or "").strip(): row for row in rows if str(row.isla_id or "").strip()}
        by_code = {str(row.isla_codigo or "").strip().lower(): row for row in rows if str(row.isla_codigo or "").strip()}
        return {"by_id": by_id, "by_code": by_code}

    def _find_isla_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> Isla | None:
        eid = str(payload.get("isla_id") or "").strip()
        if eid and eid in lookup["by_id"]:
            return lookup["by_id"][eid]
        code = str(payload.get("isla_codigo") or "").strip().lower()
        if code and code in lookup["by_code"]:
            return lookup["by_code"][code]
        return None

    def _build_municipio_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        ids = {str(payload.get("municipio_id") or "").strip() for payload in payloads}
        ids.discard("")
        codes = {str(payload.get("municipio_codigo") or "").strip() for payload in payloads}
        codes.discard("")
        statements = []
        if ids:
            statements.append(col(Municipio.municipio_id).in_(ids))
        if codes:
            statements.append(col(Municipio.municipio_codigo).in_(codes))
        rows: list[Municipio] = list(session.exec(select(Municipio).where(or_(*statements)))) if statements else []
        by_id = {str(row.municipio_id or "").strip(): row for row in rows if str(row.municipio_id or "").strip()}
        by_code = {str(row.municipio_codigo or "").strip().lower(): row for row in rows if str(row.municipio_codigo or "").strip()}
        return {"by_id": by_id, "by_code": by_code}

    def _find_municipio_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> Municipio | None:
        eid = str(payload.get("municipio_id") or "").strip()
        if eid and eid in lookup["by_id"]:
            return lookup["by_id"][eid]
        code = str(payload.get("municipio_codigo") or "").strip().lower()
        if code and code in lookup["by_code"]:
            return lookup["by_code"][code]
        return None

    def _build_codigo_postal_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        municipio_ids = {str(payload.get("municipio_id") or "").strip() for payload in payloads}
        municipio_ids.discard("")
        cps = {str(payload.get("codigo_postal") or "").strip() for payload in payloads}
        cps.discard("")
        rows: list[CodigoPostal] = []
        if municipio_ids and cps:
            rows = list(
                session.exec(
                    select(CodigoPostal).where(
                        col(CodigoPostal.municipio_id).in_(municipio_ids),
                        col(CodigoPostal.codigo_postal).in_(cps),
                    )
                )
            )
        by_pk = {(str(row.municipio_id or "").strip(), str(row.codigo_postal or "").strip()): row for row in rows}
        return {"by_pk": by_pk}

    def _find_codigo_postal_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> CodigoPostal | None:
        key = (str(payload.get("municipio_id") or "").strip(), str(payload.get("codigo_postal") or "").strip())
        return lookup["by_pk"].get(key)

    def _build_localidad_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        ids = {str(payload.get("localidad_id") or "").strip() for payload in payloads}
        ids.discard("")
        rows: list[Localidad] = list(session.exec(select(Localidad).where(col(Localidad.localidad_id).in_(ids)))) if ids else []
        by_id = {str(row.localidad_id or "").strip(): row for row in rows if str(row.localidad_id or "").strip()}
        return {"by_id": by_id}

    def _find_localidad_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> Localidad | None:
        eid = str(payload.get("localidad_id") or "").strip()
        if not eid:
            return None
        return lookup["by_id"].get(eid)

    def _build_tarifa_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        articulo_ids = {str(payload.get("articulo_id") or "").strip() for payload in payloads}
        articulo_ids.discard("")
        years = {int(payload.get("tarifa_ano") or 0) for payload in payloads}
        years.discard(0)
        rows: list[TarifaPrecioIreks] = []
        if articulo_ids and years:
            rows = list(
                session.exec(
                    select(TarifaPrecioIreks).where(
                        col(TarifaPrecioIreks.articulo_id).in_(articulo_ids),
                        col(TarifaPrecioIreks.tarifa_ano).in_(years),
                    )
                )
            )
        by_pk = {
            (str(row.articulo_id or "").strip(), int(row.tarifa_ano or 0)): row
            for row in rows
            if str(row.articulo_id or "").strip() and int(row.tarifa_ano or 0) > 0
        }
        return {"by_pk": by_pk}

    def _find_tarifa_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> TarifaPrecioIreks | None:
        key = (str(payload.get("articulo_id") or "").strip(), int(payload.get("tarifa_ano") or 0))
        if not key[0] or key[1] <= 0:
            return None
        return lookup["by_pk"].get(key)

    def _build_materia_prima_precio_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        articulo_ids = {str(payload.get("articulo_id") or "").strip() for payload in payloads}
        articulo_ids.discard("")
        fechas = {payload.get("fecha_precio") for payload in payloads if payload.get("fecha_precio")}
        rows: list[MateriaPrimaPrecio] = []
        if articulo_ids and fechas:
            rows = list(
                session.exec(
                    select(MateriaPrimaPrecio).where(
                        col(MateriaPrimaPrecio.articulo_id).in_(articulo_ids),
                        col(MateriaPrimaPrecio.fecha_precio).in_(fechas),
                    )
                )
            )
        by_pk = {
            (str(row.articulo_id or "").strip(), row.fecha_precio): row
            for row in rows
            if str(row.articulo_id or "").strip() and row.fecha_precio
        }
        return {"by_pk": by_pk}

    def _find_materia_prima_precio_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> MateriaPrimaPrecio | None:
        key = (str(payload.get("articulo_id") or "").strip(), payload.get("fecha_precio"))
        if not key[0] or not key[1]:
            return None
        return lookup["by_pk"].get(key)

    def _build_nutricion_ireks_lookup(self, session: Session, payloads: list[dict[str, Any]]) -> dict[str, Any]:
        articulo_ids = {str(payload.get("articulo_id") or "").strip() for payload in payloads}
        articulo_ids.discard("")
        referencias = {str(payload.get("articulo_referencia") or "").strip() for payload in payloads}
        referencias.discard("")

        statements = []
        if articulo_ids:
            statements.append(col(IngredienteIreks.articulo_id).in_(articulo_ids))
        if referencias:
            statements.append(col(IngredienteIreks.articulo_referencia).in_(referencias))
        ireks_rows: list[IngredienteIreks] = list(session.exec(select(IngredienteIreks).where(or_(*statements)))) if statements else []
        ireks_by_id = {str(row.articulo_id or "").strip(): row for row in ireks_rows if str(row.articulo_id or "").strip()}
        ireks_by_ref = {
            str(row.articulo_referencia or "").strip().lower(): row
            for row in ireks_rows
            if str(row.articulo_referencia or "").strip()
        }

        nutrition_rows: list[MateriaPrimaValorNutricional] = []
        if ireks_by_id:
            nutrition_rows = list(
                session.exec(
                    select(MateriaPrimaValorNutricional).where(
                        col(MateriaPrimaValorNutricional.articulo_id).in_(set(ireks_by_id.keys()))
                    )
                )
            )
        by_articulo_id = {str(row.articulo_id or "").strip(): row for row in nutrition_rows if str(row.articulo_id or "").strip()}
        return {"ireks_by_id": ireks_by_id, "ireks_by_ref": ireks_by_ref, "by_articulo_id": by_articulo_id}

    def _find_nutricion_ireks_match(self, payload: dict[str, Any], lookup: dict[str, Any]) -> MateriaPrimaValorNutricional | None:
        articulo_id = str(payload.get("articulo_id") or "").strip()
        if not articulo_id:
            ref = str(payload.get("articulo_referencia") or "").strip().lower()
            if ref:
                ireks = lookup["ireks_by_ref"].get(ref)
                if ireks is not None:
                    articulo_id = str(ireks.articulo_id or "").strip()
                    payload["articulo_id"] = articulo_id
        else:
            if articulo_id not in lookup["ireks_by_id"]:
                raise ValueError(f"Articulo_ID no pertenece a productos IREKS: {articulo_id}")

        if not articulo_id:
            raise ValueError("No se pudo resolver producto IREKS por Articulo_ID o Articulo_Referencia.")
        if articulo_id not in lookup["ireks_by_id"]:
            raise ValueError(f"No existe producto IREKS para Articulo_ID: {articulo_id}")
        return lookup["by_articulo_id"].get(articulo_id)

    def _normalize_ireks_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["almacen_id"] = str(data.get("almacen_id") or "").strip()
        data["articulo_id"] = str(data.get("articulo_id") or "").strip() or str(uuid4())
        data["articulo_referencia"] = str(data.get("articulo_referencia") or "").strip()
        data["articulo_referencia_corta"] = str(data.get("articulo_referencia_corta") or "").strip()
        data["articulo_descripcion"] = str(data.get("articulo_descripcion") or "").strip()
        data["articulo_envase_id"] = str(data.get("articulo_envase_id") or "").strip()
        data["articulo_familia_id"] = str(data.get("articulo_familia_id") or "").strip()
        data["articulo_grupo_id"] = str(data.get("articulo_grupo_id") or "").strip()
        data["articulo_subfamilia_id"] = str(data.get("articulo_subfamilia_id") or "").strip()
        data["fabricante_id"] = str(data.get("fabricante_id") or "").strip()
        proveedor_id = str(data.get("proveedor_id") or data.get("distribuidor_id") or "").strip()
        data["proveedor_id"] = proveedor_id
        data["distribuidor_id"] = proveedor_id
        data["categoria"] = str(data.get("categoria") or "").strip().lower()
        data["articulo_envase_unidad_medida"] = str(data.get("articulo_envase_unidad_medida") or "").strip()
        cantidad = self._to_float(data.get("articulo_envase_cantidad"))
        peso = self._to_float(data.get("articulo_envase_peso"))
        data["articulo_envase_cantidad"] = cantidad
        data["articulo_envase_peso"] = peso
        data["articulo_envase_peso_total"] = cantidad * peso
        data["articulo_status_activo"] = self._to_bool(data.get("articulo_status_activo"), default=True)
        data["articulo_status_en_lista"] = self._to_bool(data.get("articulo_status_en_lista"), default=False)
        return data

    def _normalize_materia_prima_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["articulo_id"] = str(data.get("articulo_id") or "").strip() or str(uuid4())
        data["articulo_referencia_distribuidor"] = str(data.get("articulo_referencia_distribuidor") or "").strip()
        data["distribuidor_id"] = str(data.get("distribuidor_id") or "").strip()
        data["articulo_descripcion"] = str(data.get("articulo_descripcion") or "").strip()
        data["articulo_grupo_id"] = str(data.get("articulo_grupo_id") or "").strip()
        data["articulo_familia_id"] = str(data.get("articulo_familia_id") or "").strip()
        data["articulo_subfamilia_id"] = str(data.get("articulo_subfamilia_id") or "").strip()
        data["categoria"] = str(data.get("categoria") or "").strip().lower()
        data["formato"] = str(data.get("formato") or "").strip()
        data["formato_cantidad"] = self._to_float(data.get("formato_cantidad"))
        data["formato_unidad"] = str(data.get("formato_unidad") or "kg").strip() or "kg"
        data["pvp_formato"] = self._to_float(data.get("pvp_formato"))
        data["pvp_unidad_medida"] = self._to_float(data.get("pvp_unidad_medida"))
        data["activo"] = self._to_bool(data.get("activo"), default=True)
        return data

    def _normalize_materia_prima_formato_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["articulo_id"] = str(data.get("articulo_id") or "").strip()
        data["formato"] = str(data.get("formato") or "").strip()
        data["formato_unidad"] = str(data.get("formato_unidad") or "").strip()
        data["formato_cantidad"] = self._to_float(data.get("formato_cantidad"))
        return data

    def _normalize_proveedor_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["proveedor_id"] = str(data.get("proveedor_id") or "").strip() or str(uuid4())
        # El codigo del proveedor siempre lo autogenera el sistema.
        data["proveedor_codigo"] = 0
        data["proveedor_razon_social"] = str(data.get("proveedor_razon_social") or "").strip()
        data["proveedor_nombre_comercial"] = str(data.get("proveedor_nombre_comercial") or "").strip()
        data["proveedor_cif"] = str(data.get("proveedor_cif") or "").strip()
        data["proveedor_telefono"] = str(data.get("proveedor_telefono") or "").strip()
        data["proveedor_contacto"] = str(data.get("proveedor_contacto") or "").strip()
        if not data["proveedor_nombre_comercial"] and data["proveedor_razon_social"]:
            data["proveedor_nombre_comercial"] = data["proveedor_razon_social"]
        return data

    def _normalize_provincia_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["provincia_id"] = str(data.get("provincia_id") or "").strip() or str(uuid4())
        data["provincia_nombre"] = str(data.get("provincia_nombre") or "").strip()
        data["provincia_codigo"] = str(data.get("provincia_codigo") or "").strip()
        return data

    def _normalize_isla_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["isla_id"] = str(data.get("isla_id") or "").strip() or str(uuid4())
        data["provincia_id"] = str(data.get("provincia_id") or "").strip()
        data["isla_nombre"] = str(data.get("isla_nombre") or "").strip()
        data["isla_codigo"] = str(data.get("isla_codigo") or "").strip()
        data["isla_iniciales"] = str(data.get("isla_iniciales") or "").strip()
        return data

    def _normalize_municipio_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["municipio_id"] = str(data.get("municipio_id") or "").strip() or str(uuid4())
        data["isla_id"] = str(data.get("isla_id") or "").strip()
        data["provincia_id"] = str(data.get("provincia_id") or "").strip()
        data["municipio_nombre"] = str(data.get("municipio_nombre") or "").strip()
        data["municipio_codigo"] = str(data.get("municipio_codigo") or "").strip()
        return data

    def _normalize_codigo_postal_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["municipio_id"] = str(data.get("municipio_id") or "").strip()
        data["codigo_postal"] = str(data.get("codigo_postal") or "").strip()
        return data

    def _normalize_localidad_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["localidad_id"] = str(data.get("localidad_id") or "").strip() or str(uuid4())
        data["municipio_id"] = str(data.get("municipio_id") or "").strip()
        data["localidad_nombre"] = str(data.get("localidad_nombre") or "").strip()
        cp = str(data.get("codigo_postal") or "").strip()
        data["codigo_postal"] = cp or None
        return data

    def _normalize_tarifa_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        articulo_id = str(data.get("articulo_id") or "").strip()
        if not articulo_id:
            raise ValueError("Campo obligatorio vacio: articulo_id")
        data["articulo_id"] = articulo_id

        ano_raw = str(data.get("tarifa_ano") or "").strip()
        if not ano_raw:
            raise ValueError("Campo obligatorio vacio: tarifa_ano")
        try:
            tarifa_ano = int(float(ano_raw.replace(",", ".")))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Ano de tarifa invalido: {ano_raw}") from exc
        if tarifa_ano < 1900 or tarifa_ano > 2100:
            raise ValueError(f"Ano de tarifa fuera de rango: {tarifa_ano}")
        data["tarifa_ano"] = tarifa_ano
        data["precio_fabricante"] = self._to_float(data.get("precio_fabricante"))
        data["precio_distribuidor"] = self._to_float(data.get("precio_distribuidor"))
        return data

    def _normalize_materia_prima_precio_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        articulo_id = str(data.get("articulo_id") or "").strip()
        if not articulo_id:
            raise ValueError("Campo obligatorio vacio: articulo_id")
        data["articulo_id"] = articulo_id

        fecha = self._to_date(data.get("fecha_precio"))
        if fecha is None:
            raise ValueError("Campo obligatorio vacio o invalido: fecha_precio")
        data["fecha_precio"] = fecha
        data["costo_neto"] = self._to_float(data.get("costo_neto"))
        return data

    def _normalize_nutricion_ireks_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["articulo_id"] = str(data.get("articulo_id") or "").strip()
        data["articulo_referencia"] = str(data.get("articulo_referencia") or "").strip()
        if not data["articulo_id"] and not data["articulo_referencia"]:
            raise ValueError("Debes informar Articulo_ID o Articulo_Referencia.")
        data["energia_kj"] = self._to_float(data.get("energia_kj"))
        data["energia_kcal"] = self._to_float(data.get("energia_kcal"))
        data["grasas_g"] = self._to_float(data.get("grasas_g"))
        data["saturadas_g"] = self._to_float(data.get("saturadas_g"))
        data["hidratos_g"] = self._to_float(data.get("hidratos_g"))
        data["azucares_g"] = self._to_float(data.get("azucares_g"))
        data["fibra_g"] = self._to_float(data.get("fibra_g"))
        data["proteinas_g"] = self._to_float(data.get("proteinas_g"))
        data["sal_g"] = self._to_float(data.get("sal_g"))
        return data

    def _apply_localidad_updates(self, *, entity: Localidad, payload: dict[str, Any], profile: MaintenanceImportProfile) -> bool:
        changed = False
        for field in profile.update_fields:
            value = payload.get(field)
            if not profile.allow_blank_updates and isinstance(value, str) and not value.strip():
                continue
            if getattr(entity, field) != value:
                setattr(entity, field, value)
                changed = True
        return changed

    def _ensure_codigo_postal_link(self, session: Session, municipio_id: str, codigo_postal: str | None) -> None:
        municipio_id = str(municipio_id or "").strip()
        cp = str(codigo_postal or "").strip()
        if not municipio_id or not cp:
            return
        existing = session.exec(
            select(CodigoPostal).where(
                CodigoPostal.municipio_id == municipio_id,
                CodigoPostal.codigo_postal == cp,
            )
        ).first()
        if existing is not None:
            return
        session.add(CodigoPostal(municipio_id=municipio_id, codigo_postal=cp))
        session.flush()

    def _to_float(self, value: Any) -> float:
        if value in (None, ""):
            return 0.0
        try:
            return float(str(value).replace(",", ".").strip())
        except Exception:  # noqa: BLE001
            return 0.0

    def _to_int(self, value: Any) -> int:
        if value in (None, ""):
            return 0
        try:
            return int(float(str(value).replace(",", ".").strip()))
        except Exception:  # noqa: BLE001
            return 0

    def _to_bool(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "si", "s"}:
            return True
        if text in {"0", "false", "no", "n", ""}:
            return False
        return default

    def _to_date(self, value: Any) -> date | None:
        if value is None or str(value).strip() == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                continue
        try:
            return datetime.fromisoformat(text).date()
        except Exception:
            return None

    def _ensure_audit_tables(self) -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS import_jobs (
                    job_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    profile_key TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    dry_run INTEGER NOT NULL DEFAULT 0,
                    mode TEXT NOT NULL DEFAULT 'upsert',
                    inserted INTEGER NOT NULL DEFAULT 0,
                    updated INTEGER NOT NULL DEFAULT 0,
                    skipped INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'running',
                    actor TEXT NOT NULL DEFAULT '',
                    error_preview TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS idx_import_jobs_created_at
                ON import_jobs (created_at DESC)
                """
            )

    def _create_job(
        self,
        *,
        job_id: str,
        profile_key: str,
        file_path: str,
        dry_run: bool,
        mode: str,
        actor: str,
        started_at: datetime,
    ) -> None:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                INSERT INTO import_jobs (
                    job_id,
                    created_at,
                    profile_key,
                    file_path,
                    dry_run,
                    mode,
                    inserted,
                    updated,
                    skipped,
                    errors,
                    status,
                    actor,
                    error_preview
                )
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 'running', ?, '')
                """,
                (
                    job_id,
                    started_at.isoformat(timespec="seconds"),
                    profile_key,
                    file_path,
                    1 if dry_run else 0,
                    mode,
                    actor,
                ),
            )

    def _finish_job(
        self,
        *,
        job_id: str,
        inserted: int,
        updated: int,
        skipped: int,
        error_count: int,
        status: str,
        finished_at: datetime,
        errors: list[str],
    ) -> None:
        preview = "\n".join(errors[:8])
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                UPDATE import_jobs
                SET
                    finished_at = ?,
                    inserted = ?,
                    updated = ?,
                    skipped = ?,
                    errors = ?,
                    status = ?,
                    error_preview = ?
                WHERE job_id = ?
                """,
                (
                    finished_at.isoformat(timespec="seconds"),
                    inserted,
                    updated,
                    skipped,
                    error_count,
                    status,
                    preview,
                    job_id,
                ),
            )

    def _status_for(self, *, inserted: int, updated: int, skipped: int, error_count: int, elapsed: float) -> str:
        if error_count > 0 and inserted == 0 and updated == 0:
            return "failed"
        if error_count > 0:
            return "partial"
        if inserted == 0 and updated == 0 and skipped > 0:
            return "no_changes"
        if elapsed > 0:
            return "ok"
        return "ok"

