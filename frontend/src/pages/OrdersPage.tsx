import { createPortal } from 'react-dom'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { getOrderDetail, listOrderItems, listOrderPending, listOrders } from '../api/orders'
import { listIreksIngredients } from '../api/ingredients'
import { EmptyState, ErrorState, LoadingState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type { IngredientIreksRead, OrderItemRead, OrderListItem, OrderPendingRead, OrderRead } from '../types/api'

interface OrderDetailPayload {
  detail: OrderRead | null
  items: OrderItemRead[]
  pending: OrderPendingRead[]
}

interface ArticleDisplayInfo {
  code: string
  name: string
  unitKg: number
}

const EMPTY_ORDER_DETAIL: OrderDetailPayload = {
  detail: null,
  items: [],
  pending: [],
}

const LIST_FETCH_SIZE = 200
const LIST_VIEW_ROWS = 12
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
type OrderSortKey = 'almacen' | 'numero' | 'fecha' | 'semana' | 'total' | 'estado'
type DetailSortKey = 'code' | 'name' | 'qty' | 'kg'
type PendingSortKey = 'code' | 'pedida' | 'recibida' | 'pendiente' | 'estado'

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
  const safeValue = Number.isFinite(value) ? value : 0
  const isNegative = safeValue < 0
  const absoluteValue = Math.abs(safeValue)
  const [integerPart, decimalPart] = absoluteValue.toFixed(2).split('.')
  const groupedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `${isNegative ? '-' : ''}${groupedInteger},${decimalPart}`
}

function formatDate(value: string | null | undefined) {
  if (!value) {
    return '-'
  }

  const [year, month, day] = value.split('-')
  if (!year || !month || !day) {
    return value
  }

  return `${day}/${month}/${year}`
}

