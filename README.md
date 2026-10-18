# Weather-Aware Truck Routing

React + Django app that helps a truck driver pick the safest of three routes based on
weather risk, load weight and travel time.

> Work in progress. Full architecture, risk rules, assumptions and scaling notes are
> added as the phases land.

## Layout

```
backend/    Django + DRF API; pure analysis engine in backend/engine
frontend/   Vite + React + TypeScript + MapLibre GL
```

## Local setup

```bash
cp .env.example .env            # add ORS_API_KEY

# backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # source .venv/bin/activate on macOS/Linux
pip install -r requirements-dev.txt
pytest
python manage.py runserver

# frontend (second terminal)
cd frontend
npm install
npm run dev
```

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/analyze` | Find up to 3 routes, score weather risk at each ETA, recommend one |
| `GET` | `/api/geocode?q=` | Place suggestions for the origin and destination inputs |
| `GET` | `/api/health` | Liveness probe |

`POST /api/analyze` body:

```json
{
  "origin": {"lat": 39.7392, "lon": -104.9847, "label": "Denver, CO"},
  "destination": "Chicago, IL",
  "departure": "2026-11-02T08:00",
  "load_lb": 42000,
  "interval_miles": 25
}
```

- Places are either `{lat, lon}` or text that is geocoded server-side.
- `departure` without an offset is read in the **origin's local time zone**; with an offset (or `Z`) it is used as given.
- `interval_miles` is 10, 25 or 50. `load_lb` is 0 to 100,000.
- Errors use one envelope: `{"error": {"code", "message", "fields"?}}` (`validation_error`, `invalid_trip`, `provider_error`).

## Risk rules and assumptions

Each checkpoint takes the worst level of wind, rain and snow, then the load rules can only raise it.

- A band's lower bound is inclusive (wind 25 mph is Moderate). Where the brief says "greater than", it is strict (rain 1.00 in/hr is Severe, 1.001 is No Travel).
- Load rules use strict `>` (exactly 30,000 lb does not escalate wind 45-54 mph).
- Each checkpoint stands for the route miles out to the midpoints with its neighbours, so Severe/High miles do not depend on the sampling interval.
- Weather is the forecast hour nearest the truck's ETA at that checkpoint. Wind is sustained 10 m wind. Open-Meteo reports rain and snow as the total for the hour *ending* at each timestamp, so the adapter shifts them to describe the hour starting there.
- Forecast requests are clamped to the 15-day forecast window; checkpoints whose ETA falls beyond it are reported as unknown and not scored.
- Weather is fetched per 0.1 degree cell (about 7 miles), so a checkpoint can be up to about 3.5 miles from the forecast point.
- Ranking is strictly lexicographic: No Travel miles, Severe miles, High miles, average risk, then travel time. Miles are compared at 0.1 mi resolution.
- ETAs assume the routing provider's driving time and ignore driver breaks.

## Route alternatives

OpenRouteService caps its own alternative-routes feature at 100 km, so it cannot offer alternatives for long truck routes. Instead the app routes through points offset to the left and right of the main `driving-hgv` route, discards results that overlap the main route or are far longer, and keeps up to three distinct routes.

## Operations notes

- Set `DJANGO_ENV=production`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` and `ORS_API_KEY` in production. A `RENDER=true` environment is treated as production even if `DJANGO_ENV` is missing.
- Rate limits (`/api/analyze` 10/min, `/api/geocode` 60/min per client) are counted in process memory, so run **one** gunicorn worker with threads. `DJANGO_NUM_PROXIES` is the number of trusted proxy hops (default 1 in production, 0 locally); it stops clients spoofing `X-Forwarded-For`.
- Trips longer than 3,500 miles are rejected before any weather is fetched. Place text and search queries are capped at 200 characters.
- Routes are cached for an hour, forecasts for 15 minutes, geocodes for a day, so repeated requests do not spend free-tier quota.
