import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, analyzeTrip, loadHeatmap } from '../lib/api'
import type { AnalyzeResponse, HeatmapResponse, TripRequestBody } from '../lib/types'

export type Phase = 'idle' | 'loading' | 'done' | 'error'
export type HeatStatus = 'idle' | 'loading' | 'ready' | 'failed'

export interface TripState {
  phase: Phase
  analysis: AnalyzeResponse | null
  heat: HeatmapResponse | null
  heatStatus: HeatStatus
  error: { message: string; fields: Record<string, string> } | null
}

const INITIAL: TripState = {
  phase: 'idle',
  analysis: null,
  heat: null,
  heatStatus: 'idle',
  error: null,
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

/**
 * Runs the analysis, then the heatmap. They run one after the other on purpose: the
 * heatmap reuses the routes the analysis just cached, so the routing service is only
 * asked once per trip.
 */
export function useTrip() {
  const [state, setState] = useState<TripState>(INITIAL)
  const controller = useRef<AbortController | null>(null)

  useEffect(() => () => controller.current?.abort(), [])

  const run = useCallback(async (body: TripRequestBody) => {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setState({ ...INITIAL, phase: 'loading' })

    let analysis: AnalyzeResponse
    try {
      analysis = await analyzeTrip(body, current.signal)
    } catch (error) {
      if (isAbort(error)) return
      const api = error instanceof ApiError ? error : null
      setState({
        ...INITIAL,
        phase: 'error',
        error: {
          message: api?.message ?? 'Something went wrong. Please try again.',
          fields: api?.fields ?? {},
        },
      })
      return
    }

    setState({ ...INITIAL, phase: 'done', analysis, heatStatus: 'loading' })
    try {
      const heat = await loadHeatmap(body, current.signal)
      setState((previous) => ({ ...previous, heat, heatStatus: 'ready' }))
    } catch (error) {
      if (isAbort(error)) return
      setState((previous) => ({ ...previous, heatStatus: 'failed' }))
    }
  }, [])

  return { state, run }
}
