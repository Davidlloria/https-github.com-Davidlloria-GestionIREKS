interface QueryStateProps {
  loading: boolean
  error: string
  empty: boolean
  emptyMessage: string
}

export function QueryState({ loading, error, empty, emptyMessage }: QueryStateProps) {
  if (loading) {
    return (
      <div className="state state-loading" role="status" aria-live="polite">
        Cargando datos...
      </div>
    )
  }
  if (error) {
    return (
      <div className="state state-error" role="status" aria-live="polite">
        Error: {error}
      </div>
    )
  }
  if (empty) {
    return (
      <div className="state state-empty" role="status">
        {emptyMessage}
      </div>
    )
  }
  return null
}
