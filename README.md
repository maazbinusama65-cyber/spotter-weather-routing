# Stormline: weather-aware truck routing

A React + Django app that helps a truck driver pick the safest of three routes. Enter a start, a
destination, a departure time and a load weight. The app finds up to three truck routes, checks the
forecast at each checkpoint for the hour the truck will actually be there, scores the risk with the
brief's thresholds and load rules, and recommends one route. A map shows every route, checkpoint,
ETA and risk level, plus a 0 to 48 hour weather heatmap along the trip corridor.

Hosted app: _add the Render URL here after the first deploy (see [Deploy](#deploy))._

## How the brief maps to the code

| Requirement | Where |
| --- | --- |
| 3 route options from a routing API | `backend/api/providers/ors.py`, `backend/engine/candidates.py` |
| Weather every 10 / 25 / 50 miles at the truck's ETA | `backend/engine/sampling.py`, `backend/engine/forecast.py` |
| Risk thresholds and load rules | `backend/engine/thresholds.py`, `backend/engine/risk.py` |
| Recommendation order (Severe, High, average risk, time) | `backend/engine/ranking.py` |
| Routes, checkpoints, risk, ETAs, summaries on a map | `frontend/src/components/MapView.tsx`, `RouteList.tsx` |
| Heatmap with a 0 to 48 hour slider | `backend/engine/corridor.py`, `heat.py`, `frontend/.../TimeScrubber.tsx` |

## How it works

```
 browser (React, MapLibre)
    |  POST /api/analyze        POST /api/heatmap        GET /api/geocode
    v
 Django + DRF  (stateless, one gunicorn worker with threads)
    |-- api/services/trip.py      orchestrates one analysis
    |-- api/services/heatmap.py   corridor grid with 49 hours of risk
    |-- api/providers/            OpenRouteService, Open-Meteo, cached wrappers
    '-- engine/                   pure functions, no I/O, no Django (98% covered)
```

1. **Routes.** OpenRouteService `driving-hgv` gives the main route. Its own alternatives feature is
   capped at 100 km, which is useless for long hauls, so the app also routes through points offset to
   the left and right of the main route, drops results that overlap it or are far longer, and keeps
   the three most different.
2. **Checkpoints.** The polyline is sampled at the chosen interval. Each checkpoint owns the route miles
   out to the midpoints with its neighbours, so Severe and High miles do not depend on the interval.
3. **ETAs.** Each checkpoint's arrival time comes from the provider's per-step durations. The forecast
   hour nearest that time is used, not the departure hour.
4. **Risk.** Worst of wind, rain and snow, then the load rules can only raise the level.
5. **Recommendation.** Strictly lexicographic: No Travel miles, Severe miles, High miles, average risk,
   then travel time. The response explains which of these decided it.
6. **Heatmap.** Weather cells (0.1 degree) along all candidate routes, up to 150, each with a 49
   character string of risk levels. The slider only changes which character is read, so scrubbing never
   waits on the network.

## Risk rules and assumptions

- A band's lower bound is inclusive (wind 25 mph is Moderate). Where the brief says "greater than", it
  is strict (rain 1.00 in/hr is Severe, 1.001 is No Travel).
- Load rules use strict `>`: exactly 30,000 lb does not escalate wind of 45 to 54 mph.
- Weather is the forecast hour nearest the ETA. Wind is sustained 10 m wind. Open-Meteo reports rain
  and snow as the total for the hour _ending_ at each timestamp, so the adapter shifts them to describe
  the hour starting there.
- Forecast requests are clamped to the 15-day window. Checkpoints beyond it are reported as unknown
  and are not scored; the UI says so instead of calling them clear.
- Weather is fetched per 0.1 degree cell (about 7 miles), so a checkpoint can be about 3.5 miles from
  its forecast point.
- ETAs use the routing provider's driving time and ignore driver breaks and traffic.
- A departure without a UTC offset is read in the time zone of the starting point.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/analyze` | Find up to 3 routes, score risk at each ETA, recommend one |
| `POST` | `/api/heatmap` | Corridor weather grid with a 0 to 48 hour risk series per point |
| `GET` | `/api/geocode?q=` | Place suggestions |
| `GET` | `/api/health` | Liveness probe |

```json
{
  "origin": {"lat": 39.7392, "lon": -104.9847, "label": "Denver, CO"},
  "destination": "Chicago, IL",
  "departure": "2026-11-02T08:00",
  "load_lb": 42000,
  "interval_miles": 25
}
```

- Places are `{lat, lon}` or text that is geocoded server-side. `interval_miles` is 10, 25 or 50.
  `load_lb` is 0 to 100,000.
- `/api/heatmap` takes the same body without `interval_miles`. Its points look like
  `{"lat": 39.7, "lon": -105.0, "levels": "000012..."}`: one character per forecast hour from the
  departure hour, the risk level `0` to `4`, or `-` where the forecast does not reach.
- Errors share one envelope: `{"error": {"code", "message", "fields"?}}` with codes
  `validation_error`, `invalid_trip`, `no_route` and `provider_error`.

## Run it locally

You need Python 3.13, Node 22 and a free [OpenRouteService key](https://openrouteservice.org/dev/#/signup).
Weather needs no key.

```bash
cp .env.example .env                 # then set ORS_API_KEY

cd backend
python -m venv .venv
.venv/Scripts/activate               # source .venv/bin/activate on macOS and Linux
pip install -r requirements-dev.txt
python manage.py runserver           # http://127.0.0.1:8000

cd ../frontend                       # second terminal
npm install
npm run dev                          # http://localhost:5173, proxies /api to Django
```

## Tests and quality

```bash
cd backend  && pytest --cov=engine --cov=api && ruff check .
cd frontend && npm test && npm run lint && npm run build
```

- 414 backend tests, about 98% coverage of `engine` and `api`: every threshold boundary, the load-rule
  matrix, each ranking tiebreaker, ETA handling, provider adapters against recorded real responses, and
  the HTTP layer.
- 90 frontend tests: the API client, place search, the form, the popup, and the whole app flow
  including the forecast slider.
- CI runs both suites, `pip-audit`, the production build, and builds the Docker image and smoke-tests
  the running container.
- Tests never call live APIs. `backend/fixtures` holds real OpenRouteService and Open-Meteo responses.

## Deploy

One Docker image serves the API and the built React app, so there is a single URL and no CORS.

1. Push the repo to GitHub and create a Render **Blueprint** from it (`render.yaml`).
2. In the Render dashboard set `ORS_API_KEY`. `DJANGO_SECRET_KEY` is generated for you.
3. Open the service URL and add it to the top of this README.

Notes for the free plan: the service sleeps when idle and takes up to a minute to wake, so open it
once before a demo. `GET /api/health` is a cheap wake-up and uptime-monitor target.

Production behaviour: `DJANGO_ENV=production` (or `RENDER=true`) turns off debug, requires a secret
key, enables HTTPS redirect and HSTS, and sends a Content Security Policy that allows only the app's
own scripts and the map tile host.

## Scaling notes

The design is stateless and the engine is pure, so it scales by running more of the same. Today it is
tuned for one small instance, on purpose:

- **Upstream quotas are the real limit, not CPU.** OpenRouteService's free tier allows about 2,000
  route requests a day and 40 a minute; one analysis uses about five. Routes are cached for an hour,
  forecasts for 15 minutes and geocodes for a day, and weather is requested per grid cell, batched and
  deduplicated.
- **Rate limits and caches live in process memory**, so the image runs one gunicorn worker with eight
  threads. To go beyond one instance: put the cache and throttle counters in Redis (a settings change
  for both), then raise the worker count.
- **Analysis is synchronous** because it finishes in a few seconds. If trips or traffic grew, wrap
  `analyze_trip` in a job and return an id, or add a second routing provider.
- The heatmap payload is bounded (at most 150 cells by 49 hours), so it stays small whatever the trip
  length.

## Limitations and future work

- Real weather is often calm, so many results read Low. The heatmap colours were checked against a
  synthetic storm band in the browser rather than a real storm.
- The 100 km alternatives cap is worked around with offset waypoints; the alternatives are plausible
  but not guaranteed to be the routes a local dispatcher would choose.
- ETAs ignore breaks, traffic and hours-of-service limits.
- Light theme only.
- Unknown-forecast miles are shown and warned about but are not part of the ranking key.

## Project layout

```
backend/
  engine/      pure analysis: thresholds, risk, sampling, forecast lookup, ranking, corridor
  api/         HTTP layer, orchestration (services), provider adapters and caches
  tests/       unit, integration and API tests
  fixtures/    recorded provider responses
frontend/src/
  components/  form, route cards, map, forecast slider, popup
  lib/         typed API client and pure helpers
  hooks/       trip state
Dockerfile, render.yaml, .github/workflows/ci.yml
```
