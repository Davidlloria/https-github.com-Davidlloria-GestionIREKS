import type { ReactNode } from 'react'

export type BinaryToggleSelectProps = {
  value: boolean
  onChange: (value: boolean) => void
  trueLabel?: string
  falseLabel?: string
  trueIcon?: ReactNode
  falseIcon?: ReactNode
  disabled?: boolean
  ariaLabel?: string
  className?: string
}

export function BinaryToggleSelect({
  value,
  onChange,
  trueLabel = 'Yes',
  falseLabel = 'No',
  trueIcon,
  falseIcon,
  disabled = false,
  ariaLabel,
  className,
}: BinaryToggleSelectProps) {
  const rootClassName = ['binary-toggle-select', className, disabled ? 'is-disabled' : ''].filter(Boolean).join(' ')
  const showTrueIcon = trueIcon !== undefined && trueIcon !== null
  const showFalseIcon = falseIcon !== undefined && falseIcon !== null

  return (
    <div className={rootClassName} role="group" aria-label={ariaLabel} data-value={value ? 'true' : 'false'}>
      <button
        type="button"
        className={`binary-toggle-select__option binary-toggle-select__option--true ${value ? 'is-active' : ''}`}
        aria-pressed={value}
        disabled={disabled}
        onClick={() => onChange(true)}
      >
        {showTrueIcon && (
          <span className="binary-toggle-select__icon" aria-hidden="true">
            {trueIcon}
          </span>
        )}
        <span className="binary-toggle-select__label">{trueLabel}</span>
      </button>

      <button
        type="button"
        className={`binary-toggle-select__option binary-toggle-select__option--false ${!value ? 'is-active' : ''}`}
        aria-pressed={!value}
        disabled={disabled}
        onClick={() => onChange(false)}
      >
        <span className="binary-toggle-select__label">{falseLabel}</span>
        {showFalseIcon && (
          <span className="binary-toggle-select__icon" aria-hidden="true">
            {falseIcon}
          </span>
        )}
      </button>
    </div>
  )
}
