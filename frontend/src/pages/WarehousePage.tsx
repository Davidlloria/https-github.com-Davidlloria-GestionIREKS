import { useCallback, useMemo, useState } from 'react'
import { createManualMovement, listInventoryHistory, listMovements, listStock } from '../api/warehouse'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type {
  InventoryHeaderRead,
  WarehouseManualMovementCreate,
  WarehouseMovementRead,
  WarehouseStockRead,
} from '../types/api'

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

interface ManualMovementForm {
  almacen_id: string
  articulo_id: string
  cantidad: string
  mode: 'in' | 'out'
  fecha_pedido: string
  articulo_lote: string
  pedido_albaran_numero: string
}

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

export function WarehousePage() {
  const [almacenId, setAlmacenId] = useState('')
  const [movementForm, setMovementForm] = useState<ManualMovementForm>({
    almacen_id: '',
    articulo_id: '',
    cantidad: '',
    mode: 'in',
    fecha_pedido: todayIsoDate(),
    articulo_lote: '',
    pedido_albaran_numero: '',
  })
  const [movementSaving, setMovementSaving] = useState(false)
  const [movementSaveMessage, setMovementSaveMessage] = useState('')
  const [movementSaveError, setMovementSaveError] = useState('')

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

  const onMovementFieldChange = <K extends keyof ManualMovementForm>(field: K, value: ManualMovementForm[K]) => {
    setMovementForm((prev) => ({ ...prev, [field]: value }))
  }

  const saveMovement = async () => {
    if (movementSaving) {
      return
    }
    const quantity = Number.parseFloat(movementForm.cantidad.replace(',', '.'))
    if (!movementForm.almacen_id.trim()) {
      setMovementSaveError('Debes indicar almacen_id.')
      setMovementSaveMessage('')
      return
    }
    if (!movementForm.articulo_id.trim()) {
      setMovementSaveError('Debes indicar articulo_id.')
      setMovementSaveMessage('')
      return
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setMovementSaveError('La cantidad debe ser un numero mayor que 0.')
      setMovementSaveMessage('')
      return
    }
    if (!movementForm.fecha_pedido) {
      setMovementSaveError('Debes indicar fecha del movimiento.')
      setMovementSaveMessage('')
      return
    }

    const payload: WarehouseManualMovementCreate = {
      almacen_id: movementForm.almacen_id.trim(),
      articulo_id: movementForm.articulo_id.trim(),
      cantidad: quantity,
      mode: movementForm.mode,
      fecha_pedido: movementForm.fecha_pedido,
      articulo_lote: movementForm.articulo_lote.trim(),
      pedido_albaran_numero: movementForm.pedido_albaran_numero.trim(),
    }

    setMovementSaving(true)
    setMovementSaveError('')
    setMovementSaveMessage('')
    try {
      await createManualMovement(payload)
      await query.reload()
      setMovementSaveMessage(
        payload.mode === 'in' ? 'Entrada manual registrada correctamente.' : 'Salida manual registrada correctamente.',
      )
      setMovementForm((prev) => ({
        ...prev,
        cantidad: '',
        articulo_lote: '',
        pedido_albaran_numero: '',
      }))
    } catch (error: unknown) {
      setMovementSaveError(error instanceof Error ? error.message : 'No se pudo registrar el movimiento manual.')
    } finally {
      setMovementSaving(false)
    }
  }

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

      <div className="detail-panel">
        <h3>Movimiento manual</h3>
        <div className="form-grid">
          <label>
            Almacen ID
            <input
              className="input"
              value={movementForm.almacen_id}
              onChange={(event) => onMovementFieldChange('almacen_id', event.target.value)}
              placeholder="Ej: ALM-01"
              disabled={movementSaving}
            />
          </label>
          <label>
            Articulo ID
            <input
              className="input"
              value={movementForm.articulo_id}
              onChange={(event) => onMovementFieldChange('articulo_id', event.target.value)}
              placeholder="Ej: 000123"
              disabled={movementSaving}
            />
          </label>
          <label>
            Modo
            <select
              className="select"
              value={movementForm.mode}
              onChange={(event) => onMovementFieldChange('mode', event.target.value as 'in' | 'out')}
              disabled={movementSaving}
            >
              <option value="in">Entrada</option>
              <option value="out">Salida</option>
            </select>
          </label>
          <label>
            Cantidad
            <input
              className="input"
              value={movementForm.cantidad}
              onChange={(event) => onMovementFieldChange('cantidad', event.target.value)}
              placeholder="Ej: 25.50"
              disabled={movementSaving}
            />
          </label>
          <label>
            Fecha pedido
            <input
              type="date"
              className="input"
              value={movementForm.fecha_pedido}
              onChange={(event) => onMovementFieldChange('fecha_pedido', event.target.value)}
              disabled={movementSaving}
            />
          </label>
          <label>
            Lote
            <input
              className="input"
              value={movementForm.articulo_lote}
              onChange={(event) => onMovementFieldChange('articulo_lote', event.target.value)}
              placeholder="Opcional"
              disabled={movementSaving}
            />
          </label>
          <label>
            Numero albaran/origen
            <input
              className="input"
              value={movementForm.pedido_albaran_numero}
              onChange={(event) => onMovementFieldChange('pedido_albaran_numero', event.target.value)}
              placeholder="Opcional"
              disabled={movementSaving}
            />
          </label>
        </div>
        <div className="toolbar">
          <button type="button" className="action-btn" onClick={saveMovement} disabled={movementSaving}>
            {movementSaving ? 'Guardando...' : 'Registrar movimiento'}
          </button>
        </div>
        {!!movementSaveMessage && <div className="state">{movementSaveMessage}</div>}
        {!!movementSaveError && <div className="state">Error: {movementSaveError}</div>}
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
