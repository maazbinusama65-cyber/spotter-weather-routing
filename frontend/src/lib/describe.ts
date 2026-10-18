import { LEVELS, UNKNOWN_LEVEL } from './risk'
import type { RouteSummaryData } from './types'

const VISIBLE_MILES = 0.5

function miles(value: number): string {
  return `${Math.round(value).toLocaleString('en-US')} mi`
}

/** One line on what the weather does to a route, worst conditions first. */
export function describeRisk(summary: RouteSummaryData): string {
  const parts: string[] = []
  if (summary.no_travel_miles >= VISIBLE_MILES) parts.push(`${miles(summary.no_travel_miles)} No Travel`)
  if (summary.severe_miles >= VISIBLE_MILES) parts.push(`${miles(summary.severe_miles)} Severe`)
  if (summary.high_miles >= VISIBLE_MILES) parts.push(`${miles(summary.high_miles)} High`)
  const unknown =
    summary.unknown_miles >= VISIBLE_MILES ? `${miles(summary.unknown_miles)} without a forecast` : null
  if (parts.length > 0) return [...parts, ...(unknown ? [unknown] : [])].join(', ')
  if (unknown) {
    const moderate =
      summary.moderate_miles >= VISIBLE_MILES ? `, ${miles(summary.moderate_miles)} Moderate` : ''
    return `No High or Severe weather where a forecast exists${moderate}, ${unknown}`
  }
  if (summary.moderate_miles >= VISIBLE_MILES) {
    return `No High or Severe weather, ${miles(summary.moderate_miles)} Moderate`
  }
  return 'Clear of High and Severe weather'
}

export interface RiskSegment {
  label: string
  color: string
  miles: number
}

/** The route's miles grouped by risk level, in display order, skipping empty groups. */
export function riskSegments(summary: RouteSummaryData): RiskSegment[] {
  const all: RiskSegment[] = [
    { label: LEVELS[0].label, color: LEVELS[0].color, miles: summary.low_miles },
    { label: LEVELS[1].label, color: LEVELS[1].color, miles: summary.moderate_miles },
    { label: LEVELS[2].label, color: LEVELS[2].color, miles: summary.high_miles },
    { label: LEVELS[3].label, color: LEVELS[3].color, miles: summary.severe_miles },
    { label: LEVELS[4].label, color: LEVELS[4].color, miles: summary.no_travel_miles },
    { label: UNKNOWN_LEVEL.label, color: UNKNOWN_LEVEL.color, miles: summary.unknown_miles },
  ]
  return all.filter((segment) => segment.miles > 0)
}
