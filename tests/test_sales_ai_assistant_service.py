from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel, Session, create_engine

import app.services.sales_annual_comparison_service as sales_annual_service_module
from app.models import Cliente, Fabricante, Familia, IngredienteIreks, Subfamilia, VentaMensualRaw
from app.services.sales_ai_assistant_service import (
    SalesQueryAssistantService,
    SalesQueryIntent,
    SalesQueryIntentResult,
)
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService


@pytest.fixture()
def isolated_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sales-ai.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(sales_annual_service_module, "engine", engine)
    return engine


def _seed_sales(session: Session) -> tuple[str, str, str, str, str]:
    cliente_id = "cli-igsa"
    fabricante_id = "fab-1"
    familia_id = "fam-1"
    subfamilia_id = "sub-1"
    articulo_id = "art-mella"
    articulo_id_plus = "art-plus"
    session.add(Cliente(cliente_id=cliente_id, cliente_codigo=91, cliente_nombre_comercial="IGSA", cliente_tipo="distribuidor"))
    session.add(Fabricante(fabricante_id=fabricante_id, fabricante_codigo=1, fabricante_nombre="Fabricante"))
    session.add(
        Familia(
            articulo_familia_id=familia_id,
            fabricante_id=fabricante_id,
            articulo_familia_nombre="Familia",
            articulo_familia_codigo="F1",
        )
    )
    session.add(
        Subfamilia(
            articulo_familia_id=familia_id,
            articulo_subfamilia_id=subfamilia_id,
            articulo_subfamilia_nombre="Subfamilia",
            articulo_subfamilia_codigo="S1",
        )
    )
    session.add(
        IngredienteIreks(
            articulo_id=articulo_id,
            almacen_id="alm-1",
            fabricante_id=fabricante_id,
            articulo_referencia="MM01",
            articulo_referencia_corta="MM01",
            articulo_descripcion="MELLA MUFFIN",
            articulo_envase_peso=1.0,
            articulo_envase_peso_total=1.0,
            articulo_familia_id=familia_id,
            articulo_subfamilia_id=subfamilia_id,
        )
    )
    session.add(
        IngredienteIreks(
            articulo_id=articulo_id_plus,
            almacen_id="alm-1",
            fabricante_id=fabricante_id,
            articulo_referencia="MP01",
            articulo_referencia_corta="MP01",
            articulo_descripcion="MUFFIN PLUS",
            articulo_envase_peso=1.0,
            articulo_envase_peso_total=1.0,
            articulo_familia_id=familia_id,
            articulo_subfamilia_id=subfamilia_id,
        )
    )
    session.add(
        VentaMensualRaw(
            raw_id="raw-1",
            lote_id="lote-1",
            fuente="ireks",
            cliente_id=cliente_id,
            periodo="2025-07",
            articulo_codigo_origen="MM01",
            articulo_id=articulo_id,
            articulo_descripcion_origen="MELLA MUFFIN",
            venta_kilos=12.0,
            venta_kilos_sc=3.0,
            venta_euros=25.0,
        )
    )
    session.add(
        VentaMensualRaw(
            raw_id="raw-2",
            lote_id="lote-2",
            fuente="ireks",
            cliente_id=cliente_id,
            periodo="2026-07",
            articulo_codigo_origen="MM01",
            articulo_id=articulo_id,
            articulo_descripcion_origen="MELLA MUFFIN",
            venta_kilos=18.5,
            venta_kilos_sc=1.5,
            venta_euros=31.0,
        )
    )
    session.add(
        VentaMensualRaw(
            raw_id="raw-3",
            lote_id="lote-3",
            fuente="ireks",
            cliente_id=cliente_id,
            periodo="2026-07",
            articulo_codigo_origen="MP01",
            articulo_id=articulo_id_plus,
            articulo_descripcion_origen="MUFFIN PLUS",
            venta_kilos=25.0,
            venta_kilos_sc=2.0,
            venta_euros=41.0,
        )
    )
    session.add(
        VentaMensualRaw(
            raw_id="raw-4",
            lote_id="lote-4",
            fuente="ireks",
            cliente_id=cliente_id,
            periodo="2025-07",
            articulo_codigo_origen="MP01",
            articulo_id=articulo_id_plus,
            articulo_descripcion_origen="MUFFIN PLUS",
            venta_kilos=10.0,
            venta_kilos_sc=1.0,
            venta_euros=16.0,
        )
    )
    session.commit()
    return cliente_id, fabricante_id, familia_id, subfamilia_id, articulo_id


