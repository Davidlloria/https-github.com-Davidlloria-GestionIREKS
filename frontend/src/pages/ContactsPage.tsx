import { useCallback, useMemo, useState } from 'react'
import { createContact, deleteContact, getContactDetail, listContactCompanies, listContacts, updateContact } from '../api/contacts'
import { QueryState } from '../components/QueryState'
import { StatCard } from '../components/StatCard'
import { useAsyncResource } from '../features/useAsyncResource'
import type { ContactDetail, ContactListItem } from '../types/api'

type ContactFormMode = 'new' | 'edit'

interface ContactFormState {
  cliente_id: string
  nombre: string
  apellidos: string
  cargo: string
  nif: string
  telefono: string
  email: string
}

const EMPTY_FORM: ContactFormState = {
  cliente_id: '',
  nombre: '',
  apellidos: '',
  cargo: '',
  nif: '',
  telefono: '',
  email: '',
}

function formFromDetail(detail: ContactDetail): ContactFormState {
  return {
    cliente_id: detail.cliente_id || '',
    nombre: detail.nombre || '',
    apellidos: detail.apellidos || '',
    cargo: detail.cargo || '',
    nif: detail.nif || '',
    telefono: detail.telefono || '',
    email: detail.email || '',
  }
}

export function ContactsPage() {
  const [search, setSearch] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [formMode, setFormMode] = useState<ContactFormMode>('edit')
  const [form, setForm] = useState<ContactFormState>(EMPTY_FORM)
  const [saveLoading, setSaveLoading] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const [saveError, setSaveError] = useState('')
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteMessage, setDeleteMessage] = useState('')
  const [deleteError, setDeleteError] = useState('')

  const contactsQuery = useAsyncResource(() => listContacts(search), [], [search])
  const companiesQuery = useAsyncResource(() => listContactCompanies(), [], [])

  const filteredContacts = useMemo(() => {
    if (!companyFilter) {
      return contactsQuery.data
    }
    return contactsQuery.data.filter((row) => row.cliente_id === companyFilter)
  }, [companyFilter, contactsQuery.data])

  const selectedContactId = useMemo(() => {
    if (!filteredContacts.length) {
      return ''
    }
    if (selectedCandidateId && filteredContacts.some((row) => row.contacto_id === selectedCandidateId)) {
      return selectedCandidateId
    }
    return filteredContacts[0].contacto_id
  }, [filteredContacts, selectedCandidateId])

  const loadSelectedDetail = useCallback(() => {
    if (!selectedContactId) {
      return Promise.resolve(null as ContactDetail | null)
    }
    return getContactDetail(selectedContactId)
  }, [selectedContactId])

  const detailQuery = useAsyncResource(loadSelectedDetail, null as ContactDetail | null, [loadSelectedDetail, selectedContactId])

  const effectiveForm = useMemo(() => {
    if (formMode === 'new') {
      return form
    }
    if (detailQuery.data) {
      return formFromDetail(detailQuery.data)
    }
    return form
  }, [detailQuery.data, form, formMode])

  const totals = useMemo(() => {
    const withEmail = filteredContacts.filter((row) => !!row.email).length
    const withPhone = filteredContacts.filter((row) => !!row.telefono).length
    const uniqueCompanies = new Set(filteredContacts.map((row) => row.cliente_id).filter(Boolean)).size
    return {
      total: filteredContacts.length,
      withEmail,
      withPhone,
      uniqueCompanies,
    }
  }, [filteredContacts])

  const fullName = (row: ContactListItem) => `${row.nombre || ''} ${row.apellidos || ''}`.trim()

  const onFieldChange = (field: keyof ContactFormState, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const beginCreate = () => {
    setFormMode('new')
    setForm({
      ...EMPTY_FORM,
      cliente_id: companyFilter || '',
    })
    setSaveError('')
    setSaveMessage('')
  }

  const beginEdit = () => {
    if (!detailQuery.data) {
      return
    }
    setFormMode('edit')
    setForm(formFromDetail(detailQuery.data))
    setSaveError('')
    setSaveMessage('')
  }

  const validateForm = (payload: ContactFormState) => {
    if (!payload.cliente_id.trim()) {
      return 'Debes seleccionar una empresa.'
    }
    if (!payload.nombre.trim() && !payload.apellidos.trim()) {
      return 'Debes informar nombre o apellidos.'
    }
    return ''
  }

  const saveContact = async () => {
    if (saveLoading) {
      return
    }
    const payload = {
      cliente_id: effectiveForm.cliente_id.trim(),
      nombre: effectiveForm.nombre.trim(),
      apellidos: effectiveForm.apellidos.trim(),
      cargo: effectiveForm.cargo.trim(),
      nif: effectiveForm.nif.trim(),
      telefono: effectiveForm.telefono.trim(),
      email: effectiveForm.email.trim(),
    }
    const validationError = validateForm(payload)
    if (validationError) {
      setSaveError(validationError)
      setSaveMessage('')
      return
    }
    if (formMode === 'edit' && !selectedContactId) {
      setSaveError('No hay contacto seleccionado para editar.')
      setSaveMessage('')
      return
    }
    setSaveLoading(true)
    setSaveError('')
    setSaveMessage('')
    try {
      if (formMode === 'new') {
        const created = await createContact(payload)
        await Promise.all([contactsQuery.reload(), companiesQuery.reload()])
        setSelectedCandidateId(created.contacto_id)
        setFormMode('edit')
        setSaveMessage('Contacto creado correctamente.')
      } else {
        await updateContact(selectedContactId, payload)
        await Promise.all([contactsQuery.reload(), detailQuery.reload(), companiesQuery.reload()])
        setSaveMessage('Contacto actualizado correctamente.')
      }
    } catch (error: unknown) {
      setSaveError(error instanceof Error ? error.message : 'No se pudo guardar el contacto.')
    } finally {
      setSaveLoading(false)
    }
  }

  const deleteSelectedContact = async () => {
    if (!selectedContactId || deleteLoading) {
      return
    }
    const target = filteredContacts.find((row) => row.contacto_id === selectedContactId)
    const targetName = target ? fullName(target) || target.contacto_id : selectedContactId
    const confirmed = window.confirm(`Se eliminara el contacto ${targetName}. Esta accion no se puede deshacer.`)
    if (!confirmed) {
      return
    }
    setDeleteLoading(true)
    setDeleteError('')
    setDeleteMessage('')
    try {
      await deleteContact(selectedContactId)
      setSelectedCandidateId('')
      await Promise.all([contactsQuery.reload(), companiesQuery.reload()])
      setDeleteMessage('Contacto eliminado correctamente.')
    } catch (error: unknown) {
      setDeleteError(error instanceof Error ? error.message : 'No se pudo eliminar el contacto.')
    } finally {
      setDeleteLoading(false)
    }
  }

  return (
    <section className="page-grid">
      <div className="toolbar">
        <input
          className="input"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por nombre, apellido, cargo, email o empresa"
        />
        <select
          className="select"
          value={companyFilter}
          onChange={(event) => setCompanyFilter(event.target.value)}
        >
          <option value="">Todas las empresas</option>
          {companiesQuery.data.map((company) => (
            <option key={company.cliente_id} value={company.cliente_id}>
              {company.nombre}
            </option>
          ))}
        </select>
      </div>

      <div className="cards">
        <StatCard label="Total contactos" value={totals.total} />
        <StatCard label="Con email" value={totals.withEmail} />
        <StatCard label="Con telefono" value={totals.withPhone} />
        <StatCard label="Empresas con contactos" value={totals.uniqueCompanies} />
      </div>

      <QueryState
        loading={contactsQuery.loading}
        error={contactsQuery.error}
        empty={!filteredContacts.length}
        emptyMessage="No hay contactos para los filtros actuales."
      />

      {!!filteredContacts.length && (
        <div className="split-panel">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Empresa</th>
                  <th>Cargo</th>
                  <th>Email</th>
                  <th>Telefono</th>
                </tr>
              </thead>
              <tbody>
                {filteredContacts.map((row) => (
                  <tr
                    key={row.contacto_id}
                    className={row.contacto_id === selectedContactId ? 'row-selected' : ''}
                    onClick={() => setSelectedCandidateId(row.contacto_id)}
                  >
                    <td>{fullName(row) || '(sin nombre)'}</td>
                    <td>{row.cliente_nombre || '-'}</td>
                    <td>{row.cargo || '-'}</td>
                    <td>{row.email || '-'}</td>
                    <td>{row.telefono || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <aside className="detail-panel">
            {!selectedContactId && <div className="state">Selecciona un contacto para ver el detalle.</div>}
            {!!selectedContactId && formMode === 'edit' && (
              <>
                <QueryState
                  loading={detailQuery.loading}
                  error={detailQuery.error}
                  empty={!detailQuery.data}
                  emptyMessage="No se encontro detalle para el contacto seleccionado."
                />

                {!!detailQuery.data && (
                  <dl className="detail-list">
                    <div>
                      <dt>Nombre completo</dt>
                      <dd>{`${detailQuery.data.nombre || ''} ${detailQuery.data.apellidos || ''}`.trim() || '-'}</dd>
                    </div>
                    <div>
                      <dt>Empresa</dt>
                      <dd>{detailQuery.data.cliente_nombre || '-'}</dd>
                    </div>
                    <div>
                      <dt>Cliente ID</dt>
                      <dd>{detailQuery.data.cliente_id || '-'}</dd>
                    </div>
                    <div>
                      <dt>Cargo</dt>
                      <dd>{detailQuery.data.cargo || '-'}</dd>
                    </div>
                    <div>
                      <dt>NIF</dt>
                      <dd>{detailQuery.data.nif || '-'}</dd>
                    </div>
                    <div>
                      <dt>Email</dt>
                      <dd>{detailQuery.data.email || '-'}</dd>
                    </div>
                    <div>
                      <dt>Telefono</dt>
                      <dd>{detailQuery.data.telefono || '-'}</dd>
                    </div>
                    <div>
                      <dt>Creado</dt>
                      <dd>{detailQuery.data.created_at || '-'}</dd>
                    </div>
                    <div>
                      <dt>Actualizado</dt>
                      <dd>{detailQuery.data.updated_at || '-'}</dd>
                    </div>
                  </dl>
                )}
              </>
            )}

            <div className="related-block">
              <h3>{formMode === 'new' ? 'Nuevo contacto' : 'Editar contacto'}</h3>
              <div className="toolbar">
                <button type="button" className="action-btn" onClick={beginCreate} disabled={saveLoading}>
                  Nuevo
                </button>
                <button
                  type="button"
                  className="action-btn"
                  onClick={beginEdit}
                  disabled={saveLoading || deleteLoading || !detailQuery.data}
                >
                  Editar seleccionado
                </button>
                <button
                  type="button"
                  className="action-btn"
                  onClick={deleteSelectedContact}
                  disabled={saveLoading || deleteLoading || !selectedContactId}
                >
                  {deleteLoading ? 'Eliminando...' : 'Eliminar seleccionado'}
                </button>
              </div>

              <div className="form-grid">
                <label>
                  Empresa
                  <select
                    className="select"
                    value={effectiveForm.cliente_id}
                    onChange={(event) => onFieldChange('cliente_id', event.target.value)}
                    disabled={saveLoading}
                  >
                    <option value="">Selecciona empresa</option>
                    {companiesQuery.data.map((company) => (
                      <option key={company.cliente_id} value={company.cliente_id}>
                        {company.nombre}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Nombre
                  <input
                    className="input"
                    value={effectiveForm.nombre}
                    onChange={(event) => onFieldChange('nombre', event.target.value)}
                    disabled={saveLoading}
                  />
                </label>
                <label>
                  Apellidos
                  <input
                    className="input"
                    value={effectiveForm.apellidos}
                    onChange={(event) => onFieldChange('apellidos', event.target.value)}
                    disabled={saveLoading}
                  />
                </label>
                <label>
                  Cargo
                  <input
                    className="input"
                    value={effectiveForm.cargo}
                    onChange={(event) => onFieldChange('cargo', event.target.value)}
                    disabled={saveLoading}
                  />
                </label>
                <label>
                  NIF
                  <input
                    className="input"
                    value={effectiveForm.nif}
                    onChange={(event) => onFieldChange('nif', event.target.value)}
                    disabled={saveLoading}
                  />
                </label>
                <label>
                  Email
                  <input
                    className="input"
                    value={effectiveForm.email}
                    onChange={(event) => onFieldChange('email', event.target.value)}
                    disabled={saveLoading}
                  />
                </label>
                <label>
                  Telefono
                  <input
                    className="input"
                    value={effectiveForm.telefono}
                    onChange={(event) => onFieldChange('telefono', event.target.value)}
                    disabled={saveLoading}
                  />
                </label>
              </div>

              <div className="toolbar">
                <button type="button" className="action-btn" onClick={saveContact} disabled={saveLoading}>
                  {saveLoading ? 'Guardando...' : 'Guardar contacto'}
                </button>
              </div>
              {!!saveMessage && <div className="state">{saveMessage}</div>}
              {!!saveError && <div className="state">Error: {saveError}</div>}
              {!!deleteMessage && <div className="state">{deleteMessage}</div>}
              {!!deleteError && <div className="state">Error: {deleteError}</div>}
            </div>
          </aside>
        </div>
      )}
    </section>
  )
}
