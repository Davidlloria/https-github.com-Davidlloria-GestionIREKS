"""Product-owned catalog maintenance, reusing the existing editors and imports."""
from PySide6.QtWidgets import QDialog, QVBoxLayout

from app.services.warehouse_catalog_service import WarehouseCatalogService
from app.ui.widgets.entity_page import EntityPage


def open_catalog_section(parent, section):
    dialog = QDialog(parent)
    dialog.resize(1100, 750)
    layout = QVBoxLayout(dialog)
    if section == "envases":
        service = WarehouseCatalogService()
        dialog.setWindowTitle("Envases")
        page = EntityPage(title="Envases",
            columns=[("envase_codigo", "Código"), ("envase_nombre", "Nombre")],
            schema=[{"name": "envase_id", "label": "Envase_ID"},
                    {"name": "envase_codigo", "label": "Código"},
                    {"name": "envase_nombre", "label": "Nombre"}],
            list_fn=service.list_envases, create_fn=service.create_envase,
            update_fn=service.update_envase, delete_fn=service.delete_envase,
            include_filters=False, import_fn=service.import_envases, id_attr="envase_id")
    elif section == "referencias":
        from app.ui.widgets.warehouse_page import OtrasReferenciasTab
        dialog.setWindowTitle("Referencias de distribuidores")
        page = OtrasReferenciasTab()
    else:
        raise ValueError("Sección de catálogo desconocida")
    layout.addWidget(page)
    dialog.exec()
