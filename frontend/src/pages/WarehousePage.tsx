import { useCallback, useMemo, useState } from 'react'
import { applyInventoryAdjustments, createManualMovement, listInventoryHistory, listMovements, listStock } from '../api/warehouse'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type {
  InventoryAdjustmentPayload,
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

interface InventoryAdjustmentForm {
  almacen_id: string
  contador: string
  aprobador: string
  articulo_id: string
  articulo_lote: string
  articulo_caducidad: string
  teorico_uds: string
  conteo_uds: string
  diferencia_uds: string
  kg_ajuste: string
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
  const [adjustmentForm, setAdjustmentForm] = useState<InventoryAdjustmentForm>({
    almacen_id: '',
    contador: '',
    aprobador: '',
    articulo_id: '',
    articulo_lote: '',
    articulo_caducidad: '',
    teorico_uds: '0',
    conteo_uds: '0',
    diferencia_uds: '0',
    kg_ajuste: '0',
  })
  const [adjustmentSaving, setAdjustmentSaving] = useState(false)
  const [adjustmentSaveMessage, setAdjustmentSaveMessage] = useState('')
  const [adjustmentSaveError, setAdjustmentSaveError] = useState('')

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

  const onAdjustmentFieldChange = <K extends keyof InventoryAdjustmentForm>(
    field: K,
    value: InventoryAdjustmentForm[K],
  ) => {
    setAdjustmentForm((prev) => ({ ...prev, [field]: value }))
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

  const saveAdjustment = async () => {
    if (adjustmentSaving) {
      return
    }
    const almacenIdValue = adjustmentForm.almacen_id.trim()
    const articuloIdValue = adjustmentForm.articulo_id.trim()
    if (!almacenIdValue) {
      setAdjustmentSaveError('Debes indicar almacen_id para el ajuste.')
      setAdjustmentSaveMessage('')
      return
    }
    if (!articuloIdValue) {
      setAdjustmentSaveError('Debes indicar articulo_id para el ajuste.')
      setAdjustmentSaveMessage('')
      return
    }

    const teoricoUds = Number.parseFloat(adjustmentForm.teorico_uds.replace(',', '.'))
    const conteoUds = Number.parseFloat(adjustmentForm.conteo_uds.replace(',', '.'))
    const diferenciaUds = Number.parseFloat(adjustmentForm.diferencia_uds.replace(',', '.'))
    const kgAjuste = Number.parseFloat(adjustmentForm.kg_ajuste.replace(',', '.'))

    if (![teoricoUds, conteoUds, diferenciaUds, kgAjuste].every((value) => Number.isFinite(value))) {
      setAdjustmentSaveError('Los campos numericos del ajuste deben ser validos.')
      setAdjustmentSaveMessage('')
      return
    }

    const payload: InventoryAdjustmentPayload = {
      almacen_id: almacenIdValue,
      contador: adjustmentForm.contador.trim(),
      aprobador: adjustmentForm.aprobador.trim(),
      adjustments: [
        {
          articulo_id: articuloIdValue,
          articulo_lote: adjustmentForm.articulo_lote.trim(),
          articulo_caducidad: adjustmentForm.articulo_caducidad.trim() || null,
          teorico_uds: teoricoUds,
          conteo_uds: conteoUds,
          diferencia_uds: diferenciaUds,
          kg_ajuste: kgAjuste,
        },
      ],
    }

    setAdjustmentSaving(true)
    setAdjustmentSaveError('')
    setAdjustmentSaveMessage('')
    try {
      const created = await applyInventoryAdjustments(payload)
      await query.reload()
      setAdjustmentSaveMessage(`Ajuste aplicado en inventario ${created.inventario_id}.`)
      setAdjustmentForm((prev) => ({
        ...prev,
        articulo_id: '',
        articulo_lote: '',
        articulo_caducidad: '',
      }))
    } catch (error: unknown) {
      setAdjustmentSaveError(error instanceof Error ? error.message : 'No se pudo aplicar el ajuste de inventario.')
    } finally {
      setAdjustmentSaving(false)
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

      <div className="detail-panel">
        <h3>Ajuste de inventario</h3>
        <div className="form-grid">
          <label>
            Almacen ID
            <input
              className="input"
              value={adjustmentForm.almacen_id}
              onChange={(event) => onAdjustmentFieldChange('almacen_id', event.target.value)}
              placeholder="Ej: ALM-01"
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            Contador
            <input
              className="input"
              value={adjustmentForm.contador}
              onChange={(event) => onAdjustmentFieldChange('contador', event.target.value)}
              placeholder="Opcional"
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            Aprobador
            <input
              className="input"
              value={adjustmentForm.aprobador}
              onChange={(event) => onAdjustmentFieldChange('aprobador', event.target.value)}
              placeholder="Opcional"
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            Articulo ID
            <input
              className="input"
              value={adjustmentForm.articulo_id}
              onChange={(event) => onAdjustmentFieldChange('articulo_id', event.target.value)}
              placeholder="Ej: 000123"
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            Lote
            <input
              className="input"
              value={adjustmentForm.articulo_lote}
              onChange={(event) => onAdjustmentFieldChange('articulo_lote', event.target.value)}
              placeholder="Opcional"
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            Caducidad
            <input
              type="date"
              className="input"
              value={adjustmentForm.articulo_caducidad}
              onChange={(event) => onAdjustmentFieldChange('articulo_caducidad', event.target.value)}
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            Teorico UDS
            <input
              className="input"
              value={adjustmentForm.teorico_uds}
              onChange={(event) => onAdjustmentFieldChange('teorico_uds', event.target.value)}
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            Conteo UDS
            <input
              className="input"
              value={adjustmentForm.conteo_uds}
              onChange={(event) => onAdjustmentFieldChange('conteo_uds', event.target.value)}
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            Diferencia UDS
            <input
              className="input"
              value={adjustmentForm.diferencia_uds}
              onChange={(event) => onAdjustmentFieldChange('diferencia_uds', event.target.value)}
              disabled={adjustmentSaving}
            />
          </label>
          <label>
            KG ajuste
            <input
              className="input"
              value={adjustmentForm.kg_ajuste}
              onChange={(event) => onAdjustmentFieldChange('kg_ajuste', event.target.value)}
              disabled={adjustmentSaving}
            />
          </label>
        </div>
        <div className="toolbar">
          <button type="button" className="action-btn" onClick={saveAdjustment} disabled={adjustmentSaving}>
            {adjustmentSaving ? 'Aplicando...' : 'Aplicar ajuste'}
          </button>
        </div>
        {!!adjustmentSaveMessage && <div className="state">{adjustmentSaveMessage}</div>}
        {!!adjustmentSaveError && <div className="state">Error: {adjustmentSaveError}</div>}
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

      {!!query.data.history.length && (
        <div className="table-wrap">
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
              {query.data.history.slice(0, 12).map((row) => (
                <tr key={row.inventario_id}>
                  <td>{row.inventario_id}</td>
                  <td>{row.almacen_id || '-'}</td>
                  <td>{row.fecha}</td>
                  <td>{row.estado || '-'}</td>
                  <td>{row.lineas}</td>
                  <td>{row.ajustes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
