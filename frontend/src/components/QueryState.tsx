interface QueryStateProps {
  loading: boolean
  error: string
  empty: boolean
  emptyMessage: string
}

interface StateProps {
  children?: string
  className?: string
  role?: 'status' | 'alert'
  ariaLive?: 'polite' | 'assertive'
}

export function LoadingState({
  children = 'Cargando datos...',
  className = 'state state-loading',
  role = 'status',
  ariaLive = 'polite',
}: StateProps) {
  return (
    <div className={className} role={role} aria-live={ariaLive}>
      {children}
    </div>
  )
}

export function ErrorState({
  children,
  className = 'state state-error',
  role = 'status',
  ariaLive = 'polite',
}: StateProps) {
  return (
    <div className={className} role={role} aria-live={ariaLive}>
      Error: {children}
    </div>
  )
}

export function EmptyState({
  children,
  className = 'state state-empty',
  role = 'status',
  ariaLive,
}: StateProps) {
  return (
    <div className={className} role={role} aria-live={ariaLive}>
      {children}
    </div>
  )
}

export function QueryState({ loading, error, empty, emptyMessage }: QueryStateProps) {
  if (loading) {
    return <LoadingState />
  }
  if (error) {
    return <ErrorState>{error}</ErrorState>
  }
  if (empty) {
    return <EmptyState>{emptyMessage}</EmptyState>
  }
  return null
}
