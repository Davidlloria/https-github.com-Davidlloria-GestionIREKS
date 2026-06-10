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
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={almacenId}
          onChange={(event) => setAlmacenId(event.target.value)}
          placeholder="Filtrar por almacen_id (opcional)"
        />
      </div>

      <div className="cards">
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
        emptyMessage="No hay datos de almacen para el filtro actual."
      />

      {!!query.data.stock.items.length && (
        <div className="detail-panel">
          <h3>Stock actual</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Almacen</th>
                  <th>Articulo ID</th>
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
      )}

      {!!query.data.movements.items.length && (
        <div className="detail-panel">
          <h3>Ultimos movimientos</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Almacen</th>
                  <th>Articulo</th>
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
      )}

      <div className="split-panel">
        <div className="table-wrap">
          <h3 style={{ marginTop: 0 }}>Historico de inventarios</h3>
          <table>
            <thead>
              <tr>
                <th>Inventario ID</th>
                <th>Almacen</th>
                <th>Fecha</th>
                <th>Estado</th>
                <th>Lineas</th>
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

        <aside className="detail-panel">
          <h3>Detalle de inventario</h3>
          <QueryState
            loading={detailQuery.loading}
            error={detailQuery.error}
            empty={!selectedHistory || !detailQuery.data.length}
            emptyMessage={
              selectedHistory
                ? 'No hay lineas para el inventario seleccionado.'
                : 'Selecciona un inventario historico para ver el detalle.'
            }
          />

          {!!selectedHistory && !!detailQuery.data.length && (
            <>
              <dl className="detail-list">
                <div>
                  <dt>Inventario ID</dt>
                  <dd>{selectedHistory.inventario_id}</dd>
                </div>
                <div>
                  <dt>Almacen</dt>
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
                  <dt>Lineas</dt>
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

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Articulo</th>
                      <th>Lote</th>
                      <th>Caducidad</th>
                      <th>Teorico</th>
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
            </>
          )}
        </aside>
      </div>
    </section>
  )
}
