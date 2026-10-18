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
pip install -r requirements.txt
pytest
python manage.py runserver

# frontend (second terminal)
cd frontend
npm install
npm run dev
```
