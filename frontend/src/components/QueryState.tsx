interface QueryStateProps {
  loading: boolean
  error: string
  empty: boolean
  emptyMessage: string
}

export function QueryState({ loading, error, empty, emptyMessage }: QueryStateProps) {
  if (loading) {
    return <div className="state">Cargando datos...</div>
  }
  if (error) {
    return <div className="state">Error: {error}</div>
  }
  if (empty) {
    return <div className="state">{emptyMessage}</div>
  }
  return null
}
