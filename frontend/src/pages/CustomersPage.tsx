import { useMemo, useState } from 'react'
import { listCustomers } from '../api/customers'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'

export function CustomersPage() {
  const [search, setSearch] = useState('')

  const query = useAsyncResource(() => listCustomers(search), [], [search])

  const totals = useMemo(() => {
    const active = query.data.filter((row) => row.activo).length
    const prospects = query.data.filter((row) => row.cliente_prospeccion).length
    return {
      total: query.data.length,
      active,
      prospects,
      inactive: query.data.length - active,
    }
  }, [query.data])

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar cliente por nombre, telefono, email o CIF"
        />
      </div>

      <div className="cards">
        <StatCard label="Total clientes" value={totals.total} />
        <StatCard label="Activos" value={totals.active} />
        <StatCard label="Prospeccion" value={totals.prospects} />
        <StatCard label="Inactivos" value={totals.inactive} />
      </div>

      <QueryState
        loading={query.loading}
        error={query.error}
        empty={!query.data.length}
        emptyMessage="No hay clientes para los filtros actuales."
      />

      {!!query.data.length && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Codigo</th>
                <th>Nombre comercial</th>
                <th>Tipo</th>
                <th>Email</th>
                <th>Telefono</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((customer) => (
                <tr key={customer.cliente_id}>
                  <td>{customer.cliente_codigo}</td>
                  <td>{customer.cliente_nombre_comercial || '(sin nombre)'}</td>
                  <td>{customer.cliente_tipo || '-'}</td>
                  <td>{customer.cliente_email || '-'}</td>
                  <td>{customer.cliente_telefono || '-'}</td>
                  <td>
                    <span className={`pill ${customer.activo ? 'ok' : 'off'}`}>
                      {customer.activo ? 'Activo' : 'Inactivo'}
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
