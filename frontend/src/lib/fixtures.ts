import type { AnalyzeResponse, CheckpointData, RouteData } from './types'

/** Small realistic analysis used by tests. */

function checkpoint(index: number, level: number | null, overrides: Partial<CheckpointData> = {}): CheckpointData {
  return {
    index,
    distance_mi: index * 25,
    segment_miles: 25,
    lat: 39.7 + index * 0.2,
    lon: -105 + index * 0.9,
    eta: `2026-11-02T${String(14 + index).padStart(2, '0')}:00:00Z`,
    wind_mph: level === null ? null : 12 + index,
    rain_in_hr: level === null ? null : 0,
    snow_in_hr: level === null ? null : 0,
    level,
    level_label: level === null ? 'Unknown' : ['Low', 'Moderate', 'High', 'Severe', 'No Travel'][level],
    driver: level ? 'wind' : null,
    load_escalated: false,
    reason: level ? 'Moderate: wind 28 mph' : 'Conditions are low risk',
    ...overrides,
  }
}

function route(id: string, label: string, levels: (number | null)[], summary: Partial<RouteData['summary']> = {}): RouteData {
  return {
    id,
    label,
    via: id === 'r1' ? 'I 76, I 80' : 'US 36',
    distance_mi: levels.length * 25,
    duration_s: levels.length * 1500,
    arrival: '2026-11-03T04:00:00Z',
    geometry: {
      type: 'LineString',
      coordinates: levels.map((_, i) => [-105 + i * 0.9, 39.7 + i * 0.2] as [number, number]),
    },
    summary: {
      no_travel_miles: 0,
      severe_miles: 0,
      high_miles: 25,
      moderate_miles: 50,
      low_miles: 100,
      unknown_miles: 0,
      avg_risk: 0.4,
      max_level: 2,
      max_level_label: 'High',
      ...summary,
    },
    checkpoints: levels.map((level, i) => checkpoint(i, level)),
  }
}

export const sampleAnalysis: AnalyzeResponse = {
  ruleset_version: 'test',
  risk_levels: [
    { value: 0, label: 'Low' },
    { value: 1, label: 'Moderate' },
    { value: 2, label: 'High' },
    { value: 3, label: 'Severe' },
    { value: 4, label: 'No Travel' },
  ],
  timezone: 'America/Denver',
  departure: '2026-11-02T14:00:00Z',
  origin: { lat: 39.7, lon: -105 },
  destination: { lat: 41.3, lon: -97.8 },
  load_lb: 42000,
  interval_miles: 25,
  routes: [
    route('r1', 'Route 1', [0, 0, 1, 2, 0, 0, 0, 0, 0]),
    route('r2', 'Route 2', [0, 0, 0, 0, null, 0, 0, 0], {
      high_miles: 0,
      moderate_miles: 0,
      low_miles: 150,
      unknown_miles: 50,
      avg_risk: 0,
      max_level: 0,
      max_level_label: 'Low',
    }),
  ],
  recommendation: {
    route_id: 'r2',
    ranking: ['r2', 'r1'],
    reason: 'Route 2 has 0 mi of Severe weather vs 0 mi on Route 1',
    all_blocked: false,
  },
  warnings: [],
}
