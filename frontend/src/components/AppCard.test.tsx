import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AppCard } from './AppCard'

describe('AppCard', () => {
  it('renders header, body and footer content', () => {
    render(
      <AppCard title="Detalle" subtitle="Subtitulo" headerRight="Chip" footer="Pie">
        Contenido
      </AppCard>,
    )

    expect(screen.getByText('Detalle')).toBeInTheDocument()
    expect(screen.getByText('Subtitulo')).toBeInTheDocument()
    expect(screen.getByText('Chip')).toBeInTheDocument()
    expect(screen.getByText('Contenido')).toBeInTheDocument()
    expect(screen.getByText('Pie')).toBeInTheDocument()
  })
})
