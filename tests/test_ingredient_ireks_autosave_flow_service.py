from __future__ import annotations

from app.services.ingredient_ireks_autosave_flow_service import (
    IngredientIreksAutosaveFlowService,
    IngredientIreksAutosaveRequest,
)


def _make_request(**overrides):
    data = dict(
        row_id=7,
        articulo_id="ART-7",
        articulo_referencia_corta="REF-C",
        articulo_descripcion="Descripcion",
        articulo_referencia="REF-EXT",
        fabricante_id="fab-1",
        articulo_familia_id="fam-1",
        articulo_subfamilia_id="sub-1",
        distribuidor_id="dist-1",
        articulo_envase_id="env-1",
        articulo_contenido_unidad="unidad",
        articulo_envase_cantidad=2.5,
        articulo_envase_peso=1.2,
        articulo_envase_unidad_medida="kg",
        transporte_pallet_tipo="europa",
        transporte_cajas_por_capa=3.0,
        transporte_capas_por_pallet=4.0,
        transporte_observaciones="obs",
        articulo_status_activo=True,
        articulo_status_en_lista=False,
        categoria="harina",
        referencia_distribuidor="DIST-REF",
        descripcion_distribuidor="Distribuidor",
    )
    data.update(overrides)
    return IngredientIreksAutosaveRequest(**data)


def test_autosave_selected_returns_invalid_selection_without_row_id() -> None:
    service = IngredientIreksAutosaveFlowService()
    result = service.autosave_selected(
        _make_request(row_id=0),
        update_product=lambda _row_id, _payload: (_ for _ in ()).throw(AssertionError("no debio guardar")),
        upsert_distributor_reference=lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no debio guardar")),
    )

    assert result.ok is False
    assert result.status == "invalid_selection"
    assert result.message == ""


def test_autosave_selected_builds_payload_and_updates_references() -> None:
    service = IngredientIreksAutosaveFlowService()
    calls: list[tuple[str, object]] = []

    result = service.autosave_selected(
        _make_request(),
        update_product=lambda row_id, payload: calls.append(("update", row_id, payload)),
        upsert_distributor_reference=lambda **kwargs: calls.append(("ref", kwargs)),
    )

    assert result.ok is True
    assert result.status == "saved"
    assert result.payload["articulo_referencia_corta"] == "REF-C"
    assert result.payload["articulo_envase_cantidad"] == 2.5
    assert result.row_updates["transporte_cajas_por_pallet"] == 12.0
    assert result.row_updates["transporte_unidades_por_pallet"] == 30.0
    assert result.row_updates["transporte_kg_por_pallet"] == 36.0
    assert calls[0][0] == "update"
    assert calls[0][1] == 7
    assert calls[0][2]["categoria"] == "harina"
    assert calls[1] == (
        "ref",
        {
            "articulo_id": "ART-7",
            "distribuidor_id": "dist-1",
            "referencia": "DIST-REF",
            "descripcion": "Distribuidor",
        },
    )


def test_autosave_selected_wraps_persistence_errors() -> None:
    service = IngredientIreksAutosaveFlowService()

    result = service.autosave_selected(
        _make_request(),
        update_product=lambda _row_id, _payload: (_ for _ in ()).throw(ValueError("fallo update")),
        upsert_distributor_reference=lambda **_kwargs: None,
    )

    assert result.ok is False
    assert result.status == "error"
    assert "fallo update" in result.message
    assert result.payload["articulo_descripcion"] == "Descripcion"
