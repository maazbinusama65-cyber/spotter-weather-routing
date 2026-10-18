import { describe, expect, it } from 'vitest'
import { boundsOf, milesToPixels } from './geo'

describe('milesToPixels', () => {
  it('doubles with each zoom level', () => {
    const z6 = milesToPixels(20, 6, 40)
    const z7 = milesToPixels(20, 7, 40)

    expect(z7 / z6).toBeCloseTo(2, 5)
  })

  it('matches the web-mercator ground resolution', () => {
    // At zoom 0 the equator is 156543 m per 512 px tile pixel... for 256 px tiles; MapLibre uses 512.
    const pixels = milesToPixels(100, 5, 0)
    const metres = 100 * 1609.344
    const metresPerPixel = 78271.517 / 2 ** 5 // 512 px tiles halve the 256 px figure
    expect(pixels).toBeCloseTo(metres / metresPerPixel, 0)
  })

  it('gets bigger at higher latitudes because the map is stretched', () => {
    expect(milesToPixels(20, 6, 60)).toBeGreaterThan(milesToPixels(20, 6, 10))
  })
})

describe('boundsOf', () => {
  it('wraps all coordinates in a south-west and north-east corner', () => {
    expect(
      boundsOf([
        [-105, 39.7],
        [-87.6, 41.9],
        [-96, 35],
      ]),
    ).toEqual([
      [-105, 35],
      [-87.6, 41.9],
    ])
  })

  it('returns null for no coordinates', () => {
    expect(boundsOf([])).toBeNull()
  })
})
