import { useMemo, useState } from 'react'
import { getSalesAnnualSummary, listSalesAnnualClients, listSalesAnnualYears } from '../api/sales'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type {
  SalesAnnualSummaryResponse,
  SalesFilterOption,
  SalesYearOption,
} from '../types/api'

const EMPTY_SUMMARY: SalesAnnualSummaryResponse = {
  source: 'ireks',
  year: 0,
  month: 0,
  acumulado: false,
  total: 0,
  items: [],
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0)
}

function formatSigned(value: number) {
  const safe = Number.isFinite(value) ? value : 0
  return `${safe >= 0 ? '+' : ''}${formatNumber(safe)}`
}

export function SalesPage() {
  const [year, setYear] = useState('')
  const [clienteId, setClienteId] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)

  const yearsQuery = useAsyncResource(() => listSalesAnnualYears(), { items: [] }, [])
  const clientsQuery = useAsyncResource(() => listSalesAnnualClients(), { items: [] }, [])
  const defaultYear = yearsQuery.data.items[0]?.year ? String(yearsQuery.data.items[0].year) : ''
  const selectedYear = year || defaultYear

  const summaryQuery = useAsyncResource(
    () => {
      if (!selectedYear) {
        return Promise.resolve(EMPTY_SUMMARY)
      }
      return getSalesAnnualSummary(Number(selectedYear), clienteId || undefined)
    },
    EMPTY_SUMMARY,
    [selectedYear, clienteId, refreshToken],
  )

  const yearOptions = yearsQuery.data.items as SalesYearOption[]
  const clientOptions = clientsQuery.data.items as SalesFilterOption[]

  const metrics = useMemo(() => {
    const rows = summaryQuery.data.items
    const totals = rows.reduce(
      (acc, row) => ({
        prevKg: acc.prevKg + row.kilos_prev,
        currKg: acc.currKg + row.kilos_curr,
        prevSales: acc.prevSales + row.ventas_prev,
        currSales: acc.currSales + row.ventas_curr,
      }),
      { prevKg: 0, currKg: 0, prevSales: 0, currSales: 0 },
    )
    return {
      rows: rows.length,
      prevKg: totals.prevKg,
      currKg: totals.currKg,
      deltaKg: totals.currKg - totals.prevKg,
      prevSales: totals.prevSales,
      currSales: totals.currSales,
      deltaSales: totals.currSales - totals.prevSales,
    }
  }, [summaryQuery.data.items])

  const canQuery = Boolean(selectedYear)
  const summaryLoading = summaryQuery.loading && canQuery
  const summaryEmpty = canQuery && !summaryQuery.loading && !summaryQuery.error && !summaryQuery.data.items.length

  return (
    <section className="page-grid">
      <div className="detail-panel">
        <h3>Ventas anual</h3>
        <div className="form-grid sales-controls">
          <label>
            Ano
            <select
              className="select"
              value={selectedYear}
              onChange={(event) => setYear(event.target.value)}
              disabled={yearsQuery.loading}
            >
              <option value="">Selecciona un ano</option>
              {yearOptions.map((option) => (
                <option key={option.year} value={String(option.year)}>
                  {option.label || option.year}
                </option>
              ))}
            </select>
          </label>
          <label>
            Cliente
            <select className="select" value={clienteId} onChange={(event) => setClienteId(event.target.value)}>
              <option value="">Todos</option>
              {clientOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name || option.code || option.id}
                </option>
              ))}
            </select>
          </label>
          <div className="sales-actions">
            <button type="button" className="action-btn" onClick={() => setRefreshToken((value) => value + 1)}>
              Consultar
            </button>
            <span className="state sales-hint">
              Datos desde <strong>/sales/annual-summary</strong> y filtros de años/clientes
            </span>
          </div>
        </div>
        {(yearsQuery.loading || clientsQuery.loading) && <div className="state state-loading">Cargando filtros...</div>}
        {!!yearsQuery.error && <div className="state state-error">Error: {yearsQuery.error}</div>}
        {!!clientsQuery.error && <div className="state state-error">Error: {clientsQuery.error}</div>}
      </div>

      <div className="cards">
        <StatCard label="Lineas" value={metrics.rows} />
        <StatCard label="Kg previos" value={formatNumber(metrics.prevKg)} />
        <StatCard label="Kg actuales" value={formatNumber(metrics.currKg)} />
        <StatCard label="Delta kg" value={formatSigned(metrics.deltaKg)} />
      </div>

      <div className="cards">
        <StatCard label="Ventas previas" value={formatNumber(metrics.prevSales)} />
        <StatCard label="Ventas actuales" value={formatNumber(metrics.currSales)} />
        <StatCard label="Delta ventas" value={formatSigned(metrics.deltaSales)} />
        <StatCard label="Fuente" value={summaryQuery.data.source ? summaryQuery.data.source.toUpperCase() : '-'} />
      </div>

      {!canQuery && !yearsQuery.loading && !yearsQuery.error && (
        <div className="state state-empty">Selecciona un ano para consultar la comparacion anual.</div>
      )}

      <QueryState
        loading={summaryLoading}
        error={summaryQuery.error}
        empty={summaryEmpty}
        emptyMessage="No hay datos para la combinacion de filtros seleccionada."
      />

      {!!summaryQuery.data.items.length && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Codigo</th>
                <th>Nombre</th>
                <th>Kg prev</th>
                <th>Kg curr</th>
                <th>Ventas prev</th>
                <th>Ventas curr</th>
                <th>Delta kg</th>
                <th>Delta ventas</th>
              </tr>
            </thead>
            <tbody>
              {summaryQuery.data.items.map((row) => (
                <tr key={row.articulo_id || row.codigo}>
                  <td>{row.codigo || row.articulo_id}</td>
                  <td>{row.nombre || '-'}</td>
                  <td>{formatNumber(row.kilos_prev)}</td>
                  <td>{formatNumber(row.kilos_curr)}</td>
                  <td>{formatNumber(row.ventas_prev)}</td>
                  <td>{formatNumber(row.ventas_curr)}</td>
                  <td>{formatSigned(row.delta_kg)}</td>
                  <td>{formatSigned(row.delta_ventas)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
