import { useEffect, useRef, useState } from 'react'
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  type ExpressionSpecification,
  type GeoJSONSource,
  type LineLayerSpecification,
  type MapLayerMouseEvent,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { boundsOf, milesToPixels } from '../lib/geo'
import { heatFeatures } from '../lib/heat'
import { EMPTY, allRouteCoordinates, checkpointFeatures, routeFeatures } from '../lib/mapdata'
import { LEVELS, UNKNOWN_LEVEL } from '../lib/risk'
import type { AnalyzeResponse, HeatmapResponse } from '../lib/types'
import { buildCheckpointPopup } from './popupContent'
import './MapView.css'

const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'
const US_CENTER: [number, number] = [-97.5, 39.2]
const HEAT_RADIUS_MILES = 21
const REFERENCE_LATITUDE = 39
const ROUTE_INK = '#17304f'
const ROUTE_MUTED = '#6f7f96'

export interface MapFocus {
  routeId: string
  index: number
  /** Changes on every request so the same checkpoint can be focused twice. */
  nonce: number
}

interface MapViewProps {
  analysis: AnalyzeResponse | null
  heat: HeatmapResponse | null
  selectedId: string | null
  hour: number
  focus: MapFocus | null
  busy: boolean
  onSelectRoute: (routeId: string) => void
}

type Source = 'heat' | 'routes' | 'checkpoints'

function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

// MapLibre's expression types cannot express a spread of match pairs, hence the cast.
const levelColorExpression = [
  'match',
  ['get', 'level'],
  ...LEVELS.flatMap((level) => [level.value, level.color]),
  UNKNOWN_LEVEL.color,
] as unknown as ExpressionSpecification

function heatRadius(): ExpressionSpecification {
  // The radius is a fixed ground distance, so it doubles with every zoom level.
  return [
    'interpolate',
    ['exponential', 2],
    ['zoom'],
    3,
    milesToPixels(HEAT_RADIUS_MILES, 3, REFERENCE_LATITUDE),
    12,
    milesToPixels(HEAT_RADIUS_MILES, 12, REFERENCE_LATITUDE),
  ]
}

function addLayers(map: MapLibreMap) {
  for (const name of ['heat', 'routes', 'checkpoints'] as const) {
    map.addSource(name, { type: 'geojson', data: EMPTY })
  }
  // Keep place names readable: weather goes under the basemap labels.
  const firstLabel = map.getStyle().layers.find((layer) => layer.type === 'symbol')?.id

  map.addLayer(
    {
      id: 'heat',
      type: 'circle',
      source: 'heat',
      paint: {
        'circle-radius': heatRadius(),
        'circle-color': levelColorExpression,
        'circle-opacity': ['match', ['get', 'level'], 1, 0.38, 2, 0.5, 3, 0.62, 4, 0.74, 0.13],
        'circle-blur': 0.9,
        'circle-pitch-alignment': 'map',
      },
    },
    firstLabel,
  )

  const lineLayout: LineLayerSpecification['layout'] = {
    'line-cap': 'round',
    'line-join': 'round',
    'line-sort-key': ['get', 'order'],
  }
  map.addLayer({
    id: 'route-casing',
    type: 'line',
    source: 'routes',
    layout: lineLayout,
    paint: { 'line-color': '#ffffff', 'line-width': ['case', ['==', ['get', 'selected'], 1], 10, 7] },
  })
  map.addLayer({
    id: 'route-line',
    type: 'line',
    source: 'routes',
    layout: lineLayout,
    paint: {
      'line-color': ['case', ['==', ['get', 'selected'], 1], ROUTE_INK, ROUTE_MUTED],
      'line-width': ['case', ['==', ['get', 'selected'], 1], 5, 3.5],
    },
  })
  map.addLayer({
    id: 'route-hit',
    type: 'line',
    source: 'routes',
    paint: { 'line-color': '#000000', 'line-opacity': 0, 'line-width': 20 },
  })
  map.addLayer({
    id: 'checkpoints',
    type: 'circle',
    source: 'checkpoints',
    layout: { 'circle-sort-key': ['get', 'order'] },
    paint: {
      'circle-radius': ['case', ['==', ['get', 'selected'], 1], 6.5, 4],
      'circle-color': levelColorExpression,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': ['case', ['==', ['get', 'selected'], 1], 2, 1],
      'circle-opacity': ['case', ['==', ['get', 'selected'], 1], 1, 0.8],
    },
  })
}

function endpointMarker(letter: string, label: string): Marker {
  const node = document.createElement('div')
  node.className = 'endpoint'
  node.textContent = letter
  node.setAttribute('role', 'img')
  node.setAttribute('aria-label', label)
  return new Marker({ element: node })
}