function compareText(left: string, right: string) {
  return left.localeCompare(right, 'es', { sensitivity: 'base', numeric: true })
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
  const [almacenMenuOpen, setAlmacenMenuOpen] = useState(false)
  const [almacenMenuStyle, setAlmacenMenuStyle] = useState<{ left: number; top: number; width: number } | null>(null)
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [activeTab, setActiveTab] = useState<DetailTab>('pedido')
  const [sortKey, setSortKey] = useState<OrderSortKey>('fecha')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [detailSortKey, setDetailSortKey] = useState<DetailSortKey>('code')
  const [detailSortDirection, setDetailSortDirection] = useState<'asc' | 'desc'>('asc')
  const [pendingSortKey, setPendingSortKey] = useState<PendingSortKey>('code')
  const [pendingSortDirection, setPendingSortDirection] = useState<'asc' | 'desc'>('asc')

  const loadAllOrders = useCallback(async () => {
    const items: OrderListItem[] = []
    let offset = 0

    while (true) {
      const payload = await listOrders({
        year,
        monthFrom: monthFrom ? Number(monthFrom) : undefined,
        monthTo: monthTo ? Number(monthTo) : undefined,
        almacenId,
        limit: LIST_FETCH_SIZE,
        offset,
      })

      items.push(...payload.items)

      const fetched = payload.items.length
      if (!fetched || items.length >= payload.total) {
        return {
          items,
          total: items.length,
          limit: payload.limit,
          offset: 0,
        }
      }

      offset += fetched
    }
  }, [year, monthFrom, monthTo, almacenId])

  const ordersQuery = useAsyncResource(loadAllOrders, { items: [], total: 0, limit: LIST_FETCH_SIZE, offset: 0 }, [loadAllOrders])
  const orderRows = ordersQuery.data.items

  const loadAlmacenOptions = useCallback(async () => {
    const items: OrderListItem[] = []
    let offset = 0

    while (true) {
      const payload = await listOrders({
        year,
        monthFrom: monthFrom ? Number(monthFrom) : undefined,
        monthTo: monthTo ? Number(monthTo) : undefined,
        almacenId: '',
        limit: LIST_FETCH_SIZE,
        offset,
      })

      items.push(...payload.items)

      const fetched = payload.items.length
      if (!fetched || items.length >= payload.total) {
        return {
          items,
          total: items.length,
          limit: payload.limit,
          offset: 0,
        }
      }

      offset += fetched
    }
  }, [year, monthFrom, monthTo])

  const almacenOptionsQuery = useAsyncResource(loadAlmacenOptions, { items: [], total: 0, limit: LIST_FETCH_SIZE, offset: 0 }, [loadAlmacenOptions])

  const updateSort = (nextKey: OrderSortKey) => {
    if (sortKey === nextKey) {
      setSortDirection((currentDirection) => (currentDirection === 'asc' ? 'desc' : 'asc'))
      return
    }

    setSortKey(nextKey)
    setSortDirection('asc')
  }

  const updateDetailSort = (nextKey: DetailSortKey) => {
    if (detailSortKey === nextKey) {
      setDetailSortDirection((currentDirection) => (currentDirection === 'asc' ? 'desc' : 'asc'))
      return
    }

    setDetailSortKey(nextKey)
    setDetailSortDirection('asc')
  }

  const updatePendingSort = (nextKey: PendingSortKey) => {
    if (pendingSortKey === nextKey) {
      setPendingSortDirection((currentDirection) => (currentDirection === 'asc' ? 'desc' : 'asc'))
      return
    }

    setPendingSortKey(nextKey)
    setPendingSortDirection('asc')
  }

  const sortedRows = useMemo(() => {
    const sorted = [...orderRows]

    sorted.sort((left, right) => {
      let comparison = 0

      switch (sortKey) {
        case 'almacen': {
          comparison = compareText(left.almacen_nombre || left.almacen_id || '', right.almacen_nombre || right.almacen_id || '')
          break
        }
        case 'numero': {
          comparison = compareText(left.pedido_numero || '', right.pedido_numero || '')
          break
        }
        case 'fecha': {
          comparison = compareText(left.pedido_fecha || '', right.pedido_fecha || '')
          break
        }
        case 'semana': {
          comparison = safeNumber(left.semana) - safeNumber(right.semana)
          break
        }
        case 'total': {
          comparison = safeNumber(left.total_kg) - safeNumber(right.total_kg)
          break
        }
        case 'estado': {
          comparison = compareText(left.pedido_estado || '', right.pedido_estado || '')
          break
        }
      }

      if (comparison === 0) {
        comparison = compareText(left.pedido_id, right.pedido_id)
      }

      return sortDirection === 'asc' ? comparison : -comparison
    })

    return sorted
  }, [orderRows, sortDirection, sortKey])

  const almacenOptions = useMemo(() => {
    const seen = new Map<string, string>()
    almacenOptionsQuery.data.items.forEach((row) => {
      const value = String(row.almacen_id || '').trim()
      if (!value || seen.has(value)) {
        return
      }
      seen.set(value, row.almacen_nombre || value)
    })
    return Array.from(seen.entries()).map(([value, label]) => ({ value, label }))
  }, [almacenOptionsQuery.data.items])

  const almacenMenuRef = useRef<HTMLDivElement | null>(null)
  const almacenTriggerRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const triggerNode = almacenTriggerRef.current
      const menuNode = almacenMenuRef.current
      if (!triggerNode && !menuNode) {
        return
      }
      const target = event.target as Node
      if (triggerNode?.contains(target) || menuNode?.contains(target)) {
        return
      }
        setAlmacenMenuOpen(false)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setAlmacenMenuOpen(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  useLayoutEffect(() => {
    if (!almacenMenuOpen || !almacenTriggerRef.current) {
      setAlmacenMenuStyle(null)
      return
    }

    const updateMenuPosition = () => {
      const triggerRect = almacenTriggerRef.current?.getBoundingClientRect()
      if (!triggerRect) {
        return
      }

      const estimatedHeight = Math.min(360, 44 + almacenOptions.length * 48)
      const spaceBelow = window.innerHeight - triggerRect.bottom
      const openAbove = spaceBelow < estimatedHeight && triggerRect.top > estimatedHeight

      setAlmacenMenuStyle({
        left: triggerRect.left,
        top: openAbove ? Math.max(8, triggerRect.top - estimatedHeight - 4) : triggerRect.bottom + 4,
        width: triggerRect.width,
      })
    }

    updateMenuPosition()
    window.addEventListener('resize', updateMenuPosition)
    window.addEventListener('scroll', updateMenuPosition, true)
    return () => {
      window.removeEventListener('resize', updateMenuPosition)
      window.removeEventListener('scroll', updateMenuPosition, true)
    }
  }, [almacenMenuOpen, almacenOptions.length])

  const selectedAlmacenLabel = useMemo(() => {
    if (!almacenId) {
      return 'Todos'
    }
    return almacenOptions.find((option) => option.value === almacenId)?.label || 'Todos'
  }, [almacenId, almacenOptions])

  const selectedOrder = useMemo(() => {
    if (!sortedRows.length) {
      return null as OrderListItem | null
    }
    const explicit = sortedRows.find((row) => row.pedido_id === selectedCandidateId)
    return explicit ?? sortedRows[0]
  }, [selectedCandidateId, sortedRows])

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

  const loadIreksArticleCatalog = useCallback(async () => {
    const items: Array<{ articuloId: string; code: string; name: string; unitKg: number }> = []
    let offset = 0

    while (true) {
      const payload = await listIreksIngredients('', LIST_FETCH_SIZE, offset)
      items.push(
        ...payload.items.map((item: IngredientIreksRead) => {
          const articuloId = String(item.articulo_id || '').trim()
          const unitKg = safeNumber(item.articulo_envase_peso_total) > 0
            ? safeNumber(item.articulo_envase_peso_total)
            : safeNumber(item.articulo_envase_cantidad) * safeNumber(item.articulo_envase_peso)

          return {
            articuloId,
            code: item.articulo_referencia_corta || item.articulo_referencia || articuloId,
            name: item.articulo_descripcion || item.articulo_referencia || articuloId,
            unitKg,
          }
        }),
      )

      const fetched = payload.items.length
      if (!fetched || items.length >= payload.total) {
        return Object.fromEntries(
          items.map((item) => [
            item.articuloId,
            {
              code: item.code,
              name: item.name,
              unitKg: item.unitKg,
            },
          ]),
        )
      }

      offset += fetched
    }
  }, [])

  const articleDisplayQuery = useAsyncResource(loadIreksArticleCatalog, {} as Record<string, ArticleDisplayInfo>, [loadIreksArticleCatalog])

  const getArticleDisplay = (articleId: string) =>
    articleDisplayQuery.data[articleId] || { code: articleId, name: articleId, unitKg: 0 }

  function resolveLineKg(row: OrderItemRead) {
    const display = getArticleDisplay(row.articulo_id)
    const quantity = safeNumber(row.articulo_cantidad)
    const unitKg = safeNumber(display.unitKg)
    const lineKg = quantity * unitKg
    return lineKg > 0 ? lineKg : quantity
  }

  const listTotalKg = orderRows.reduce((acc, row) => acc + safeNumber(row.total_kg), 0)
  const detailLineQty = detailQuery.data.items.reduce((acc, row) => acc + safeNumber(row.articulo_cantidad), 0)
  const detailLineKg = detailQuery.data.items.reduce((acc, row) => acc + resolveLineKg(row), 0)
  const pendingQty = detailQuery.data.pending.reduce((acc, row) => acc + safeNumber(row.cantidad_pendiente), 0)

  const sortedDetailRows = useMemo(() => {
    const rows = [...detailQuery.data.items]

    rows.sort((left, right) => {
      let comparison = 0
      const leftDisplay = getArticleDisplay(left.articulo_id)
      const rightDisplay = getArticleDisplay(right.articulo_id)

      switch (detailSortKey) {
        case 'code':
          comparison = compareText(leftDisplay.code, rightDisplay.code)
          break
        case 'name':
          comparison = compareText(leftDisplay.name, rightDisplay.name)
          break
        case 'qty':
          comparison = safeNumber(left.articulo_cantidad) - safeNumber(right.articulo_cantidad)
          break
        case 'kg':
          comparison = resolveLineKg(left) - resolveLineKg(right)
          break
      }

      if (comparison === 0) {
        comparison = compareText(left.item_id, right.item_id)
      }

      return detailSortDirection === 'asc' ? comparison : -comparison
    })

    return rows
  }, [detailQuery.data.items, detailSortDirection, detailSortKey, articleDisplayQuery.data])

  const sortedPendingRows = useMemo(() => {
    const rows = [...detailQuery.data.pending]

    rows.sort((left, right) => {
      let comparison = 0
      const leftDisplay = getArticleDisplay(left.articulo_id)
      const rightDisplay = getArticleDisplay(right.articulo_id)

      switch (pendingSortKey) {
        case 'code':
          comparison = compareText(leftDisplay.code, rightDisplay.code)
          break
        case 'pedida':
          comparison = safeNumber(left.cantidad_pedida) - safeNumber(right.cantidad_pedida)
          break
        case 'recibida':
          comparison = safeNumber(left.cantidad_recibida) - safeNumber(right.cantidad_recibida)
          break
        case 'pendiente':
          comparison = safeNumber(left.cantidad_pendiente) - safeNumber(right.cantidad_pendiente)
          break
        case 'estado':
          comparison = compareText(left.estado || '', right.estado || '')
          break
      }

      if (comparison === 0) {
        comparison = compareText(left.pendiente_id, right.pendiente_id)
      }

      return pendingSortDirection === 'asc' ? comparison : -comparison
    })

    return rows
  }, [detailQuery.data.pending, pendingSortDirection, pendingSortKey, articleDisplayQuery.data])

  const sortAriaValue = (key: OrderSortKey) => {
    if (sortKey !== key) {
      return 'none'
    }
    return sortDirection === 'asc' ? 'ascending' : 'descending'
  }

  const detailSortAriaValue = (key: DetailSortKey) => {
    if (detailSortKey !== key) {
      return 'none'
    }
    return detailSortDirection === 'asc' ? 'ascending' : 'descending'
  }

  const pendingSortAriaValue = (key: PendingSortKey) => {
    if (pendingSortKey !== key) {
      return 'none'
    }
    return pendingSortDirection === 'asc' ? 'ascending' : 'descending'
  }

  const visibleOrderRows = useMemo(() => {
    const fillerRows = Math.max(0, LIST_VIEW_ROWS - sortedRows.length)
    return [
      ...sortedRows.map((row) => ({ type: 'data' as const, row })),
      ...Array.from({ length: fillerRows }, () => ({ type: 'empty' as const })),
    ]
  }, [sortedRows])

  return (
    <section className="page-grid orders-page">
      <div className="orders-workspace">
        <section className="panel-section orders-list-panel">
          <div className="section-heading">
            <div>
              <h3>Pedidos</h3>
            </div>
            <span className="surface-chip">{ordersQuery.data.total} visibles</span>
          </div>

          <div className="orders-filter-grid">
            <label className="orders-filter-field">
              <span>Ano</span>
              <select
                className="select"
                value={year}
                onChange={(event) => {
                  setYear(event.target.value)
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
                }}
              >
                {MONTH_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <div className="orders-filter-field orders-filter-field-wide orders-select-field">
              <span>Cliente/Distribuidor</span>
              <button
                type="button"
                className="select orders-select-trigger"
                aria-label="Cliente/Distribuidor"
                aria-haspopup="listbox"
                aria-expanded={almacenMenuOpen}
                ref={almacenTriggerRef}
                onClick={() => setAlmacenMenuOpen((current) => !current)}
              >
                <span className="orders-select-trigger-label">{selectedAlmacenLabel}</span>
                <span className="orders-select-trigger-arrow">▾</span>
              </button>
              {almacenMenuOpen && almacenMenuStyle &&
                createPortal(
                  <div
                    className="orders-select-menu"
                    role="listbox"
                    aria-label="Cliente/Distribuidor"
                    ref={almacenMenuRef}
                    style={{
                      position: 'fixed',
                      left: almacenMenuStyle.left,
                      top: almacenMenuStyle.top,
                      width: almacenMenuStyle.width,
                    }}
                  >
                    <button
                      type="button"
                      className={`orders-select-option ${almacenId === '' ? 'active' : ''}`}
                      onClick={() => {
                        setAlmacenId('')
                        setAlmacenMenuOpen(false)
                      }}
                    >
                      Todos
                    </button>
                    {almacenOptions.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className={`orders-select-option ${almacenId === option.value ? 'active' : ''}`}
                        onClick={() => {
                          setAlmacenId(option.value)
                          setAlmacenMenuOpen(false)
                        }}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>,
                  document.body,
                )}
            </div>
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
            {!ordersQuery.loading && !ordersQuery.error && (
              <>
                <div className="table-wrap orders-table-wrap">
                  <table>
                  <thead>
                    <tr>
                      <th className="orders-col-almacen" aria-sort={sortAriaValue('almacen')}>
                        <button type="button" className="orders-sort-button" onClick={() => updateSort('almacen')}>
                          <span>Almacen</span>
                          {sortKey === 'almacen' && <span className="orders-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                        </button>
                      </th>
                      <th className="orders-col-num" aria-sort={sortAriaValue('numero')}>
                        <button type="button" className="orders-sort-button" onClick={() => updateSort('numero')}>
                          <span>N&ordm;</span>
                          {sortKey === 'numero' && <span className="orders-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                        </button>
                      </th>
                      <th className="orders-col-fecha" aria-sort={sortAriaValue('fecha')}>
                        <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updateSort('fecha')}>
                          <span>Fecha</span>
                          {sortKey === 'fecha' && <span className="orders-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                        </button>
                      </th>
                      <th className="orders-col-semana" aria-sort={sortAriaValue('semana')}>
                        <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updateSort('semana')}>
                          <span>Sem.</span>
                          {sortKey === 'semana' && <span className="orders-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                        </button>
                      </th>
                      <th className="orders-col-total" aria-sort={sortAriaValue('total')}>
                        <button type="button" className="orders-sort-button" onClick={() => updateSort('total')}>
                          <span>Total Kg</span>
                          {sortKey === 'total' && <span className="orders-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                        </button>
                      </th>
                      <th className="orders-col-estado" aria-sort={sortAriaValue('estado')}>
                        <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updateSort('estado')}>
                          <span>Edo.</span>
                          {sortKey === 'estado' && <span className="orders-sort-indicator">{sortDirection === 'asc' ? '▲' : '▼'}</span>}
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleOrderRows.map((entry, index) =>
                      entry.type === 'data' ? (
                        <tr
                          key={entry.row.pedido_id}
                          className={entry.row.pedido_id === selectedOrder?.pedido_id ? 'row-selected' : ''}
                          onClick={() => setSelectedCandidateId(entry.row.pedido_id)}
                        >
                          <td className="orders-col-almacen">{entry.row.almacen_nombre || entry.row.almacen_id || '-'}</td>
                          <td className="orders-col-num">{entry.row.pedido_numero || '-'}</td>
                          <td className="orders-col-fecha">{formatDate(entry.row.pedido_fecha)}</td>
                          <td className="orders-col-semana">{entry.row.semana}</td>
                          <td className="orders-col-total">{formatNumber(safeNumber(entry.row.total_kg))} kg</td>
                          <td className="orders-col-estado">{entry.row.pedido_estado || '-'}</td>
                        </tr>
                      ) : (
                        <tr key={`empty-${index}`} className="orders-empty-row" aria-hidden="true">
                          <td className="orders-col-almacen">&nbsp;</td>
                          <td className="orders-col-num">&nbsp;</td>
                          <td className="orders-col-fecha">&nbsp;</td>
                          <td className="orders-col-semana">&nbsp;</td>
                          <td className="orders-col-total">&nbsp;</td>
                          <td className="orders-col-estado">&nbsp;</td>
                        </tr>
                      ),
                    )}
                  </tbody>
                  </table>
                </div>
                <div className="orders-list-footer">
                  <strong>TOTAL</strong>
                  <span className="orders-list-footer-value">{formatNumber(listTotalKg)} kg</span>
                </div>
              </>
            )}
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
              <span>Almacen</span>
              <input className="input" readOnly value={selectedOrder?.almacen_nombre || selectedOrder?.almacen_id || '-'} />
            </label>
            <label className="orders-detail-field">
              <span>Semana</span>
              <input className="input" readOnly value={selectedOrder ? String(selectedOrder.semana) : '-'} />
            </label>
            <label className="orders-detail-field">
              <span>Fecha</span>
              <input className="input" readOnly value={formatDate(selectedOrder?.pedido_fecha)} />
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
                        <th className="orders-detail-col-code" aria-sort={detailSortAriaValue('code')}>
                          <button type="button" className="orders-sort-button" onClick={() => updateDetailSort('code')}>
                            <span>Cod.</span>
                            {detailSortKey === 'code' && (
                              <span className="orders-sort-indicator">{detailSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                        <th className="orders-detail-col-name" aria-sort={detailSortAriaValue('name')}>
                          <button type="button" className="orders-sort-button" onClick={() => updateDetailSort('name')}>
                            <span>Nombre</span>
                            {detailSortKey === 'name' && (
                              <span className="orders-sort-indicator">{detailSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                        <th className="orders-detail-col-qty" aria-sort={detailSortAriaValue('qty')}>
                          <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updateDetailSort('qty')}>
                            <span>Cantidad</span>
                            {detailSortKey === 'qty' && (
                              <span className="orders-sort-indicator">{detailSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                        <th className="orders-detail-col-kg" aria-sort={detailSortAriaValue('kg')}>
                          <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updateDetailSort('kg')}>
                            <span>Kg</span>
                            {detailSortKey === 'kg' && (
                              <span className="orders-sort-indicator">{detailSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                      </tr>
                    </thead>
                  <tbody>
                    {sortedDetailRows.length ? (
                      sortedDetailRows.map((item) => (
                          <tr key={item.item_id}>
                            <td className="orders-detail-col-code">{getArticleDisplay(item.articulo_id).code}</td>
                            <td className="orders-detail-col-name">{getArticleDisplay(item.articulo_id).name}</td>
                            <td className="orders-detail-col-qty">{formatNumber(safeNumber(item.articulo_cantidad))}</td>
                            <td className="orders-detail-col-kg">{formatNumber(resolveLineKg(item))} kg</td>
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
                  <span className="orders-tab-footer-qty">{formatNumber(detailLineQty)}</span>
                  <span className="orders-tab-footer-kg">{formatNumber(detailLineKg)} kg</span>
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
                        <th className="orders-detail-col-pending-code" aria-sort={pendingSortAriaValue('code')}>
                          <button type="button" className="orders-sort-button" onClick={() => updatePendingSort('code')}>
                            <span>Cod.</span>
                            {pendingSortKey === 'code' && (
                              <span className="orders-sort-indicator">{pendingSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                        <th className="orders-detail-col-pending-num" aria-sort={pendingSortAriaValue('pedida')}>
                          <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updatePendingSort('pedida')}>
                            <span>Pedida</span>
                            {pendingSortKey === 'pedida' && (
                              <span className="orders-sort-indicator">{pendingSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                        <th className="orders-detail-col-pending-num" aria-sort={pendingSortAriaValue('recibida')}>
                          <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updatePendingSort('recibida')}>
                            <span>Recibida</span>
                            {pendingSortKey === 'recibida' && (
                              <span className="orders-sort-indicator">{pendingSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                        <th className="orders-detail-col-pending-num" aria-sort={pendingSortAriaValue('pendiente')}>
                          <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updatePendingSort('pendiente')}>
                            <span>Pendiente</span>
                            {pendingSortKey === 'pendiente' && (
                              <span className="orders-sort-indicator">{pendingSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                        <th className="orders-detail-col-pending-state" aria-sort={pendingSortAriaValue('estado')}>
                          <button type="button" className="orders-sort-button orders-sort-button-center" onClick={() => updatePendingSort('estado')}>
                            <span>Estado</span>
                            {pendingSortKey === 'estado' && (
                              <span className="orders-sort-indicator">{pendingSortDirection === 'asc' ? '▲' : '▼'}</span>
                            )}
                          </button>
                        </th>
                      </tr>
                    </thead>
                  <tbody>
                    {sortedPendingRows.length ? (
                      sortedPendingRows.map((row) => (
                          <tr key={row.pendiente_id}>
                            <td className="orders-detail-col-pending-code">{getArticleDisplay(row.articulo_id).code}</td>
                            <td className="orders-detail-col-pending-num">{formatNumber(safeNumber(row.cantidad_pedida))}</td>
                            <td className="orders-detail-col-pending-num">{formatNumber(safeNumber(row.cantidad_recibida))}</td>
                            <td className="orders-detail-col-pending-num">{formatNumber(safeNumber(row.cantidad_pendiente))}</td>
                            <td className="orders-detail-col-pending-state">{row.estado || '-'}</td>
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
