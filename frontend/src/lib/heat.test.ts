import { describe, expect, it } from 'vitest'
import { heatFeatures, levelCounts } from './heat'
import type { HeatPointData } from './types'

const points: HeatPointData[] = [
  { lat: 39.7, lon: -105, levels: '0123-' },
  { lat: 40.1, lon: -104.2, levels: '1111-' },
  { lat: 41.0, lon: -100.0, levels: '4000-' },
]

describe('heatFeatures', () => {
  it('builds one point per grid cell in lon, lat order with the level at the hour', () => {
    const collection = heatFeatures(points, 2)

    expect(collection.type).toBe('FeatureCollection')
    expect(collection.features).toHaveLength(3)
    expect(collection.features[0].geometry).toEqual({ type: 'Point', coordinates: [-105, 39.7] })
    expect(collection.features.map((f) => f.properties.level)).toEqual([2, 1, 0])
  })

  it('marks unknown hours with -1 so they can be styled apart', () => {
    expect(heatFeatures(points, 4).features.map((f) => f.properties.level)).toEqual([-1, -1, -1])
  })

  it('treats an hour past the series as unknown', () => {
    expect(heatFeatures(points, 30).features[0].properties.level).toBe(-1)
  })
})

describe('levelCounts', () => {
  it('counts how many cells sit at each level at that hour', () => {
    expect(levelCounts(points, 0)).toEqual({ 0: 1, 1: 1, 2: 0, 3: 0, 4: 1, unknown: 0 })
    expect(levelCounts(points, 4)).toEqual({ 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, unknown: 3 })
  })
})
