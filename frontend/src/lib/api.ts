import type {
  AnalyzeResponse,
  HeatmapResponse,
  Place,
  TripRequestBody,
} from './types'

export class ApiError extends Error {
  readonly code: string
  readonly fields: Record<string, string>

  constructor(code: string, message: string, fields: Record<string, string> = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.fields = fields
  }
}

interface ErrorEnvelope {
  error?: { code?: string; message?: string; fields?: Record<string, string> }
}

const REQUEST_TIMEOUT_MS = 90_000

/** The caller's signal plus a deadline, so a hung server cannot leave the UI waiting forever. */
function withDeadline(signal?: AbortSignal) {
  const controller = new AbortController()
  let timedOut = false
  const timer = window.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, REQUEST_TIMEOUT_MS)
  signal?.addEventListener('abort', () => controller.abort(), { once: true })
  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    done: () => window.clearTimeout(timer),
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const deadline = withDeadline(init.signal ?? undefined)
  try {
    return await send<T>(path, { ...init, signal: deadline.signal })
  } catch (error) {
    if (deadline.timedOut()) {
      throw new ApiError('timeout', 'The server took too long to respond. Please try again.')
    }
    throw error
  } finally {
    deadline.done()
  }
}

async function send<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('network_error', 'Could not reach the server. Check your connection.')
  }

  if (response.ok) {
    try {
      return (await response.json()) as T
    } catch {
      throw new ApiError('server_error', 'The server sent a response the app could not read.')
    }
  }

  const envelope = (await response.json().catch(() => null)) as ErrorEnvelope | null
  if (envelope?.error?.message) {
    throw new ApiError(
      envelope.error.code ?? 'error',
      envelope.error.message,
      envelope.error.fields,
    )
  }
  throw new ApiError('server_error', 'The server had a problem. Please try again in a moment.')
}

function postJson<T>(path: string, body: TripRequestBody, signal?: AbortSignal): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export function analyzeTrip(body: TripRequestBody, signal?: AbortSignal): Promise<AnalyzeResponse> {
  return postJson<AnalyzeResponse>('/api/analyze', body, signal)
}

export function loadHeatmap(body: TripRequestBody, signal?: AbortSignal): Promise<HeatmapResponse> {
  return postJson<HeatmapResponse>('/api/heatmap', body, signal)
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const data = await request<{ places: Place[] }>(`/api/geocode?q=${encodeURIComponent(query)}`, {
    signal,
  })
  return data.places
}
