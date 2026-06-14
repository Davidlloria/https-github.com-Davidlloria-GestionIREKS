import { useMemo, useState } from 'react'
import {
  getSalesAnnualSummary,
  listSalesAnnualClients,
  listSalesAnnualFamilies,
  listSalesAnnualManufacturers,
  listSalesAnnualSubfamilies,
  listSalesAnnualYears,
  type SalesSource,
} from '../api/sales'
import { EmptyState, ErrorState, LoadingState, QueryState } from '../components/QueryState'
import { useAsyncResource } from '../features/useAsyncResource'
import type {
  SalesAnnualSummaryResponse,
  SalesFilterOption,
  SalesFilterOptionsResponse,
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

const MONTH_OPTIONS = [
  ['0', 'Todos'],
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

const SOURCE_TABS: Array<{ key: SalesSource; label: string }> = [
  { key: 'ireks', label: 'IREKS' },
  { key: 'igsa', label: 'IGSA' },
]

function formatNumber(value: number) {
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0)
}

function formatSigned(value: number) {
  const safe = Number.isFinite(value) ? value : 0
  return `${safe >= 0 ? '' : '-'}${formatNumber(Math.abs(safe))}`
}

function formatPercent(value: number) {
  const safe = Number.isFinite(value) ? value : 0
  return `${safe >= 0 ? '' : '-'}${formatNumber(Math.abs(safe))} %`
}

function getOptionLabel(option: SalesFilterOption) {
  return option.name || option.code || option.id
}

export function SalesPage() {
  const [source, setSource] = useState<SalesSource>('ireks')
  const [year, setYear] = useState('')
  const [month, setMonth] = useState('0')
  const [acumulado, setAcumulado] = useState(false)
  const [clienteId, setClienteId] = useState('')
  const [fabricanteId, setFabricanteId] = useState('')
  const [familiaId, setFamiliaId] = useState('')
  const [subfamiliaId, setSubfamiliaId] = useState('')
  const [productoTexto, setProductoTexto] = useState('')
  const [refreshToken, setRefreshToken] = useState(0)

  const yearsQuery = useAsyncResource(() => listSalesAnnualYears(source), { items: [] }, [source, refreshToken])
  const clientsQuery = useAsyncResource(
    () => (source === 'ireks' ? listSalesAnnualClients() : Promise.resolve({ items: [] } as SalesFilterOptionsResponse)),
    { items: [] },
    [source, refreshToken],
  )
  const manufacturersQuery = useAsyncResource(
    () => listSalesAnnualManufacturers(source),
    { items: [] },
    [source, refreshToken],
  )
  const familiesQuery = useAsyncResource(
    () => listSalesAnnualFamilies(source, fabricanteId),
    { items: [] },
    [source, fabricanteId, refreshToken],
  )
  const subfamiliesQuery = useAsyncResource(
    () => listSalesAnnualSubfamilies(source, familiaId),
    { items: [] },
    [source, familiaId, refreshToken],
  )

  const defaultYear = yearsQuery.loading ? '' : yearsQuery.data.items[0]?.year ? String(yearsQuery.data.items[0].year) : ''
  const selectedYear = year || defaultYear
  const selectedYearNumber = Number(selectedYear)
  const previousYearLabel = selectedYearNumber > 0 ? String(selectedYearNumber - 1) : 'Año previo'
  const currentYearLabel = selectedYear || 'Año actual'

  const summaryQuery = useAsyncResource(
    () => {
      if (!selectedYear) {
        return Promise.resolve(EMPTY_SUMMARY)
      }
      return getSalesAnnualSummary({
        source,
        year: selectedYearNumber,
        month: Number(month),
        acumulado,
        clienteId: source === 'ireks' ? clienteId || undefined : undefined,
        productoTexto: productoTexto || undefined,
        fabricanteId: fabricanteId || undefined,
        familiaId: familiaId || undefined,
        subfamiliaId: subfamiliaId || undefined,
      })
    },
    EMPTY_SUMMARY,
    [source, selectedYear, month, acumulado, clienteId, productoTexto, fabricanteId, familiaId, subfamiliaId, refreshToken],
  )

  const yearOptions = yearsQuery.data.items as SalesYearOption[]
  const clientOptions = clientsQuery.data.items as SalesFilterOption[]
  const manufacturerOptions = manufacturersQuery.data.items as SalesFilterOption[]
  const familyOptions = familiesQuery.data.items as SalesFilterOption[]
  const subfamilyOptions = subfamiliesQuery.data.items as SalesFilterOption[]

  const rows = summaryQuery.data.items
  const totals = useMemo(
    () =>
      rows.reduce(
        (acc, row) => ({
          prevKg: acc.prevKg + row.kilos_prev,
          currKg: acc.currKg + row.kilos_curr,
          prevSc: acc.prevSc + row.sc_prev,
          currSc: acc.currSc + row.sc_curr,
          prevSales: acc.prevSales + row.ventas_prev,
          currSales: acc.currSales + row.ventas_curr,
        }),
        { prevKg: 0, currKg: 0, prevSc: 0, currSc: 0, prevSales: 0, currSales: 0 },
      ),
    [rows],
  )

  const deltaKg = totals.currKg - totals.prevKg
  const deltaKgPct = totals.prevKg === 0 ? 0 : (deltaKg / totals.prevKg) * 100
  const deltaSales = totals.currSales - totals.prevSales
  const deltaSalesPct = totals.prevSales === 0 ? 0 : (deltaSales / totals.prevSales) * 100

  const canQuery = Boolean(selectedYear)
  const summaryLoading = summaryQuery.loading && canQuery
  const summaryEmpty = canQuery && !summaryQuery.loading && !summaryQuery.error && !rows.length

  const visibleCount = summaryLoading ? 0 : summaryQuery.data.total || rows.length

  return (
    <section className="page-grid sales-page">
      <header className="sales-page-header">
        <div className="sales-page-header-copy">
          <p className="module-kicker">Comparativa anual read-only</p>
          <h2>Ventas</h2>
          <p className="module-description">
            Consulta de ventas con estructura SaaS compacta, filtros read-only y comparación entre ejercicios.
          </p>
        </div>
        <div className="sales-page-header-meta">
          <span className="surface-chip">{source.toUpperCase()}</span>
          <span className="surface-chip">{selectedYear ? `Año ${selectedYear}` : 'Sin año seleccionado'}</span>
          <span className="surface-chip">{visibleCount} visibles</span>
        </div>
      </header>

      <div className="sales-source-tabs" role="tablist" aria-label="Origen de ventas">
        {SOURCE_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={source === tab.key}
            aria-current={source === tab.key ? 'page' : undefined}
            className={`sales-source-tab ${source === tab.key ? 'sales-source-tab-active' : ''}`}
            onClick={() => setSource(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <section className="panel-section sales-filters-panel">
        <div className="section-heading section-heading-compact">
          <div>
            <h3>Filtros</h3>
            <p>Usa los filtros read-only para comparar el resumen anual.</p>
          </div>
          <div className="toolbar pager-toolbar">
            <button type="button" className="action-btn sales-refresh-btn" onClick={() => setRefreshToken((value) => value + 1)}>
              Refrescar
            </button>
          </div>
        </div>

        <div className="sales-filter-grid">
          <label className="sales-filter-field">
            <span>Año</span>
            <select
              className="select"
              value={selectedYear}
              onChange={(event) => setYear(event.target.value)}
              disabled={yearsQuery.loading}
            >
              <option value="">Selecciona un año</option>
              {yearOptions.map((option) => (
                <option key={option.year} value={String(option.year)}>
                  {option.label || option.year}
                </option>
              ))}
            </select>
          </label>
          <label className="sales-filter-field">
            <span>Mes</span>
            <select className="select" value={month} onChange={(event) => setMonth(event.target.value)}>
              {MONTH_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="sales-check-field">
            <span>Acumulado</span>
            <div className="sales-check-row">
              <input type="checkbox" checked={acumulado} onChange={(event) => setAcumulado(event.target.checked)} />
              <span>{acumulado ? 'Sí' : 'No'}</span>
            </div>
          </label>
          <label className="sales-filter-field">
            <span>Cliente/Distribuidor</span>
            <select
              className="select"
              value={source === 'ireks' ? clienteId : ''}
              onChange={(event) => setClienteId(event.target.value)}
              disabled={source === 'igsa' || clientsQuery.loading}
            >
              <option value="">{source === 'igsa' ? 'No disponible en IGSA' : 'Todos'}</option>
              {source === 'ireks' &&
                clientOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {getOptionLabel(option)}
                  </option>
                ))}
            </select>
          </label>
        </div>

        <div className="sales-filter-grid sales-filter-grid-secondary">
          <label className="sales-filter-field">
            <span>Fabricante</span>
            <select className="select" value={fabricanteId} onChange={(event) => setFabricanteId(event.target.value)}>
              <option value="">Todos</option>
              {manufacturerOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {getOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="sales-filter-field">
            <span>Familia</span>
            <select
              className="select"
              value={familiaId}
              onChange={(event) => {
                setFamiliaId(event.target.value)
                setSubfamiliaId('')
              }}
            >
              <option value="">Todas</option>
              {familyOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {getOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="sales-filter-field">
            <span>Subfamilia</span>
            <select className="select" value={subfamiliaId} onChange={(event) => setSubfamiliaId(event.target.value)}>
              <option value="">Todas</option>
              {subfamilyOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {getOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="sales-filter-field sales-filter-field-wide">
            <span>Producto</span>
            <input
              className="input"
              value={productoTexto}
              onChange={(event) => setProductoTexto(event.target.value)}
              placeholder="Buscar por código o descripción..."
            />
          </label>
          <div className="sales-actions">
            <span className="state sales-hint">
              Datos desde <strong>{source === 'igsa' ? '/sales/annual-summary/igsa' : '/sales/annual-summary'}</strong>
            </span>
          </div>
        </div>

        {(yearsQuery.loading ||
          clientsQuery.loading ||
          manufacturersQuery.loading ||
          familiesQuery.loading ||
          subfamiliesQuery.loading) && <LoadingState>Cargando filtros...</LoadingState>}
        {!!yearsQuery.error && <ErrorState>{yearsQuery.error}</ErrorState>}
        {!!clientsQuery.error && <ErrorState>{clientsQuery.error}</ErrorState>}
        {!!manufacturersQuery.error && <ErrorState>{manufacturersQuery.error}</ErrorState>}
        {!!familiesQuery.error && <ErrorState>{familiesQuery.error}</ErrorState>}
        {!!subfamiliesQuery.error && <ErrorState>{subfamiliesQuery.error}</ErrorState>}
      </section>

      <section className="panel-section sales-table-panel">
        <div className="section-heading section-heading-compact">
          <div>
            <h3>Resumen anual</h3>
            <p>Comparativa detallada por artículo con kilos, S/C, ventas y diferencias.</p>
          </div>
          <span className="surface-chip">Fuente {source.toUpperCase()}</span>
        </div>

        <QueryState
          loading={summaryLoading}
          error={summaryQuery.error}
          empty={summaryEmpty}
          emptyMessage="No hay datos para la combinación de filtros seleccionada."
        />

        {!!rows.length && (
          <div className="sales-table-shell">
            <div className="sales-group-band" aria-hidden="true">
              <div className="sales-group-band-spacer" />
              <div className="sales-group-band-spacer" />
              <div className="sales-group-band-prev">{previousYearLabel}</div>
              <div className="sales-group-band-curr">{currentYearLabel}</div>
              <div className="sales-group-band-diff">Diferencias</div>
            </div>

            <div className="table-wrap sales-table-wrap">
              <table className="sales-comparison-table">
                <thead>
                  <tr>
                    <th>Cod.</th>
                    <th>Producto</th>
                    <th>Kilos</th>
                    <th>S/C</th>
                    <th>Ventas</th>
                    <th>Kilos</th>
                    <th>S/C</th>
                    <th>Ventas</th>
                    <th>Δ kg</th>
                    <th>Δ kg %</th>
                    <th>Δ €</th>
                    <th>Δ € %</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.articulo_id || row.codigo}>
                      <td>{row.codigo || row.articulo_id}</td>
                      <td>{row.nombre || '-'}</td>
                      <td>{formatNumber(row.kilos_prev)}</td>
                      <td>{formatNumber(row.sc_prev)}</td>
                      <td>{formatNumber(row.ventas_prev)}</td>
                      <td>{formatNumber(row.kilos_curr)}</td>
                      <td>{formatNumber(row.sc_curr)}</td>
                      <td>{formatNumber(row.ventas_curr)}</td>
                      <td className={row.delta_kg < 0 ? 'sales-negative' : row.delta_kg > 0 ? 'sales-positive' : ''}>
                        {formatSigned(row.delta_kg)}
                      </td>
                      <td className={row.delta_kg_pct < 0 ? 'sales-negative' : row.delta_kg_pct > 0 ? 'sales-positive' : ''}>
                        {formatPercent(row.delta_kg_pct)}
                      </td>
                      <td className={row.delta_ventas < 0 ? 'sales-negative' : row.delta_ventas > 0 ? 'sales-positive' : ''}>
                        {formatSigned(row.delta_ventas)}
                      </td>
                      <td className={row.delta_ventas_pct < 0 ? 'sales-negative' : row.delta_ventas_pct > 0 ? 'sales-positive' : ''}>
                        {formatPercent(row.delta_ventas_pct)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th colSpan={2}>TOTAL</th>
                    <th>{formatNumber(totals.prevKg)}</th>
                    <th>{formatNumber(totals.prevSc)}</th>
                    <th>{formatNumber(totals.prevSales)}</th>
                    <th>{formatNumber(totals.currKg)}</th>
                    <th>{formatNumber(totals.currSc)}</th>
                    <th>{formatNumber(totals.currSales)}</th>
                    <th className={deltaKg < 0 ? 'sales-negative' : deltaKg > 0 ? 'sales-positive' : ''}>{formatSigned(deltaKg)}</th>
                    <th className={deltaKgPct < 0 ? 'sales-negative' : deltaKgPct > 0 ? 'sales-positive' : ''}>
                      {formatPercent(deltaKgPct)}
                    </th>
                    <th className={deltaSales < 0 ? 'sales-negative' : deltaSales > 0 ? 'sales-positive' : ''}>
                      {formatSigned(deltaSales)}
                    </th>
                    <th className={deltaSalesPct < 0 ? 'sales-negative' : deltaSalesPct > 0 ? 'sales-positive' : ''}>
                      {formatPercent(deltaSalesPct)}
                    </th>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {!canQuery && !yearsQuery.loading && !yearsQuery.error && (
          <EmptyState>Selecciona un año para consultar la comparativa anual.</EmptyState>
        )}
      </section>
    </section>
  )
}
