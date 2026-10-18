import { useEffect, useId, useState } from 'react'
import { CheckCircle, MapPin } from '@phosphor-icons/react'
import { searchPlaces } from '../lib/api'
import type { Place } from '../lib/types'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import './PlaceField.css'

const MIN_QUERY = 3
const DEBOUNCE_MS = 300

interface PlaceFieldProps {
  label: string
  text: string
  place: Place | null
  error?: string
  onChange: (text: string, place: Place | null) => void
}

/** Each state remembers the query it answers, so results for old text are never shown. */
type SearchState =
  | { status: 'idle' }
  | { status: 'done'; query: string; places: Place[] }
  | { status: 'failed'; query: string }

/** Text input with place suggestions, following the ARIA combobox pattern. */
export function PlaceField({ label, text, place, error, onChange }: PlaceFieldProps) {
  const id = useId()
  const listId = `${id}-list`
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [search, setSearch] = useState<SearchState>({ status: 'idle' })
  const debounced = useDebouncedValue(text.trim(), DEBOUNCE_MS)
  const query = text.trim()

  useEffect(() => {
    // Wait until typing has paused: `debounced` lags `query` while the user is still typing.
    if (place || query.length < MIN_QUERY || debounced !== query) return
    const controller = new AbortController()
    searchPlaces(query, controller.signal)
      .then((places) => {
        setSearch({ status: 'done', query, places })
        setActive(places.length > 0 ? 0 : -1)
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        setSearch({ status: 'failed', query })
      })
    return () => controller.abort()
  }, [debounced, query, place])

  const current = search.status !== 'idle' && search.query === query ? search : null
  const places = current?.status === 'done' ? current.places : []
  const showPanel = open && !place && query.length >= MIN_QUERY
  const showList = showPanel && places.length > 0
  const note =
    current?.status === 'failed'
      ? 'Search is unavailable. You can still type a city and state.'
      : current?.status === 'done' && places.length === 0
        ? 'No matches. Try adding the state.'
        : 'Searching' // no answer yet for what is typed now
  const announcement = showList ? `${places.length} suggestions available` : showPanel ? note : ''

  useEffect(() => {
    if (showList && active >= 0) {
      document.getElementById(`${id}-option-${active}`)?.scrollIntoView({ block: 'nearest' })
    }
  }, [showList, active, id])

  function choose(choice: Place) {
    onChange(choice.label, choice)
    setOpen(false)
    setSearch({ status: 'idle' })
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!showList) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((index) => (index + 1) % places.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((index) => (index - 1 + places.length) % places.length)
    } else if (event.key === 'Enter' && active >= 0 && places[active]) {
      event.preventDefault()
      choose(places[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="field place-field">
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      <div className="place-field__control">
        <MapPin className="place-field__icon" size={18} weight="regular" aria-hidden="true" />
        <input
          id={id}
          className="input place-field__input"
          type="text"
          role="combobox"
          autoComplete="off"
          spellCheck={false}
          aria-expanded={showList}
          aria-controls={showList ? listId : undefined}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? `${id}-option-${active}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          value={text}
          onChange={(event) => {
            setActive(-1)
            onChange(event.target.value, null)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {place && (
          <span className="place-field__check" role="img" aria-label="Location confirmed">
            <CheckCircle size={18} weight="fill" aria-hidden="true" />
          </span>
        )}
        {showList && (
          <ul className="place-field__list" id={listId} role="listbox" aria-label={`${label} suggestions`}>
            {places.map((option, index) => (
              <li
                key={`${option.label}-${option.lat}-${option.lon}`}
                id={`${id}-option-${index}`}
                role="option"
                aria-selected={index === active}
                className="place-field__option"
                onMouseDown={(event) => {
                  event.preventDefault()
                  choose(option)
                }}
                onMouseEnter={() => setActive(index)}
              >
                {option.label}
              </li>
            ))}
          </ul>
        )}
        {showPanel && !showList && <div className="place-field__list place-field__note">{note}</div>}
        <span className="visually-hidden" role="status">
          {announcement}
        </span>
      </div>
      {error && (
        <p className="field__error" id={`${id}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
