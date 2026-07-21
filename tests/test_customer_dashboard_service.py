from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from app.models import Cliente, ClienteAgenda, Isla, Provincia
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
                cliente_nombre_comercial="Panadería Norte",
                cliente_direccion_isla_id="isla-1",
                activo=True,
            )
        )
        session.add(
            Cliente(
                cliente_id="cli-2",
                cliente_codigo=202,
                cliente_nombre_comercial="Pastelería Centro",
                cliente_direccion_isla_id="isla-2",
                activo=True,
            )
        )
        session.add(
            Cliente(
                cliente_id="cli-3",
                cliente_codigo=303,
                cliente_nombre_comercial="Cafetería Sur",
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
                detalle="Pendiente de devolución",
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
                detalle="Revisión de lanzamientos",
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
        session.commit()


def test_customer_dashboard_service_builds_snapshot(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'customer-dashboard.db'}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    _seed_customer_dashboard(engine)

    service = CustomerDashboardService(engine=engine)

    snapshot = service.load_snapshot(today=date(2026, 7, 21), horizon_days=7, reactivation_days=30, reactivation_limit=10)

