import { useState } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Place } from '../lib/types'
import { PlaceField } from './PlaceField'

vi.mock('../lib/api', () => ({ searchPlaces: vi.fn() }))
import { searchPlaces } from '../lib/api'

const denver: Place = { label: 'Denver, CO, USA', lat: 39.74, lon: -104.98 }
const county: Place = { label: 'Denver County, CO, USA', lat: 39.74, lon: -104.99 }

function Harness({ error, onPlace }: { error?: string; onPlace?: (p: Place | null) => void }) {
  const [text, setText] = useState('')
  const [place, setPlace] = useState<Place | null>(null)
  return (
    <PlaceField
      label="From"
      text={text}
      place={place}
      error={error}
      onChange={(nextText, nextPlace) => {
        setText(nextText)
        setPlace(nextPlace)
        onPlace?.(nextPlace)
      }}
    />
  )
}

const search = vi.mocked(searchPlaces)

beforeEach(() => {
  search.mockReset()
  search.mockResolvedValue([])
})
afterEach(cleanup)

describe('PlaceField', () => {
  it('suggests places after the user types three characters', async () => {
    search.mockResolvedValue([denver, county])
    const user = userEvent.setup()
    render(<Harness />)

    await user.type(screen.getByRole('combobox', { name: 'From' }), 'Den')

    expect(await screen.findByRole('option', { name: denver.label })).toBeTruthy()
    expect(screen.getAllByRole('option')).toHaveLength(2)
    expect(search).toHaveBeenCalledTimes(1)
    expect(search.mock.calls[0][0]).toBe('Den')
  })

  it('does not search for fewer than three characters', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.type(screen.getByRole('combobox', { name: 'From' }), 'De')
    await new Promise((resolve) => setTimeout(resolve, 450))

    expect(search).not.toHaveBeenCalled()
  })

  it('fills the field and reports the place when a suggestion is clicked', async () => {
    search.mockResolvedValue([denver])
    const onPlace = vi.fn()
    const user = userEvent.setup()
    render(<Harness onPlace={onPlace} />)
    const input = screen.getByRole('combobox', { name: 'From' })

    await user.type(input, 'Den')
    await user.click(await screen.findByRole('option', { name: denver.label }))

    expect((input as HTMLInputElement).value).toBe(denver.label)
    expect(onPlace).toHaveBeenLastCalledWith(denver)
    expect(screen.queryByRole('listbox')).toBeNull()
  })

  it('supports choosing with the keyboard', async () => {
    search.mockResolvedValue([denver, county])
    const onPlace = vi.fn()
    const user = userEvent.setup()
    render(<Harness onPlace={onPlace} />)

    await user.type(screen.getByRole('combobox', { name: 'From' }), 'Den')
    await screen.findByRole('option', { name: county.label })
    await user.keyboard('{ArrowDown}{Enter}')

    expect(onPlace).toHaveBeenLastCalledWith(county)
  })

  it('forgets the chosen place as soon as the text is edited', async () => {
    search.mockResolvedValue([denver])
    const onPlace = vi.fn()
    const user = userEvent.setup()
    render(<Harness onPlace={onPlace} />)
    const input = screen.getByRole('combobox', { name: 'From' })
    await user.type(input, 'Den')
    await user.click(await screen.findByRole('option', { name: denver.label }))

    await user.type(input, 'x')

    expect(onPlace).toHaveBeenLastCalledWith(null)
  })

  it('tells the user when search is unavailable but typing still works', async () => {
    search.mockImplementation(() => Promise.reject(new Error('down')))
    const user = userEvent.setup()
    render(<Harness />)

    await user.type(screen.getByRole('combobox', { name: 'From' }), 'Boise')

    await waitFor(() => expect(screen.getAllByText(/search is unavailable/i).length).toBeGreaterThan(0))
  })

  it('says when nothing matches', async () => {
    search.mockResolvedValue([])
    const user = userEvent.setup()
    render(<Harness />)

    await user.type(screen.getByRole('combobox', { name: 'From' }), 'Zzzzz')

    expect((await screen.findAllByText(/no matches/i)).length).toBeGreaterThan(0)
  })

  it('shows a validation error and marks the input invalid', () => {
    render(<Harness error="Enter the starting city or address" />)

    expect(screen.getByRole('alert').textContent).toBe('Enter the starting city or address')
    expect(screen.getByRole('combobox', { name: 'From' }).getAttribute('aria-invalid')).toBe('true')
  })

  it('never selects a suggestion that belongs to older text', async () => {
    const dal: Place = { label: 'Dal Lake, India', lat: 34.1, lon: 74.8 }
    const dallas: Place = { label: 'Dallas, TX, USA', lat: 32.78, lon: -96.8 }
    search.mockImplementation(async (query: string) => (query === 'Dal' ? [dal] : [dallas]))
    const onPlace = vi.fn()
    const user = userEvent.setup()
    render(<Harness onPlace={onPlace} />)
    const input = screen.getByRole('combobox', { name: 'From' })
    await user.type(input, 'Dal')
    await screen.findByRole('option', { name: dal.label })

    await user.type(input, 'las{Enter}')

    expect(onPlace).not.toHaveBeenCalledWith(dal)
    expect(screen.queryByRole('option', { name: dal.label })).toBeNull()
    expect(await screen.findByRole('option', { name: dallas.label })).toBeTruthy()
    expect(search).toHaveBeenLastCalledWith('Dallas', expect.anything())
  })

  it('does not search again for old text after a suggestion is chosen and edited', async () => {
    search.mockResolvedValue([denver])
    const user = userEvent.setup()
    render(<Harness />)
    const input = screen.getByRole('combobox', { name: 'From' })
    await user.type(input, 'Den')
    await user.click(await screen.findByRole('option', { name: denver.label }))
    search.mockClear()

    await user.type(input, ' x')
    await new Promise((resolve) => setTimeout(resolve, 100))

    expect(search).not.toHaveBeenCalled()
  })

  it('announces how many suggestions there are for screen readers', async () => {
    search.mockResolvedValue([denver, county])
    const user = userEvent.setup()
    render(<Harness />)

    await user.type(screen.getByRole('combobox', { name: 'From' }), 'Den')
    await screen.findByRole('option', { name: denver.label })

    expect(screen.getByRole('status').textContent).toBe('2 suggestions available')
  })
})
