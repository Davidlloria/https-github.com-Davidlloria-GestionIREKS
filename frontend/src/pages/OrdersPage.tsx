import { useCallback, useMemo, useState } from 'react'
import { getOrderDetail, listOrderItems, listOrderPending, listOrders } from '../api/orders'
import { EmptyState, ErrorState, LoadingState } from '../components/QueryState'
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
const CURRENT_YEAR = String(new Date().getFullYear())

const MONTH_OPTIONS = [
  ['1', 'Enero'],
  ['2', 'Febrero'],
  ['3', 'Marzo'],
  ['4', 'Abril'],
  ['5', 'Mayo'],
  ['6', 'Junio'],
  ['7', 'Julio'],
  ['8', 'Agosto'],
  ['9', 'Septiembre'],
  ['10', 'Octubre'],
  ['11', 'Noviembre'],
  ['12', 'Diciembre'],
] as const

type DetailTab = 'pedido' | 'albaran' | 'factura' | 'pendientes'

const DETAIL_TABS: Array<{ key: DetailTab; label: string }> = [
  { key: 'pedido', label: 'Pedido' },
  { key: 'albaran', label: 'Albaran' },
  { key: 'factura', label: 'Factura' },
  { key: 'pendientes', label: 'Pendientes' },
]

function safeNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function formatNumber(value: number) {
  return value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function buildYearOptions() {
  const current = Number(CURRENT_YEAR)
  return Array.from({ length: 5 }, (_, index) => String(current - 2 + index))
}

export function OrdersPage() {
  const [year, setYear] = useState(CURRENT_YEAR)
  const [monthFrom, setMonthFrom] = useState('1')
  const [monthTo, setMonthTo] = useState('12')
  const [almacenId, setAlmacenId] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [activeTab, setActiveTab] = useState<DetailTab>('pedido')

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

  const almacenOptions = useMemo(() => {
    const seen = new Map<string, string>()
    orderRows.forEach((row) => {
      const value = String(row.almacen_id || '').trim()
      if (!value || seen.has(value)) {
        return
      }
      seen.set(value, row.almacen_nombre || value)
    })
    return Array.from(seen.entries()).map(([value, label]) => ({ value, label }))
  }, [orderRows])

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

  const hasPreviousPage = pageIndex > 0
  const hasNextPage = offset + orderRows.length < ordersQuery.data.total
  const currentPage = pageIndex + 1
  const totalPages = Math.max(1, Math.ceil(ordersQuery.data.total / PAGE_SIZE))
  const listTotalKg = orderRows.reduce((acc, row) => acc + safeNumber(row.total_kg), 0)
  const detailLineQty = detailQuery.data.items.reduce((acc, row) => acc + safeNumber(row.articulo_cantidad), 0)
  const pendingQty = detailQuery.data.pending.reduce((acc, row) => acc + safeNumber(row.cantidad_pendiente), 0)

  return (
    <section className="page-grid orders-page">
      <header className="orders-page-header">
        <div className="orders-page-header-copy">
          <p className="module-kicker">Pedidos</p>
          <h2>Pedidos</h2>
        </div>
        <span className="surface-chip">{ordersQuery.data.total} visibles</span>
      </header>

      <div className="orders-workspace">
        <section className="panel-section orders-list-panel">
          <div className="section-heading section-heading-compact">
            <div>
              <h3>Listado de pedidos</h3>
              <p>Consulta read-only con filtros y seleccion de pedido.</p>
            </div>
          </div>

          <div className="orders-filter-grid">
            <label className="orders-filter-field">
              <span>Ano</span>
              <select
                className="select"
                value={year}
                onChange={(event) => {
                  setYear(event.target.value)
                  setPageIndex(0)
                }}
              >
                {buildYearOptions().map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="orders-filter-field">
              <span>Mes inicial</span>
              <select
                className="select"
                value={monthFrom}
                onChange={(event) => {
                  setMonthFrom(event.target.value)
                  setPageIndex(0)
                }}
              >
                {MONTH_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="orders-filter-field">
              <span>Mes final</span>
              <select
                className="select"
                value={monthTo}
                onChange={(event) => {
                  setMonthTo(event.target.value)
                  setPageIndex(0)
                }}
              >
                {MONTH_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="orders-filter-field orders-filter-field-wide">
              <span>Cliente/Distribuidor</span>
              <select
                className="select"
                value={almacenId}
                onChange={(event) => {
                  setAlmacenId(event.target.value)
                  setPageIndex(0)
                }}
              >
                <option value="">Todos</option>
                {almacenOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="toolbar orders-action-toolbar">
            <button type="button" className="orders-action-btn orders-action-btn-success">
              Nuevo pedido
            </button>
            <button type="button" className="orders-action-btn orders-action-btn-warning">
              Editar
            </button>
            <button type="button" className="orders-action-btn orders-action-btn-danger">
              Eliminar
            </button>
            <button type="button" className="orders-action-btn orders-action-btn-outline">
              Exportar
            </button>
            <button type="button" className="orders-action-btn orders-action-btn-outline">
              Enviar Outlook
            </button>
            <button type="button" className="orders-action-btn orders-action-btn-outline">
              Imprimir
            </button>
          </div>

          <div className="orders-list-scroll">
            {ordersQuery.loading && <LoadingState />}
            {!ordersQuery.loading && ordersQuery.error && <ErrorState>{ordersQuery.error}</ErrorState>}
            {!ordersQuery.loading && !ordersQuery.error && !orderRows.length && (
              <EmptyState>No hay pedidos para los filtros actuales.</EmptyState>
            )}
            {!ordersQuery.loading && !ordersQuery.error && !!orderRows.length && (
              <div className="table-wrap orders-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Almacen</th>
                      <th>N&ordm;</th>
                      <th>Fecha</th>
                      <th>Semana</th>
                      <th>Total Kg</th>
                      <th>Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orderRows.map((row) => (
                      <tr
                        key={row.pedido_id}
                        className={row.pedido_id === selectedOrder?.pedido_id ? 'row-selected' : ''}
                        onClick={() => setSelectedCandidateId(row.pedido_id)}
                      >
                        <td>{row.almacen_nombre || row.almacen_id || '-'}</td>
                        <td>{row.pedido_numero || '-'}</td>
                        <td>{row.pedido_fecha}</td>
                        <td>{row.semana}</td>
                        <td>{formatNumber(safeNumber(row.total_kg))}</td>
                        <td>{row.pedido_estado || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="orders-list-footer">
            <strong>TOTAL</strong>
            <span>{formatNumber(listTotalKg)} kg</span>
            <div className="orders-page-controls">
              <span className="surface-chip">Pagina {currentPage} de {totalPages}</span>
              <div className="toolbar pager-toolbar">
                <button
                  type="button"
                  className="orders-action-btn orders-action-btn-outline"
                  disabled={!hasPreviousPage}
                  onClick={() => setPageIndex((prev) => Math.max(0, prev - 1))}
                >
                  Anterior
                </button>
                <button
                  type="button"
                  className="orders-action-btn orders-action-btn-outline"
                  disabled={!hasNextPage}
                  onClick={() => setPageIndex((prev) => prev + 1)}
                >
                  Siguiente
                </button>
              </div>
            </div>
          </div>
        </section>

        <aside className="panel-section orders-detail-panel">
          <div className="section-heading section-heading-compact">
            <div>
              <h3>Detalle del pedido</h3>
              <p>Cabecera, lineas y pendientes del pedido seleccionado.</p>
            </div>
          </div>

          <div className="orders-detail-meta-grid">
            <label className="orders-detail-field">
              <span>Semana</span>
              <input className="input" readOnly value={selectedOrder ? String(selectedOrder.semana) : '-'} />
            </label>
            <label className="orders-detail-field">
              <span>Fecha</span>
              <input className="input" readOnly value={selectedOrder?.pedido_fecha || '-'} />
            </label>
            <label className="orders-detail-field">
              <span>Numero</span>
              <input className="input" readOnly value={selectedOrder?.pedido_numero || '-'} />
            </label>
          </div>

          <div className="orders-tabs" role="tablist" aria-label="Detalle del pedido">
            {DETAIL_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.key}
                className={`orders-tab-btn ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="toolbar orders-detail-actions">
            <button type="button" className="orders-action-btn orders-action-btn-success">
              Anadir
            </button>
            <button type="button" className="orders-action-btn orders-action-btn-warning">
              Editar
            </button>
            <button type="button" className="orders-action-btn orders-action-btn-danger">
              Eliminar
            </button>
            <button type="button" className="orders-action-btn orders-action-btn-warning">
              Editar pedido
            </button>
          </div>

          <div className="orders-detail-scroll">
            {detailQuery.loading && <LoadingState />}
            {!detailQuery.loading && detailQuery.error && <ErrorState>{detailQuery.error}</ErrorState>}
            {!detailQuery.loading && !detailQuery.error && !selectedOrder && (
              <EmptyState>Selecciona un pedido para ver detalle.</EmptyState>
            )}

            {!detailQuery.loading && !detailQuery.error && selectedOrder && activeTab === 'pedido' && (
              <div className="orders-tab-stack">
                <div className="table-wrap orders-detail-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Cod.</th>
                        <th>Nombre</th>
                        <th>Cantidad</th>
                        <th>Kg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailQuery.data.items.length ? (
                        detailQuery.data.items.map((item) => (
                          <tr key={item.item_id}>
                            <td>{item.articulo_id}</td>
                            <td>{item.articulo_id || '-'}</td>
                            <td>{formatNumber(safeNumber(item.articulo_cantidad))}</td>
                            <td>{formatNumber(safeNumber(item.articulo_cantidad))} kg</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={4}>
                            <EmptyState>No hay lineas para el pedido seleccionado.</EmptyState>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="orders-tab-footer">
                  <strong>TOTAL</strong>
                  <span>{formatNumber(detailLineQty)} kg</span>
                </div>
              </div>
            )}

            {!detailQuery.loading && !detailQuery.error && selectedOrder && activeTab === 'albaran' && (
              <div className="orders-tab-stack">
                <EmptyState>{`Albaran ${selectedOrder.pedido_albaran_numero || '-'} pendiente de conexion read-only.`}</EmptyState>
                <div className="orders-tab-footer">
                  <strong>TOTAL</strong>
                  <span>{selectedOrder.pedido_albaran_numero || '-'}</span>
                </div>
              </div>
            )}

            {!detailQuery.loading && !detailQuery.error && selectedOrder && activeTab === 'factura' && (
              <div className="orders-tab-stack">
                <EmptyState>{`Factura ${selectedOrder.pedido_factura_numero || '-'} pendiente de conexion read-only.`}</EmptyState>
                <div className="orders-tab-footer">
                  <strong>TOTAL</strong>
                  <span>{selectedOrder.pedido_factura_numero || '-'}</span>
                </div>
              </div>
            )}

            {!detailQuery.loading && !detailQuery.error && selectedOrder && activeTab === 'pendientes' && (
              <div className="orders-tab-stack">
                <div className="table-wrap orders-detail-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Cod.</th>
                        <th>Pedida</th>
                        <th>Recibida</th>
                        <th>Pendiente</th>
                        <th>Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailQuery.data.pending.length ? (
                        detailQuery.data.pending.map((row) => (
                          <tr key={row.pendiente_id}>
                            <td>{row.articulo_id}</td>
                            <td>{formatNumber(safeNumber(row.cantidad_pedida))}</td>
                            <td>{formatNumber(safeNumber(row.cantidad_recibida))}</td>
                            <td>{formatNumber(safeNumber(row.cantidad_pendiente))}</td>
                            <td>{row.estado || '-'}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5}>
                            <EmptyState>Sin pendientes.</EmptyState>
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="orders-tab-footer">
                  <strong>TOTAL</strong>
                  <span>{formatNumber(pendingQty)} kg</span>
                </div>
              </div>
            )}
          </div>
        </aside>
      </div>
    </section>
  )
}
