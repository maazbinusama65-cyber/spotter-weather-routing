import { describe, expect, it } from 'vitest'
import { loadRuleHint, validateTrip, type TripFormValues } from './validation'

const denver = { label: 'Denver, CO, USA', lat: 39.7392, lon: -104.9847 }
const chicago = { label: 'Chicago, IL, USA', lat: 41.8781, lon: -87.6298 }

function values(overrides: Partial<TripFormValues> = {}): TripFormValues {
  return {
    origin: { text: denver.label, place: denver },
    destination: { text: chicago.label, place: chicago },
    departure: '2026-11-02T08:00',
    load: '42000',
    interval: 25,
    ...overrides,
  }
}

describe('validateTrip', () => {
  it('builds the request body from chosen places', () => {
    const result = validateTrip(values())

    expect(result).toEqual({
      ok: true,
      body: {
        origin: denver,
        destination: chicago,
        departure: '2026-11-02T08:00',
        load_lb: 42000,
        interval_miles: 25,
      },
    })
  })

  it('sends typed text when no suggestion was chosen so the server can geocode it', () => {
    const result = validateTrip(
      values({ origin: { text: ' Boise, ID ', place: null } }),
    )

    expect(result.ok && result.body.origin).toBe('Boise, ID')
  })

  it('asks for missing places', () => {
    const result = validateTrip(values({ origin: { text: '', place: null }, destination: { text: ' ', place: null } }))

    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.errors.origin).toMatch(/starting/)
      expect(result.errors.destination).toMatch(/destination/)
    }
  })

  it('rejects the same place twice', () => {
    const result = validateTrip(values({ destination: { text: denver.label, place: denver } }))

    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.errors.destination).toMatch(/different/)
  })

  it('rejects the same typed text twice, ignoring case', () => {
    const result = validateTrip(
      values({ origin: { text: 'Boise', place: null }, destination: { text: 'boise ', place: null } }),
    )

    expect(result.ok).toBe(false)
  })

  it.each([
    ['', /load weight/],
    ['heavy', /load weight/],
    ['-5', /between/],
    ['150000', /between/],
  ])('rejects load %j', (load, message) => {
    const result = validateTrip(values({ load }))

    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.errors.load).toMatch(message)
  })

  it('accepts zero and the maximum load', () => {
    expect(validateTrip(values({ load: '0' })).ok).toBe(true)
    expect(validateTrip(values({ load: '100000' })).ok).toBe(true)
  })

  it('requires a departure', () => {
    const result = validateTrip(values({ departure: '' }))

    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.errors.departure).toBeDefined()
  })

  it('reports every problem at once', () => {
    const result = validateTrip(values({ departure: '', load: '', origin: { text: '', place: null } }))

    expect(result.ok).toBe(false)
    if (!result.ok) expect(Object.keys(result.errors).sort()).toEqual(['departure', 'load', 'origin'])
  })
})

describe('loadRuleHint', () => {
  it('describes which wind rules the load triggers', () => {
    expect(loadRuleHint(20_000)).toMatch(/Standard/)
    expect(loadRuleHint(30_000)).toMatch(/Standard/)
    expect(loadRuleHint(30_001)).toMatch(/45 mph/)
    expect(loadRuleHint(40_000)).not.toMatch(/35 mph/)
    expect(loadRuleHint(40_001)).toMatch(/35 mph/)
  })
})
