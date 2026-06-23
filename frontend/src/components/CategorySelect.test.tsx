import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { CategorySelect } from './CategorySelect'

describe('CategorySelect', () => {
  it('renders the current selection', () => {
    render(
      <CategorySelect
        value="HARINA"
        onChange={() => {}}
        harinaLabel="Harina"
        liquidoLabel="Liquido"
        noneLabel="Sin categoria"
        ariaLabel="Categoria"
      />,
    )

    expect(screen.getByRole('button', { name: 'Harina' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Liquido' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByRole('button', { name: 'Sin categoria' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('emits the selected value on click', () => {
    const handleChange = vi.fn()

    render(<CategorySelect value={null} onChange={handleChange} ariaLabel="Categoria" />)

    fireEvent.click(screen.getByRole('button', { name: 'HARINA' }))
    fireEvent.click(screen.getByRole('button', { name: 'LIQUIDO' }))
    fireEvent.click(screen.getByRole('button', { name: 'SIN CATEGORIA' }))

    expect(handleChange).toHaveBeenNthCalledWith(1, 'HARINA')
    expect(handleChange).toHaveBeenNthCalledWith(2, 'LIQUIDO')
    expect(handleChange).toHaveBeenNthCalledWith(3, null)
  })

  it('disables interaction when requested', () => {
    const handleChange = vi.fn()

    render(<CategorySelect value={null} onChange={handleChange} disabled ariaLabel="Categoria" />)

    const harina = screen.getByRole('button', { name: 'HARINA' })
    expect(harina).toBeDisabled()
    fireEvent.click(harina)
    expect(handleChange).not.toHaveBeenCalled()
  })
})
