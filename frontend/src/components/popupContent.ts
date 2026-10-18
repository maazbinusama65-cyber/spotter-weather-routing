import { formatTime } from '../lib/format'
import { levelInfo } from '../lib/risk'
import type { CheckpointData, RouteData } from '../lib/types'

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag)
  node.className = className
  if (text !== undefined) node.textContent = text
  return node
}

function reading(value: number | null, unit: string): string {
  return value === null ? 'No data' : `${value} ${unit}`
}

/**
 * The checkpoint popup. Built from DOM nodes and textContent, never innerHTML, so nothing
 * from the API can be interpreted as markup.
 */
export function buildCheckpointPopup(
  route: RouteData,
  checkpoint: CheckpointData,
  timezone: string,
): HTMLElement {
  const level = levelInfo(checkpoint.level)
  const root = element('div', 'popup')

  const head = element('div', 'popup__head')
  const badge = element('span', 'popup__level', level.label)
  badge.style.background = level.color
  badge.style.color = level.ink
  head.append(
    badge,
    element('strong', 'popup__title', `${route.label}, mile ${Math.round(checkpoint.distance_mi)}`),
  )

  const time = element('p', 'popup__time mono', `Arrive ${formatTime(checkpoint.eta, timezone)}`)

  const grid = element('dl', 'popup__grid mono')
  const rows: [string, string][] = [
    ['Wind', reading(checkpoint.wind_mph, 'mph')],
    ['Rain', reading(checkpoint.rain_in_hr, 'in/hr')],
    ['Snow', reading(checkpoint.snow_in_hr, 'in/hr')],
  ]
  for (const [name, value] of rows) {
    grid.append(element('dt', 'popup__term', name), element('dd', 'popup__value', value))
  }

  root.append(head, time, grid, element('p', 'popup__reason', checkpoint.reason))
  if (checkpoint.load_escalated) {
    root.append(element('p', 'popup__note', 'Raised because of the load weight.'))
  }
  return root
}
