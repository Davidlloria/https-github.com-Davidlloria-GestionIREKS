import type { ButtonHTMLAttributes, ReactNode } from 'react'

export type AppButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
export type AppButtonSize = 'sm' | 'md' | 'lg'

export type AppButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'> & {
  variant?: AppButtonVariant
  size?: AppButtonSize
  icon?: ReactNode
  children: ReactNode
}

export function AppButton({
  variant = 'secondary',
  size = 'md',
  icon,
  className,
  children,
  type = 'button',
  ...props
}: AppButtonProps) {
  const rootClassName = ['app-button', `app-button--${variant}`, `app-button--${size}`, className].filter(Boolean).join(' ')

  return (
    <button type={type} className={rootClassName} {...props}>
      {icon !== undefined && icon !== null && (
        <span className="app-button__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <span className="app-button__label">{children}</span>
    </button>
  )
}
