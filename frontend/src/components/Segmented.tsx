import { useId } from 'react'
import './Segmented.css'

interface SegmentedProps<T extends string | number> {
  label: string
  options: readonly { value: T; label: string; hint?: string }[]
  value: T | null
  onChange: (value: T) => void
}

/** A row of mutually exclusive choices, built on real radio inputs. */
export function Segmented<T extends string | number>({
  label,
  options,
  value,
  onChange,
}: SegmentedProps<T>) {
  const name = useId()
  return (
    <fieldset className="segmented">
      <legend className="field__label">{label}</legend>
      <div className="segmented__row">
        {options.map((option) => (
          <label key={option.value} className="segmented__option">
            <input
              className="visually-hidden"
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
            />
            <span className="segmented__face">
              <span className="segmented__label">{option.label}</span>
              {option.hint && <span className="segmented__hint mono">{option.hint}</span>}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
