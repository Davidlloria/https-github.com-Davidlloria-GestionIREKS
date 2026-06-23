import { Fragment, type CSSProperties, type KeyboardEvent, type ReactNode } from 'react'

export type AppListingGridColumn<T> = {
  key: string
  header: ReactNode
  render: (row: T, rowIndex: number) => ReactNode
  cellClassName?: string
}

export type AppListingGridProps<T> = {
  columns: Array<AppListingGridColumn<T>>
  rows: T[]
  getRowKey?: (row: T, rowIndex: number) => string | number
  onRowClick?: (row: T, rowIndex: number) => void
  rowClassName?: (row: T, rowIndex: number) => string | undefined
  emptyState?: ReactNode
  className?: string
  gridTemplateColumns?: string
}

function isActivatableKey(event: KeyboardEvent<HTMLDivElement>) {
  return event.key === 'Enter' || event.key === ' '
}

export function AppListingGrid<T>({
  columns,
  rows,
  getRowKey,
  onRowClick,
  rowClassName,
  emptyState = 'Sin datos para mostrar.',
  className,
  gridTemplateColumns = '52px minmax(0, 1fr) 72px',
}: AppListingGridProps<T>) {
  const rootClassName = ['customers-list-grid', className].filter(Boolean).join(' ')
  const headerStyle = { gridTemplateColumns } as CSSProperties

  return (
    <div className={rootClassName}>
      <div className="customers-list-header" style={headerStyle}>
        {columns.map((column) => (
          <Fragment key={column.key}>{column.header}</Fragment>
        ))}
      </div>

      <div className="customers-list-body">
        {rows.length ? (
          rows.map((row, rowIndex) => {
            const rowKey = getRowKey ? getRowKey(row, rowIndex) : rowIndex
            const extraClassName = rowClassName ? rowClassName(row, rowIndex) : undefined
            const rowStyle = { gridTemplateColumns } as CSSProperties

            return (
              <div
                key={rowKey}
                className={['customers-list-row', extraClassName].filter(Boolean).join(' ')}
                style={rowStyle}
                role={onRowClick ? 'button' : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(row, rowIndex) : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (isActivatableKey(event)) {
                          event.preventDefault()
                          onRowClick(row, rowIndex)
                        }
                      }
                    : undefined
                }
              >
                {columns.map((column) => (
                  <span key={column.key} className={['customers-list-cell', column.cellClassName].filter(Boolean).join(' ')}>
                    {column.render(row, rowIndex)}
                  </span>
                ))}
              </div>
            )
          })
        ) : (
          <div className="app-data-table__empty">{emptyState}</div>
        )}
      </div>
    </div>
  )
}
