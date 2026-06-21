import type { ComponentPropsWithoutRef, ElementType, ReactNode } from 'react'

export type AppSectionHeaderProps<TTag extends ElementType = 'h3'> = {
  title: ReactNode
  subtitle?: ReactNode
  rightSlot?: ReactNode
  titleAs?: TTag
  className?: string
} & Omit<ComponentPropsWithoutRef<TTag>, 'children' | 'className'>

export function AppSectionHeader<TTag extends ElementType = 'h3'>({
  title,
  subtitle,
  rightSlot,
  titleAs,
  className,
  ...props
}: AppSectionHeaderProps<TTag>) {
  const TitleTag = (titleAs || 'h3') as ElementType
  const rootClassName = ['app-section-header', className].filter(Boolean).join(' ')

  return (
    <header className={rootClassName} {...props}>
      <div className="app-section-header__copy">
        <TitleTag className="app-section-header__title">{title}</TitleTag>
        {subtitle !== undefined && subtitle !== null && <div className="app-section-header__subtitle">{subtitle}</div>}
      </div>
      {rightSlot !== undefined && rightSlot !== null && <div className="app-section-header__right">{rightSlot}</div>}
    </header>
  )
}
