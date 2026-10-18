const METRES_PER_MILE = 1609.344
/** Metres per pixel at zoom 0 on the equator for MapLibre's 512 px tiles. */
const METRES_PER_PIXEL_AT_ZOOM_0 = 78271.517

/** How many screen pixels a distance on the ground spans at a zoom level and latitude. */
export function milesToPixels(miles: number, zoom: number, latitude: number): number {
  const metresPerPixel =
    (METRES_PER_PIXEL_AT_ZOOM_0 * Math.cos((latitude * Math.PI) / 180)) / 2 ** zoom
  return (miles * METRES_PER_MILE) / metresPerPixel
}

export type LonLat = [number, number]
export type Bounds = [LonLat, LonLat]

export function boundsOf(coordinates: LonLat[]): Bounds | null {
  if (coordinates.length === 0) return null
  let west = Infinity
  let south = Infinity
  let east = -Infinity
  let north = -Infinity
  for (const [lon, lat] of coordinates) {
    west = Math.min(west, lon)
    east = Math.max(east, lon)
    south = Math.min(south, lat)
    north = Math.max(north, lat)
  }
  return [
    [west, south],
    [east, north],
  ]
}
