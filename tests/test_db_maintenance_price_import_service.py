from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import SQLModel, Session, create_engine

from app.models import MateriaPrimaPrecio, TarifaPrecioIreks
from app.services.db_maintenance_price_import_service import DbMaintenancePriceImportService


@pytest.fixture()
def isolated_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'price-import.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_normalize_tarifa_payload_converts_values() -> None:
    service = DbMaintenancePriceImportService()

    payload = service.normalize_payload(
        "tarifa_precios_ireks",
        {
            "articulo_id": "  art-1  ",
            "tarifa_ano": "2026",
            "precio_fabricante": "12,5",
            "precio_distribuidor": 13,
        },
    )

    assert payload["articulo_id"] == "art-1"
    assert payload["tarifa_ano"] == 2026
    assert payload["precio_fabricante"] == 12.5
    assert payload["precio_distribuidor"] == 13.0


def test_normalize_materia_prima_precio_payload_parses_date() -> None:
    service = DbMaintenancePriceImportService()

    payload = service.normalize_payload(
        "precios_materias_primas",
        {
            "articulo_id": "  mp-1  ",
            "fecha_precio": "12/05/2026",
            "costo_neto": "45,7",
        },
    )

    assert payload["articulo_id"] == "mp-1"
    assert payload["fecha_precio"] == date(2026, 5, 12)
    assert payload["costo_neto"] == 45.7


def test_tarifa_lookup_and_update_flow_uses_existing_match(isolated_session: Session) -> None:
    service = DbMaintenancePriceImportService()
    existing = TarifaPrecioIreks(
        articulo_id="art-1",
        tarifa_ano=2026,
        precio_fabricante=10.0,
        precio_distribuidor=11.0,
    )
    isolated_session.add(existing)
    isolated_session.commit()
    isolated_session.refresh(existing)

    lookup = service.build_lookup(
        session=isolated_session,
        profile_key="tarifa_precios_ireks",
        payloads=[{"articulo_id": "art-1", "tarifa_ano": 2026}],
    )
    match = service.find_match(
        profile_key="tarifa_precios_ireks",
        payload={"articulo_id": "art-1", "tarifa_ano": 2026},
        lookup=lookup,
    )
    assert match is existing
    assert (
        service.find_match(
            profile_key="tarifa_precios_ireks",
            payload={"articulo_id": "art-1", "tarifa_ano": 2025},
            lookup=lookup,
        )
        is None
    )

    changed = service.apply_updates(
        profile_key="tarifa_precios_ireks",
        entity=existing,
        payload={"precio_fabricante": 12.0, "precio_distribuidor": 13.5},
    )
    assert changed is True
    assert existing.precio_fabricante == 12.0
    assert existing.precio_distribuidor == 13.5


def test_materia_prima_precio_lookup_and_insert_updates_lookup(isolated_session: Session) -> None:
    service = DbMaintenancePriceImportService()

    lookup = service.build_lookup(
        session=isolated_session,
        profile_key="precios_materias_primas",
        payloads=[{"articulo_id": "mp-1", "fecha_precio": date(2026, 5, 12)}],
    )
    assert service.find_match(
        profile_key="precios_materias_primas",
        payload={"articulo_id": "mp-1", "fecha_precio": date(2026, 5, 12)},
        lookup=lookup,
    ) is None

    entity = service.create_entity(
        session=isolated_session,
        profile_key="precios_materias_primas",
        payload={"articulo_id": "mp-1", "fecha_precio": date(2026, 5, 12), "costo_neto": 4.25},
    )
    service.update_lookup_after_insert(profile_key="precios_materias_primas", lookup=lookup, entity=entity)
    assert lookup["by_pk"][("mp-1", date(2026, 5, 12))] is entity


def test_profile_key_validation_is_explicit(isolated_session: Session) -> None:
    service = DbMaintenancePriceImportService()

    with pytest.raises(ValueError):
        service.normalize_payload("other", {})

    with pytest.raises(ValueError):
        service.build_lookup(session=isolated_session, profile_key="other", payloads=[])