def test_listar_detalle_ventas_filters_by_client_and_product_text(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        cliente_id, fabricante_id, familia_id, subfamilia_id, articulo_id = _seed_sales(session)

    service = SalesAnnualComparisonService()
    rows = service.listar_detalle_ventas(
        year=2025,
        month=7,
        cliente_texto="igsa",
        producto_texto="mella muffin",
        fabricante_id=fabricante_id,
        familia_id=familia_id,
        subfamilia_id=subfamilia_id,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.cliente_id == cliente_id
    assert row.articulo_id == articulo_id
    assert row.codigo == "MM01"
    assert row.nombre == "MELLA MUFFIN"
    assert row.kilos == pytest.approx(12.0)
    assert row.sc == pytest.approx(3.0)
    assert row.ventas == pytest.approx(25.0)


def test_sales_assistant_uses_detail_rows_for_specific_query(isolated_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    with Session(isolated_engine) as session:
        _seed_sales(session)

    assistant = SalesQueryAssistantService(sales_service=SalesAnnualComparisonService(), api_key="")
    captured: dict[str, str] = {}

    def fake_generate(prompt: str):
        captured["prompt"] = prompt
        return type("Result", (), {"ok": True, "text": "Respuesta final", "message": "ok"})()

    monkeypatch.setattr(assistant.answer_service, "generate_process", fake_generate)
    monkeypatch.setattr(
        assistant,
        "interpret",
        lambda question, defaults=None: SalesQueryIntentResult(
            True,
            SalesQueryIntent(
                query_type="detalle",
                year=2025,
                month=7,
                cliente_texto="IGSA",
                producto_texto="MELLA MUFFIN",
                limit=20,
            ),
            "ok",
            False,
        ),
    )

    result = assistant.answer(
        "dime las ventas de mella muffin de julio de 2025 del cliente igsa",
        defaults={"year": 2026, "month": 5, "acumulado": False},
    )

    assert result.ok is True
    assert result.text == "Respuesta final"
    assert "MELLA MUFFIN" in captured["prompt"]
    assert "IGSA" in captured["prompt"]
    assert "2025-07" in captured["prompt"]


def test_sales_assistant_uses_comparative_detail_rows_for_years(isolated_engine, monkeypatch: pytest.MonkeyPatch) -> None:
    with Session(isolated_engine) as session:
        _seed_sales(session)

    assistant = SalesQueryAssistantService(sales_service=SalesAnnualComparisonService(), api_key="")
    captured: dict[str, str] = {}

    def fake_generate(prompt: str):
        captured["prompt"] = prompt
        return type("Result", (), {"ok": True, "text": "Comparativa final", "message": "ok"})()

    monkeypatch.setattr(assistant.answer_service, "generate_process", fake_generate)
    monkeypatch.setattr(
        assistant,
        "interpret",
        lambda question, defaults=None: SalesQueryIntentResult(
            True,
            SalesQueryIntent(
                query_type="comparativa",
                year=2025,
                year_compare=2026,
                month=7,
                cliente_texto="IGSA",
                producto_texto="MELLA MUFFIN",
                limit=20,
            ),
            "ok",
            False,
        ),
    )

    result = assistant.answer(
        "dime las ventas en kg de mella muffin de julio de 2025 comparadas con las de 2026 del mismo mes del cliente igsa",
        defaults={"year": 2026, "month": 7, "acumulado": False},
    )

    assert result.ok is True
    assert "Año 2025" in result.text
    assert "Año 2026" in result.text
    assert "Diferencia 2026 vs 2025" in result.text


def test_sales_assistant_fallback_marks_comparative_queries(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        _seed_sales(session)

    assistant = SalesQueryAssistantService(sales_service=SalesAnnualComparisonService(), api_key="")
    assistant.api_key = ""
    intent_result = assistant.interpret(
        "dime las ventas en kg de mella muffin de julio de 2025 comparadas con las de 2026 del mismo mes del cliente igsa",
        defaults={"year": 2026, "month": 7},
    )

    assert intent_result.ok is True
    assert intent_result.intent.query_type == "comparativa"
    assert intent_result.intent.year == 2025
    assert intent_result.intent.year_compare == 2026
    assert intent_result.intent.month == 7


def test_listar_ranking_anual_orders_by_current_year_kilos(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        _seed_sales(session)

    service = SalesAnnualComparisonService()
    rows = service.listar_ranking_anual(year=2026, acumulado=True, cliente_id="cli-igsa", limit=10)

    assert len(rows) >= 2
    assert rows[0].nombre == "MUFFIN PLUS"
    assert rows[1].nombre == "MELLA MUFFIN"
    assert (rows[0].kilos_curr + rows[0].sc_curr) > (rows[1].kilos_curr + rows[1].sc_curr)


def test_sales_assistant_returns_deterministic_ranking(isolated_engine) -> None:
    with Session(isolated_engine) as session:
        _seed_sales(session)

    assistant = SalesQueryAssistantService(sales_service=SalesAnnualComparisonService(), api_key="")
    result = assistant.answer(
        "dame el ranking de ventas en kg acumulado del 2026, del cliente igsa, ordenados de mayor a menos",
        defaults={"year": 2026, "acumulado": True, "cliente_texto": "IGSA"},
    )

    assert result.ok is True
    assert "Ranking de ventas en kg acumulado 2026" in result.text
    assert "MUFFIN PLUS" in result.text
    assert "MELLA MUFFIN" in result.text
    assert result.text.index("1. MUFFIN PLUS") < result.text.index("2. MELLA MUFFIN")
