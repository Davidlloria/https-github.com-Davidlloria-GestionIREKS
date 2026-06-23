import type { KeyboardEvent } from 'react'
import './YesNoSliderToggle.css'

export type YesNoSliderToggleProps = {
  value: boolean
  onChange: (nextValue: boolean) => void
  yesLabel?: string
  noLabel?: string
  disabled?: boolean
  ariaLabel?: string
  className?: string
}

function isToggleKey(key: string) {
  return key === ' ' || key === 'Enter'
}

export function YesNoSliderToggle({
  value,
  onChange,
  yesLabel = 'SI',
  noLabel = 'NO',
  disabled = false,
  ariaLabel = 'Selector si o no',
  className = '',
}: YesNoSliderToggleProps) {
  const rootClassName = [
    'yes-no-slider-toggle',
    value ? 'yes-no-slider-toggle--yes' : 'yes-no-slider-toggle--no',
    disabled ? 'yes-no-slider-toggle--disabled' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ')

  const handleToggle = () => {
    if (!disabled) {
      onChange(!value)
    }
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) {
      return
    }

    if (isToggleKey(event.key)) {
      event.preventDefault()
      onChange(!value)
      return
    }

    if (event.key === 'ArrowLeft') {
      event.preventDefault()
      onChange(false)
      return
    }

    if (event.key === 'ArrowRight') {
      event.preventDefault()
      onChange(true)
    }
  }

  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      aria-label={ariaLabel}
      aria-disabled={disabled}
      disabled={disabled}
      className={rootClassName}
      onClick={handleToggle}
      onKeyDown={handleKeyDown}
    >
      <span className="yes-no-slider-toggle__white" aria-hidden="true">
        <span className="yes-no-slider-toggle__grip">
          <span />
          <span />
          <span />
        </span>
      </span>

      <span className="yes-no-slider-toggle__label">{value ? yesLabel : noLabel}</span>
    </button>
  )
}
