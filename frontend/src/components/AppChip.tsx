import type { ReactNode } from 'react'

export type AppChipTone = 'neutral' | 'success' | 'warning' | 'info' | 'danger'

export type AppChipProps = {
  tone?: AppChipTone
  icon?: ReactNode
  active?: boolean
  className?: string
  children: ReactNode
}

export function AppChip({ tone = 'neutral', icon, active = false, className, children }: AppChipProps) {
  const rootClassName = ['app-chip', `app-chip--${tone}`, active ? 'is-active' : '', className].filter(Boolean).join(' ')

  return (
    <span className={rootClassName}>
      {icon !== undefined && icon !== null && (
        <span className="app-chip__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <span className="app-chip__label">{children}</span>
    </span>
  )
}