export default function MapView({
  analysis,
  heat,
  selectedId,
  hour,
  focus,
  busy,
  onSelectRoute,
}: MapViewProps) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markers = useRef<Marker[]>([])
  const popup = useRef<Popup | null>(null)
  const [ready, setReady] = useState(false)
  const [tilesFailed, setTilesFailed] = useState(false)

  // Handlers registered once must still see the latest props.
  const analysisRef = useRef(analysis)
  const selectRef = useRef(onSelectRoute)
  useEffect(() => {
    analysisRef.current = analysis
    selectRef.current = onSelectRoute
  })

  function showPopup(routeId: string, index: number, flyTo: boolean) {
    const current = analysisRef.current
    const map = mapRef.current
    const route = current?.routes.find((candidate) => candidate.id === routeId)
    const checkpoint = route?.checkpoints.find((candidate) => candidate.index === index)
    if (!current || !map || !route || !checkpoint) return
    popup.current?.remove()
    popup.current = new Popup({ maxWidth: '280px', offset: 12 })
      .setLngLat([checkpoint.lon, checkpoint.lat])
      .setDOMContent(buildCheckpointPopup(route, checkpoint, current.timezone))
      .addTo(map)
    if (flyTo) {
      map.easeTo({
        center: [checkpoint.lon, checkpoint.lat],
        duration: prefersReducedMotion() ? 0 : 500,
      })
    }
  }

  useEffect(() => {
    if (!container.current) return
    const map = new MapLibreMap({
      container: container.current,
      style: STYLE_URL,
      center: US_CENTER,
      zoom: 3.6,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
    })
    map.touchZoomRotate.disableRotation()
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    mapRef.current = map

    map.on('load', () => {
      addLayers(map)

      map.on('click', 'checkpoints', (event: MapLayerMouseEvent) => {
        const props = event.features?.[0]?.properties
        if (props) showPopup(String(props.routeId), Number(props.index), false)
      })
      map.on('click', 'route-hit', (event: MapLayerMouseEvent) => {
        const onCheckpoint = map.queryRenderedFeatures(event.point, { layers: ['checkpoints'] })
        const routeId = event.features?.[0]?.properties?.routeId
        if (onCheckpoint.length === 0 && routeId) selectRef.current(String(routeId))
      })
      for (const layer of ['checkpoints', 'route-hit']) {
        map.on('mouseenter', layer, () => (map.getCanvas().style.cursor = 'pointer'))
        map.on('mouseleave', layer, () => (map.getCanvas().style.cursor = ''))
      }
      setReady(true)
    })
    map.on('error', () => {
      if (!map.isStyleLoaded()) setTilesFailed(true)
    })

    return () => {
      popup.current?.remove()
      markers.current.forEach((marker) => marker.remove())
      markers.current = []
      map.remove()
      mapRef.current = null
      setReady(false)
    }
    // The map is created once; showPopup reads everything it needs from refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function setData(name: Source, data: unknown) {
    const source = mapRef.current?.getSource(name) as GeoJSONSource | undefined
    source?.setData(data as Parameters<GeoJSONSource['setData']>[0])
  }

  useEffect(() => {
    if (!ready) return
    setData('routes', analysis ? routeFeatures(analysis, selectedId) : EMPTY)
    setData('checkpoints', analysis ? checkpointFeatures(analysis, selectedId) : EMPTY)
  }, [ready, analysis, selectedId])

  useEffect(() => {
    if (ready) setData('heat', heat ? heatFeatures(heat.points, hour) : EMPTY)
  }, [ready, heat, hour])

  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    popup.current?.remove()
    markers.current.forEach((marker) => marker.remove())
    markers.current = []
    if (!analysis) return

    markers.current = [
      endpointMarker('A', 'Start').setLngLat([analysis.origin.lon, analysis.origin.lat]).addTo(map),
      endpointMarker('B', 'Destination')
        .setLngLat([analysis.destination.lon, analysis.destination.lat])
        .addTo(map),
    ]
    const bounds = boundsOf(allRouteCoordinates(analysis))
    if (bounds) {
      map.fitBounds(bounds, {
        padding: { top: 70, right: 50, bottom: 250, left: 50 },
        duration: prefersReducedMotion() ? 0 : 900,
        maxZoom: 9,
      })
    }
  }, [ready, analysis])

  useEffect(() => {
    if (ready && focus) showPopup(focus.routeId, focus.index, true)
    // showPopup is stable in behaviour: it reads current data from refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, focus])

  return (
    <div className="map">
      <div ref={container} className="map__canvas" role="region" aria-label="Route map" />
      {busy && (
        <div className="map__busy" role="status">
          <span className="map__busy-bar" aria-hidden="true" />
          Reading forecasts along each route
        </div>
      )}
      {tilesFailed && (
        <div className="map__fallback" role="alert">
          The map background could not be loaded. Routes and results still work.
        </div>
      )}
    </div>
  )
}
