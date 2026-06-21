import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AppChip } from './AppChip'

describe('AppChip', () => {
  it('renders tone and icon content', () => {
    render(
      <AppChip tone="success" active icon="✓">
        Listo
      </AppChip>,
    )

    const chip = screen.getByText('Listo').closest('.app-chip')
    expect(chip).toHaveClass('app-chip--success')
    expect(chip).toHaveClass('is-active')
    expect(screen.getByText('✓')).toBeInTheDocument()
  })
})
