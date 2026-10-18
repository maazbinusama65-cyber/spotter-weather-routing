import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { ArrowClockwise, CloudLightning, Truck } from '@phosphor-icons/react'
import { Notice } from './components/Notice'
import { Recommendation } from './components/Recommendation'
import { RiskGuide } from './components/RiskGuide'
import { RouteList } from './components/RouteList'
import { TimeScrubber } from './components/TimeScrubber'
import { TripForm } from './components/TripForm'
import type { MapFocus } from './components/MapView'
import { useTrip } from './hooks/useTrip'
import type { AnalyzeResponse, TripRequestBody } from './lib/types'
import './App.css'

// The map library is the largest dependency; load it while the form is already usable.
const MapView = lazy(() => import('./components/MapView'))

function ResultsSkeleton() {
  return (
    <div className="skeleton" aria-hidden="true">
      <div className="skeleton__block skeleton__block--tall" />
      {[0, 1, 2].map((key) => (
        <div key={key} className="skeleton__block" />
      ))}
    </div>
  )
}

function EmptyResults() {
  return (
    <div className="empty">
      <CloudLightning size={28} weight="duotone" aria-hidden="true" />
      <h2 className="empty__title">Check the sky before you roll</h2>
      <p className="empty__text">
        Choose a start, a destination and a departure time. You get up to three routes, weather
        checked for the hour you reach each point, and a recommendation.
      </p>
    </div>
  )
}

interface View {
  /** The analysis this view belongs to; a new analysis starts a fresh view. */
  forAnalysis: AnalyzeResponse | null
  selectedId: string | null
  hour: number
  focus: MapFocus | null
}

export default function App() {
  const { state, run } = useTrip()
  const { analysis } = state
  const [stored, setStored] = useState<View>({
    forAnalysis: null,
    selectedId: null,
    hour: 0,
    focus: null,
  })
  const [lastBody, setLastBody] = useState<TripRequestBody | null>(null)
  const nonce = useRef(0)
  const results = useRef<HTMLDivElement>(null)

  const view: View =
    stored.forAnalysis === analysis
      ? stored
      : {
          forAnalysis: analysis,
          selectedId: analysis?.recommendation.route_id ?? null,
          hour: 0,
          focus: null,
        }
  const update = (patch: Partial<View>) => setStored({ ...view, ...patch })
  const setHour = useCallback((hour: number) => setStored((previous) => ({ ...previous, hour })), [])

  // Bring the answer into view: on a phone it sits well below the form.
  useEffect(() => {
    if (!analysis) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    results.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' })
  }, [analysis])

  const submit = useCallback(
    (body: TripRequestBody) => {
      setLastBody(body)
      void run(body)
    },
    [run],
  )

  const loading = state.phase === 'loading'

  return (
    <div className="app">
      <aside className="desk">
        <header className="desk__brand">
          <span className="desk__mark" aria-hidden="true">
            <Truck size={20} weight="bold" />
          </span>
          <div>
            <h1 className="desk__name">Stormline</h1>
            <p className="desk__tagline">Weather-aware truck routing</p>
          </div>
        </header>

        <div className="desk__section">
          <TripForm loading={loading} serverErrors={state.error?.fields} onSubmit={submit} />
        </div>

        <div className="desk__section desk__results" aria-live="polite" ref={results}>
          {loading && <ResultsSkeleton />}

          {state.phase === 'idle' && <EmptyResults />}

          {state.phase === 'error' && state.error && (
            <Notice
              tone="error"
              action={
                lastBody ? (
                  <button
                    type="button"
                    className="button button--quiet"
                    onClick={() => submit(lastBody)}
                  >
                    <ArrowClockwise size={14} aria-hidden="true" />
                    Retry
                  </button>
                ) : undefined
              }
            >
              {state.error.message}
            </Notice>
          )}

          {analysis && (
            <>
              <Recommendation analysis={analysis} />
              {analysis.warnings.map((warning) => (
                <Notice key={warning} tone="warning">
                  {warning}
                </Notice>
              ))}
              <RouteList
                analysis={analysis}
                selectedId={view.selectedId}
                onSelect={(selectedId) => update({ selectedId })}
                onPickCheckpoint={(routeId, index) => {
                  nonce.current += 1
                  update({ selectedId: routeId, focus: { routeId, index, nonce: nonce.current } })
                }}
              />
            </>
          )}

          <RiskGuide />
        </div>
      </aside>

      <main className="stage">
        <Suspense fallback={<div className="stage__loading">Loading map</div>}>
          <MapView
            analysis={analysis}
            heat={state.heat}
            selectedId={view.selectedId}
            hour={view.hour}
            focus={view.focus}
            busy={loading}
            onSelectRoute={(selectedId) => update({ selectedId })}
          />
        </Suspense>
        {analysis && (
          <div className="stage__scrubber">
            <TimeScrubber heat={state.heat} status={state.heatStatus} hour={view.hour} onHour={setHour} />
          </div>
        )}
      </main>
    </div>
  )
}
