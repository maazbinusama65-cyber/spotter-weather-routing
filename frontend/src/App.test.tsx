import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { sampleAnalysis } from './lib/fixtures'
import type { HeatmapResponse } from './lib/types'

// The real map needs WebGL; the stub exposes what App passes to it.
vi.mock('./components/MapView', () => ({
  default: (props: { hour: number; selectedId: string | null; heat: unknown }) => (
    <div
      data-testid="map"
      data-hour={props.hour}
      data-selected={props.selectedId ?? ''}
      data-heat={props.heat ? 'yes' : 'no'}
    />
  ),
}))

const heat: HeatmapResponse = {
  start: '2026-11-02T14:00:00Z',
  hours: 49,
  timezone: 'America/Denver',
  risk_levels: sampleAnalysis.risk_levels,
  points: [
    { lat: 39.7, lon: -105, levels: '0'.repeat(10) + '3'.repeat(39) },
    { lat: 40.1, lon: -104.2, levels: '0'.repeat(49) },
  ],
  warnings: [],
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function mockApi(overrides: { analyze?: () => Response; heatmap?: () => Response } = {}) {
  const fetchMock = vi.fn((url: string) => {
    if (url === '/api/analyze') return Promise.resolve(overrides.analyze?.() ?? json(sampleAnalysis))
    if (url === '/api/heatmap') return Promise.resolve(overrides.heatmap?.() ?? json(heat))
    return Promise.resolve(json({ places: [] }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function runExample(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Denver to Chicago' }))
  await user.click(screen.getByRole('button', { name: /find safest route/i }))
}

const slider = () => screen.getByRole('slider', { name: /forecast hour/i }) as HTMLInputElement
const mapHour = () => screen.getByTestId('map').getAttribute('data-hour')

beforeEach(() => vi.unstubAllGlobals())
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('starts with an empty state and the form', () => {
    render(<App />)

    expect(screen.getByText(/check the sky before you roll/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /find safest route/i })).toBeTruthy()
  })

  it('shows the recommendation, the routes best first, and selects the recommended route', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)

    await runExample(user)

    expect(await screen.findByRole('heading', { name: /route 2/i })).toBeTruthy()
    const cards = screen.getAllByRole('button', { pressed: true })
    expect(cards).toHaveLength(1)
    expect(screen.getByTestId('map').getAttribute('data-selected')).toBe('r2')
    const statuses = screen.getAllByRole('status').map((node) => node.textContent)
    expect(statuses).toContain('Analysis complete. 2 routes. Recommended: Route 2.')
  })

  it('moves the map to the chosen forecast hour when the slider is dragged', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await runExample(user)
    await waitFor(() => expect(slider().disabled).toBe(false))

    fireEvent.change(slider(), { target: { value: '12' } })

    expect(mapHour()).toBe('12')
    expect(slider().value).toBe('12')
    // 10 hours of calm, then Severe: the legend follows the hour
    const legend = within(screen.getByRole('list', { name: /corridor cells/i }))
    expect(legend.getByText('Severe').parentElement?.textContent).toContain('1')
  })

  it('keeps the slider working after the user picks another route', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await runExample(user)
    await waitFor(() => expect(slider().disabled).toBe(false))

    await user.click(screen.getByRole('button', { name: /route 1/i }))
    fireEvent.change(slider(), { target: { value: '30' } })

    expect(mapHour()).toBe('30')
    expect(screen.getByTestId('map').getAttribute('data-selected')).toBe('r1')
  })

  it('starts a fresh view, back at departure, when a new analysis arrives, and the slider still works', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await runExample(user)
    await waitFor(() => expect(slider().disabled).toBe(false))
    fireEvent.change(slider(), { target: { value: '20' } })
    expect(mapHour()).toBe('20')

    await user.click(screen.getByRole('button', { name: /find safest route/i }))
    await waitFor(() => expect(mapHour()).toBe('0'))
    await waitFor(() => expect(slider().disabled).toBe(false))
    fireEvent.change(slider(), { target: { value: '7' } })

    expect(mapHour()).toBe('7')
  })

  it('plays the forecast forward one hour at a time and stops at the end', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await runExample(user)
    await waitFor(() => expect(slider().disabled).toBe(false))
    fireEvent.change(slider(), { target: { value: '46' } })

    await user.click(screen.getByRole('button', { name: /play forecast forward/i }))

    await waitFor(() => expect(mapHour()).toBe('48'), { timeout: 3000 })
    await waitFor(() => expect(screen.getByRole('button', { name: /play forecast forward/i })).toBeTruthy())
  })

  it('shows the analysis even when the heatmap fails, and says so', async () => {
    mockApi({ heatmap: () => json({ error: { code: 'provider_error', message: 'busy' } }, 502) })
    const user = userEvent.setup()
    render(<App />)

    await runExample(user)

    expect(await screen.findByRole('heading', { name: /route 2/i })).toBeTruthy()
    expect(await screen.findByText(/48 hour weather map could not be loaded/i)).toBeTruthy()
  })

  it('shows the server message and offers a retry when the analysis fails', async () => {
    const analyze = vi
      .fn()
      .mockReturnValueOnce(json({ error: { code: 'provider_error', message: 'Routing service is busy' } }, 502))
      .mockReturnValue(json(sampleAnalysis))
    mockApi({ analyze })
    const user = userEvent.setup()
    render(<App />)

    await runExample(user)
    expect((await screen.findByRole('alert')).textContent).toContain('Routing service is busy')
    await user.click(screen.getByRole('button', { name: /retry/i }))

    expect(await screen.findByRole('heading', { name: /route 2/i })).toBeTruthy()
  })
})
