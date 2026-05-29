from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
import re
from typing import Any, cast

from sqlmodel import Session, select

from app.core.database import engine
from app.models import (
    Albaran,
    AlbaranItem,
    AlmacenMovimiento,
    Factura,
    FacturaItem,
    IngredienteIreks,
    Pedido,
    PedidoItem,
    PedidoPendiente,
    TarifaPrecioIreks,
)
from app.services.order_document_parser import OrderDocumentParser


@dataclass
class OrderDocumentImportResult:
    imported: int = 0
    errors: list[str] = field(default_factory=list)
    already_imported: bool = False
    message: str = ""


class OrderDocumentImportService:
    def import_albaran_pdf(self, pedido_id: str, source: Path) -> OrderDocumentImportResult:
        header, rows = OrderDocumentParser.parse_albaran_pdf(source)
        return self.import_albaran(pedido_id, header, rows)

    def import_factura_pdf(self, pedido_id: str, source: Path) -> OrderDocumentImportResult:
        header, rows = OrderDocumentParser.parse_factura_pdf(source)
        enriched_rows = self.enrich_factura_rows_from_tarifa(rows)
        return self.import_factura(pedido_id, header, enriched_rows)

    def list_facturas(self, pedido_id: str) -> list[Factura]:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return []
        with Session(engine) as session:
            return list(
                session.exec(
                    select(Factura)
                    .where(Factura.pedido_id == clean_pedido_id)
                    .order_by(Factura.factura_fecha.desc(), Factura.factura_numero)
                )
            )

    def list_factura_items(
        self,
        pedido_id: str,
        factura_id: str = "",
    ) -> tuple[list[tuple[FacturaItem, IngredienteIreks | None]], dict[str, bool]]:
        clean_pedido_id = str(pedido_id or "").strip()
        clean_factura_id = str(factura_id or "").strip()
        if not clean_pedido_id:
            return [], {}
        price_discrepancy_by_item: dict[str, bool] = {}
        with Session(engine) as session:
            query = (
                select(FacturaItem, IngredienteIreks)
                .outerjoin(IngredienteIreks, cast(Any, IngredienteIreks.articulo_id == FacturaItem.articulo_id))
                .where(FacturaItem.pedido_id == clean_pedido_id)
            )
            if clean_factura_id:
                query = query.where(FacturaItem.factura_id == clean_factura_id)
            rows = list(session.exec(query.order_by(FacturaItem.item_id)))
            for item, article in rows:
                item_id = str(getattr(item, "item_id", "") or "").strip()
                articulo_id = str(getattr(item, "articulo_id", "") or "").strip()
                if not item_id or article is None or not articulo_id:
                    continue
                formato_kg = float(getattr(article, "articulo_envase_peso_total", 0.0) or 0.0)
                tarifa_price = self.find_tarifa_price(
                    session,
                    articulo_id,
                    self.parse_date(getattr(item, "factura_fecha", None)).year,
                    formato_kg,
                )
                stored_price = float(getattr(item, "precio_unitario", 0.0) or 0.0)
                price_discrepancy_by_item[item_id] = tarifa_price > 0 and stored_price > 0 and abs(tarifa_price - stored_price) > 0.01
        return rows, price_discrepancy_by_item

    def get_factura_item(self, item_id: str) -> FacturaItem | None:
        clean_item_id = str(item_id or "").strip()
        if not clean_item_id:
            return None
        with Session(engine) as session:
            return session.get(FacturaItem, clean_item_id)

    def update_factura_item(self, item_id: str, payload: dict[str, Any]) -> None:
        clean_item_id = str(item_id or "").strip()
        if not clean_item_id:
            raise ValueError("Línea de factura no válida.")
        with Session(engine) as session:
            item = session.get(FacturaItem, clean_item_id)
            if item is None:
                raise ValueError("Línea de factura no encontrada.")
            for field_name, value in payload.items():
                setattr(item, field_name, value)
            session.add(item)
            factura = session.get(Factura, str(getattr(item, "factura_id", "") or "").strip())
            if factura is not None:
                factura.factura_numero = str(payload.get("factura_numero") or "").strip()
                factura.factura_fecha = payload["factura_fecha"]
                factura.albaran_numero = str(payload.get("albaran_numero") or "").strip()
                session.add(factura)
            session.commit()

    def delete_factura(self, pedido_id: str, factura_id: str) -> None:
        clean_pedido_id = str(pedido_id or "").strip()
        clean_factura_id = str(factura_id or "").strip()
        if not clean_pedido_id or not clean_factura_id:
            raise ValueError("Factura no válida.")
        with Session(engine) as session:
            factura = session.get(Factura, clean_factura_id)
            if factura is None:
                raise ValueError("Factura no encontrada.")
            factura_numero = str(getattr(factura, "factura_numero", "") or "").strip()
            items = list(session.exec(select(FacturaItem).where(FacturaItem.factura_id == clean_factura_id)))
            for item in items:
                session.delete(item)
            session.delete(factura)
            pedido = session.get(Pedido, clean_pedido_id)
            if pedido is not None and factura_numero and str(getattr(pedido, "pedido_factura_numero", "") or "").strip() == factura_numero:
                remaining = session.exec(
                    select(Factura).where(Factura.pedido_id == clean_pedido_id, Factura.factura_id != clean_factura_id)
                ).first()
                pedido.pedido_factura_numero = str(getattr(remaining, "factura_numero", "") or "").strip() if remaining else ""
                session.add(pedido)
            session.commit()

    def repair_albaran_item_mappings_for_order(self, pedido_id: str, albaran_id: str = "") -> None:
        with Session(engine) as session:
            self.repair_albaran_item_mappings(session, pedido_id, albaran_id)

    def is_albaran_item_pending(self, albaran_item_id: str) -> bool:
        clean_item_id = str(albaran_item_id or "").strip()
        if not clean_item_id:
            return False
        with Session(engine) as session:
            row = session.get(AlbaranItem, clean_item_id)
            if row is None:
                return False
            article = session.get(IngredienteIreks, str(getattr(row, "articulo_id", "") or "").strip())
        if article is None:
            return True
        descripcion = str(getattr(article, "articulo_descripcion", "") or "").strip().lower()
        if not descripcion or descripcion.startswith("pendiente"):
            return True
        for field_name in ("fabricante_id", "articulo_envase_id", "articulo_familia_id", "articulo_subfamilia_id"):
            if not str(getattr(article, field_name, "") or "").strip():
                return True
        return False

    def import_albaran(
        self,
        pedido_id: str,
        preview_header: dict[str, str],
        mapped_rows: list[dict[str, Any]],
    ) -> OrderDocumentImportResult:
        result = OrderDocumentImportResult()
        imported_rows = 0

        with Session(engine) as session:
            pedido = session.get(Pedido, pedido_id)
            if pedido is None:
                raise ValueError("El pedido seleccionado ya no existe.")

            preview_albaran_numero = str(preview_header.get("albaran_numero") or "").strip()
            existing_same_number = None
            if preview_albaran_numero:
                existing_same_number = session.exec(
                    select(Albaran).where(
                        Albaran.pedido_id == str(pedido.pedido_id or "").strip(),
                        Albaran.albaran_numero == preview_albaran_numero,
                    )
                ).first()
            if existing_same_number is not None:
                existing_albaran_id = str(getattr(existing_same_number, "albaran_id", "") or "").strip()
                self.repair_albaran_item_mappings(session, str(pedido.pedido_id or "").strip(), existing_albaran_id)
                result.already_imported = True
                result.message = (
                    f"El albaran {preview_albaran_numero} ya estaba importado para este pedido.\n"
                    "No se han creado lineas duplicadas. Se han revisado las equivalencias y entradas de almacen existentes."
                )
                return result

            albaran_header: Albaran | None = None

            def create_row(payload: dict[str, Any]) -> None:
                nonlocal albaran_header, imported_rows
                articulo_codigo = str(payload.get("articulo_codigo") or "").strip()
                if not articulo_codigo:
                    raise ValueError("Campo obligatorio vacio: articulo_codigo")
                albaran_numero = str(payload.get("albaran_numero") or "").strip()
                if not albaran_numero:
                    raise ValueError("Campo obligatorio vacio: albaran_numero")
                albaran_fecha = self.parse_required_date(payload.get("albaran_fecha"), "albaran_fecha")
                pedido_numero_raw = str(payload.get("pedido_numero") or "").strip()
                lote = str(payload.get("articulo_lote") or "").strip()
                caducidad = self.parse_optional_date(payload.get("articulo_caducidad"))
                qty_raw = payload.get("articulo_cantidad")
                kilos_raw = payload.get("articulo_kilos")
                qty_from_file = self.parse_float(qty_raw, default=0.0) if str(qty_raw or "").strip() else 0.0
                kilos_from_file = self.parse_float(kilos_raw, default=0.0) if str(kilos_raw or "").strip() else 0.0

                article = self.find_article_by_code(session, articulo_codigo)
                articulo_id = str(getattr(article, "articulo_id", "") or "").strip() if article else ""

                if albaran_header is None:
                    albaran_header = Albaran(
                        almacen_id=str(pedido.almacen_id or "").strip(),
                        pedido_id=str(pedido.pedido_id or "").strip(),
                        albaran_numero=albaran_numero,
                        albaran_fecha=albaran_fecha,
                    )
                    session.add(albaran_header)
                    if pedido_numero_raw and pedido_numero_raw not in {"0", "0.0"}:
                        pedido.pedido_numero = pedido_numero_raw
                    if not str(pedido.pedido_albaran_numero or "").strip():
                        pedido.pedido_albaran_numero = albaran_numero
                    session.add(pedido)
                    session.flush()
                else:
                    if str(albaran_header.albaran_numero or "").strip() != albaran_numero:
                        raise ValueError("El archivo contiene mas de un albaran_numero")
                    if pedido_numero_raw and pedido_numero_raw not in {"0", "0.0"}:
                        if str(pedido.pedido_numero or "").strip() and str(pedido.pedido_numero or "").strip() != pedido_numero_raw:
                            raise ValueError("El archivo contiene mas de un numero de pedido")

                qty_from_items = session.exec(
                    select(PedidoItem).where(PedidoItem.pedido_id == pedido.pedido_id, PedidoItem.articulo_id == articulo_id)
                ).all()
                qty_items_sum = sum(float(getattr(x, "articulo_cantidad", 0.0) or 0.0) for x in qty_from_items)
                qty_from_kilos = 0.0
                envase_peso_total = float(getattr(article, "articulo_envase_peso_total", 0.0) or 0.0) if article else 0.0
                if kilos_from_file > 0 and envase_peso_total > 0:
                    qty_from_kilos = kilos_from_file / envase_peso_total
                cantidad = qty_from_file if qty_from_file > 0 else (qty_from_kilos if qty_from_kilos > 0 else qty_items_sum)
                if cantidad <= 0:
                    raise ValueError(f"No se pudo resolver cantidad para articulo_id: {articulo_id}")

                albaran_item = AlbaranItem(
                    pedido_id=str(pedido.pedido_id or "").strip(),
                    albaran_id=str(albaran_header.albaran_id or "").strip(),
                    albaran_numero=str(albaran_header.albaran_numero or "").strip(),
                    albaran_fecha=albaran_fecha,
                    articulo_codigo=articulo_codigo,
                    articulo_id=articulo_id,
                    articulo_cantidad=float(cantidad),
                    articulo_lote=lote,
                    articulo_caducidad=caducidad,
                )
                session.add(albaran_item)
                session.flush()
                if article is not None and articulo_id:
                    session.add(
                        AlmacenMovimiento(
                            almacen_id=str(pedido.almacen_id or "").strip(),
                            articulo_id=articulo_id,
                            pedido_numero=str(pedido.pedido_numero or "").strip(),
                            pedido_albaran_numero=str(albaran_header.albaran_numero or "").strip(),
                            cantidad=float(cantidad),
                            articulo_lote=lote,
                            articulo_caducidad=caducidad,
                            fecha_pedido=albaran_fecha,
                            albaran_item_id=str(albaran_item.item_id or "").strip(),
                        )
                    )
                session.commit()
                imported_rows += 1

            for idx, payload in enumerate(mapped_rows, start=2):
                try:
                    self.validate_required_fields(payload, ["albaran_numero", "albaran_fecha", "articulo_codigo"])
                    create_row(payload)
                    result.imported += 1
                except Exception as exc:
                    result.errors.append(f"Fila {idx}: {exc}")
            if imported_rows == 0 and albaran_header is not None:
                session.delete(albaran_header)
                session.commit()
            if imported_rows > 0 and albaran_header is not None:
                self.rebuild_order_pendientes(
                    session,
                    str(pedido.pedido_id or "").strip(),
                    str(albaran_header.albaran_id or "").strip(),
                )
        return result

    def import_factura(
        self,
        pedido_id: str,
        preview_header: dict[str, str],
        mapped_rows: list[dict[str, Any]],
    ) -> OrderDocumentImportResult:
        result = OrderDocumentImportResult()
        imported_rows = 0

        with Session(engine) as session:
            pedido = session.get(Pedido, pedido_id)
            if pedido is None:
                raise ValueError("El pedido seleccionado ya no existe.")

            preview_factura_numero = str(preview_header.get("factura_numero") or "").strip()
            existing_same_number = None
            if preview_factura_numero:
                existing_same_number = session.exec(
                    select(Factura).where(
                        Factura.pedido_id == str(pedido.pedido_id or "").strip(),
                        Factura.factura_numero == preview_factura_numero,
                    )
                ).first()
            if existing_same_number is not None:
                result.already_imported = True
                result.message = f"La factura {preview_factura_numero} ya estaba importada para este pedido. No se han creado líneas duplicadas."
                return result

            factura_header: Factura | None = None

            def create_row(payload: dict[str, Any]) -> None:
                nonlocal factura_header, imported_rows
                articulo_codigo = str(payload.get("articulo_codigo") or "").strip()
                if not articulo_codigo:
                    raise ValueError("Campo obligatorio vacio: articulo_codigo")
                factura_numero = str(payload.get("factura_numero") or "").strip()
                if not factura_numero:
                    raise ValueError("Campo obligatorio vacio: factura_numero")
                factura_fecha = self.parse_required_date(payload.get("factura_fecha"), "factura_fecha")
                albaran_numero = str(payload.get("albaran_numero") or "").strip()
                factura_referencia = str(payload.get("factura_referencia") or "").strip()
                article = self.find_article_by_code(session, articulo_codigo)
                articulo_id = str(getattr(article, "articulo_id", "") or "").strip() if article else ""

                if factura_header is None:
                    factura_header = Factura(
                        almacen_id=str(pedido.almacen_id or "").strip(),
                        pedido_id=str(pedido.pedido_id or "").strip(),
                        factura_numero=factura_numero,
                        factura_fecha=factura_fecha,
                        albaran_numero=albaran_numero,
                        factura_referencia=factura_referencia,
                        total_kilos=OrderDocumentParser.parse_decimal_es(preview_header.get("total_kilos"), 0.0),
                        importe_neto=OrderDocumentParser.parse_decimal_es(preview_header.get("importe_neto"), 0.0),
                        total_factura=OrderDocumentParser.parse_decimal_es(preview_header.get("total_factura"), 0.0),
                    )
                    session.add(factura_header)
                    if not str(pedido.pedido_factura_numero or "").strip():
                        pedido.pedido_factura_numero = factura_numero
                    if albaran_numero and not str(pedido.pedido_albaran_numero or "").strip():
                        pedido.pedido_albaran_numero = albaran_numero
                    session.add(pedido)
                    session.flush()
                else:
                    if str(factura_header.factura_numero or "").strip() != factura_numero:
                        raise ValueError("El archivo contiene mas de un factura_numero")
                    if albaran_numero and str(factura_header.albaran_numero or "").strip() != albaran_numero:
                        raise ValueError("El archivo contiene mas de un albaran_numero")

                uds = OrderDocumentParser.parse_decimal_es(payload.get("articulo_cantidad"), 0.0)
                envase = OrderDocumentParser.parse_decimal_es(payload.get("articulo_envase"), 0.0)
                kilos = OrderDocumentParser.parse_decimal_es(payload.get("articulo_kilos"), 0.0)
                if kilos <= 0 and uds > 0 and envase > 0:
                    kilos = uds * envase
                pdf_price = OrderDocumentParser.parse_decimal_es(payload.get("precio_unitario"), 0.0)
                dto = OrderDocumentParser.parse_decimal_es(payload.get("dto_pct"), 20.0)
                if pdf_price <= 0:
                    pdf_price = self.infer_factura_price_from_total(payload, kilos, dto)
                precio = self.resolve_factura_price(session, article, factura_fecha, pdf_price)
                iva = 0.0
                total_linea = (kilos * precio) * (1.0 - (dto / 100.0)) if kilos > 0 and precio > 0 else 0.0

                session.add(
                    FacturaItem(
                        pedido_id=str(pedido.pedido_id or "").strip(),
                        factura_id=str(factura_header.factura_id or "").strip(),
                        factura_numero=str(factura_header.factura_numero or "").strip(),
                        factura_fecha=factura_fecha,
                        albaran_numero=albaran_numero,
                        articulo_codigo=articulo_codigo,
                        articulo_id=articulo_id,
                        articulo_descripcion=str(payload.get("articulo_descripcion") or "").strip(),
                        articulo_cantidad=uds,
                        articulo_envase=envase,
                        articulo_kilos=kilos,
                        articulo_lote=str(payload.get("articulo_lote") or "").strip(),
                        articulo_caducidad=self.parse_optional_date(payload.get("articulo_caducidad")),
                        precio_unitario=precio,
                        dto_pct=dto,
                        iva_pct=iva,
                        total_linea=total_linea,
                    )
                )
                session.commit()
                imported_rows += 1

            for idx, payload in enumerate(mapped_rows, start=2):
                try:
                    self.validate_required_fields(payload, ["factura_numero", "factura_fecha", "articulo_codigo"])
                    create_row(payload)
                    result.imported += 1
                except Exception as exc:
                    result.errors.append(f"Fila {idx}: {exc}")
            if imported_rows == 0 and factura_header is not None:
                session.delete(factura_header)
                session.commit()
        return result

    def enrich_factura_rows_from_tarifa(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return rows
        enriched: list[dict[str, Any]] = []
        with Session(engine) as session:
            for row in rows:
                payload = dict(row)
                factura_fecha = self.parse_date(payload.get("factura_fecha"))
                article = self.find_article_by_code(session, str(payload.get("articulo_codigo") or "").strip())
                uds = OrderDocumentParser.parse_decimal_es(payload.get("articulo_cantidad"), 0.0)
                envase = OrderDocumentParser.parse_decimal_es(payload.get("articulo_envase"), 0.0)
                kilos = OrderDocumentParser.parse_decimal_es(payload.get("articulo_kilos"), 0.0)
                formato_kg = 0.0
                if article is not None:
                    formato_kg = float(getattr(article, "articulo_envase_peso_total", 0.0) or 0.0)
                    if formato_kg > 0:
                        envase = formato_kg
                if uds <= 0 and envase > 0 and kilos > 0:
                    uds = kilos / envase
                    payload["articulo_cantidad"] = OrderDocumentParser.format_number_es(uds, 0)
                if kilos <= 0 and uds > 0 and envase > 0:
                    kilos = uds * envase
                elif formato_kg > 0 and uds > 0:
                    kilos = uds * formato_kg
                dto = OrderDocumentParser.parse_decimal_es(payload.get("dto_pct"), 20.0)
                pdf_price = OrderDocumentParser.parse_decimal_es(payload.get("precio_unitario"), 0.0)
                if pdf_price <= 0:
                    pdf_price = self.infer_factura_price_from_total(payload, kilos, dto)
                tarifa_price = 0.0
                if article is not None:
                    tarifa_price = self.find_tarifa_price(
                        session,
                        str(getattr(article, "articulo_id", "") or "").strip(),
                        factura_fecha.year,
                        formato_kg,
                    )
                precio = pdf_price if pdf_price > 0 else tarifa_price
                payload["precio_discrepancia"] = tarifa_price > 0 and pdf_price > 0 and abs(tarifa_price - pdf_price) > 0.01
                total_linea = (kilos * precio) * (1.0 - (dto / 100.0)) if kilos > 0 and precio > 0 else 0.0
                if envase > 0:
                    payload["articulo_envase"] = OrderDocumentParser.format_number_es(envase, 2)
                if kilos > 0:
                    payload["articulo_kilos"] = OrderDocumentParser.format_number_es(kilos, 2)
                if precio > 0:
                    payload["precio_unitario"] = OrderDocumentParser.format_number_es(precio, 2)
                payload["dto_pct"] = OrderDocumentParser.format_number_es(dto, 0)
                iva = OrderDocumentParser.parse_decimal_es(payload.get("iva_pct"), 0.0)
                payload["iva_pct"] = OrderDocumentParser.format_number_es(iva, 0)
                if total_linea > 0:
                    payload["total_linea"] = OrderDocumentParser.format_number_es(total_linea, 2)
                enriched.append(payload)
        return enriched

    def repair_albaran_item_mappings(self, session: Session, pedido_id: str, albaran_id: str = "") -> None:
        clean_pedido_id = str(pedido_id or "").strip()
        if not clean_pedido_id:
            return
        pedido = session.get(Pedido, clean_pedido_id)
        if pedido is None:
            return
        query = select(AlbaranItem).where(AlbaranItem.pedido_id == clean_pedido_id)
        clean_albaran_id = str(albaran_id or "").strip()
        if clean_albaran_id:
            query = query.where(AlbaranItem.albaran_id == clean_albaran_id)
        rows = list(session.exec(query))
        touched_albaran_ids: set[str] = set()
        changed = False
        for albaran_item in rows:
            current_articulo_id = str(getattr(albaran_item, "articulo_id", "") or "").strip()
            article = session.get(IngredienteIreks, current_articulo_id) if current_articulo_id else None
            if article is None:
                codigo = str(getattr(albaran_item, "articulo_codigo", "") or "").strip()
                article = self.find_article_by_code(session, codigo)
                current_articulo_id = str(getattr(article, "articulo_id", "") or "").strip() if article else ""
                if not current_articulo_id:
                    continue
                albaran_item.articulo_id = current_articulo_id
                session.add(albaran_item)
                changed = True

            item_id = str(getattr(albaran_item, "item_id", "") or "").strip()
            already_moved = (
                session.exec(select(AlmacenMovimiento).where(AlmacenMovimiento.albaran_item_id == item_id)).first()
                is not None
            )
            cantidad = float(getattr(albaran_item, "articulo_cantidad", 0.0) or 0.0)
            if not already_moved and cantidad > 0 and current_articulo_id:
                albaran = session.get(Albaran, str(getattr(albaran_item, "albaran_id", "") or "").strip())
                session.add(
                    AlmacenMovimiento(
                        almacen_id=str(getattr(pedido, "almacen_id", "") or "").strip(),
                        articulo_id=current_articulo_id,
                        pedido_numero=str(getattr(pedido, "pedido_numero", "") or "").strip(),
                        pedido_albaran_numero=str(getattr(albaran, "albaran_numero", "") or "").strip()
                        if albaran is not None
                        else str(getattr(albaran_item, "albaran_numero", "") or "").strip(),
                        cantidad=cantidad,
                        articulo_lote=str(getattr(albaran_item, "articulo_lote", "") or "").strip(),
                        articulo_caducidad=getattr(albaran_item, "articulo_caducidad", None),
                        fecha_pedido=self.parse_date(getattr(albaran_item, "albaran_fecha", None)),
                        albaran_item_id=item_id,
                    )
                )
                changed = True
            touched_albaran_id = str(getattr(albaran_item, "albaran_id", "") or "").strip()
            if touched_albaran_id:
                touched_albaran_ids.add(touched_albaran_id)
        if not changed:
            return
        session.flush()
        for touched_albaran_id in touched_albaran_ids:
            self.rebuild_order_pendientes(session, clean_pedido_id, touched_albaran_id)
        session.commit()

    def refresh_albaran_item_mapping(self, albaran_item_id: str) -> None:
        with Session(engine) as session:
            albaran_item = session.get(AlbaranItem, albaran_item_id)
            if albaran_item is None:
                raise ValueError("Item de albaran no encontrado.")
            codigo = str(getattr(albaran_item, "articulo_codigo", "") or "").strip()
            if not codigo:
                raise ValueError("El item no tiene codigo de articulo para refrescar.")
            article = self.find_article_by_code(session, codigo)
            if article is None:
                raise ValueError(f"El codigo sigue sin existir en productos: {codigo}")
            articulo_id = str(getattr(article, "articulo_id", "") or "").strip()
            if not articulo_id:
                raise ValueError(f"Articulo sin ID para codigo: {codigo}")
            if str(getattr(albaran_item, "articulo_id", "") or "").strip() != articulo_id:
                albaran_item.articulo_id = articulo_id
                session.add(albaran_item)
                session.flush()

            already_moved = (
                session.exec(
                    select(AlmacenMovimiento).where(AlmacenMovimiento.albaran_item_id == str(albaran_item.item_id or "").strip())
                ).first()
                is not None
            )
            if not already_moved:
                pedido = session.get(Pedido, str(getattr(albaran_item, "pedido_id", "") or "").strip())
                albaran = session.get(Albaran, str(getattr(albaran_item, "albaran_id", "") or "").strip())
                if pedido is None or albaran is None:
                    raise ValueError("No se encontro el pedido/albaran relacionado.")
                cantidad = float(getattr(albaran_item, "articulo_cantidad", 0.0) or 0.0)
                if cantidad <= 0:
                    raise ValueError("El item no tiene cantidad valida para entrada en almacen.")
                session.add(
                    AlmacenMovimiento(
                        almacen_id=str(pedido.almacen_id or "").strip(),
                        articulo_id=articulo_id,
                        pedido_numero=str(pedido.pedido_numero or "").strip(),
                        pedido_albaran_numero=str(albaran.albaran_numero or "").strip(),
                        cantidad=cantidad,
                        articulo_lote=str(getattr(albaran_item, "articulo_lote", "") or "").strip(),
                        articulo_caducidad=getattr(albaran_item, "articulo_caducidad", None),
                        fecha_pedido=self.parse_date(getattr(albaran, "albaran_fecha", None)),
                        albaran_item_id=str(albaran_item.item_id or "").strip(),
                    )
                )
            self.rebuild_order_pendientes(
                session,
                str(getattr(albaran_item, "pedido_id", "") or "").strip(),
                str(getattr(albaran_item, "albaran_id", "") or "").strip(),
            )

    def rebuild_order_pendientes(self, session: Session, pedido_id: str, albaran_id: str) -> None:
        if not pedido_id or not albaran_id:
            return
        pedido = session.get(Pedido, pedido_id)
        if pedido is None:
            return
        almacen_id = str(getattr(pedido, "almacen_id", "") or "").strip()
        if not almacen_id:
            return

        pedidos_almacen = list(
            session.exec(
                select(Pedido)
                .where(Pedido.almacen_id == almacen_id)
                .order_by(cast(Any, Pedido.pedido_fecha), Pedido.pedido_numero, Pedido.pedido_id)
            )
        )
        pedido_ids = [str(getattr(row, "pedido_id", "") or "").strip() for row in pedidos_almacen]
        pedido_ids = [x for x in pedido_ids if x]
        if not pedido_ids:
            return

        existing = list(session.exec(select(PedidoPendiente).where(cast(Any, PedidoPendiente.pedido_id).in_(pedido_ids))))
        for row in existing:
            session.delete(row)
        session.flush()

        ordered_rows = list(session.exec(select(PedidoItem).where(cast(Any, PedidoItem.pedido_id).in_(pedido_ids))))
        ordered_by_article_pedido: dict[str, dict[str, float]] = {}
        for row in ordered_rows:
            row_pedido_id = str(getattr(row, "pedido_id", "") or "").strip()
            articulo_id = str(getattr(row, "articulo_id", "") or "").strip()
            if not row_pedido_id or not articulo_id:
                continue
            by_pedido = ordered_by_article_pedido.setdefault(articulo_id, {})
            by_pedido[row_pedido_id] = by_pedido.get(row_pedido_id, 0.0) + float(getattr(row, "articulo_cantidad", 0.0) or 0.0)

        pedido_order = {pid: idx for idx, pid in enumerate(pedido_ids)}
        stats: dict[tuple[str, str], dict[str, float]] = {}
        open_by_article: dict[str, list[dict[str, float | str]]] = {}
        for articulo_id, by_pedido in ordered_by_article_pedido.items():
            for row_pedido_id in sorted(by_pedido.keys(), key=lambda pid: pedido_order.get(pid, 10**9)):
                ordered_qty = float(by_pedido.get(row_pedido_id, 0.0) or 0.0)
                if ordered_qty <= 1e-9:
                    continue
                stats[(row_pedido_id, articulo_id)] = {"ordered": ordered_qty, "received": 0.0}
                open_by_article.setdefault(articulo_id, []).append({"pedido_id": row_pedido_id, "remaining": ordered_qty})

        received_rows = list(
            session.exec(
                select(AlbaranItem, Albaran)
                .outerjoin(Albaran, cast(Any, Albaran.albaran_id == AlbaranItem.albaran_id))
                .where(cast(Any, AlbaranItem.pedido_id).in_(pedido_ids))
                .order_by(cast(Any, Albaran.albaran_fecha), Albaran.albaran_numero, AlbaranItem.item_id)
            )
        )
        excess_by_pedido_article: dict[tuple[str, str], float] = {}
        for albaran_item, _albaran in received_rows:
            source_pedido_id = str(getattr(albaran_item, "pedido_id", "") or "").strip()
            articulo_id = str(getattr(albaran_item, "articulo_id", "") or "").strip()
            cantidad = float(getattr(albaran_item, "articulo_cantidad", 0.0) or 0.0)
            if not source_pedido_id or not articulo_id or cantidad <= 1e-9:
                continue
            pending_queue = open_by_article.get(articulo_id, [])
            remaining = cantidad
            while remaining > 1e-9 and pending_queue:
                target = pending_queue[0]
                target_pedido_id = str(target.get("pedido_id") or "").strip()
                target_remaining = float(target.get("remaining", 0.0) or 0.0)
                if target_remaining <= 1e-9:
                    pending_queue.pop(0)
                    continue
                applied = min(target_remaining, remaining)
                stats[(target_pedido_id, articulo_id)]["received"] += applied
                target["remaining"] = target_remaining - applied
                remaining -= applied
                if float(target["remaining"] or 0.0) <= 1e-9:
                    pending_queue.pop(0)
            if remaining > 1e-9:
                key = (source_pedido_id, articulo_id)
                excess_by_pedido_article[key] = excess_by_pedido_article.get(key, 0.0) + remaining

        for (row_pedido_id, articulo_id), values in stats.items():
            cantidad_pedida = float(values["ordered"] or 0.0)
            cantidad_recibida = float(values["received"] or 0.0)
            cantidad_pendiente = cantidad_pedida - cantidad_recibida
            if cantidad_pendiente <= 1e-9:
                continue
            session.add(
                PedidoPendiente(
                    pedido_id=row_pedido_id,
                    albaran_id=albaran_id,
                    articulo_id=articulo_id,
                    cantidad_pedida=cantidad_pedida,
                    cantidad_recibida=cantidad_recibida,
                    cantidad_pendiente=cantidad_pendiente,
                    estado="pendiente",
                )
            )

        for (source_pedido_id, articulo_id), exceso_qty in excess_by_pedido_article.items():
            if exceso_qty <= 1e-9:
                continue
            session.add(
                PedidoPendiente(
                    pedido_id=source_pedido_id,
                    albaran_id=albaran_id,
                    articulo_id=articulo_id,
                    cantidad_pedida=0.0,
                    cantidad_recibida=exceso_qty,
                    cantidad_pendiente=-exceso_qty,
                    estado="exceso",
                )
            )
        session.commit()

    def find_article_by_code(self, session: Session, codigo: str) -> IngredienteIreks | None:
        candidates = OrderDocumentParser.article_code_candidates(codigo)
        if not candidates:
            return None
        return session.exec(
            select(IngredienteIreks).where(
                cast(Any, IngredienteIreks.articulo_referencia).in_(candidates)
                | cast(Any, IngredienteIreks.articulo_referencia_corta).in_(candidates)
            )
        ).first()

    def resolve_factura_price(
        self,
        session: Session,
        article: IngredienteIreks | None,
        factura_fecha: date,
        pdf_price: float,
    ) -> float:
        fallback_price = float(pdf_price or 0.0)
        if fallback_price > 0:
            return fallback_price
        if article is None:
            return 0.0
        articulo_id = str(getattr(article, "articulo_id", "") or "").strip()
        if not articulo_id:
            return 0.0
        tarifa_ano = int(getattr(factura_fecha, "year", date.today().year) or date.today().year)
        formato_kg = float(getattr(article, "articulo_envase_peso_total", 0.0) or 0.0)
        tarifa_price = self.find_tarifa_price(session, articulo_id, tarifa_ano, formato_kg)
        if tarifa_price > 0:
            return tarifa_price
        return fallback_price

    def find_tarifa_price(self, session: Session, articulo_id: str, tarifa_ano: int, formato_kg: float) -> float:
        clean_articulo_id = str(articulo_id or "").strip()
        if not clean_articulo_id:
            return 0.0
        tarifa = session.exec(
            select(TarifaPrecioIreks)
            .where(TarifaPrecioIreks.articulo_id == clean_articulo_id, TarifaPrecioIreks.tarifa_ano == tarifa_ano)
            .order_by(cast(Any, TarifaPrecioIreks.id).desc())
        ).first()
        if tarifa is None:
            tarifa = session.exec(
                select(TarifaPrecioIreks)
                .where(TarifaPrecioIreks.articulo_id == clean_articulo_id, TarifaPrecioIreks.tarifa_ano <= tarifa_ano)
                .order_by(cast(Any, TarifaPrecioIreks.tarifa_ano).desc(), cast(Any, TarifaPrecioIreks.id).desc())
            ).first()
        if tarifa is None:
            tarifa = session.exec(
                select(TarifaPrecioIreks)
                .where(TarifaPrecioIreks.articulo_id == clean_articulo_id)
                .order_by(cast(Any, TarifaPrecioIreks.tarifa_ano).desc(), cast(Any, TarifaPrecioIreks.id).desc())
            ).first()
        if tarifa is not None:
            precio = float(getattr(tarifa, "precio_fabricante", 0.0) or 0.0)
            if precio <= 0:
                precio = float(getattr(tarifa, "precio_distribuidor", 0.0) or 0.0)
            if precio > 0:
                return precio / formato_kg if formato_kg > 0 else precio
        return 0.0

    def infer_factura_price_from_total(self, payload: dict[str, Any], kilos: float, dto: float) -> float:
        total_pdf = OrderDocumentParser.parse_decimal_es(payload.get("total_linea"), 0.0)
        factor = 1.0 - (float(dto or 0.0) / 100.0)
        if total_pdf <= 0 or kilos <= 0 or factor <= 0:
            return 0.0
        return total_pdf / (kilos * factor)

    @staticmethod
    def validate_required_fields(payload: dict[str, Any], required: list[str]) -> None:
        for field_name in required:
            if not str(payload.get(field_name) or "").strip():
                raise ValueError(f"Campo obligatorio vacio: {field_name}")

    @staticmethod
    def parse_float(value: object, default: float = 0.0) -> float:
        text_value = str(value or "").strip()
        if not text_value:
            return default
        try:
            return float(text_value.replace(",", "."))
        except Exception:
            return default

    @staticmethod
    def try_parse_date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        if value is not None:
            as_text = str(value).strip()
            if re.fullmatch(r"\d+([.,]\d+)?", as_text):
                try:
                    serial = float(as_text.replace(",", "."))
                    if serial > 0:
                        return datetime.fromordinal(date(1899, 12, 30).toordinal() + int(serial)).date()
                except Exception:
                    pass

            to_py = getattr(value, "to_pydatetime", None)
            if callable(to_py):
                try:
                    dt = to_py()
                    if isinstance(dt, datetime):
                        return dt.date()
                except Exception:
                    pass

        text_value = str(value or "").strip()
        for fmt in (
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
            "%d/%m/%y",
            "%d-%m-%y",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return datetime.strptime(text_value, fmt).date()
            except Exception:
                continue
        return None

    def parse_date(self, value: object) -> date:
        parsed = self.try_parse_date(value)
        if parsed is not None:
            return parsed
        return date.today()

    def parse_optional_date(self, value: object) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        return self.try_parse_date(value)

    def parse_required_date(self, value: object, field_name: str) -> date:
        parsed = self.try_parse_date(value)
        if parsed is None:
            raise ValueError(f"Formato de fecha invalido en {field_name}: {value}")
        return parsed
