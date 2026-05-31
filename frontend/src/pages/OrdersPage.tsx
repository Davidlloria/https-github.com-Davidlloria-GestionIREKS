import { useCallback, useMemo, useState } from 'react'
import {
  createOrderItem,
  deleteOrder,
  deleteOrderItem,
  getOrderDetail,
  listOrderItems,
  listOrderPending,
  listOrders,
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

function safeNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

export function OrdersPage() {
  const [year, setYear] = useState('')
  const [monthFrom, setMonthFrom] = useState('')
  const [monthTo, setMonthTo] = useState('')
  const [almacenId, setAlmacenId] = useState('')
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

  const ordersQuery = useAsyncResource(
    () =>
      listOrders({
        year,
        monthFrom: monthFrom ? Number(monthFrom) : undefined,
        monthTo: monthTo ? Number(monthTo) : undefined,
        almacenId,
      }),
    [],
    [year, monthFrom, monthTo, almacenId],
  )

  const selectedOrder = useMemo(() => {
    if (!ordersQuery.data.length) {
      return null as OrderListItem | null
    }
    const explicit = ordersQuery.data.find((row) => row.pedido_id === selectedCandidateId)
    return explicit ?? ordersQuery.data[0]
  }, [ordersQuery.data, selectedCandidateId])

  const loadSelectedOrder = useCallback(() => {
    if (!selectedOrder) {
      return Promise.resolve(EMPTY_ORDER_DETAIL)
    }
    return Promise.all([
      getOrderDetail(selectedOrder.pedido_id),
      listOrderItems(selectedOrder.pedido_id),
      listOrderPending(selectedOrder.pedido_id),
    ]).then(([detail, items, pending]) => ({ detail, items, pending }))
  }, [selectedOrder])

  const detailQuery = useAsyncResource(loadSelectedOrder, EMPTY_ORDER_DETAIL, [loadSelectedOrder, selectedOrder?.pedido_id])

  const totals = useMemo(() => {
    const withAlbaran = ordersQuery.data.filter((row) => !!row.pedido_albaran_numero).length
    const withFactura = ordersQuery.data.filter((row) => !!row.pedido_factura_numero).length
    const totalKg = ordersQuery.data.reduce((acc, row) => acc + safeNumber(row.total_kg), 0)
    return {
      total: ordersQuery.data.length,
      withAlbaran,
      withFactura,
      totalKg: totalKg.toFixed(2),
    }
  }, [ordersQuery.data])

  const selectedOrderItem = useMemo(
    () => detailQuery.data.items.find((item) => item.item_id === selectedOrderItemId) ?? null,
    [detailQuery.data.items, selectedOrderItemId],
  )

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

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={year}
          onChange={(event) => setYear(event.target.value)}
          placeholder="Ano (ej: 2026)"
        />
        <input
          className="input"
          value={monthFrom}
          onChange={(event) => setMonthFrom(event.target.value)}
          placeholder="Mes desde (1-12)"
        />
        <input
          className="input"
          value={monthTo}
          onChange={(event) => setMonthTo(event.target.value)}
          placeholder="Mes hasta (1-12)"
        />
        <input
          className="input"
          value={almacenId}
          onChange={(event) => setAlmacenId(event.target.value)}
          placeholder="Filtrar por almacen_id"
        />
      </div>

      <div className="cards">
        <StatCard label="Total pedidos" value={totals.total} />
        <StatCard label="Con albaran" value={totals.withAlbaran} />
        <StatCard label="Con factura" value={totals.withFactura} />
        <StatCard label="Total kg (listado)" value={totals.totalKg} />
      </div>

      <QueryState
        loading={ordersQuery.loading}
        error={ordersQuery.error}
        empty={!ordersQuery.data.length}
        emptyMessage="No hay pedidos para los filtros actuales."
      />

      {!!ordersQuery.data.length && (
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
                {ordersQuery.data.map((row) => (
                  <tr
                    key={row.pedido_id}
                    className={row.pedido_id === selectedOrder?.pedido_id ? 'row-selected' : ''}
                    onClick={() => {
                      setSelectedCandidateId(row.pedido_id)
                      resetOrderItemForm()
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
