from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from app.models import Cliente, ClienteAgenda, Isla, Provincia, VentaMensualRaw
from app.services.customer_dashboard_service import CustomerDashboardService


def _seed_customer_dashboard(engine) -> None:
    with Session(engine) as session:
        session.add(Provincia(provincia_id="prov-1", provincia_nombre="Las Palmas", provincia_codigo="LP"))
        session.add(Isla(isla_id="isla-1", provincia_id="prov-1", isla_nombre="Gran Canaria", isla_codigo="GC", isla_iniciales="GC"))
        session.add(Isla(isla_id="isla-2", provincia_id="prov-1", isla_nombre="Tenerife", isla_codigo="TF", isla_iniciales="TF"))
        session.add(
            Cliente(
                cliente_id="cli-1",
                cliente_codigo=101,
                cliente_nombre_comercial="Panaderia Norte",
                cliente_direccion_isla_id="isla-1",
                activo=True,
            )
        )
        session.add(
            Cliente(
                cliente_id="cli-2",
                cliente_codigo=202,
                cliente_nombre_comercial="Pasteleria Centro",
                cliente_direccion_isla_id="isla-2",
                activo=True,
            )
        )
        session.add(
            Cliente(
                cliente_id="cli-3",
                cliente_codigo=303,
                cliente_nombre_comercial="Cafeteria Sur",
                cliente_direccion_isla_id="isla-1",
                activo=True,
            )
        )
        session.add(
            Cliente(
                cliente_id="cli-4",
                cliente_codigo=404,
                cliente_nombre_comercial="Cliente inactivo",
                cliente_direccion_isla_id="isla-2",
                activo=False,
            )
        )
        session.add(
            ClienteAgenda(
                agenda_id="ag-1",
                cliente_id="cli-1",
                fecha_actividad=date(2026, 7, 21),
                tipo="seguimiento",
                estado="pendiente",
                resumen="Llamar para revisar pedido",
                detalle="Confirmar necesidades de harina",
                prioridad="alta",
                responsable="Juan",
                created_at=datetime(2026, 7, 21, 8, 0, 0),
                updated_at=datetime(2026, 7, 21, 8, 0, 0),
            )
        )
        session.add(
            ClienteAgenda(
                agenda_id="ag-2",
                cliente_id="cli-1",
                fecha_actividad=date(2026, 7, 19),
                fecha_seguimiento=date(2026, 7, 20),
                tipo="incidencia",
                estado="pendiente",
                resumen="Resolver incidencia",
                detalle="Pendiente de devolucion",
                prioridad="media",
                responsable="Juan",
                created_at=datetime(2026, 7, 19, 9, 0, 0),
                updated_at=datetime(2026, 7, 19, 9, 0, 0),
            )
        )
        session.add(
            ClienteAgenda(
                agenda_id="ag-3",
                cliente_id="cli-2",
                fecha_actividad=date(2026, 7, 21),
                tipo="visita_realizada",
                estado="hecho",
                resumen="Visita completada",
                detalle="Revision de lanzamientos",
                prioridad="normal",
                responsable="Ana",
                created_at=datetime(2026, 7, 21, 10, 0, 0),
                updated_at=datetime(2026, 7, 21, 12, 0, 0),
            )
        )
        session.add(
            ClienteAgenda(
                agenda_id="ag-4",
                cliente_id="cli-2",
                fecha_actividad=date(2026, 7, 22),
                tipo="visita_prevista",
                estado="aplazado",
                resumen="Visita aplazada",
                detalle="Mover a la tarde",
                prioridad="baja",
                responsable="Ana",
                created_at=datetime(2026, 7, 20, 12, 0, 0),
                updated_at=datetime(2026, 7, 20, 12, 0, 0),
            )
        )
        session.add_all(
            [
                VentaMensualRaw(lote_id="lot-1", cliente_id="cli-1", fuente="ireks", periodo="2026-06", venta_kilos=180.0),
                VentaMensualRaw(lote_id="lot-2", cliente_id="cli-1", fuente="ireks", periodo="2026-07", venta_kilos=120.0),
                VentaMensualRaw(lote_id="lot-3", cliente_id="cli-2", fuente="ireks", periodo="2026-06", venta_kilos=60.0),
                VentaMensualRaw(lote_id="lot-4", cliente_id="cli-2", fuente="ireks", periodo="2026-07", venta_kilos=95.0),
                VentaMensualRaw(lote_id="lot-5", cliente_id="cli-3", fuente="ireks", periodo="2026-06", venta_kilos=50.0),
                VentaMensualRaw(lote_id="lot-6", cliente_id="cli-3", fuente="ireks", periodo="2026-07", venta_kilos=20.0),
                VentaMensualRaw(lote_id="lot-7", cliente_id="cli-4", fuente="ireks", periodo="2026-06", venta_kilos=500.0),
                VentaMensualRaw(lote_id="lot-8", cliente_id="cli-4", fuente="ireks", periodo="2026-07", venta_kilos=100.0),
            ]
        )
        session.commit()


def test_customer_dashboard_service_builds_snapshot(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'customer-dashboard.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    _seed_customer_dashboard(engine)

    service = CustomerDashboardService(engine=engine)

    activities = {row.agenda_id: row for row in service.list_all_activities()}
    assert activities["ag-2"].due_date == date(2026, 7, 19)
    assert activities["ag-2"].fecha_seguimiento == date(2026, 7, 20)

    snapshot = service.load_snapshot(today=date(2026, 7, 21), horizon_days=7, reactivation_days=30, reactivation_limit=10)

    assert snapshot.pending_today == 1
    assert snapshot.overdue == 1
    assert snapshot.completed_today == 1
    assert snapshot.customers_without_follow_up == 1
    assert [row.agenda_id for row in snapshot.today_items] == ["ag-1", "ag-3"]
    assert [row.agenda_id for row in snapshot.upcoming_tomorrow] == ["ag-4"]
    assert snapshot.upcoming_next_three_days == []
    assert snapshot.upcoming_week == []
    assert snapshot.reactivation_metric_label == "Variación kg · 2026-06 vs 2026-07"

    assert len(snapshot.reactivation_rows) == 1
    reactivation = snapshot.reactivation_rows[0]
    assert reactivation.cliente_id == "cli-3"
    assert reactivation.cliente_codigo == 303
    assert reactivation.cliente_nombre == "Cafeteria Sur"
    assert reactivation.isla_nombre == "Gran Canaria"
    assert reactivation.last_contact is None
    assert reactivation.previous_kg == 50.0
    assert reactivation.current_kg == 20.0
    assert reactivation.delta_kg == -30.0
    assert reactivation.priority == "Alta"

    assert [row.isla_nombre for row in snapshot.island_rows] == ["Tenerife", "Gran Canaria"]
    island_tenerife = snapshot.island_rows[0]
    assert island_tenerife.pending == 0
    assert island_tenerife.postponed == 1
    assert island_tenerife.completed == 1
    assert island_tenerife.total == 2

    island_gran_canaria = snapshot.island_rows[1]
    assert island_gran_canaria.pending == 1
    assert island_gran_canaria.postponed == 0
    assert island_gran_canaria.completed == 0
    assert island_gran_canaria.total == 1
