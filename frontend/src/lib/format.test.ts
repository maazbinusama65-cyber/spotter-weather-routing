import { describe, expect, it } from 'vitest'
import {
  addHours,
  formatDuration,
  formatHourOffset,
  formatMiles,
  formatTime,
  localDateTimeValue,
} from './format'

describe('formatDuration', () => {
  it('shows hours and minutes', () => {
    expect(formatDuration(22.95 * 3600)).toBe('22 h 57 min')
  })

  it('drops the hours under one hour and the minutes on the hour', () => {
    expect(formatDuration(45 * 60)).toBe('45 min')
    expect(formatDuration(2 * 3600)).toBe('2 h')
  })

  it('rolls 59.5 minutes over instead of printing 60', () => {
    expect(formatDuration(3600 + 59.6 * 60)).toBe('2 h')
  })
})

describe('formatMiles', () => {
  it('groups thousands and rounds', () => {
    expect(formatMiles(1001.24)).toBe('1,001 mi')
    expect(formatMiles(0.4)).toBe('0 mi')
  })
})

describe('formatTime', () => {
  it('renders in the given time zone with its abbreviation', () => {
    expect(formatTime('2026-11-02T14:00:00Z', 'America/Denver')).toBe('Mon 7:00 AM MST')
    expect(formatTime('2026-11-02T14:00:00Z', 'America/Chicago')).toBe('Mon 8:00 AM CST')
  })
})

describe('forecast hour helpers', () => {
  it('adds whole hours to an ISO time', () => {
    expect(addHours('2026-11-02T14:00:00Z', 26)).toBe('2026-11-03T16:00:00.000Z')
  })

  it('labels the offset', () => {
    expect(formatHourOffset(0)).toBe('Departure')
    expect(formatHourOffset(14)).toBe('+14 h')
  })
})

describe('localDateTimeValue', () => {
  it('formats a Date for a datetime-local input in local time', () => {
    const value = localDateTimeValue(new Date(2026, 10, 2, 8, 5))

    expect(value).toBe('2026-11-02T08:05')
  })
})
