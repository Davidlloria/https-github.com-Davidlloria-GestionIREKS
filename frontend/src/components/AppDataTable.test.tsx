import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AppDataTable } from './AppDataTable'

describe('AppDataTable', () => {
  it('renders table headers and rows', () => {
    render(
      <AppDataTable<{ name: string; city: string }>
        columns={[
          { key: 'name', header: 'Nombre', render: (row) => row.name },
          { key: 'city', header: 'Ciudad', render: (row) => row.city },
        ]}
        rows={[{ name: 'Panaderia', city: 'Tenerife' }]}
        getRowKey={(row) => row.name}
      />,
    )

    expect(screen.getByText('Nombre')).toBeInTheDocument()
    expect(screen.getByText('Ciudad')).toBeInTheDocument()
    expect(screen.getByText('Panaderia')).toBeInTheDocument()
    expect(screen.getByText('Tenerife')).toBeInTheDocument()
  })

  it('renders empty state when there are no rows', () => {
    render(<AppDataTable<{ name: string }> columns={[{ key: 'name', header: 'Nombre', render: () => 'x' }]} rows={[]} emptyState="Sin datos" />)

    expect(screen.getByText('Sin datos')).toBeInTheDocument()
  })
})
