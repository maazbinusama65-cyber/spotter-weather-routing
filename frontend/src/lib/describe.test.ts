import { describe, expect, it } from 'vitest'
import { describeRisk, riskSegments } from './describe'
import { sampleAnalysis } from './fixtures'
import type { RouteSummaryData } from './types'

const base: RouteSummaryData = {
  no_travel_miles: 0,
  severe_miles: 0,
  high_miles: 0,
  moderate_miles: 0,
  low_miles: 200,
  unknown_miles: 0,
  avg_risk: 0,
  max_level: 0,
  max_level_label: 'Low',
}

describe('describeRisk', () => {
  it('lists the worst conditions first', () => {
    const text = describeRisk({ ...base, no_travel_miles: 12, severe_miles: 40.4, high_miles: 1200 })

    expect(text).toBe('12 mi No Travel, 40 mi Severe, 1,200 mi High')
  })

  it('omits levels that are absent', () => {
    expect(describeRisk({ ...base, high_miles: 25 })).toBe('25 mi High')
  })

  it('reports moderate-only routes without alarm', () => {
    expect(describeRisk({ ...base, moderate_miles: 75 })).toBe(
      'No High or Severe weather, 75 mi Moderate',
    )
  })

  it('says so when nothing notable lies ahead', () => {
    expect(describeRisk(base)).toBe('Clear of High and Severe weather')
  })

  it('never calls a route clear when part of it has no forecast', () => {
    expect(describeRisk({ ...base, low_miles: 150, unknown_miles: 50 })).toBe(
      'No High or Severe weather where a forecast exists, 50 mi without a forecast',
    )
  })

  it('adds missing forecast miles after the worst conditions', () => {
    expect(describeRisk({ ...base, severe_miles: 20, unknown_miles: 30 })).toBe(
      '20 mi Severe, 30 mi without a forecast',
    )
  })

  it('ignores slivers under half a mile', () => {
    expect(describeRisk({ ...base, severe_miles: 0.3 })).toBe('Clear of High and Severe weather')
  })
})

describe('riskSegments', () => {
  it('returns non-empty groups in level order with their colours', () => {
    const segments = riskSegments(sampleAnalysis.routes[0].summary)

    expect(segments.map((s) => s.label)).toEqual(['Low', 'Moderate', 'High'])
    expect(segments.map((s) => s.miles)).toEqual([100, 50, 25])
    expect(new Set(segments.map((s) => s.color)).size).toBe(3)
  })

  it('includes unknown miles last', () => {
    const segments = riskSegments(sampleAnalysis.routes[1].summary)

    expect(segments.at(-1)?.label).toBe('Unknown')
  })
})
