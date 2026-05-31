import { useCallback, useMemo, useState } from 'react'
import { listContacts } from '../api/contacts'
import { deleteCustomer, getCustomerDetail, listCustomers, updateCustomerActive } from '../api/customers'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactListItem, CustomerDetail } from '../types/api'

export function CustomersPage() {
  const [search, setSearch] = useState('')
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [customerActiveLoading, setCustomerActiveLoading] = useState(false)
  const [customerActiveMessage, setCustomerActiveMessage] = useState('')
  const [customerActiveError, setCustomerActiveError] = useState('')
  const [customerDeleteLoading, setCustomerDeleteLoading] = useState(false)
  const [customerDeleteMessage, setCustomerDeleteMessage] = useState('')
  const [customerDeleteError, setCustomerDeleteError] = useState('')

  const query = useAsyncResource(() => listCustomers(search), [], [search])
  const contactsQuery = useAsyncResource(() => listContacts(''), [], [])

  const selectedCustomerId = useMemo(() => {
    if (!query.data.length) {
      return ''
    }
    if (selectedCandidateId && query.data.some((row) => row.cliente_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return query.data[0].cliente_id
  }, [query.data, selectedCandidateId])

  const fetchDetail = useCallback(() => {
    if (!selectedCustomerId) {
      return Promise.resolve(null as CustomerDetail | null)
    }
    return getCustomerDetail(selectedCustomerId)
  }, [selectedCustomerId])

  const detailQuery = useAsyncResource(fetchDetail, null as CustomerDetail | null, [fetchDetail, selectedCustomerId])

  const totals = useMemo(() => {
    const active = query.data.filter((row) => row.activo).length
    const prospects = query.data.filter((row) => row.cliente_prospeccion).length
    const withEmail = query.data.filter((row) => !!row.cliente_email).length
    return {
      total: query.data.length,
      active,
      prospects,
      withEmail,
    }
  }, [query.data])

  const customerContacts = useMemo(() => {
    if (!selectedCustomerId) {
      return [] as ContactListItem[]
    }
    return contactsQuery.data
      .filter((row) => row.cliente_id === selectedCustomerId)
      .sort((a, b) => `${a.apellidos} ${a.nombre}`.localeCompare(`${b.apellidos} ${b.nombre}`))
  }, [contactsQuery.data, selectedCustomerId])

  const toggleCustomerActive = async () => {
    if (!detailQuery.data || customerActiveLoading) {
      return
    }
    setCustomerActiveLoading(true)
    setCustomerActiveError('')
    setCustomerActiveMessage('')
    const nextActive = !detailQuery.data.activo
    try {
      await updateCustomerActive(detailQuery.data.cliente_id, nextActive)
      await Promise.all([query.reload(), detailQuery.reload()])
      setCustomerActiveMessage(nextActive ? 'Cliente activado.' : 'Cliente desactivado.')
    } catch (error: unknown) {
      setCustomerActiveError(error instanceof Error ? error.message : 'No se pudo actualizar el estado del cliente.')
    } finally {
      setCustomerActiveLoading(false)
    }
  }

  const deleteSelectedCustomer = async () => {
    if (!detailQuery.data || customerDeleteLoading) {
      return
    }
    const confirmed = window.confirm(
      `Se eliminara el cliente ${detailQuery.data.cliente_nombre_comercial || detailQuery.data.cliente_id}. Esta accion no se puede deshacer.`,
    )
    if (!confirmed) {
      return
    }
    setCustomerDeleteLoading(true)
    setCustomerDeleteError('')
    setCustomerDeleteMessage('')
    try {
      await deleteCustomer(detailQuery.data.cliente_id)
      setSelectedCandidateId('')
      await Promise.all([query.reload(), contactsQuery.reload()])
      setCustomerDeleteMessage('Cliente eliminado correctamente.')
    } catch (error: unknown) {
      setCustomerDeleteError(error instanceof Error ? error.message : 'No se pudo eliminar el cliente.')
    } finally {
      setCustomerDeleteLoading(false)
    }
  }

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
        <StatCard label="Con email" value={totals.withEmail} />
      </div>

      <QueryState
        loading={query.loading}
        error={query.error}
        empty={!query.data.length}
        emptyMessage="No hay clientes para los filtros actuales."
      />

      {!!query.data.length && (
        <div className="split-panel">
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
                  <tr
                    key={customer.cliente_id}
                    className={customer.cliente_id === selectedCustomerId ? 'row-selected' : ''}
                    onClick={() => setSelectedCandidateId(customer.cliente_id)}
                  >
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

          <aside className="detail-panel">
            {!selectedCustomerId && <div className="state">Selecciona un cliente para ver el detalle.</div>}
            {!!selectedCustomerId && (
              <>
                <QueryState
                  loading={detailQuery.loading}
                  error={detailQuery.error}
                  empty={!detailQuery.data}
                  emptyMessage="No se encontro detalle para el cliente seleccionado."
                />

                {!!detailQuery.data && (
                  <>
                    <dl className="detail-list">
                      <div>
                        <dt>Cliente ID</dt>
                        <dd>{detailQuery.data.cliente_id}</dd>
                      </div>
                      <div>
                        <dt>Nombre fiscal</dt>
                        <dd>{detailQuery.data.cliente_nombre_fiscal || '-'}</dd>
                      </div>
                      <div>
                        <dt>CIF</dt>
                        <dd>{detailQuery.data.cliente_cif || '-'}</dd>
                      </div>
                      <div>
                        <dt>Grupo</dt>
                        <dd>{detailQuery.data.cliente_grupo || '-'}</dd>
                      </div>
                      <div>
                        <dt>Direccion</dt>
                        <dd>{detailQuery.data.cliente_direccion || '-'}</dd>
                      </div>
                      <div>
                        <dt>Codigo postal</dt>
                        <dd>{detailQuery.data.cliente_direccion_cp || '-'}</dd>
                      </div>
                    </dl>

                    <div className="related-block">
                      <button
                        type="button"
                        className="action-btn"
                        disabled={customerActiveLoading || customerDeleteLoading}
                        onClick={toggleCustomerActive}
                      >
                        {customerActiveLoading
                          ? 'Guardando...'
                          : detailQuery.data.activo
                            ? 'Desactivar cliente'
                            : 'Activar cliente'}
                      </button>
                      {!!customerActiveMessage && <div className="state">{customerActiveMessage}</div>}
                      {!!customerActiveError && <div className="state">Error: {customerActiveError}</div>}
                    </div>

                    <div className="related-block">
                      <button
                        type="button"
                        className="action-btn"
                        disabled={customerDeleteLoading || customerActiveLoading}
                        onClick={deleteSelectedCustomer}
                      >
                        {customerDeleteLoading ? 'Eliminando...' : 'Eliminar cliente'}
                      </button>
                      {!!customerDeleteMessage && <div className="state">{customerDeleteMessage}</div>}
                      {!!customerDeleteError && <div className="state">Error: {customerDeleteError}</div>}
                    </div>

                    <div className="related-block">
                      <h3>Contactos asociados</h3>
                      {!customerContacts.length && <div className="state">No hay contactos asociados.</div>}
                      {!!customerContacts.length && (
                        <div className="table-wrap">
                          <table>
                            <thead>
                              <tr>
                                <th>Nombre</th>
                                <th>Cargo</th>
                                <th>Email</th>
                                <th>Telefono</th>
                              </tr>
                            </thead>
                            <tbody>
                              {customerContacts.map((contact) => (
                                <tr key={contact.contacto_id}>
                                  <td>{`${contact.nombre || ''} ${contact.apellidos || ''}`.trim() || '-'}</td>
                                  <td>{contact.cargo || '-'}</td>
                                  <td>{contact.email || '-'}</td>
                                  <td>{contact.telefono || '-'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  )
}
