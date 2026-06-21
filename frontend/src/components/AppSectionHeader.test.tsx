import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AppSectionHeader } from './AppSectionHeader'

describe('AppSectionHeader', () => {
  it('renders title, subtitle and right slot', () => {
    render(<AppSectionHeader title="Detalle" subtitle="Subtitulo" rightSlot="Chip" />)

    expect(screen.getByText('Detalle')).toBeInTheDocument()
    expect(screen.getByText('Subtitulo')).toBeInTheDocument()
    expect(screen.getByText('Chip')).toBeInTheDocument()
  })
})
