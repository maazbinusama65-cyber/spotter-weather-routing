import type { Place, TripRequestBody } from './types'

export const INTERVAL_OPTIONS = [10, 25, 50] as const
export const MAX_LOAD_LB = 100_000
export const MIN_PLACE_TEXT = 2

export interface PlaceValue {
  text: string
  place: Place | null
}

export interface TripFormValues {
  origin: PlaceValue
  destination: PlaceValue
  /** Value of a datetime-local input; read in the origin's time zone by the server. */
  departure: string
  load: string
  interval: number
}

export type TripFormErrors = Partial<Record<'origin' | 'destination' | 'departure' | 'load', string>>

export type Validation =
  | { ok: true; body: TripRequestBody }
  | { ok: false; errors: TripFormErrors }

const SAME_PLACE_DEGREES = 0.005

function placeError(value: PlaceValue, noun: string): string | undefined {
  if (value.place) return undefined
  return value.text.trim().length >= MIN_PLACE_TEXT ? undefined : `Enter the ${noun} city or address`
}

function placeForRequest(value: PlaceValue): Place | string {
  return value.place ?? value.text.trim()
}

export function validateTrip(values: TripFormValues): Validation {
  const errors: TripFormErrors = {}

  const originError = placeError(values.origin, 'starting')
  if (originError) errors.origin = originError
  const destinationError = placeError(values.destination, 'destination')
  if (destinationError) errors.destination = destinationError

  const { origin, destination } = values
  if (!errors.origin && !errors.destination) {
    const samePlace = origin.place && destination.place
      ? Math.abs(origin.place.lat - destination.place.lat) < SAME_PLACE_DEGREES &&
        Math.abs(origin.place.lon - destination.place.lon) < SAME_PLACE_DEGREES
      : origin.text.trim().toLowerCase() === destination.text.trim().toLowerCase()
    if (samePlace) errors.destination = 'Choose a destination different from the start'
  }

  if (!values.departure || Number.isNaN(Date.parse(values.departure))) {
    errors.departure = 'Pick a departure date and time'
  }

  const load = Number(values.load)
  if (values.load.trim() === '' || !Number.isFinite(load)) {
    errors.load = 'Enter the load weight in pounds'
  } else if (load < 0 || load > MAX_LOAD_LB) {
    errors.load = `Load must be between 0 and ${MAX_LOAD_LB.toLocaleString('en-US')} lb`
  }

  if (Object.keys(errors).length > 0) return { ok: false, errors }

  return {
    ok: true,
    body: {
      origin: placeForRequest(origin),
      destination: placeForRequest(destination),
      departure: values.departure,
      load_lb: Math.round(load),
      interval_miles: values.interval,
    },
  }
}

/** Which of the load rules apply, in the words a driver would use. */
export function loadRuleHint(loadLb: number): string {
  if (!Number.isFinite(loadLb)) return ''
  if (loadLb > 40_000) {
    return 'Heavy load: wind from 35 mph counts as Severe and from 45 mph as No Travel.'
  }
  if (loadLb > 30_000) {
    return 'Wind from 45 mph counts as No Travel for this load.'
  }
  return 'Standard wind thresholds apply. Winds of 55 mph or more are No Travel for any load.'
}
