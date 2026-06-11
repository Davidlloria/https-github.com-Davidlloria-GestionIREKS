import { useCallback, useMemo, useState } from 'react'
import { getOrderDetail, listOrderItems, listOrderPending, listOrders } from '../api/orders'
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

  return (
    <section className="page-grid">
      <header className="module-header">
        <div className="module-header-copy">
          <p className="module-kicker">Modulo read-only</p>
          <h2>Pedidos</h2>
          <p className="module-description">
            Consulta de pedidos, lineas y pendientes con navegacion por pagina y detalle lateral.
          </p>
        </div>
        <div className="module-header-meta">
          <span className="surface-chip">Pagina {currentPage} de {totalPages}</span>
          <span className="surface-chip">Vista sin mutaciones</span>
        </div>
      </header>

      <section className="panel-section">
        <div className="section-heading">
          <div>
            <h3>Filtros</h3>
            <p>Reduce el listado antes de revisar detalle o pendientes.</p>
          </div>
          <div className="toolbar pager-toolbar">
            <button type="button" className="action-btn" disabled={!hasPreviousPage} onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}>
              Anterior
            </button>
            <button type="button" className="action-btn" disabled={!hasNextPage} onClick={() => setPageIndex((prev) => prev + 1)}>
              Siguiente
            </button>
          </div>
        </div>

        <div className="toolbar orders-toolbar">
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
        </div>
      </section>

      <div className="cards">
        <StatCard label="Total pedidos" value={totals.total} />
        <StatCard label="Con albaran" value={totals.withAlbaran} />
        <StatCard label="Con factura" value={totals.withFactura} />
        <StatCard label="Total kg (listado)" value={totals.totalKg} />
      </div>

      <QueryState
        loading={ordersQuery.loading}
        error={ordersQuery.error}
        empty={!orderRows.length}
        emptyMessage="No hay pedidos para los filtros actuales."
      />

      {!!orderRows.length && (
        <div className="orders-workspace">
          <section className="orders-list-panel">
            <div className="panel-section">
              <div className="section-heading">
                <div>
                  <h3>Listado de pedidos</h3>
                  <p>Selecciona una fila para abrir el detalle lateral.</p>
                </div>
                <span className="surface-chip">Mostrando {orderRows.length} de {ordersQuery.data.total}</span>
              </div>
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
                        onClick={() => setSelectedCandidateId(row.pedido_id)}
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
            </div>
          </section>

          <aside className="detail-panel detail-panel-orders">
            <div className="section-heading section-heading-compact">
              <div>
                <h3>Detalle de pedido</h3>
                <p>Cabecera, lineas y pendientes del pedido seleccionado.</p>
              </div>
            </div>
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
                            <tr key={item.item_id}>
                              <td>{item.articulo_id}</td>
                              <td>{safeNumber(item.articulo_cantidad).toFixed(2)}</td>
                              <td>{item.pedido_item_fecha}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
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
