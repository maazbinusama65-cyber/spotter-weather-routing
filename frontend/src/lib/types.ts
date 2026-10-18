/** Shapes returned by the Django API (see README). */

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface RiskLevelInfo {
  value: number
  label: string
}

export interface CheckpointData {
  index: number
  distance_mi: number
  segment_miles: number
  lat: number
  lon: number
  eta: string
  wind_mph: number | null
  rain_in_hr: number | null
  snow_in_hr: number | null
  level: number | null
  level_label: string
  driver: 'wind' | 'rain' | 'snow' | null
  load_escalated: boolean
  reason: string
}

export interface RouteSummaryData {
  no_travel_miles: number
  severe_miles: number
  high_miles: number
  moderate_miles: number
  low_miles: number
  unknown_miles: number
  avg_risk: number
  max_level: number
  max_level_label: string
}

export interface RouteData {
  id: string
  label: string
  via: string
  distance_mi: number
  duration_s: number
  arrival: string
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  summary: RouteSummaryData
  checkpoints: CheckpointData[]
}

export interface RecommendationData {
  route_id: string
  ranking: string[]
  reason: string
  all_blocked: boolean
}

export interface AnalyzeResponse {
  ruleset_version: string
  risk_levels: RiskLevelInfo[]
  timezone: string
  departure: string
  origin: { lat: number; lon: number }
  destination: { lat: number; lon: number }
  load_lb: number
  interval_miles: number
  routes: RouteData[]
  recommendation: RecommendationData
  warnings: string[]
}

export interface HeatPointData {
  lat: number
  lon: number
  /** One character per forecast hour: risk level 0-4, or "-" when unknown. */
  levels: string
}

export interface HeatmapResponse {
  start: string
  hours: number
  timezone: string
  risk_levels: RiskLevelInfo[]
  points: HeatPointData[]
  warnings: string[]
}

export interface TripRequestBody {
  origin: Place | string
  destination: Place | string
  departure: string
  load_lb: number
  interval_miles?: number
}
