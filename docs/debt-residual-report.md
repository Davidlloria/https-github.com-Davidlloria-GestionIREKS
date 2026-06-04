# Informe de deuda residual

Fecha de referencia: 2026-06-02.

## Alcance

Basado en:

- [AGENTS.md](./AGENTS.md)
- [migration-roadmap.md](./migration-roadmap.md)
- [migration-history.md](./migration-history.md)

Este informe resume la deuda residual visible en los widgets desktop mas grandes y el retorno esperado de seguir extrayendo logica a servicios o helpers puros.

## Tamano actual

| Archivo | Tamano | Lineas | Metodos aprox. |
|---|---:|---:|---:|
| `app/ui/widgets/orders_page.py` | 138,010 bytes | 2,634 | 105 |
| `app/ui/widgets/settings_page.py` | 107,020 bytes | 2,173 | 97 |
| `app/ui/widgets/ingredients_page.py` | 211,130 bytes | 3,933 | 145 |
| `app/ui/widgets/warehouse_page.py` | 133,714 bytes | 2,533 | 113 |
| `app/ui/widgets/recipes_page.py` | 163,775 bytes | 3,225 | 183 |

## Metodos que siguen usando dependencias sensibles

### `QFileDialog`

- `orders_page.py`: `_export_order_to_excel`, `_import_document_for_selected_order`
- `settings_page.py`: `_backup_db`, `_import_entities`, `_import_ireks_sales_json`, `_import_orders_json_from_settings`, `_pick_orders_historico_dir`, `_preview_igsa_sales_pdf`, `_preview_igsa_sales_workbook`
- `ingredients_page.py`: `_export_product_report_excel`, `_export_product_report_pdf`, `_import_products`
- `warehouse_page.py`: `_export_count_template`, `_export_history_excel`, `_import_count_template`, `_import_entities`
- `recipes_page.py`: `_add_recipe_image`, `_export_pdf`, `_export_pdf_layout`, `_replace_recipe_image`

### `QPrinter`

- `ingredients_page.py`: `_print_product_report`

### `Outlook`

- `orders_page.py`: `_build_ui`, `_send_selected_order_by_outlook`
- `settings_page.py`: `_save_orders_mail_settings`

### `OCR`

- Ninguno de estos cinco archivos usa OCR directamente.
- El riesgo OCR vive en `app/services/order_document_parser.py`.

### Payloads complejos

- `orders_page.py`: `_autosave_selected_order`, `_edit_factura_line`, `_edit_order`, `_edit_order_line`, `_on_pedido_item_cell_changed`, `_send_selected_order_by_outlook`
- `settings_page.py`: `_build_api_tab`, `_build_db_import_tab`, `_build_db_maintenance_tab`, `_build_export_section_tab`, `_build_import_section_tab`, `_build_mail_tab`, `_build_ui`, `_edit_entity`, `_import_entities`, `_import_igsa_sales_pdf_preview`, `_import_igsa_sales_workbook_preview`, `_import_ireks_sales_json`, `_import_orders_json_from_settings`, `_load_orders_import_almacen_combo`, `_new_entity`, `_preview_igsa_sales_pdf`, `_preview_igsa_sales_workbook`, `_refresh_status`, `_save_fatsecret_settings`, `_save_fdc_settings`, `_save_openai_settings`, `_save_orders_mail_settings`, `_show_igsa_book_import_result_dialog`, `_show_igsa_pdf_preview_dialog`, `_show_igsa_workbook_preview_dialog`, `_validate_required`
- `ingredients_page.py`: `__init__`, `_apply_saved_panel_values`, `_auto_recalculate_summary`, `_build_chatgpt_process_prompt`, `_build_elaboration_panel`, `_build_escandallo_panel`, `_build_lines`, `_build_recipe_model`, `_build_ui`, `_collect_images_gallery`, `_delete_recipe`, `_duplicate_recipe`, `_export_excel`, `_export_pdf`, `_export_pdf_extended`, `_export_pdf_layout`, `_export_pdf_simple`, `_flush_autosave`, `_generate_process_with_chatgpt`, `_json_to_string_dict`, `_load_base_recipe_template`, `_load_customers`, `_load_images_gallery`, `_load_process_panel_values`, `_load_recipe`, `_load_recipe_image_gallery`, `_load_std_prices`, `_new_recipe`, `_on_process_changed`, `_on_recipe_selected`, `_on_recipe_tab_changed`, `_open_process_editor_dialog`, `_open_recipe_technical`, `_perform_autosave`, `_pick_customer_filter`, `_recalculate`, `_reload_customer_filter`, `_reload_recipe_list`, `_save_recipe`, `_save_version`, `_scale_recipe`, `_schedule_autosave`, `get_payload`
- `warehouse_page.py`: `_build_envases_tab`, `_build_fabricantes_tab`, `_build_familias_tab`, `_build_subfamilias_tab`, `_build_ui`, `_count_template_mapping`, `_create_envase`, `_create_fabricante`, `_create_familia`, `_create_manual_move`, `_create_subfamilia`, `_edit_manual_move`, `_export_history_excel`, `_import_count_template`, `_import_entities`, `_import_envases`, `_import_fabricantes`, `_import_familias`, `_import_subfamilias`, `_prepare_adjustments`, `_reload_history`, `_reload_history_detail`, `_save_manual_move`, `_update_envase`, `_update_fabricante`, `_update_familia`, `_update_subfamilia`, `reload`
- `recipes_page.py`: `__init__`, `_apply_saved_panel_values`, `_auto_recalculate_summary`, `_build_chatgpt_process_prompt`, `_build_elaboration_panel`, `_build_escandallo_panel`, `_build_lines`, `_build_recipe_model`, `_build_ui`, `_collect_images_gallery`, `_delete_recipe`, `_duplicate_recipe`, `_export_excel`, `_export_pdf`, `_export_pdf_extended`, `_export_pdf_layout`, `_export_pdf_simple`, `_flush_autosave`, `_generate_process_with_chatgpt`, `_json_to_string_dict`, `_load_base_recipe_template`, `_load_customers`, `_load_images_gallery`, `_load_process_panel_values`, `_load_recipe`, `_load_recipe_image_gallery`, `_load_std_prices`, `_new_recipe`, `_on_process_changed`, `_on_recipe_selected`, `_on_recipe_tab_changed`, `_open_process_editor_dialog`, `_open_recipe_technical`, `_perform_autosave`, `_pick_customer_filter`, `_recalculate`, `_reload_customer_filter`, `_reload_recipe_list`, `_save_recipe`, `_save_version`, `_scale_recipe`, `_schedule_autosave`, `get_payload`

