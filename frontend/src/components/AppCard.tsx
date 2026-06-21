import type { ComponentPropsWithoutRef, ElementType, ReactNode } from 'react'

export type AppCardProps<TTag extends ElementType = 'div'> = {
  as?: TTag
  title?: ReactNode
  subtitle?: ReactNode
  headerRight?: ReactNode
  footer?: ReactNode
  scrollable?: boolean
  className?: string
  children?: ReactNode
} & Omit<ComponentPropsWithoutRef<TTag>, 'as' | 'title' | 'children' | 'className'>

export function AppCard<TTag extends ElementType = 'div'>({
  as,
  title,
  subtitle,
  headerRight,
  footer,
  scrollable = false,
  className,
  children,
  ...props
}: AppCardProps<TTag>) {
  const Component = (as || 'div') as ElementType
  const rootClassName = ['app-card', scrollable ? 'app-card--scrollable' : '', className].filter(Boolean).join(' ')
  const hasHeader = title !== undefined || subtitle !== undefined || headerRight !== undefined
  const hasFooter = footer !== undefined && footer !== null

  return (
    <Component className={rootClassName} {...props}>
      {hasHeader && (
        <div className="app-card__header">
          <div className="app-card__copy">
            {title !== undefined && title !== null && <strong className="app-card__title">{title}</strong>}
            {subtitle !== undefined && subtitle !== null && <div className="app-card__subtitle">{subtitle}</div>}
          </div>
          {headerRight !== undefined && headerRight !== null && <div className="app-card__header-right">{headerRight}</div>}
        </div>
      )}
      {children !== undefined &&
        children !== null &&
        (hasHeader || hasFooter ? <div className="app-card__body">{children}</div> : children)}
      {hasFooter && <div className="app-card__footer">{footer}</div>}
    </Component>
  )
}
