import { describeRisk } from '../lib/describe'
import { formatDuration, formatMiles, formatTime } from '../lib/format'
import { levelInfo } from '../lib/risk'
import type { AnalyzeResponse, RouteData } from '../lib/types'
import { RiskBar } from './RiskBar'
import './RouteList.css'

interface RouteListProps {
  analysis: AnalyzeResponse
  selectedId: string | null
  onSelect: (routeId: string) => void
  onPickCheckpoint: (routeId: string, index: number) => void
}

export function RouteList({ analysis, selectedId, onSelect, onPickCheckpoint }: RouteListProps) {
  const ordered = analysis.recommendation.ranking
    .map((id) => analysis.routes.find((route) => route.id === id))
    .filter((route): route is RouteData => route !== undefined)

  return (
    <ol className="route-list" aria-label="Route options, best first">
      {ordered.map((route) => {
        const selected = route.id === selectedId
        const recommended = route.id === analysis.recommendation.route_id
        return (
          <li key={route.id} className="route-list__item">
            <button
              type="button"
              className="route"
              aria-pressed={selected}
              onClick={() => onSelect(route.id)}
            >
              <span className="route__head">
                <span className="route__name">{route.label}</span>
                {recommended && <span className="route__badge">Recommended</span>}
                <span className="route__level mono">
                  Worst: {levelInfo(route.summary.max_level).label}
                </span>
              </span>
              {route.via && <span className="route__via">via {route.via}</span>}
              <span className="route__stats mono">
                <span>{formatMiles(route.distance_mi)}</span>
                <span>{formatDuration(route.duration_s)}</span>
                <span>Arrive {formatTime(route.arrival, analysis.timezone)}</span>
              </span>
              <RiskBar summary={route.summary} />
              <span className="route__risk">{describeRisk(route.summary)}</span>
            </button>
            {selected && <CheckpointStrip route={route} onPick={onPickCheckpoint} />}
          </li>
        )
      })}
    </ol>
  )
}

function CheckpointStrip({
  route,
  onPick,
}: {
  route: RouteData
  onPick: (routeId: string, index: number) => void
}) {
  return (
    <div className="strip" role="group" aria-label={`Weather at each checkpoint on ${route.label}`}>
      <p className="strip__caption">Checkpoints, start to destination</p>
      <div className="strip__cells">
        {route.checkpoints.map((checkpoint) => {
          const level = levelInfo(checkpoint.level)
          return (
            <button
              key={checkpoint.index}
              type="button"
              className="strip__cell"
              style={{ background: level.color }}
              title={`Mile ${Math.round(checkpoint.distance_mi)}: ${level.label}`}
              aria-label={`Mile ${Math.round(checkpoint.distance_mi)}, ${level.label}`}
              onClick={() => onPick(route.id, checkpoint.index)}
            />
          )
        })}
      </div>
    </div>
  )
}
