import type { KeyboardEvent } from 'react'

export type CategorySelectValue = 'HARINA' | 'LIQUIDO' | null

export type CategorySelectProps = {
  value: CategorySelectValue
  onChange: (nextValue: CategorySelectValue) => void
  harinaLabel?: string
  liquidoLabel?: string
  noneLabel?: string
  disabled?: boolean
  ariaLabel?: string
  className?: string
}

function isSelectionKey(key: string) {
  return key === ' ' || key === 'Enter'
}

export function CategorySelect({
  value,
  onChange,
  harinaLabel = 'HARINA',
  liquidoLabel = 'LIQUIDO',
  noneLabel = 'SIN CATEGORIA',
  disabled = false,
  ariaLabel = 'Categoria del producto',
  className = '',
}: CategorySelectProps) {
  const rootClassName = ['category-select', disabled ? 'is-disabled' : '', className].filter(Boolean).join(' ')

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, nextValue: CategorySelectValue) => {
    if (disabled) {
      return
    }

    if (isSelectionKey(event.key)) {
      event.preventDefault()
      onChange(nextValue)
    }
  }

  return (
    <div className={rootClassName} role="group" aria-label={ariaLabel} data-value={value || 'none'}>
      <button
        type="button"
        className={`category-select__option category-select__option--harina ${value === 'HARINA' ? 'is-active' : ''}`}
        aria-pressed={value === 'HARINA'}
        disabled={disabled}
        onClick={() => onChange('HARINA')}
        onKeyDown={(event) => handleKeyDown(event, 'HARINA')}
      >
        <span className="category-select__label">{harinaLabel}</span>
      </button>

      <button
        type="button"
        className={`category-select__option category-select__option--liquido ${value === 'LIQUIDO' ? 'is-active' : ''}`}
        aria-pressed={value === 'LIQUIDO'}
        disabled={disabled}
        onClick={() => onChange('LIQUIDO')}
        onKeyDown={(event) => handleKeyDown(event, 'LIQUIDO')}
      >
        <span className="category-select__label">{liquidoLabel}</span>
      </button>

      <button
        type="button"
        className={`category-select__option category-select__option--none ${value === null ? 'is-active' : ''}`}
        aria-pressed={value === null}
        disabled={disabled}
        onClick={() => onChange(null)}
        onKeyDown={(event) => handleKeyDown(event, null)}
      >
        <span className="category-select__label">{noneLabel}</span>
      </button>
    </div>
  )
}
