import { useMemo, useState } from 'react'
import { getInventoryDetail, listInventoryHistory, listMovements, listStock } from '../api/warehouse'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { InventoryDetailRead, InventoryHeaderRead, PaginatedList, WarehouseMovementRead, WarehouseStockRead } from '../types/api'

const PAGE_SIZE = 12

interface WarehousePayload {
  stock: PaginatedList<WarehouseStockRead>
  movements: PaginatedList<WarehouseMovementRead>
  history: PaginatedList<InventoryHeaderRead>
}

const EMPTY_PAYLOAD: WarehousePayload = {
  stock: { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
  movements: { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
  history: { items: [], total: 0, limit: PAGE_SIZE, offset: 0 },
}

const EMPTY_DETAIL: InventoryDetailRead[] = []

function safeNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function formatNumber(value: unknown) {
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(safeNumber(value))
}

function formatMaybeText(value: string | number | null | undefined) {
  if (value === null || value === undefined) {
    return '-'
  }
  const text = String(value).trim()
  return text || '-'
}

function limitLabel(total: number, visible: number) {
  if (total <= visible) {
    return 'Registros cargados'
  }
  return `Primeros ${visible} registros`
}

function SectionHead({
  title,
  description,
  countLabel,
}: {
  title: string
  description: string
  countLabel?: string
}) {
  return (
    <div className="section-heading warehouse-section-head">
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
      {!!countLabel && <span className="surface-chip">{countLabel}</span>}
    </div>
  )
}

export function WarehousePage() {
  const [almacenId, setAlmacenId] = useState('')
  const [selectedHistoryCandidateId, setSelectedHistoryCandidateId] = useState('')

  const fetchPayload = async () => {
    const [stock, movements, history] = await Promise.all([
      listStock(almacenId, PAGE_SIZE, 0),
      listMovements(almacenId, PAGE_SIZE, 0),
      listInventoryHistory(almacenId, PAGE_SIZE, 0),
    ])
    return { stock, movements, history }
  }

  const query = useAsyncResource(fetchPayload, EMPTY_PAYLOAD, [almacenId])
  const historyRows = query.data.history.items

  const selectedHistory = useMemo(() => {
    if (!historyRows.length) {
      return null
    }
    if (selectedHistoryCandidateId && historyRows.some((row) => row.inventario_id === selectedHistoryCandidateId)) {
      return historyRows.find((row) => row.inventario_id === selectedHistoryCandidateId) ?? null
    }
    return historyRows[0] ?? null
  }, [historyRows, selectedHistoryCandidateId])

  const detailQuery = useAsyncResource(
    () => (selectedHistory ? getInventoryDetail(selectedHistory.inventario_id) : Promise.resolve(EMPTY_DETAIL)),
    EMPTY_DETAIL,
    [selectedHistory?.inventario_id],
  )

  const totals = useMemo(() => {
    const stockTotal = query.data.stock.items.reduce((acc, row) => acc + safeNumber(row.cantidad_total), 0)
    const movementTotal = query.data.movements.items.reduce((acc, row) => acc + safeNumber(row.cantidad), 0)
    const detailTotal = detailQuery.data.reduce((acc, row) => acc + safeNumber(row.kg_ajuste), 0)
    return {
      stockRows: query.data.stock.total,
      movementsRows: query.data.movements.total,
      inventoryRows: query.data.history.total,
      stockTotal: formatNumber(stockTotal),
      movementTotal: formatNumber(movementTotal),
      detailTotal: formatNumber(detailTotal),
    }
  }, [detailQuery.data, query.data.history.total, query.data.movements.items, query.data.movements.total, query.data.stock.items, query.data.stock.total])

  return (
    <section className="page-grid warehouse-page">
      <header className="warehouse-header">
        <div className="warehouse-header-copy">
          <p className="warehouse-kicker">Almacén</p>
          <h2>Almacén</h2>
          <p className="warehouse-subtitle">Consulta read-only de stock, movimientos e inventarios históricos.</p>
        </div>
        <div className="warehouse-header-meta">
          <span className="surface-chip">Vista read-only</span>
          <span className="surface-chip">{selectedHistory ? `Inventario ${selectedHistory.inventario_id}` : 'Sin inventario seleccionado'}</span>
        </div>
      </header>

      <section className="panel-section warehouse-filter-panel">
        <SectionHead
          title="Filtro de almacén"
          description="Filtra el stock, los movimientos y el histórico actualmente cargados."
        />
        <div className="toolbar warehouse-filter-toolbar">
          <input
            className="input"
            value={almacenId}
            onChange={(event) => setAlmacenId(event.target.value)}
            placeholder="Filtrar por almacen_id (opcional)"
          />
        </div>
      </section>

      <div className="warehouse-summary-grid">
        <StatCard label="Filas stock" value={totals.stockRows} />
        <StatCard label="Movimientos" value={totals.movementsRows} />
        <StatCard label="Inventarios" value={totals.inventoryRows} />
        <StatCard label="Stock total" value={totals.stockTotal} />
        <StatCard label="Movimientos uds" value={totals.movementTotal} />
      </div>

      <QueryState
        loading={query.loading}
        error={query.error}
        empty={!query.data.stock.items.length && !query.data.movements.items.length && !query.data.history.items.length}
        emptyMessage="No hay datos de almacén para el filtro actual."
      />

      <div className="warehouse-workspace">
        <div className="warehouse-left-column">
          <section className="panel-section warehouse-panel warehouse-stock-panel">
            <SectionHead
              title="Stock actual"
              description="Consulta de stock agregado por almacén y artículo."
              countLabel={`${limitLabel(query.data.stock.total, query.data.stock.items.length)} · ${query.data.stock.total} filas`}
            />
            {query.data.stock.items.length > 0 ? (
              <div className="warehouse-scroll">
                <div className="table-wrap warehouse-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Almacén</th>
                        <th>Artículo ID</th>
                        <th>Cantidad total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {query.data.stock.items.map((row) => (
                        <tr key={`${row.almacen_id}-${row.articulo_id}`}>
                          <td>{row.almacen_id}</td>
                          <td>{row.articulo_id}</td>
                          <td>{formatNumber(row.cantidad_total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="state state-empty">Sin filas de stock para el filtro actual.</div>
            )}
          </section>

          <section className="panel-section warehouse-panel warehouse-movements-panel">
            <SectionHead
              title="Últimos movimientos"
              description="Movimientos recientes del almacén con fecha, artículo y origen."
              countLabel={`${limitLabel(query.data.movements.total, query.data.movements.items.length)} · ${query.data.movements.total} filas`}
            />
            {query.data.movements.items.length > 0 ? (
              <div className="warehouse-scroll">
                <div className="table-wrap warehouse-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Almacén</th>
                        <th>Artículo</th>
                        <th>Cantidad</th>
                        <th>Pedido / origen</th>
                        <th>Lote</th>
                      </tr>
                    </thead>
                    <tbody>
                      {query.data.movements.items.map((row) => (
                        <tr key={`${row.id ?? row.albaran_item_id}-${row.articulo_id}-${row.fecha_pedido}`}>
                          <td>{formatMaybeText(row.fecha_pedido)}</td>
                          <td>{formatMaybeText(row.almacen_id)}</td>
                          <td>{formatMaybeText(row.articulo_id)}</td>
                          <td>{formatNumber(row.cantidad)}</td>
                          <td>{formatMaybeText(row.pedido_albaran_numero || row.pedido_numero)}</td>
                          <td>{formatMaybeText(row.articulo_lote)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="state state-empty">Sin movimientos para el filtro actual.</div>
            )}
          </section>
        </div>

        <div className="warehouse-right-column">
          <section className="panel-section warehouse-panel warehouse-history-panel">
            <SectionHead
              title="Histórico de inventarios"
              description="Selecciona un inventario para abrir su detalle read-only."
              countLabel={`${historyRows.length} visibles`}
            />
            {historyRows.length > 0 ? (
              <div className="warehouse-scroll">
                <div className="table-wrap warehouse-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Inventario ID</th>
                        <th>Almacén</th>
                        <th>Fecha</th>
                        <th>Estado</th>
                        <th>Líneas</th>
                        <th>Ajustes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historyRows.map((row) => (
                        <tr
                          key={row.inventario_id}
                          className={row.inventario_id === selectedHistory?.inventario_id ? 'row-selected' : ''}
                          onClick={() => setSelectedHistoryCandidateId(row.inventario_id)}
                        >
                          <td>{row.inventario_id}</td>
                          <td>{formatMaybeText(row.almacen_id)}</td>
                          <td>{formatMaybeText(row.fecha)}</td>
                          <td>{formatMaybeText(row.estado)}</td>
                          <td>{row.lineas}</td>
                          <td>{row.ajustes}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="state state-empty">Sin inventarios para el filtro actual.</div>
            )}
          </section>

          <section className="panel-section warehouse-panel warehouse-detail-panel">
            <SectionHead
              title="Detalle de inventario"
              description="Cabecera del inventario y líneas de ajuste."
              countLabel={selectedHistory ? selectedHistory.inventario_id : 'Sin selección'}
            />
            <QueryState
              loading={detailQuery.loading}
              error={detailQuery.error}
              empty={!selectedHistory || !detailQuery.data.length}
              emptyMessage={
                selectedHistory
                  ? 'No hay líneas para el inventario seleccionado.'
                  : 'Selecciona un inventario histórico para ver el detalle.'
              }
            />

            {!!selectedHistory && !!detailQuery.data.length && (
              <div className="warehouse-detail-scroll">
                <dl className="detail-list warehouse-detail-summary">
                  <div>
                    <dt>Inventario ID</dt>
                    <dd>{selectedHistory.inventario_id}</dd>
                  </div>
                  <div>
                    <dt>Almacén</dt>
                    <dd>{formatMaybeText(selectedHistory.almacen_id)}</dd>
                  </div>
                  <div>
                    <dt>Fecha</dt>
                    <dd>{formatMaybeText(selectedHistory.fecha)}</dd>
                  </div>
                  <div>
                    <dt>Estado</dt>
                    <dd>{formatMaybeText(selectedHistory.estado)}</dd>
                  </div>
                  <div>
                    <dt>Líneas</dt>
                    <dd>{selectedHistory.lineas}</dd>
                  </div>
                  <div>
                    <dt>Ajustes</dt>
                    <dd>{selectedHistory.ajustes}</dd>
                  </div>
                  <div>
                    <dt>Total ajuste KG</dt>
                    <dd>{totals.detailTotal}</dd>
                  </div>
                </dl>

                <div className="table-wrap warehouse-table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Artículo</th>
                        <th>Lote</th>
                        <th>Caducidad</th>
                        <th>Teórico</th>
                        <th>Conteo</th>
                        <th>Diferencia</th>
                        <th>KG ajuste</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailQuery.data.map((row) => (
                        <tr key={`${row.id ?? row.articulo_id}-${row.articulo_lote}`}>
                          <td>{formatMaybeText(row.articulo_id)}</td>
                          <td>{formatMaybeText(row.articulo_lote)}</td>
                          <td>{formatMaybeText(row.articulo_caducidad)}</td>
                          <td>{formatNumber(row.teorico_uds)}</td>
                          <td>{formatNumber(row.conteo_uds)}</td>
                          <td>{formatNumber(row.diferencia_uds)}</td>
                          <td>{formatNumber(row.kg_ajuste)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </section>
  )
}
