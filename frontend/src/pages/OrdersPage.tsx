import { useCallback, useMemo, useState } from 'react'
import {
  createOrder,
  createOrderItem,
  deleteOrder,
  deleteOrderItem,
  getOrderDetail,
  importOrderAlbaranPdfUpload,
  importOrderFacturaPdfUpload,
  importOrderJsonUpload,
  listOrderItems,
  listOrderPending,
  listOrders,
  updateOrder,
  updateOrderItem,
} from '../api/orders'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { OrderItemRead, OrderListItem, OrderPendingRead, OrderRead } from '../types/api'

interface OrderDetailPayload {
  detail: OrderRead | null
  items: OrderItemRead[]
  pending: OrderPendingRead[]
}

const EMPTY_ORDER_DETAIL: OrderDetailPayload = {
  detail: null,
  items: [],
  pending: [],
}

const PAGE_SIZE = 50

function todayIsoDate() {
  const now = new Date()
  const year = now.getFullYear()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

function safeNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

export function OrdersPage() {
  const [year, setYear] = useState('')
  const [monthFrom, setMonthFrom] = useState('')
  const [monthTo, setMonthTo] = useState('')
  const [almacenId, setAlmacenId] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [selectedOrderItemId, setSelectedOrderItemId] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteMessage, setDeleteMessage] = useState('')
  const [deleteError, setDeleteError] = useState('')
  const [lineArticuloId, setLineArticuloId] = useState('')
  const [lineCantidad, setLineCantidad] = useState('')
  const [lineSaveLoading, setLineSaveLoading] = useState(false)
  const [lineDeleteLoading, setLineDeleteLoading] = useState(false)
  const [lineMessage, setLineMessage] = useState('')
  const [lineError, setLineError] = useState('')
  const [createAlmacenId, setCreateAlmacenId] = useState('')
  const [createPedidoFecha, setCreatePedidoFecha] = useState(todayIsoDate())
  const [createPedidoNumero, setCreatePedidoNumero] = useState('')
  const [createPending, setCreatePending] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [createMessage, setCreateMessage] = useState('')
  const [createError, setCreateError] = useState('')
  const [headerTargetOrderId, setHeaderTargetOrderId] = useState('')
  const [headerPedidoFecha, setHeaderPedidoFecha] = useState('')
  const [headerPedidoNumero, setHeaderPedidoNumero] = useState('')
  const [headerSubmitMode, setHeaderSubmitMode] = useState<'normal' | 'pendiente'>('normal')
  const [headerSaveLoading, setHeaderSaveLoading] = useState(false)
  const [headerSaveMessage, setHeaderSaveMessage] = useState('')
  const [headerSaveError, setHeaderSaveError] = useState('')
  const [importJsonAlmacenId, setImportJsonAlmacenId] = useState('')
  const [importJsonFile, setImportJsonFile] = useState<File | null>(null)
  const [importJsonLoading, setImportJsonLoading] = useState(false)
  const [importJsonMessage, setImportJsonMessage] = useState('')
  const [importJsonError, setImportJsonError] = useState('')
  const [importPdfFile, setImportPdfFile] = useState<File | null>(null)
  const [importPdfType, setImportPdfType] = useState<'albaran' | 'factura'>('albaran')
  const [importPdfLoading, setImportPdfLoading] = useState(false)
  const [importPdfMessage, setImportPdfMessage] = useState('')
  const [importPdfError, setImportPdfError] = useState('')

  const offset = pageIndex * PAGE_SIZE
  const ordersQuery = useAsyncResource(
    () =>
      listOrders({
        year,
        monthFrom: monthFrom ? Number(monthFrom) : undefined,
        monthTo: monthTo ? Number(monthTo) : undefined,
        almacenId,
        limit: PAGE_SIZE,
        offset,
      }),
    { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
    [year, monthFrom, monthTo, almacenId, offset],
  )
  const orderRows = ordersQuery.data.items

  const selectedOrder = useMemo(() => {
    if (!orderRows.length) {
      return null as OrderListItem | null
    }
    const explicit = orderRows.find((row) => row.pedido_id === selectedCandidateId)
    return explicit ?? orderRows[0]
  }, [orderRows, selectedCandidateId])

  const loadSelectedOrder = useCallback(() => {
    if (!selectedOrder) {
      return Promise.resolve(EMPTY_ORDER_DETAIL)
    }
    return Promise.all([
      getOrderDetail(selectedOrder.pedido_id),
      listOrderItems(selectedOrder.pedido_id, 500, 0),
      listOrderPending(selectedOrder.pedido_id, 500, 0),
    ]).then(([detail, items, pending]) => ({ detail, items: items.items, pending: pending.items }))
  }, [selectedOrder])

  const detailQuery = useAsyncResource(loadSelectedOrder, EMPTY_ORDER_DETAIL, [loadSelectedOrder, selectedOrder?.pedido_id])

  const totals = useMemo(() => {
    const withAlbaran = orderRows.filter((row) => !!row.pedido_albaran_numero).length
    const withFactura = orderRows.filter((row) => !!row.pedido_factura_numero).length
    const totalKg = orderRows.reduce((acc, row) => acc + safeNumber(row.total_kg), 0)
    return {
      total: ordersQuery.data.total,
      withAlbaran,
      withFactura,
      totalKg: totalKg.toFixed(2),
    }
  }, [orderRows, ordersQuery.data.total])

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + orderRows.length < ordersQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(ordersQuery.data.total / PAGE_SIZE))

  const selectedOrderItem = useMemo(
    () => detailQuery.data.items.find((item) => item.item_id === selectedOrderItemId) ?? null,
    [detailQuery.data.items, selectedOrderItemId],
  )

  const effectiveHeaderValues = useMemo(() => {
    const detail = detailQuery.data.detail
    if (!detail) {
      return {
        pedidoFecha: '',
        pedidoNumero: '',
        submitMode: 'normal' as const,
      }
    }
    if (headerTargetOrderId !== detail.pedido_id) {
      return {
        pedidoFecha: detail.pedido_fecha || '',
        pedidoNumero: detail.pedido_numero || '',
        submitMode: detail.pedido_estado === 'P' ? ('pendiente' as const) : ('normal' as const),
      }
    }
    return {
      pedidoFecha: headerPedidoFecha,
      pedidoNumero: headerPedidoNumero,
      submitMode: headerSubmitMode,
    }
  }, [detailQuery.data.detail, headerPedidoFecha, headerPedidoNumero, headerSubmitMode, headerTargetOrderId])

  const deleteSelectedOrder = async () => {
    if (!selectedOrder || deleteLoading) {
      return
    }
    const confirmed = window.confirm(
      `Se eliminara el pedido ${selectedOrder.pedido_numero || selectedOrder.pedido_id}. Esta accion no se puede deshacer.`,
    )
    if (!confirmed) {
      return
    }
    setDeleteLoading(true)
    setDeleteMessage('')
    setDeleteError('')
    try {
      await deleteOrder(selectedOrder.pedido_id)
      setSelectedCandidateId('')
      await ordersQuery.reload()
      setDeleteMessage('Pedido eliminado correctamente.')
    } catch (error: unknown) {
      setDeleteError(error instanceof Error ? error.message : 'No se pudo eliminar el pedido.')
    } finally {
      setDeleteLoading(false)
    }
  }

  const saveOrderHeader = async () => {
    const detail = detailQuery.data.detail
    if (!detail || headerSaveLoading) {
      return
    }
    if (!effectiveHeaderValues.pedidoFecha) {
      setHeaderSaveError('La fecha del pedido es obligatoria.')
      setHeaderSaveMessage('')
      return
    }
    const lines = detailQuery.data.items.map((item) => ({
      articulo_id: item.articulo_id,
      uds: safeNumber(item.articulo_cantidad),
    }))
    setHeaderSaveLoading(true)
    setHeaderSaveError('')
    setHeaderSaveMessage('')
    try {
      const updated = await updateOrder(detail.pedido_id, {
        pedido_fecha: effectiveHeaderValues.pedidoFecha,
        pedido_numero: effectiveHeaderValues.pedidoNumero.trim(),
        lines,
        submit_mode: effectiveHeaderValues.submitMode === 'pendiente' ? 'pendiente' : '',
      })
      setHeaderTargetOrderId(updated.pedido_id)
      setHeaderPedidoFecha(updated.pedido_fecha || '')
      setHeaderPedidoNumero(updated.pedido_numero || '')
      setHeaderSubmitMode(updated.pedido_estado === 'P' ? 'pendiente' : 'normal')
      await Promise.all([ordersQuery.reload(), detailQuery.reload()])
      setHeaderSaveMessage('Cabecera de pedido actualizada correctamente.')
    } catch (error: unknown) {
      setHeaderSaveError(error instanceof Error ? error.message : 'No se pudo actualizar la cabecera del pedido.')
    } finally {
      setHeaderSaveLoading(false)
    }
  }

  const onSelectOrderItem = (item: OrderItemRead) => {
    setSelectedOrderItemId(item.item_id)
    setLineArticuloId(item.articulo_id || '')
    setLineCantidad(String(item.articulo_cantidad ?? 0))
    setLineMessage('')
    setLineError('')
  }

  const resetOrderItemForm = () => {
    setSelectedOrderItemId('')
    setLineArticuloId('')
    setLineCantidad('')
  }

  const saveOrderItem = async () => {
    if (!selectedOrder || lineSaveLoading || lineDeleteLoading) {
      return
    }
    const articuloId = lineArticuloId.trim()
    const cantidad = Number.parseFloat(lineCantidad.replace(',', '.'))
    if (!articuloId) {
      setLineError('Debes indicar articulo_id.')
      setLineMessage('')
      return
    }
    if (!Number.isFinite(cantidad) || cantidad <= 0) {
      setLineError('La cantidad debe ser un numero mayor que 0.')
      setLineMessage('')
      return
    }
    setLineSaveLoading(true)
    setLineMessage('')
    setLineError('')
    try {
      const payload = { articulo_id: articuloId, articulo_cantidad: cantidad }
      const saved = selectedOrderItem
        ? await updateOrderItem(selectedOrderItem.item_id, payload)
        : await createOrderItem(selectedOrder.pedido_id, payload)
      setSelectedOrderItemId(saved.item_id)
      setLineArticuloId(saved.articulo_id)
      setLineCantidad(String(saved.articulo_cantidad))
      await detailQuery.reload()
      setLineMessage(selectedOrderItem ? 'Linea actualizada correctamente.' : 'Linea creada correctamente.')
    } catch (error: unknown) {
      setLineError(error instanceof Error ? error.message : 'No se pudo guardar la linea de pedido.')
    } finally {
      setLineSaveLoading(false)
    }
  }

  const deleteSelectedOrderItem = async () => {
    if (!selectedOrderItem || lineDeleteLoading || lineSaveLoading) {
      return
    }
    const confirmed = window.confirm('Se eliminara la linea seleccionada del pedido. Esta accion no se puede deshacer.')
    if (!confirmed) {
      return
    }
    setLineDeleteLoading(true)
    setLineMessage('')
    setLineError('')
    try {
      await deleteOrderItem(selectedOrderItem.item_id)
      resetOrderItemForm()
      await detailQuery.reload()
      setLineMessage('Linea eliminada correctamente.')
    } catch (error: unknown) {
      setLineError(error instanceof Error ? error.message : 'No se pudo eliminar la linea de pedido.')
    } finally {
      setLineDeleteLoading(false)
    }
  }

  const createNewOrder = async () => {
    if (createLoading) {
      return
    }
    if (!createAlmacenId.trim()) {
      setCreateError('Debes indicar almacen_id para crear el pedido.')
      setCreateMessage('')
      return
    }
    if (!createPedidoFecha) {
      setCreateError('Debes indicar la fecha del pedido.')
      setCreateMessage('')
      return
    }
    setCreateLoading(true)
    setCreateError('')
    setCreateMessage('')
    try {
      const created = await createOrder({
        almacen_id: createAlmacenId.trim(),
        pedido_fecha: createPedidoFecha,
        pedido_numero: createPedidoNumero.trim(),
        lines: [],
        is_pending: createPending,
      })
      await ordersQuery.reload()
      setSelectedCandidateId(created.pedido_id)
      setHeaderTargetOrderId(created.pedido_id)
      setHeaderPedidoFecha(created.pedido_fecha || '')
      setHeaderPedidoNumero(created.pedido_numero || '')
      setHeaderSubmitMode(created.pedido_estado === 'P' ? 'pendiente' : 'normal')
      setCreateMessage('Pedido creado correctamente.')
      setCreatePedidoNumero('')
    } catch (error: unknown) {
      setCreateError(error instanceof Error ? error.message : 'No se pudo crear el pedido.')
    } finally {
      setCreateLoading(false)
    }
  }

  const runJsonImport = async () => {
    if (importJsonLoading) {
      return
    }
    const almacen = importJsonAlmacenId.trim()
    if (!almacen) {
      setImportJsonError('Debes indicar almacen_id para importar JSON.')
      setImportJsonMessage('')
      return
    }
    if (!importJsonFile) {
      setImportJsonError('Debes seleccionar un archivo JSON.')
      setImportJsonMessage('')
      return
    }
    if (!importJsonFile.name.toLowerCase().endsWith('.json')) {
      setImportJsonError('El archivo debe tener extension .json.')
      setImportJsonMessage('')
      return
    }
    setImportJsonLoading(true)
    setImportJsonError('')
    setImportJsonMessage('')
    try {
      const result = await importOrderJsonUpload({ almacen_id: almacen, file: importJsonFile })
      await ordersQuery.reload()
      if (result.pedido_id) {
        setSelectedCandidateId(result.pedido_id)
      }
      setImportJsonFile(null)
      setImportJsonMessage(
        `Importacion JSON completada: ${result.imported_items} linea(s) importadas, ${result.skipped_invalid} invalida(s), ${result.skipped_unknown.length} desconocida(s).`,
      )
    } catch (error: unknown) {
      setImportJsonError(error instanceof Error ? error.message : 'No se pudo importar el JSON de pedido.')
    } finally {
      setImportJsonLoading(false)
    }
  }

  const runPdfImport = async () => {
    if (!selectedOrder || importPdfLoading) {
      return
    }
    if (!importPdfFile) {
      setImportPdfError('Debes seleccionar un archivo PDF.')
      setImportPdfMessage('')
      return
    }
    if (!importPdfFile.name.toLowerCase().endsWith('.pdf')) {
      setImportPdfError('El archivo debe tener extension .pdf.')
      setImportPdfMessage('')
      return
    }
    setImportPdfLoading(true)
    setImportPdfError('')
    setImportPdfMessage('')
    try {
      const result = importPdfType === 'albaran'
        ? await importOrderAlbaranPdfUpload(selectedOrder.pedido_id, { file: importPdfFile })
        : await importOrderFacturaPdfUpload(selectedOrder.pedido_id, { file: importPdfFile })
      await Promise.all([ordersQuery.reload(), detailQuery.reload()])
      setImportPdfFile(null)
      setImportPdfMessage(
        `${importPdfType === 'albaran' ? 'Albaran' : 'Factura'} importado: ${result.imported} linea(s). ${result.message || ''}`.trim(),
      )
    } catch (error: unknown) {
      setImportPdfError(error instanceof Error ? error.message : 'No se pudo importar el PDF.')
    } finally {
      setImportPdfLoading(false)
    }
  }

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={year}
          onChange={(event) => {
            setYear(event.target.value)
            setPageIndex(0)
          }}
          placeholder="Ano (ej: 2026)"
        />
        <input
          className="input"
          value={monthFrom}
          onChange={(event) => {
            setMonthFrom(event.target.value)
            setPageIndex(0)
          }}
          placeholder="Mes desde (1-12)"
        />
        <input
          className="input"
          value={monthTo}
          onChange={(event) => {
            setMonthTo(event.target.value)
            setPageIndex(0)
          }}
          placeholder="Mes hasta (1-12)"
        />
        <input
          className="input"
          value={almacenId}
          onChange={(event) => {
            setAlmacenId(event.target.value)
            setPageIndex(0)
          }}
          placeholder="Filtrar por almacen_id"
        />
        <button type="button" className="action-btn" disabled={!hasPreviousPage} onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}>
          Anterior
        </button>
        <button type="button" className="action-btn" disabled={!hasNextPage} onClick={() => setPageIndex((prev) => prev + 1)}>
          Siguiente
        </button>
        <span className="state">
          Pagina {currentPage} de {totalPages}
        </span>
      </div>

      <div className="cards">
        <StatCard label="Total pedidos" value={totals.total} />
        <StatCard label="Con albaran" value={totals.withAlbaran} />
        <StatCard label="Con factura" value={totals.withFactura} />
        <StatCard label="Total kg (listado)" value={totals.totalKg} />
      </div>

      <div className="detail-panel">
        <h3>Crear pedido</h3>
        <div className="form-grid">
          <label>
            Almacen ID
            <input
              className="input"
              value={createAlmacenId}
              onChange={(event) => setCreateAlmacenId(event.target.value)}
              placeholder="Ej: ALM-01"
              disabled={createLoading}
            />
          </label>
          <label>
            Fecha pedido
            <input
              type="date"
              className="input"
              value={createPedidoFecha}
              onChange={(event) => setCreatePedidoFecha(event.target.value)}
              disabled={createLoading}
            />
          </label>
          <label>
            Numero pedido
            <input
              className="input"
              value={createPedidoNumero}
              onChange={(event) => setCreatePedidoNumero(event.target.value)}
              placeholder="Opcional"
              disabled={createLoading}
            />
          </label>
          <label>
            Estado inicial
            <select
              className="select"
              value={createPending ? 'pendiente' : 'normal'}
              onChange={(event) => setCreatePending(event.target.value === 'pendiente')}
              disabled={createLoading}
            >
              <option value="normal">Normal</option>
              <option value="pendiente">Pendiente</option>
            </select>
          </label>
        </div>
        <div className="toolbar">
          <button type="button" className="action-btn" onClick={createNewOrder} disabled={createLoading}>
            {createLoading ? 'Creando...' : 'Crear pedido'}
          </button>
        </div>
        {!!createMessage && <div className="state">{createMessage}</div>}
        {!!createError && <div className="state">Error: {createError}</div>}
      </div>

      <div className="detail-panel">
        <h3>Importar pedidos</h3>
        <div className="form-grid">
          <label>
            Almacen ID (JSON)
            <input
              className="input"
              value={importJsonAlmacenId}
              onChange={(event) => setImportJsonAlmacenId(event.target.value)}
              placeholder="Ej: ALM-01"
              disabled={importJsonLoading}
            />
          </label>
          <label>
            Archivo JSON
            <input
              type="file"
              className="input"
              accept=".json,application/json"
              onChange={(event) => setImportJsonFile(event.target.files?.[0] ?? null)}
              disabled={importJsonLoading}
            />
          </label>
        </div>
        <div className="toolbar">
          <button type="button" className="action-btn" onClick={runJsonImport} disabled={importJsonLoading}>
            {importJsonLoading ? 'Importando JSON...' : 'Importar JSON'}
          </button>
        </div>
        {!!importJsonMessage && <div className="state">{importJsonMessage}</div>}
        {!!importJsonError && <div className="state">Error: {importJsonError}</div>}

        <div className="form-grid">
          <label>
            Tipo PDF
            <select
              className="select"
              value={importPdfType}
              onChange={(event) => setImportPdfType(event.target.value === 'factura' ? 'factura' : 'albaran')}
              disabled={importPdfLoading}
            >
              <option value="albaran">Albaran</option>
              <option value="factura">Factura</option>
            </select>
          </label>
          <label>
            Archivo PDF (pedido seleccionado)
            <input
              type="file"
              className="input"
              accept=".pdf,application/pdf"
              onChange={(event) => setImportPdfFile(event.target.files?.[0] ?? null)}
              disabled={importPdfLoading}
            />
          </label>
        </div>
        <div className="toolbar">
          <button
            type="button"
            className="action-btn"
            onClick={runPdfImport}
            disabled={importPdfLoading || !selectedOrder}
          >
            {importPdfLoading ? 'Importando PDF...' : 'Importar PDF'}
          </button>
        </div>
        {!!importPdfMessage && <div className="state">{importPdfMessage}</div>}
        {!!importPdfError && <div className="state">Error: {importPdfError}</div>}
      </div>

      <QueryState
        loading={ordersQuery.loading}
        error={ordersQuery.error}
        empty={!orderRows.length}
        emptyMessage="No hay pedidos para los filtros actuales."
      />

      {!!orderRows.length && (
        <div className="split-panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Almacen</th>
                  <th>N pedido</th>
                  <th>Estado</th>
                  <th>Semana</th>
                  <th>Total kg</th>
                </tr>
              </thead>
              <tbody>
                {orderRows.map((row) => (
                  <tr
                    key={row.pedido_id}
                    className={row.pedido_id === selectedOrder?.pedido_id ? 'row-selected' : ''}
                    onClick={() => {
                      setSelectedCandidateId(row.pedido_id)
                      resetOrderItemForm()
                      setHeaderTargetOrderId(row.pedido_id)
                      setHeaderPedidoFecha(row.pedido_fecha || '')
                      setHeaderPedidoNumero(row.pedido_numero || '')
                      setHeaderSubmitMode(row.pedido_estado === 'P' ? 'pendiente' : 'normal')
                    }}
                  >
                    <td>{row.pedido_fecha}</td>
                    <td>{row.almacen_nombre || row.almacen_id}</td>
                    <td>{row.pedido_numero || '-'}</td>
                    <td>{row.pedido_estado || '-'}</td>
                    <td>{row.semana}</td>
                    <td>{safeNumber(row.total_kg).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <aside className="detail-panel">
            <QueryState
              loading={detailQuery.loading}
              error={detailQuery.error}
              empty={!detailQuery.data.detail}
              emptyMessage="Selecciona un pedido para ver detalle."
            />

            {!!detailQuery.data.detail && (
              <>
                <dl className="detail-list">
                  <div>
                    <dt>Pedido ID</dt>
                    <dd>{detailQuery.data.detail.pedido_id}</dd>
                  </div>
                  <div>
                    <dt>Fecha</dt>
                    <dd>{detailQuery.data.detail.pedido_fecha}</dd>
                  </div>
                  <div>
                    <dt>Numero pedido</dt>
                    <dd>{detailQuery.data.detail.pedido_numero || '-'}</dd>
                  </div>
                  <div>
                    <dt>Albaran</dt>
                    <dd>{detailQuery.data.detail.pedido_albaran_numero || '-'}</dd>
                  </div>
                  <div>
                    <dt>Factura</dt>
                    <dd>{detailQuery.data.detail.pedido_factura_numero || '-'}</dd>
                  </div>
                  <div>
                    <dt>Referencia</dt>
                    <dd>{detailQuery.data.detail.pedido_ref || '-'}</dd>
                  </div>
                </dl>

                <div className="related-block">
                  <h3>Editar cabecera</h3>
                  <div className="form-grid">
                    <label>
                      Fecha pedido
                      <input
                        type="date"
                        className="input"
                        value={effectiveHeaderValues.pedidoFecha}
                        onChange={(event) => {
                          if (detailQuery.data.detail) {
                            setHeaderTargetOrderId(detailQuery.data.detail.pedido_id)
                          }
                          setHeaderPedidoFecha(event.target.value)
                        }}
                        disabled={headerSaveLoading}
                      />
                    </label>
                    <label>
                      Numero pedido
                      <input
                        className="input"
                        value={effectiveHeaderValues.pedidoNumero}
                        onChange={(event) => {
                          if (detailQuery.data.detail) {
                            setHeaderTargetOrderId(detailQuery.data.detail.pedido_id)
                          }
                          setHeaderPedidoNumero(event.target.value)
                        }}
                        disabled={headerSaveLoading}
                      />
                    </label>
                    <label>
                      Modo
                      <select
                        className="select"
                        value={effectiveHeaderValues.submitMode}
                        onChange={(event) => {
                          if (detailQuery.data.detail) {
                            setHeaderTargetOrderId(detailQuery.data.detail.pedido_id)
                          }
                          setHeaderSubmitMode(event.target.value === 'pendiente' ? 'pendiente' : 'normal')
                        }}
                        disabled={headerSaveLoading}
                      >
                        <option value="normal">Normal</option>
                        <option value="pendiente">Pendiente</option>
                      </select>
                    </label>
                  </div>
                  <div className="toolbar">
                    <button
                      type="button"
                      className="action-btn"
                      onClick={saveOrderHeader}
                      disabled={headerSaveLoading}
                    >
                      {headerSaveLoading ? 'Guardando...' : 'Guardar cabecera'}
                    </button>
                  </div>
                  {!!headerSaveMessage && <div className="state">{headerSaveMessage}</div>}
                  {!!headerSaveError && <div className="state">Error: {headerSaveError}</div>}
                </div>

                <div className="related-block">
                  <button
                    type="button"
                    className="action-btn"
                    onClick={deleteSelectedOrder}
                    disabled={deleteLoading}
                  >
                    {deleteLoading ? 'Eliminando...' : 'Eliminar pedido'}
                  </button>
                  {!!deleteMessage && <div className="state">{deleteMessage}</div>}
                  {!!deleteError && <div className="state">Error: {deleteError}</div>}
                </div>

                <div className="related-block">
                  <h3>Lineas de pedido</h3>
                  {!detailQuery.data.items.length && <div className="state">Sin lineas.</div>}
                  {!!detailQuery.data.items.length && (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Articulo ID</th>
                            <th>Cantidad</th>
                            <th>Fecha linea</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detailQuery.data.items.slice(0, 12).map((item) => (
                            <tr
                              key={item.item_id}
                              className={item.item_id === selectedOrderItemId ? 'row-selected' : ''}
                              onClick={() => onSelectOrderItem(item)}
                            >
                              <td>{item.articulo_id}</td>
                              <td>{safeNumber(item.articulo_cantidad).toFixed(2)}</td>
                              <td>{item.pedido_item_fecha}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                  <div className="form-grid">
                    <label>
                      Articulo ID
                      <input
                        className="input"
                        value={lineArticuloId}
                        onChange={(event) => setLineArticuloId(event.target.value)}
                        disabled={lineSaveLoading || lineDeleteLoading}
                        placeholder="Ej: 000123"
                      />
                    </label>
                    <label>
                      Cantidad
                      <input
                        className="input"
                        value={lineCantidad}
                        onChange={(event) => setLineCantidad(event.target.value)}
                        disabled={lineSaveLoading || lineDeleteLoading}
                        placeholder="Ej: 25.5"
                      />
                    </label>
                  </div>
                  <div className="toolbar">
                    <button
                      type="button"
                      className="action-btn"
                      onClick={saveOrderItem}
                      disabled={lineSaveLoading || lineDeleteLoading}
                    >
                      {lineSaveLoading ? 'Guardando...' : selectedOrderItem ? 'Actualizar linea' : 'Crear linea'}
                    </button>
                    <button
                      type="button"
                      className="action-btn"
                      onClick={deleteSelectedOrderItem}
                      disabled={lineSaveLoading || lineDeleteLoading || !selectedOrderItem}
                    >
                      {lineDeleteLoading ? 'Eliminando...' : 'Eliminar linea'}
                    </button>
                    <button
                      type="button"
                      className="action-btn"
                      onClick={resetOrderItemForm}
                      disabled={lineSaveLoading || lineDeleteLoading}
                    >
                      Limpiar seleccion
                    </button>
                  </div>
                  {!!lineMessage && <div className="state">{lineMessage}</div>}
                  {!!lineError && <div className="state">Error: {lineError}</div>}
                </div>

                <div className="related-block">
                  <h3>Pendientes</h3>
                  {!detailQuery.data.pending.length && <div className="state">Sin pendientes.</div>}
                  {!!detailQuery.data.pending.length && (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Articulo ID</th>
                            <th>Pedida</th>
                            <th>Recibida</th>
                            <th>Pendiente</th>
                            <th>Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detailQuery.data.pending.slice(0, 12).map((row) => (
                            <tr key={row.pendiente_id}>
                              <td>{row.articulo_id}</td>
                              <td>{safeNumber(row.cantidad_pedida).toFixed(2)}</td>
                              <td>{safeNumber(row.cantidad_recibida).toFixed(2)}</td>
                              <td>{safeNumber(row.cantidad_pendiente).toFixed(2)}</td>
                              <td>{row.estado || '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
