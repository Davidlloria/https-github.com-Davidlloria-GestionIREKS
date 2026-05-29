import { useCallback, useMemo, useState } from 'react'
import { listInventoryHistory, listMovements, listStock } from '../api/warehouse'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { InventoryHeaderRead, WarehouseMovementRead, WarehouseStockRead } from '../types/api'

interface WarehousePayload {
  stock: WarehouseStockRead[]
  movements: WarehouseMovementRead[]
  history: InventoryHeaderRead[]
}

const EMPTY_PAYLOAD: WarehousePayload = {
  stock: [],
  movements: [],
  history: [],
}

function safeNumber(value: unknown) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

export function WarehousePage() {
  const [almacenId, setAlmacenId] = useState('')

  const fetchPayload = useCallback(async () => {
    const [stock, movements, history] = await Promise.all([
      listStock(almacenId),
      listMovements(almacenId),
      listInventoryHistory(almacenId),
    ])
    return { stock, movements, history }
  }, [almacenId])

  const query = useAsyncResource(fetchPayload, EMPTY_PAYLOAD, [fetchPayload])

  const totals = useMemo(() => {
    const totalKg = query.data.stock.reduce((acc, row) => acc + safeNumber(row.cantidad_total), 0)
    return {
      stockRows: query.data.stock.length,
      movements: query.data.movements.length,
      inventoryChecks: query.data.history.length,
      totalKg: totalKg.toFixed(2),
    }
  }, [query.data])

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={almacenId}
          onChange={(event) => setAlmacenId(event.target.value)}
          placeholder="Filtrar por almacen_id (vacio = todos)"
        />
      </div>

      <div className="cards">
        <StatCard label="Filas stock" value={totals.stockRows} />
        <StatCard label="Movimientos" value={totals.movements} />
        <StatCard label="Inventarios" value={totals.inventoryChecks} />
        <StatCard label="Total stock (uds/kg)" value={totals.totalKg} />
      </div>

      <QueryState
        loading={query.loading}
        error={query.error}
        empty={!query.data.stock.length}
        emptyMessage="No hay stock para el almacen indicado."
      />

      {!!query.data.stock.length && (
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
              {query.data.stock.map((row) => (
                <tr key={`${row.almacen_id}-${row.articulo_id}`}>
                  <td>{row.almacen_id}</td>
                  <td>{row.articulo_id}</td>
                  <td>{safeNumber(row.cantidad_total).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!!query.data.movements.length && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Almacen</th>
                <th>Articulo</th>
                <th>Cantidad</th>
                <th>Pedido/Origen</th>
                <th>Lote</th>
              </tr>
            </thead>
            <tbody>
              {query.data.movements.slice(0, 12).map((row) => (
                <tr key={`${row.id ?? row.albaran_item_id}-${row.articulo_id}`}>
                  <td>{row.fecha_pedido}</td>
                  <td>{row.almacen_id}</td>
                  <td>{row.articulo_id}</td>
                  <td>{safeNumber(row.cantidad).toFixed(2)}</td>
                  <td>{row.pedido_albaran_numero || row.pedido_numero || '-'}</td>
                  <td>{row.articulo_lote || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
