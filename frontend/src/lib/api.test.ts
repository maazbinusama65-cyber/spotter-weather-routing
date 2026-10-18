import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, analyzeTrip, searchPlaces } from './api'

const body = {
  origin: 'Denver, CO',
  destination: 'Chicago, IL',
  departure: '2026-11-02T08:00',
  load_lb: 42000,
  interval_miles: 25,
}

function respond(status: number, payload: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('api client', () => {
  it('posts JSON to the analyze endpoint and returns the parsed body', async () => {
    const fetchMock = respond(200, { routes: [] })
    vi.stubGlobal('fetch', fetchMock)

    const result = await analyzeTrip(body)

    expect(result).toEqual({ routes: [] })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/analyze')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual(body)
    expect(init.headers['Content-Type']).toBe('application/json')
  })

  it('turns the error envelope into an ApiError with field messages', async () => {
    vi.stubGlobal(
      'fetch',
      respond(400, {
        error: {
          code: 'validation_error',
          message: 'load_lb must be a number',
          fields: { load_lb: 'load_lb must be a number' },
        },
      }),
    )

    const error = await analyzeTrip(body).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('validation_error')
    expect(error.message).toBe('load_lb must be a number')
    expect(error.fields).toEqual({ load_lb: 'load_lb must be a number' })
  })

  it('explains gateway failures that carry no JSON envelope', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>', { status: 502 })))

    const error = await analyzeTrip(body).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.message).toMatch(/server/i)
  })

  it('explains network failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    const error = await analyzeTrip(body).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('network_error')
  })

  it('lets an aborted request surface as an abort, not an API error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('aborted', 'AbortError')))

    const error = await analyzeTrip(body).catch((e) => e)

    expect(error).not.toBeInstanceOf(ApiError)
    expect(error.name).toBe('AbortError')
  })

  it('searches places with an encoded query', async () => {
    const fetchMock = respond(200, { places: [{ label: 'Denver, CO, USA', lat: 39.7, lon: -105 }] })
    vi.stubGlobal('fetch', fetchMock)

    const places = await searchPlaces('Denver & Co')

    expect(places).toHaveLength(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/geocode?q=Denver%20%26%20Co')
  })

  it('gives up with a clear message when the server never answers', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener('abort', () =>
              reject(new DOMException('aborted', 'AbortError')),
            )
          }),
      ),
    )

    const pending = analyzeTrip(body).catch((e) => e)
    await vi.advanceTimersByTimeAsync(91_000)
    const error = await pending

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('timeout')
  })

  it('still reports a caller abort as an abort, not a timeout', async () => {
    const controller = new AbortController()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener('abort', () =>
              reject(new DOMException('aborted', 'AbortError')),
            )
          }),
      ),
    )

    const pending = analyzeTrip(body, controller.signal).catch((e) => e)
    controller.abort()
    const error = await pending

    expect(error).not.toBeInstanceOf(ApiError)
    expect(error.name).toBe('AbortError')
  })

  it('explains a successful response that is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>ok</html>', { status: 200 })))

    const error = await analyzeTrip(body).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('server_error')
  })
})
