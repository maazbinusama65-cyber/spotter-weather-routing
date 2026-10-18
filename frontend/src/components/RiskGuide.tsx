import { LEVELS } from '../lib/risk'
import './RiskGuide.css'

const ROWS: readonly [string, string, string][] = [
  ['Under 25', 'Under 0.10', 'Under 0.5'],
  ['25 to 34', '0.10 to 0.25', '0.5 to 1.0'],
  ['35 to 44', '0.25 to 0.50', '1.0 to 2.0'],
  ['45 to 54', '0.50 to 1.00', '2.0 to 3.0'],
  ['55 or more', 'Over 1.00', 'Over 3.0'],
]

export function RiskGuide() {
  return (
    <details className="guide">
      <summary className="guide__summary">How risk is scored</summary>
      <div className="guide__body">
        <p>
          Each checkpoint takes the worst of wind, rain and snow, using the forecast for the hour the
          truck arrives there. Load weight can raise wind risk.
        </p>
        <table className="guide__table mono">
          <thead>
            <tr>
              <th scope="col">Level</th>
              <th scope="col">Wind mph</th>
              <th scope="col">Rain in/hr</th>
              <th scope="col">Snow in/hr</th>
            </tr>
          </thead>
          <tbody>
            {LEVELS.map((level, index) => (
              <tr key={level.value}>
                <th scope="row">
                  <span className="guide__swatch" style={{ background: level.color }} aria-hidden="true" />
                  {level.label}
                </th>
                {ROWS[index].map((cell) => (
                  <td key={cell}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="guide__rules">
          <li>Wind of 45 to 54 mph is No Travel when the load is over 30,000 lb.</li>
          <li>Wind of 35 to 44 mph is Severe when the load is over 40,000 lb.</li>
          <li>
            Routes are ranked by fewest Severe miles, then High miles, then average risk, then
            travel time.
          </li>
        </ul>
      </div>
    </details>
  )
}
