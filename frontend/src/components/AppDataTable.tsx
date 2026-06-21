import type { HTMLAttributes, ReactNode } from 'react'

export type AppDataTableColumn<T> = {
  key: string
  header: ReactNode
  render: (row: T, rowIndex: number) => ReactNode
  headerClassName?: string
  cellClassName?: string
  headerCellProps?: HTMLAttributes<HTMLTableCellElement>
}

export type AppDataTableProps<T> = {
  columns: Array<AppDataTableColumn<T>>
  rows: T[]
  getRowKey?: (row: T, rowIndex: number) => string | number
  onRowClick?: (row: T, rowIndex: number) => void
  rowClassName?: (row: T, rowIndex: number) => string | undefined
  emptyState?: ReactNode
  footer?: ReactNode
  className?: string
  wrapClassName?: string
  tableClassName?: string
}

export function AppDataTable<T>({
  columns,
  rows,
  getRowKey,
  onRowClick,
  rowClassName,
  emptyState = 'Sin datos para mostrar.',
  footer,
  className,
  wrapClassName,
  tableClassName,
}: AppDataTableProps<T>) {
  const rootClassName = ['app-data-table', className].filter(Boolean).join(' ')
  const wrapRootClassName = ['table-wrap', 'app-data-table__wrap', wrapClassName].filter(Boolean).join(' ')
  const tableRootClassName = ['app-data-table__table', tableClassName].filter(Boolean).join(' ')

  return (
    <div className={rootClassName}>
      <div className={wrapRootClassName}>
        <table className={tableRootClassName}>
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key} className={column.headerClassName} {...column.headerCellProps}>
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row, rowIndex) => (
                <tr
                  key={getRowKey ? getRowKey(row, rowIndex) : rowIndex}
                  className={rowClassName ? rowClassName(row, rowIndex) : undefined}
                  onClick={onRowClick ? () => onRowClick(row, rowIndex) : undefined}
                >
                  {columns.map((column) => (
                    <td key={column.key} className={column.cellClassName}>
                      {column.render(row, rowIndex)}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length}>
                  <div className="app-data-table__empty">{emptyState}</div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {footer !== undefined && footer !== null && <div className="app-data-table__footer">{footer}</div>}
    </div>
  )
}
