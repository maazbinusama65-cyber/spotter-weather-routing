import { useEffect, useState } from 'react'
import { ArrowCounterClockwise, Pause, Play } from '@phosphor-icons/react'
import { addHours, formatHourOffset, formatTime } from '../lib/format'
import { levelCounts } from '../lib/heat'
import { LEVELS, UNKNOWN_LEVEL } from '../lib/risk'
import type { HeatStatus } from '../hooks/useTrip'
import type { HeatmapResponse } from '../lib/types'
import { Notice } from './Notice'
import './TimeScrubber.css'

const DEFAULT_LAST_HOUR = 48
const PLAY_STEP_MS = 420

interface TimeScrubberProps {
  heat: HeatmapResponse | null
  status: HeatStatus
  hour: number
  onHour: (hour: number) => void
}

export function TimeScrubber({ heat, status, hour, onHour }: TimeScrubberProps) {
  const [playing, setPlaying] = useState(false)
  const ready = status === 'ready' && heat !== null
  const lastHour = heat ? heat.hours - 1 : DEFAULT_LAST_HOUR
  const tickHours = [0, 12, 24, 36].filter((tick) => tick < lastHour).concat(lastHour)

  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => {
      onHour(Math.min(hour + 1, lastHour))
      if (hour + 1 >= lastHour) setPlaying(false)
    }, PLAY_STEP_MS)
    return () => window.clearInterval(timer)
  }, [playing, hour, lastHour, onHour])

  if (status === 'failed') {
    return (
      <section className="scrubber" aria-label="Forecast time">
        <Notice tone="warning">
          The 48 hour weather map could not be loaded. Routes, checkpoints and the recommendation
          are not affected.
        </Notice>
      </section>
    )
  }

  const moment = heat ? addHours(heat.start, hour) : null
  const timeLabel = heat && moment ? formatTime(moment, heat.timezone) : 'Loading forecast'
  const counts = heat ? levelCounts(heat.points, hour) : null

  return (
    <section className="scrubber" aria-label="Forecast time" aria-busy={!ready}>
      <div className="scrubber__head">
        <div>
          <h2 className="scrubber__title">Weather on the corridor</h2>
          <p className="scrubber__time mono" aria-live="off">
            {timeLabel}
            {ready && <span className="scrubber__offset"> {formatHourOffset(hour)}</span>}
          </p>
        </div>
        <div className="scrubber__buttons">
          <button
            type="button"
            className="icon-button"
            disabled={!ready}
            aria-label={playing ? 'Pause forecast playback' : 'Play forecast forward'}
            onClick={() => {
              if (!playing && hour >= lastHour) onHour(0)
              setPlaying((value) => !value)
            }}
          >
            {playing ? <Pause size={18} weight="fill" /> : <Play size={18} weight="fill" />}
          </button>
          <button
            type="button"
            className="icon-button"
            disabled={!ready || hour === 0}
            aria-label="Back to departure"
            onClick={() => {
              setPlaying(false)
              onHour(0)
            }}
          >
            <ArrowCounterClockwise size={18} />
          </button>
        </div>
      </div>

      <input
        className="scrubber__range"
        type="range"
        min={0}
        max={lastHour}
        step={1}
        value={hour}
        disabled={!ready}
        aria-label="Forecast hour after departure"
        aria-valuetext={`${timeLabel}, ${formatHourOffset(hour)}`}
        onChange={(event) => {
          setPlaying(false)
          onHour(Number(event.target.value))
        }}
      />
      <div className="scrubber__ticks mono" aria-hidden="true">
        {tickHours.map((tick) => (
          <span key={tick} style={{ left: `${(tick / lastHour) * 100}%` }}>
            {tick === 0 ? 'Dep.' : `+${tick} h`}
          </span>
        ))}
      </div>

      <ul className="scrubber__legend" aria-label="Corridor cells by risk level at this hour">
        {[...LEVELS, UNKNOWN_LEVEL].map((level) => {
          const key = level.value < 0 ? 'unknown' : (level.value as 0 | 1 | 2 | 3 | 4)
          const count = counts ? counts[key] : 0
          if (level.value < 0 && count === 0) return null
          return (
            <li key={level.label} className="scrubber__legend-item" data-empty={count === 0}>
              <span className="scrubber__swatch" style={{ background: level.color }} aria-hidden="true" />
              <span>{level.label}</span>
              <span className="mono scrubber__count">{count}</span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
