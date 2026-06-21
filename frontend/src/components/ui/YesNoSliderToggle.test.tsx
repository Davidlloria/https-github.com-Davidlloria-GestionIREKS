import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { YesNoSliderToggle } from './YesNoSliderToggle'

describe('YesNoSliderToggle', () => {
  it('renders the yes state', () => {
    render(<YesNoSliderToggle value={true} onChange={() => {}} ariaLabel="Estado activo" />)

    const toggle = screen.getByRole('switch', { name: 'Estado activo' })
    expect(toggle).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('SI')).toBeInTheDocument()
  })

  it('renders the no state', () => {
    render(<YesNoSliderToggle value={false} onChange={() => {}} ariaLabel="Estado activo" />)

    const toggle = screen.getByRole('switch', { name: 'Estado activo' })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText('NO')).toBeInTheDocument()
  })

  it('toggles on click and keyboard', () => {
    const handleChange = vi.fn()

    render(<YesNoSliderToggle value={false} onChange={handleChange} ariaLabel="Estado activo" />)

    const toggle = screen.getByRole('switch', { name: 'Estado activo' })
    fireEvent.click(toggle)
    fireEvent.keyDown(toggle, { key: 'Enter' })
    fireEvent.keyDown(toggle, { key: ' ' })
    fireEvent.keyDown(toggle, { key: 'ArrowRight' })
    fireEvent.keyDown(toggle, { key: 'ArrowLeft' })

    expect(handleChange).toHaveBeenNthCalledWith(1, true)
    expect(handleChange).toHaveBeenNthCalledWith(2, true)
    expect(handleChange).toHaveBeenNthCalledWith(3, true)
    expect(handleChange).toHaveBeenNthCalledWith(4, true)
    expect(handleChange).toHaveBeenNthCalledWith(5, false)
  })

  it('does not change when disabled', () => {
    const handleChange = vi.fn()

    render(<YesNoSliderToggle value={true} onChange={handleChange} disabled ariaLabel="Estado activo" />)

    const toggle = screen.getByRole('switch', { name: 'Estado activo' })
    expect(toggle).toBeDisabled()
    expect(toggle).toHaveAttribute('aria-disabled', 'true')
    fireEvent.click(toggle)
    expect(handleChange).not.toHaveBeenCalled()
  })
})
