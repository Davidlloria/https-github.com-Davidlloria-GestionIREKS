import { useCallback, useEffect, useState } from 'react'

interface AsyncState<T> {
  data: T
  loading: boolean
  error: string
}

export function useAsyncResource<T>(factory: () => Promise<T>, initial: T, deps: ReadonlyArray<unknown>) {
  const [state, setState] = useState<AsyncState<T>>({
    data: initial,
    loading: true,
    error: '',
  })

  const reload = useCallback(() => {
    let cancelled = false
    Promise.resolve()
      .then(() => {
        if (!cancelled) {
          setState((prev) => ({ ...prev, loading: true, error: '' }))
        }
        return factory()
      })
      .then((data) => {
        if (!cancelled) {
          setState({ data, loading: false, error: '' })
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            data: initial,
            loading: false,
            error: error instanceof Error ? error.message : 'Error de red',
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [factory, initial])

  useEffect(() => {
    const stop = reload()
    return stop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { ...state, reload }
}
