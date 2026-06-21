import type { ReactNode } from 'react'

export type AppStateKind = 'empty' | 'error' | 'info' | 'success' | 'loading'

export type AppStateBoxProps = {
  kind?: AppStateKind
  title?: ReactNode
  message: ReactNode
  icon?: ReactNode
  className?: string
  role?: 'status' | 'alert'
  ariaLive?: 'polite' | 'assertive'
}

export function AppStateBox({
  kind = 'info',
  title,
  message,
  icon,
  className,
  role = kind === 'error' ? 'alert' : 'status',
  ariaLive = kind === 'error' ? 'assertive' : 'polite',
}: AppStateBoxProps) {
  const rootClassName = ['app-state', `app-state--${kind}`, className].filter(Boolean).join(' ')

  return (
    <div className={rootClassName} role={role} aria-live={ariaLive}>
      {icon !== undefined && icon !== null && (
        <span className="app-state__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <div className="app-state__copy">
        {title !== undefined && title !== null && <strong className="app-state__title">{title}</strong>}
        <span className="app-state__message">{message}</span>
      </div>
    </div>
  )
}
