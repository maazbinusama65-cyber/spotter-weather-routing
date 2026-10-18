import type { AnalyzeResponse } from './types'

/** GeoJSON for the map layers. `order` makes the selected route draw on top. */

export interface RouteFeature {
  type: 'Feature'
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  properties: { routeId: string; selected: 0 | 1; recommended: 0 | 1; order: number }
}

export interface CheckpointFeature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: {
    routeId: string
    index: number
    level: number
    selected: 0 | 1
    order: number
  }
}

export interface Collection<F> {
  type: 'FeatureCollection'
  features: F[]
}

export const EMPTY: Collection<never> = { type: 'FeatureCollection', features: [] }

export function routeFeatures(
  analysis: AnalyzeResponse,
  selectedId: string | null,
): Collection<RouteFeature> {
  return {
    type: 'FeatureCollection',
    features: analysis.routes.map((route) => {
      const selected = route.id === selectedId ? 1 : 0
      return {
        type: 'Feature',
        geometry: route.geometry,
        properties: {
          routeId: route.id,
          selected,
          recommended: route.id === analysis.recommendation.route_id ? 1 : 0,
          order: selected,
        },
      }
    }),
  }
}

export function checkpointFeatures(
  analysis: AnalyzeResponse,
  selectedId: string | null,
): Collection<CheckpointFeature> {
  return {
    type: 'FeatureCollection',
    features: analysis.routes.flatMap((route) => {
      const selected = route.id === selectedId ? 1 : 0
      return route.checkpoints.map((checkpoint) => ({
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: [checkpoint.lon, checkpoint.lat] as [number, number] },
        properties: {
          routeId: route.id,
          index: checkpoint.index,
          level: checkpoint.level ?? -1,
          selected: selected as 0 | 1,
          order: selected,
        },
      }))
    }),
  }
}

/** Every vertex of every route, for fitting the map to the trip. */
export function allRouteCoordinates(analysis: AnalyzeResponse): [number, number][] {
  return analysis.routes.flatMap((route) => route.geometry.coordinates)
}
