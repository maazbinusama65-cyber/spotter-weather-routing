import { describe, expect, it } from 'vitest'
import { sampleAnalysis } from './fixtures'
import { allRouteCoordinates, checkpointFeatures, routeFeatures } from './mapdata'

describe('routeFeatures', () => {
  it('flags the selected and recommended routes and draws the selected one last', () => {
    const { features } = routeFeatures(sampleAnalysis, 'r1')

    const byId = Object.fromEntries(features.map((f) => [f.properties.routeId, f.properties]))
    expect(byId.r1).toMatchObject({ selected: 1, recommended: 0, order: 1 })
    expect(byId.r2).toMatchObject({ selected: 0, recommended: 1, order: 0 })
  })

  it('keeps the route geometry untouched', () => {
    const { features } = routeFeatures(sampleAnalysis, null)

    expect(features[0].geometry).toBe(sampleAnalysis.routes[0].geometry)
    expect(features.every((f) => f.properties.selected === 0)).toBe(true)
  })
})

describe('checkpointFeatures', () => {
  it('makes one point per checkpoint of every route in lon, lat order', () => {
    const { features } = checkpointFeatures(sampleAnalysis, 'r1')

    const total = sampleAnalysis.routes.reduce((sum, r) => sum + r.checkpoints.length, 0)
    expect(features).toHaveLength(total)
    const first = sampleAnalysis.routes[0].checkpoints[0]
    expect(features[0].geometry.coordinates).toEqual([first.lon, first.lat])
  })

  it('carries the level, using -1 where the weather is unknown', () => {
    const { features } = checkpointFeatures(sampleAnalysis, 'r2')

    const unknown = features.find((f) => f.properties.routeId === 'r2' && f.properties.index === 4)
    expect(unknown?.properties.level).toBe(-1)
    const high = features.find((f) => f.properties.routeId === 'r1' && f.properties.index === 3)
    expect(high?.properties.level).toBe(2)
  })

  it('marks only the selected route as selected', () => {
    const { features } = checkpointFeatures(sampleAnalysis, 'r2')

    expect(new Set(features.filter((f) => f.properties.selected).map((f) => f.properties.routeId))).toEqual(
      new Set(['r2']),
    )
  })
})

describe('allRouteCoordinates', () => {
  it('gathers every vertex of every route', () => {
    const count = sampleAnalysis.routes.reduce((sum, r) => sum + r.geometry.coordinates.length, 0)

    expect(allRouteCoordinates(sampleAnalysis)).toHaveLength(count)
  })
})
