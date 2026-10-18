import { useEffect, useId, useRef, useState } from 'react'
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

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'done'; places: Place[] }
  | { status: 'failed' }

/** Text input with place suggestions, following the ARIA combobox pattern. */
export function PlaceField({ label, text, place, error, onChange }: PlaceFieldProps) {
  const id = useId()
  const listId = `${id}-list`
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [search, setSearch] = useState<SearchState>({ status: 'idle' })
  const debounced = useDebouncedValue(text.trim(), DEBOUNCE_MS)
  const skipNextSearch = useRef(false)

  useEffect(() => {
    if (place || debounced.length < MIN_QUERY || skipNextSearch.current) {
      skipNextSearch.current = false
      return
    }
    const controller = new AbortController()
    setSearch({ status: 'loading' })
    searchPlaces(debounced, controller.signal)
      .then((places) => {
        setSearch({ status: 'done', places })
        setActive(places.length > 0 ? 0 : -1)
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        setSearch({ status: 'failed' })
      })
    return () => controller.abort()
  }, [debounced, place])

  const places = search.status === 'done' ? search.places : []
  const showList = open && !place && text.trim().length >= MIN_QUERY && search.status !== 'idle'

  function choose(choice: Place) {
    skipNextSearch.current = true
    onChange(choice.label, choice)
    setOpen(false)
    setSearch({ status: 'idle' })
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!showList) {
      if (event.key === 'ArrowDown' && places.length > 0) setOpen(true)
      return
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((index) => (places.length === 0 ? -1 : (index + 1) % places.length))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((index) => (places.length === 0 ? -1 : (index - 1 + places.length) % places.length))
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
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? `${id}-option-${active}` : undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          value={text}
          onChange={(event) => {
            onChange(event.target.value, null)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
        />
        {place && (
          <CheckCircle
            className="place-field__check"
            size={18}
            weight="fill"
            aria-label="Location confirmed"
          />
        )}
        {showList && (
          <ul className="place-field__list" id={listId} role="listbox" aria-label={`${label} suggestions`}>
            {search.status === 'loading' && <li className="place-field__note">Searching</li>}
            {search.status === 'failed' && (
              <li className="place-field__note">
                Search is unavailable. You can still type a city and state.
              </li>
            )}
            {search.status === 'done' && places.length === 0 && (
              <li className="place-field__note">No matches. Try adding the state.</li>
            )}
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
      </div>
      {error && (
        <p className="field__error" id={`${id}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
