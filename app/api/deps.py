from __future__ import annotations

from app.services.contact_service import ContactService
from app.services.course_service import CourseService
from app.services.customer_service import CustomerService
from app.services.api_settings_service import ApiSettingsService
from app.services.ingredient_ireks_service import IngredientIreksService
from app.services.ingredient_std_service import IngredientStdService
from app.services.order_document_import_service import OrderDocumentImportService
from app.services.order_query_service import OrderQueryService
from app.services.order_service import OrderService
from app.services.sales_annual_comparison_service import SalesAnnualComparisonService
from app.services.settings_import_service import SettingsImportService
from app.services.settings_maintenance_service import SettingsMaintenanceService
from app.services.warehouse_inventory_service import WarehouseInventoryService
from app.services.warehouse_movement_service import WarehouseMovementService


def get_customer_service() -> CustomerService:
    return CustomerService()


def get_contact_service() -> ContactService:
    return ContactService()


def get_course_service() -> CourseService:
    return CourseService()


def get_api_settings_service() -> ApiSettingsService:
    return ApiSettingsService()


def get_ingredient_ireks_service() -> IngredientIreksService:
    return IngredientIreksService()


def get_ingredient_std_service() -> IngredientStdService:
    return IngredientStdService()


def get_order_query_service() -> OrderQueryService:
    return OrderQueryService()


def get_order_service() -> OrderService:
    return OrderService()


def get_order_document_import_service() -> OrderDocumentImportService:
    return OrderDocumentImportService()


def get_sales_annual_comparison_service() -> SalesAnnualComparisonService:
    return SalesAnnualComparisonService()


def get_settings_import_service() -> SettingsImportService:
    return SettingsImportService()


def get_settings_maintenance_service() -> SettingsMaintenanceService:
    return SettingsMaintenanceService()


def get_warehouse_inventory_service() -> WarehouseInventoryService:
    return WarehouseInventoryService()


def get_warehouse_movement_service() -> WarehouseMovementService:
    return WarehouseMovementService()
