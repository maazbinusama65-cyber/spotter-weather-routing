import { levelFromChar } from './risk'
import type { HeatPointData } from './types'

export interface HeatFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: { level: number }
}

export interface HeatCollection {
  type: 'FeatureCollection'
  features: HeatFeature[]
}

export type LevelCounts = Record<0 | 1 | 2 | 3 | 4 | 'unknown', number>

/** Risk at one forecast hour for every grid cell. -1 means the forecast has no value. */
export function heatFeatures(points: HeatPointData[], hour: number): HeatCollection {
  return {
    type: 'FeatureCollection',
    features: points.map((point) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [point.lon, point.lat] },
      properties: { level: levelFromChar(point.levels[hour]) ?? -1 },
    })),
  }
}

export function levelCounts(points: HeatPointData[], hour: number): LevelCounts {
  const counts: LevelCounts = { 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, unknown: 0 }
  for (const point of points) {
    const level = levelFromChar(point.levels[hour])
    if (level === null) counts.unknown += 1
    else counts[level as 0 | 1 | 2 | 3 | 4] += 1
  }
  return counts
}
