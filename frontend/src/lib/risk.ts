/** The five risk levels, from the API's risk_levels, with the colours the whole UI shares. */

export interface LevelStyle {
  value: number
  label: string
  /** Fill colour for markers, bars and the heatmap. */
  color: string
  /** Text colour that stays readable on `color` (WCAG AA for normal text). */
  ink: string
}

export const LEVELS: readonly LevelStyle[] = [
  { value: 0, label: 'Low', color: '#2f9e6e', ink: '#ffffff' },
  { value: 1, label: 'Moderate', color: '#e8b923', ink: '#1b1f27' },
  { value: 2, label: 'High', color: '#ee7b1d', ink: '#1b1f27' },
  { value: 3, label: 'Severe', color: '#d62839', ink: '#ffffff' },
  { value: 4, label: 'No Travel', color: '#3d1856', ink: '#ffffff' },
]

export const UNKNOWN_LEVEL: LevelStyle = {
  value: -1,
  label: 'Unknown',
  color: '#8b95a5',
  ink: '#ffffff',
}

export function levelInfo(level: number | null | undefined): LevelStyle {
  if (level === null || level === undefined) return UNKNOWN_LEVEL
  return LEVELS[level] ?? UNKNOWN_LEVEL
}

/** One character of a heatmap `levels` string: "0" to "4", or "-" for unknown. */
export function levelFromChar(char: string | undefined): number | null {
  if (char === undefined || char < '0' || char > '4' || char.length !== 1) return null
  return Number(char)
}
