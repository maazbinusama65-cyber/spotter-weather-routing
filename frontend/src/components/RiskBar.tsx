import { riskSegments } from '../lib/describe'
import type { RouteSummaryData } from '../lib/types'

/** The route's miles split by risk level, as one proportional bar. */
export function RiskBar({ summary }: { summary: RouteSummaryData }) {
  const segments = riskSegments(summary)
  const label = segments.map((s) => `${s.label} ${Math.round(s.miles)} miles`).join(', ')
  return (
    <div className="risk-bar" role="img" aria-label={`Miles by risk level: ${label}`}>
      {segments.map((segment) => (
        <span
          key={segment.label}
          className="risk-bar__segment"
          style={{ flexGrow: segment.miles, background: segment.color }}
          title={`${segment.label}: ${Math.round(segment.miles)} mi`}
        />
      ))}
    </div>
  )
}
