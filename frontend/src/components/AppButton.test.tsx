import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AppButton } from './AppButton'

describe('AppButton', () => {
  it('renders the label and icon', () => {
    render(
      <AppButton variant="primary" icon="+">
        Nuevo
      </AppButton>,
    )

    expect(screen.getByRole('button', { name: 'Nuevo' })).toBeInTheDocument()
    expect(screen.getByText('+')).toBeInTheDocument()
  })

  it('does not trigger clicks when disabled', () => {
    const handleClick = vi.fn()

    render(
      <AppButton disabled onClick={handleClick}>
        Guardar
      </AppButton>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(handleClick).not.toHaveBeenCalled()
  })
})
