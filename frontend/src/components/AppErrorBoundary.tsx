import { Component, type ErrorInfo, type ReactNode } from 'react'

interface AppErrorBoundaryProps {
  children: ReactNode
}

interface AppErrorBoundaryState {
  hasError: boolean
  message: string
}

export class AppErrorBoundary extends Component<AppErrorBoundaryProps, AppErrorBoundaryState> {
  public state: AppErrorBoundaryState = {
    hasError: false,
    message: '',
  }

  public static getDerivedStateFromError(error: unknown): AppErrorBoundaryState {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : 'Error inesperado en la interfaz',
    }
  }

  public componentDidCatch(error: unknown, info: ErrorInfo): void {
    // Keeps a useful trace in the browser console for local debugging.
    console.error('UI render error', error, info)
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="state">
          Error de renderizado: {this.state.message}. Recarga la pagina o revisa la consola del navegador.
        </div>
      )
    }

    return this.props.children
  }
}
