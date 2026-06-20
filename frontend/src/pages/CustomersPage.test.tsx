import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CustomersPage } from './CustomersPage'

const catalogs = {
  provincias: [{ id: 'P1', label: 'Provincia 1', parent_id: '', code: 'PR1' }],
  islas: [{ id: 'I1', label: 'Isla Uno', parent_id: 'P1', code: 'IU' }],
  municipios: [{ id: 'M1', label: 'Municipio 1', parent_id: 'I1', code: 'MU1' }],
  codigos_postales: [{ id: 'P1:35001', label: '35001', parent_id: 'M1', code: '35001' }],
  localidades: [{ id: 'L1', label: 'Localidad 1', parent_id: 'M1', code: 'LOC1' }],
}

const baseCustomer = {
  cliente_id: 'C-1',
  cliente_codigo: 101,
  cliente_nombre_comercial: 'Cliente Uno',
  cliente_nombre_fiscal: 'Cliente Uno SL',
  cliente_nombre_interno: 'Interno Uno',
  cliente_abreviatura: 'C1',
  cliente_cif: 'B123',
  cliente_telefono: '928000000',
  cliente_email: 'cliente1@example.com',
  cliente_direccion: 'Calle 1',
  cliente_direccion_cp: '35001',
  cliente_direccion_localidad_id: 'L1',
  cliente_direccion_municipio_id: 'M1',
  cliente_direccion_provincia_id: 'P1',
  cliente_direccion_isla_id: 'I1',
  cliente_tipo: 'CAFETERIA',
  cliente_grupo: 'Grupo A',
  cliente_prospeccion: false,
  distribuidor_id: 'DIST-1',
  activo: true,
}

let customerStore = [baseCustomer]
let nextCustomerCode = 102

function buildListResponse() {
  return {
    items: customerStore.map((item) => ({ ...item })),
    total: customerStore.length,
    limit: 25,
    offset: 0,
  }
}

vi.mock('../api/customers', () => ({
  getCustomerAddressCatalogs: vi.fn(async () => catalogs),
  getCustomerDetail: vi.fn(async (customerId: string) => {
    const customer = customerStore.find((item) => item.cliente_id === customerId)
    return customer ? { ...customer } : null
  }),
  listCustomers: vi.fn(async () => buildListResponse()),
  createCustomer: vi.fn(async (payload: Record<string, unknown>) => {
    const created = {
      ...baseCustomer,
      cliente_id: `C-${customerStore.length + 1}`,
      cliente_codigo: nextCustomerCode++,
      ...payload,
    }
    customerStore = [...customerStore, created]
    return { ...created }
  }),
  updateCustomer: vi.fn(async (customerId: string, payload: Record<string, unknown>) => {
    customerStore = customerStore.map((item) => (item.cliente_id === customerId ? { ...item, ...payload } : item))
    const customer = customerStore.find((item) => item.cliente_id === customerId)
    return customer ? { ...customer } : baseCustomer
  }),
  deleteCustomer: vi.fn(async (customerId: string) => {
    customerStore = customerStore.filter((item) => item.cliente_id !== customerId)
  }),
}))

vi.mock('../api/contacts', () => ({
  listContacts: vi.fn(async () => ({
    items: [],
    total: 0,
    limit: 25,
    offset: 0,
  })),
}))

describe('CustomersPage CRUD', () => {
  it('creates, updates and deletes customers from the page', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<CustomersPage />)

    expect(await screen.findByRole('button', { name: '+ Nuevo' })).toBeEnabled()
    expect(screen.getByText('Cliente Uno')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '+ Nuevo' }))
    expect(await screen.findByRole('heading', { name: 'Nuevo cliente' })).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Nombre comercial'), { target: { value: 'Cliente Dos' } })
    fireEvent.change(screen.getByLabelText('Nombre fiscal'), { target: { value: 'Cliente Dos SL' } })
    fireEvent.change(screen.getByLabelText('C.I.F.'), { target: { value: 'B999' } })
    fireEvent.change(screen.getByLabelText('Telefono'), { target: { value: '928000002' } })
    fireEvent.change(screen.getByPlaceholderText('Tipo de cliente'), { target: { value: 'HOTEL' } })
    fireEvent.change(screen.getByLabelText('Grupo'), { target: { value: 'Grupo B' } })
    fireEvent.change(screen.getByLabelText('Distribuidor'), { target: { value: 'DIST-2' } })

    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))

    expect(await screen.findByText('Cliente Dos')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Nuevo cliente' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Editar' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByText('Cliente Uno'))
    expect(await screen.findByDisplayValue('Cliente Uno')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Nombre comercial'), { target: { value: 'Cliente Uno Editado' } })

    await waitFor(() => {
      expect(screen.getByDisplayValue('Cliente Uno Editado')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Cliente Uno Editado/ })).toBeInTheDocument()
    }, { timeout: 7000 })

    fireEvent.click(screen.getByText('Cliente Uno Editado'))
    fireEvent.click(screen.getByRole('button', { name: 'Eliminar' }))

    await waitFor(() => {
      expect(confirmSpy).toHaveBeenCalled()
    })

    await waitFor(() => {
      expect(screen.queryByText('Cliente Uno Editado')).not.toBeInTheDocument()
    })

    confirmSpy.mockRestore()
  }, 15000)
})
