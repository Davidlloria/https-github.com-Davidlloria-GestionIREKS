from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from app.models import Cliente
from app.services.customer_service import CustomerService


class CustomersBridge(QObject):
    customersChanged = Signal()
    selectedCustomerChanged = Signal()
    errorChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = CustomerService()
        self._customers: list[dict[str, Any]] = []
        self._selected_customer: dict[str, Any] = {}
        self._error_message = ""

    @Property("QVariantList", notify=customersChanged)
    def customers(self) -> list[dict[str, Any]]:
        return self._customers

    @Property("QVariantMap", notify=selectedCustomerChanged)
    def selectedCustomer(self) -> dict[str, Any]:
        return self._selected_customer

    @Property(str, notify=errorChanged)
    def errorMessage(self) -> str:
        return self._error_message

    @Slot(str)
    def loadCustomers(self, term: str = "") -> None:
        try:
            rows = self._service.list(str(term or "").strip())
            catalogs = self._service.address_catalogs()
            island_names = {str(x.isla_id or ""): str(x.isla_nombre or "") for x in catalogs.islas}
            self._customers = [self._to_item(row, island_names) for row in rows]
            self._error_message = ""
            self.customersChanged.emit()
            self.errorChanged.emit()
        except Exception as exc:  # noqa: BLE001
            self._customers = []
            self._error_message = str(exc)
            self.customersChanged.emit()
            self.errorChanged.emit()

    @Slot(str)
    def selectCustomer(self, customer_id: str) -> None:
        cid = str(customer_id or "").strip()
        self._selected_customer = next((x for x in self._customers if str(x.get("cliente_id", "")) == cid), {})
        self.selectedCustomerChanged.emit()

    @Slot()
    def clearSelection(self) -> None:
        self._selected_customer = {}
        self.selectedCustomerChanged.emit()

    def _to_item(self, row: Cliente, island_names: dict[str, str]) -> dict[str, Any]:
        isla_id = str(getattr(row, "cliente_direccion_isla_id", "") or "").strip()
        return {
            "cliente_id": str(getattr(row, "cliente_id", "") or "").strip(),
            "codigo": int(getattr(row, "cliente_codigo", 0) or 0),
            "nombre": str(getattr(row, "cliente_nombre_comercial", "") or getattr(row, "cliente_nombre_fiscal", "") or "").strip(),
            "telefono": str(getattr(row, "cliente_telefono", "") or "").strip(),
            "cif": str(getattr(row, "cliente_cif", "") or "").strip(),
            "nombre_fiscal": str(getattr(row, "cliente_nombre_fiscal", "") or "").strip(),
            "direccion": str(getattr(row, "cliente_direccion", "") or "").strip(),
            "isla": str(island_names.get(isla_id, "") or "").strip(),
            "isla_id": isla_id,
            "tipo": str(getattr(row, "cliente_tipo", "") or "").strip(),
            "activo": bool(getattr(row, "activo", False)),
        }
