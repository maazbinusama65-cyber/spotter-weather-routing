# Fixtures

Recorded or hand-built provider responses used by tests so the suite never calls a live API.

| File | Source |
| --- | --- |
| `open_meteo_two_locations.json` | Real Open-Meteo response (2 locations, first 8 hours), trimmed |
| `ors_directions_live.json` | Real OpenRouteService `driving-hgv` GeoJSON response (Denver to Fort Collins, 563 vertices, 16 steps) |
| `ors_directions.json` | Small hand-built response in the same shape, for readable unit-test arithmetic |
