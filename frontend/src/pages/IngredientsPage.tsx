import { useMemo, useState } from 'react'
import { listIreksIngredients } from '../api/ingredients'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'

export function IngredientsPage() {
  const [search, setSearch] = useState('')
  const [activityFilter, setActivityFilter] = useState('all')

  const query = useAsyncResource(
    () => listIreksIngredients(search, activityFilter),
    { rows: [], catalogs: { distribuidores: [], fabricantes: [], familias: [], subfamilias: [], envases: [] } },
    [search, activityFilter],
  )

  const totals = useMemo(() => {
    const active = query.data.rows.filter((row) => row.articulo_status_activo).length
    const inList = query.data.rows.filter((row) => row.articulo_status_en_lista).length
    return {
      total: query.data.rows.length,
      active,
      inList,
      familias: query.data.catalogs.familias.length,
    }
  }, [query.data])

  const formatWeight = (value: unknown) => {
    const numeric = Number(value)
    return Number.isFinite(numeric) ? numeric.toFixed(2) : '0.00'
  }

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por referencia, descripcion o almacen"
        />
        <select
          className="select"
          value={activityFilter}
          onChange={(event) => setActivityFilter(event.target.value)}
        >
          <option value="all">Todos</option>
          <option value="active">Activos</option>
          <option value="inactive">Inactivos</option>
        </select>
      </div>

      <div className="cards">
        <StatCard label="Total IREKS" value={totals.total} />
        <StatCard label="Activos" value={totals.active} />
        <StatCard label="En lista pedidos" value={totals.inList} />
        <StatCard label="Familias catalogo" value={totals.familias} />
      </div>

      <QueryState
        loading={query.loading}
        error={query.error}
        empty={!query.data.rows.length}
        emptyMessage="No hay ingredientes para los filtros actuales."
      />

      {!!query.data.rows.length && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Referencia</th>
                <th>Descripcion</th>
                <th>Articulo ID</th>
                <th>Peso envase total</th>
                <th>Categoria</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {query.data.rows.map((row) => (
                <tr key={`${row.id ?? row.articulo_id}`}>
                  <td>{row.articulo_referencia || '-'}</td>
                  <td>{row.articulo_descripcion || '-'}</td>
                  <td>{row.articulo_id || '-'}</td>
                  <td>{formatWeight(row.articulo_envase_peso_total)}</td>
                  <td>{row.categoria || '-'}</td>
                  <td>
                    <span className={`pill ${row.articulo_status_activo ? 'ok' : 'off'}`}>
                      {row.articulo_status_activo ? 'Activo' : 'Inactivo'}
                    </span>{' '}
                    <span className={`pill ${row.articulo_status_en_lista ? 'warn' : 'off'}`}>
                      {row.articulo_status_en_lista ? 'En lista' : 'Fuera lista'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