### Validaciones de negocio

- `orders_page.py`: alta, edicion, importaciones, borrados, exportacion, envio por Outlook, persistencia y previsualizacion.
- `settings_page.py`: backup, importacion, preview, validaciones de configuracion y guardado de secretos.
- `ingredients_page.py`: validacion de recetas, precios, nutricion, importacion, exportacion e impresion.
- `warehouse_page.py`: validacion de movimientos, inventario, importacion de plantilla y ajustes.
- `recipes_page.py`: validacion de receta, versionado, autosave, exportacion y edicion de procesos.

## Ranking de los 10 bloques con mayor retorno

| Rank | Bloque | Impacto | Motivo |
|---|---|---|---|
| 1 | `orders_page.py` flujo Outlook de envio | Alto | Mezcla seleccion, preparacion, confirmacion y correo local en una sola ruta critica. |
| 2 | `orders_page.py` importacion y exportacion de documentos | Alto | Sigue concentrando rutas locales, validaciones y manejo de archivos de usuario. |
| 3 | `ingredients_page.py` cargadores de nutricion FDC/FatSecret/ChatGPT | Alto | Hay varios flujos externos, dialogos y validaciones en una pantalla muy grande. |
| 4 | `ingredients_page.py` impresion y exportacion de reportes | Alto | `QPrinter` y exportaciones son deuda desktop clara y de alto coste de mantenimiento. |
| 5 | `settings_page.py` backup, importacion y preview de configuracion | Alto | Es P1 y sigue siendo la pantalla mas cargada de orquestacion desktop sensible. |
| 6 | `warehouse_page.py` ajustes manuales de inventario | Medio-Alto | Tiene validacion de negocio real y payloads de movimiento con impacto operativo. |
| 7 | `warehouse_page.py` importacion/exportacion de plantillas e historico | Medio | Mucho archivo local y soporte a inventario, pero ya se extrajo parte del low hanging fruit. |
| 8 | `recipes_page.py` exportacion PDF y gestion de imagenes | Medio | Archivo grande, con rutas locales y UI pesada, pero no es el P1/P2 prioritario. |
| 9 | `recipes_page.py` autosave, versionado y payload de receta | Medio | Costoso, pero el retorno inmediato es menor que en pedidos/configuracion/ingredientes. |
| 10 | `settings_page.py` validaciones y saves de formularios de API | Medio | Aun hay logica, pero varios bloques ya fueron vaciados y el retorno marginal baja. |

## Estimacion de impacto por archivo

- `orders_page.py`: Alto
- `settings_page.py`: Alto
- `ingredients_page.py`: Alto
- `warehouse_page.py`: Medio
- `recipes_page.py`: Medio

## Que no merece la pena tocar ya

- Mas extraccion de etiquetas y literales aislados en `settings_page.py` o `warehouse_page.py` si no reducen una frontera real de logica.
- Helpers de servicio que ya son metadata pura y tienen cobertura de tests.
- Refactors amplios de `recipes_page.py` sin reservar un bloque dedicado.
- Intentar mover OCR desde estos cinco archivos: el problema vive en otra capa.
- Limpieza documental sin cambio funcional asociado.

## Conclusión

La deuda residual mas rentable sigue concentrada en:

1. `orders_page.py`
2. `settings_page.py`
3. `ingredients_page.py`

`warehouse_page.py` y `recipes_page.py` siguen siendo grandes, pero su retorno marginal es menor que el de los tres anteriores.
