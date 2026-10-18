import { useState, type FormEvent } from 'react'
import { ArrowsDownUp, Path } from '@phosphor-icons/react'
import { localDateTimeValue } from '../lib/format'
import type { Place, TripRequestBody } from '../lib/types'
import {
  INTERVAL_OPTIONS,
  MAX_LOAD_LB,
  loadRuleHint,
  validateTrip,
  type PlaceValue,
  type TripFormErrors,
  type TripFormValues,
} from '../lib/validation'
import { PlaceField } from './PlaceField'
import { Segmented } from './Segmented'
import './TripForm.css'

const LOAD_PRESETS = [
  { value: '10000', label: 'Light', hint: '10,000 lb' },
  { value: '42000', label: 'Typical', hint: '42,000 lb' },
  { value: '78000', label: 'Heavy', hint: '78,000 lb' },
] as const

const INTERVAL_CHOICES = INTERVAL_OPTIONS.map((miles) => ({
  value: miles as number,
  label: `${miles} mi`,
}))

interface Example {
  label: string
  origin: Place
  destination: Place
}

const EXAMPLES: readonly Example[] = [
  {
    label: 'Denver to Chicago',
    origin: { label: 'Denver, CO, USA', lat: 39.7392, lon: -104.9847 },
    destination: { label: 'Chicago, IL, USA', lat: 41.8781, lon: -87.6298 },
  },
  {
    label: 'Seattle to Salt Lake City',
    origin: { label: 'Seattle, WA, USA', lat: 47.6062, lon: -122.3321 },
    destination: { label: 'Salt Lake City, UT, USA', lat: 40.7608, lon: -111.891 },
  },
  {
    label: 'Miami to Orlando',
    origin: { label: 'Miami, FL, USA', lat: 25.7617, lon: -80.1918 },
    destination: { label: 'Orlando, FL, USA', lat: 28.5384, lon: -81.3789 },
  },
]

function tomorrowMorning(): string {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  date.setHours(8, 0, 0, 0)
  return localDateTimeValue(date)
}

const EMPTY_PLACE: PlaceValue = { text: '', place: null }

/** The API names fields after its own parameters; the form names them after its inputs. */
const SERVER_FIELD_TO_INPUT: Record<string, keyof TripFormErrors> = {
  origin: 'origin',
  destination: 'destination',
  departure: 'departure',
  load_lb: 'load',
}

function visibleServerErrors(
  source: Record<string, string> | undefined,
  dismissed: string[],
): TripFormErrors {
  const visible: TripFormErrors = {}
  for (const [field, message] of Object.entries(source ?? {})) {
    const input = SERVER_FIELD_TO_INPUT[field]
    if (input && !dismissed.includes(input)) visible[input] = message
  }
  return visible
}

interface TripFormProps {
  loading: boolean
  /** Field messages from the server, shown next to the matching input. */
  serverErrors?: Record<string, string>
  onSubmit: (body: TripRequestBody) => void
}

export function TripForm({ loading, serverErrors, onSubmit }: TripFormProps) {
  const [values, setValues] = useState<TripFormValues>(() => ({
    origin: EMPTY_PLACE,
    destination: EMPTY_PLACE,
    departure: tomorrowMorning(),
    load: '42000',
    interval: 25,
  }))
  const [errors, setErrors] = useState<TripFormErrors>({})
  // Inputs the user has edited since the server last complained: their old message is stale.
  const [dismissed, setDismissed] = useState<{
    source: Record<string, string> | undefined
    inputs: string[]
  }>({ source: serverErrors, inputs: [] })
  const dismissedInputs = dismissed.source === serverErrors ? dismissed.inputs : []

  const update = (patch: Partial<TripFormValues>) => {
    setValues((current) => ({ ...current, ...patch }))
    setDismissed({ source: serverErrors, inputs: [...dismissedInputs, ...Object.keys(patch)] })
    setErrors((current) => {
      const next = { ...current }
      for (const key of Object.keys(patch)) delete next[key as keyof TripFormErrors]
      return next
    })
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const result = validateTrip(values)
    if (!result.ok) {
      setErrors(result.errors)
      return
    }
    setErrors({})
    onSubmit(result.body)
  }

  const shown: TripFormErrors = { ...visibleServerErrors(serverErrors, dismissedInputs), ...errors }
  const loadNumber = Number(values.load)
  const activePreset = LOAD_PRESETS.find((preset) => preset.value === values.load)

  return (
    <form className="trip-form" onSubmit={handleSubmit} noValidate>
      <div className="trip-form__places">
        <PlaceField
          label="From"
          text={values.origin.text}
          place={values.origin.place}
          error={shown.origin}
          onChange={(text, place) => update({ origin: { text, place } })}
        />
        <button
          type="button"
          className="icon-button trip-form__swap"
          aria-label="Swap start and destination"
          onClick={() => update({ origin: values.destination, destination: values.origin })}
        >
          <ArrowsDownUp size={18} />
        </button>
        <PlaceField
          label="To"
          text={values.destination.text}
          place={values.destination.place}
          error={shown.destination}
          onChange={(text, place) => update({ destination: { text, place } })}
        />
      </div>

      <div className="trip-form__row">
        <div className="field">
          <label className="field__label" htmlFor="departure">
            Departure
          </label>
          <input
            id="departure"
            className="input mono"
            type="datetime-local"
            value={values.departure}
            aria-invalid={shown.departure ? true : undefined}
            aria-describedby="departure-hint"
            onChange={(event) => update({ departure: event.target.value })}
          />
          <p className="field__hint" id="departure-hint">
            Time at the starting point
          </p>
          {shown.departure && (
            <p className="field__error" role="alert">
              {shown.departure}
            </p>
          )}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="load">
            Load weight
          </label>
          <div className="input-unit">
            <input
              id="load"
              className="input mono"
              type="number"
              inputMode="numeric"
              min={0}
              max={MAX_LOAD_LB}
              step={500}
              value={values.load}
              aria-invalid={shown.load ? true : undefined}
              aria-describedby="load-hint"
              onChange={(event) => update({ load: event.target.value })}
            />
            <span className="input-unit__unit mono" aria-hidden="true">
              lb
            </span>
          </div>
          {shown.load && (
            <p className="field__error" role="alert">
              {shown.load}
            </p>
          )}
        </div>
      </div>

      <Segmented
        label="Load presets"
        options={LOAD_PRESETS}
        value={activePreset?.value ?? null}
        onChange={(load) => update({ load })}
      />
      <p className="field__hint trip-form__rule" id="load-hint" aria-live="polite">
        {loadRuleHint(loadNumber)}
      </p>

      <Segmented
        label="Weather check every"
        options={INTERVAL_CHOICES}
        value={values.interval}
        onChange={(interval) => update({ interval })}
      />

      <button className="button button--primary" type="submit" disabled={loading}>
        <Path size={18} weight="bold" aria-hidden="true" />
        {loading ? 'Analyzing routes' : 'Find safest route'}
      </button>

      <div className="trip-form__examples">
        <p className="field__label">Try an example</p>
        <div className="trip-form__example-list">
          {EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              className="button button--quiet"
              onClick={() => {
                setErrors({})
                setValues((current) => ({
                  ...current,
                  origin: { text: example.origin.label, place: example.origin },
                  destination: { text: example.destination.label, place: example.destination },
                }))
              }}
            >
              {example.label}
            </button>
          ))}
        </div>
      </div>
    </form>
  )
}
