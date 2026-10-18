import { Warning } from '@phosphor-icons/react'
import { formatDuration, formatMiles } from '../lib/format'
import type { AnalyzeResponse } from '../lib/types'
import './Recommendation.css'

export function Recommendation({ analysis }: { analysis: AnalyzeResponse }) {
  const { recommendation } = analysis
  const route = analysis.routes.find((candidate) => candidate.id === recommendation.route_id)
  if (!route) return null
  const blocked = recommendation.all_blocked

  return (
    <section
      className={`recommendation${blocked ? ' recommendation--blocked' : ''}`}
      aria-labelledby="recommendation-title"
    >
      <p className="recommendation__kicker">
        {blocked ? <Warning size={16} weight="fill" aria-hidden="true" /> : null}
        {blocked ? 'No clear route' : 'Recommended'}
      </p>
      <h2 className="recommendation__title" id="recommendation-title">
        {route.label}
        <span className="recommendation__facts mono">
          {formatMiles(route.distance_mi)} · {formatDuration(route.duration_s)}
        </span>
      </h2>
      <p className="recommendation__reason">{recommendation.reason}</p>
      {blocked && (
        <p className="recommendation__reason">
          Every option has No Travel conditions at some point. This is the least affected one.
        </p>
      )}
    </section>
  )
}
