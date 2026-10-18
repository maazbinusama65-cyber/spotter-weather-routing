import { describe, expect, it } from 'vitest'
import { LEVELS, UNKNOWN_LEVEL, levelInfo, levelFromChar } from './risk'

describe('risk levels', () => {
  it('orders the five levels from Low to No Travel', () => {
    expect(LEVELS.map((l) => l.label)).toEqual(['Low', 'Moderate', 'High', 'Severe', 'No Travel'])
    expect(LEVELS.map((l) => l.value)).toEqual([0, 1, 2, 3, 4])
  })

  it('gives every level a distinct colour', () => {
    const colours = new Set([...LEVELS.map((l) => l.color), UNKNOWN_LEVEL.color])
    expect(colours.size).toBe(LEVELS.length + 1)
  })

  it('looks up a level and falls back to unknown', () => {
    expect(levelInfo(3).label).toBe('Severe')
    expect(levelInfo(null)).toBe(UNKNOWN_LEVEL)
    expect(levelInfo(9)).toBe(UNKNOWN_LEVEL)
  })

  it('reads one character of a heatmap series', () => {
    expect(levelFromChar('0')).toBe(0)
    expect(levelFromChar('4')).toBe(4)
    expect(levelFromChar('-')).toBeNull()
    expect(levelFromChar(undefined)).toBeNull()
    expect(levelFromChar('x')).toBeNull()
  })
})
