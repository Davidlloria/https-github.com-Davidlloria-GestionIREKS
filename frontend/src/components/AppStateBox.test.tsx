import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AppStateBox } from './AppStateBox'

describe('AppStateBox', () => {
  it('renders an error state by default', () => {
    render(<AppStateBox kind="error" title="Error" message="Fallo de carga" />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Error')).toBeInTheDocument()
    expect(screen.getByText('Fallo de carga')).toBeInTheDocument()
  })
})
