import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { BinaryToggleSelect } from './BinaryToggleSelect'

describe('BinaryToggleSelect', () => {
  it('toggles between true and false states', () => {
    const handleChange = vi.fn()

    render(
      <BinaryToggleSelect
        value={true}
        onChange={handleChange}
        trueLabel="Activo"
        falseLabel="Inactivo"
        ariaLabel="Estado activo"
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Inactivo' }))
    expect(handleChange).toHaveBeenCalledWith(false)
  })

  it('disables interaction when requested', () => {
    const handleChange = vi.fn()

    render(
      <BinaryToggleSelect
        value={false}
        onChange={handleChange}
        trueLabel="Sí"
        falseLabel="No"
        disabled
        ariaLabel="Disponibilidad"
      />,
    )

    expect(screen.getByRole('button', { name: 'Sí' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'No' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Sí' }))
    expect(handleChange).not.toHaveBeenCalled()
  })
})
