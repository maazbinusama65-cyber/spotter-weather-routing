import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TripForm } from './TripForm'

vi.mock('../lib/api', () => ({ searchPlaces: vi.fn().mockResolvedValue([]) }))

afterEach(cleanup)

function setup(props: Partial<React.ComponentProps<typeof TripForm>> = {}) {
  const onSubmit = vi.fn()
  const user = userEvent.setup()
  render(<TripForm loading={false} onSubmit={onSubmit} {...props} />)
  return { onSubmit, user }
}

describe('TripForm', () => {
  it('does not submit an empty form and explains what is missing', async () => {
    const { onSubmit, user } = setup()

    await user.click(screen.getByRole('button', { name: /find safest route/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    const alerts = screen.getAllByRole('alert').map((node) => node.textContent)
    expect(alerts).toContain('Enter the starting city or address')
    expect(alerts).toContain('Enter the destination city or address')
  })

  it('submits an example trip with real coordinates, the default load and interval', async () => {
    const { onSubmit, user } = setup()

    await user.click(screen.getByRole('button', { name: 'Denver to Chicago' }))
    await user.click(screen.getByRole('button', { name: /find safest route/i }))

    expect(onSubmit).toHaveBeenCalledTimes(1)
    const body = onSubmit.mock.calls[0][0]
    expect(body.origin).toMatchObject({ label: 'Denver, CO, USA', lat: 39.7392 })
    expect(body.destination).toMatchObject({ label: 'Chicago, IL, USA' })
    expect(body.load_lb).toBe(42000)
    expect(body.interval_miles).toBe(25)
    expect(body.departure).toMatch(/^\d{4}-\d{2}-\d{2}T08:00$/)
  })

  it('applies the chosen load preset and checking interval', async () => {
    const { onSubmit, user } = setup()
    await user.click(screen.getByRole('button', { name: 'Denver to Chicago' }))

    await user.click(screen.getByRole('radio', { name: /heavy/i }))
    await user.click(screen.getByRole('radio', { name: '50 mi' }))
    await user.click(screen.getByRole('button', { name: /find safest route/i }))

    const body = onSubmit.mock.calls[0][0]
    expect(body.load_lb).toBe(78000)
    expect(body.interval_miles).toBe(50)
  })

  it('explains which load rules apply as the weight changes', async () => {
    const { user } = setup()
    const load = screen.getByLabelText('Load weight')

    await user.clear(load)
    await user.type(load, '20000')
    expect(screen.getByText(/standard wind thresholds/i)).toBeTruthy()

    await user.clear(load)
    await user.type(load, '45000')
    expect(screen.getByText(/heavy load/i)).toBeTruthy()
  })

  it('rejects an out of range load with a message next to the field', async () => {
    const { onSubmit, user } = setup()
    await user.click(screen.getByRole('button', { name: 'Denver to Chicago' }))
    const load = screen.getByLabelText('Load weight')
    await user.clear(load)
    await user.type(load, '250000')

    await user.click(screen.getByRole('button', { name: /find safest route/i }))

    expect(onSubmit).not.toHaveBeenCalled()
    expect(screen.getByRole('alert').textContent).toMatch(/between 0 and 100,000/)
  })

  it('swaps the start and destination', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: 'Denver to Chicago' }))

    await user.click(screen.getByRole('button', { name: /swap start and destination/i }))

    expect((screen.getByRole('combobox', { name: 'From' }) as HTMLInputElement).value).toBe(
      'Chicago, IL, USA',
    )
    expect((screen.getByRole('combobox', { name: 'To' }) as HTMLInputElement).value).toBe(
      'Denver, CO, USA',
    )
  })

  it('locks the button while a request is running', () => {
    setup({ loading: true })

    const button = screen.getByRole('button', { name: /analyzing routes/i }) as HTMLButtonElement
    expect(button.disabled).toBe(true)
  })

  it('shows messages the server attached to a field', () => {
    setup({ serverErrors: { departure: 'Departure is beyond the 15-day weather forecast' } })

    expect(screen.getByRole('alert').textContent).toMatch(/15-day weather forecast/)
  })

  it('clears a server message as soon as the user edits that field', async () => {
    const { user } = setup({ serverErrors: { load_lb: 'load_lb must be a number' } })
    expect(screen.getByRole('alert').textContent).toMatch(/load_lb/)

    await user.type(screen.getByLabelText('Load weight'), '0')

    expect(screen.queryByRole('alert')).toBeNull()
  })
})
