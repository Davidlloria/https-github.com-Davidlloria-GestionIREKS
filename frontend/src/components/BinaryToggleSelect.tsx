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

function resolveIcon(icon: ReactNode | undefined, fallback: ReactNode) {
  if (icon === null) {
    return null
  }
  return icon ?? fallback
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
  const resolvedTrueIcon = resolveIcon(trueIcon, <span aria-hidden="true">✓</span>)
  const resolvedFalseIcon = resolveIcon(falseIcon, <span aria-hidden="true">×</span>)

  return (
    <div className={rootClassName} role="group" aria-label={ariaLabel} data-value={value ? 'true' : 'false'}>
      <button
        type="button"
        className={`binary-toggle-select__option binary-toggle-select__option--true ${value ? 'is-active' : ''}`}
        aria-pressed={value}
        disabled={disabled}
        onClick={() => onChange(true)}
      >
        {resolvedTrueIcon !== null && (
          <span className="binary-toggle-select__icon" aria-hidden="true">
            {resolvedTrueIcon}
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
        {resolvedFalseIcon !== null && (
          <span className="binary-toggle-select__icon" aria-hidden="true">
            {resolvedFalseIcon}
          </span>
        )}
      </button>
    </div>
  )
}
