import { describe, expect, it } from 'vitest'
import { sampleAnalysis } from '../lib/fixtures'
import { buildCheckpointPopup } from './popupContent'

const route = sampleAnalysis.routes[0]

describe('buildCheckpointPopup', () => {
  it('shows the level, mile, arrival time and weather readings', () => {
    const popup = buildCheckpointPopup(route, route.checkpoints[3], 'America/Denver')

    expect(popup.textContent).toContain('High')
    expect(popup.textContent).toContain('Route 1, mile 75')
    expect(popup.textContent).toMatch(/Arrive \w{3} \d{1,2}:\d{2} [AP]M M[SD]T/)
    expect(popup.textContent).toContain('Wind')
    expect(popup.textContent).toContain('15 mph')
  })

  it('says when there is no weather data', () => {
    const unknown = sampleAnalysis.routes[1].checkpoints[4]

    const popup = buildCheckpointPopup(sampleAnalysis.routes[1], unknown, 'America/Denver')

    expect(popup.textContent).toContain('Unknown')
    expect(popup.textContent).toContain('No data')
  })

  it('mentions the load only when it raised the risk', () => {
    const escalated = { ...route.checkpoints[2], load_escalated: true }

    expect(buildCheckpointPopup(route, escalated, 'UTC').textContent).toContain('load weight')
    expect(buildCheckpointPopup(route, route.checkpoints[2], 'UTC').textContent).not.toContain(
      'load weight',
    )
  })

  it('never turns API text into markup', () => {
    const hostile = {
      ...route,
      label: '<img src=x onerror=alert(1)>',
    }
    const checkpoint = { ...route.checkpoints[1], reason: '<script>alert(1)</script>' }

    const popup = buildCheckpointPopup(hostile, checkpoint, 'UTC')

    expect(popup.querySelector('img')).toBeNull()
    expect(popup.querySelector('script')).toBeNull()
    expect(popup.textContent).toContain('<script>alert(1)</script>')
  })
})
