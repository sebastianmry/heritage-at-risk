# HERITAGE AT RISK
### Threat mapping of UNESCO World Heritage and archaeological sites in the MENA region

© Sebastian Macherey, [github.com/sebastianmry/heritage-at-risk](https://github.com/sebastianmry/heritage-at-risk)

**Academic project for the module *Geodatenhaltung und -vernetzung* (M.Sc. Geoinformation, BHT Berlin).**

---

## Motivation

Cultural heritage in the Middle East and North Africa is exposed to two forces at
once: armed conflict and political instability on one side, natural hazards such
as earthquakes and floods on the other. The losses of Palmyra, Aleppo and Mosul
showed how quickly irreplaceable sites can be damaged, while the ground reporting
that would let anyone gauge the risk is scarce and slow. The practical way to keep
an overview is to combine open, public data sources into a single, comparable
signal per site.

Heritage at Risk is a mobile, location-based Android app (Flutter) that maps 100
UNESCO World Heritage Sites and archaeological sites across the MENA region:
Syria, Lebanon, Israel, Palestine, Iraq, Iran, Yemen, Jordan, Egypt, Saudi
Arabia, the UAE, Oman, Qatar, Bahrain and Kuwait. Each site carries a spatially
computed threat score from 0 to 10. Stable countries appear with many
low-scoring sites by design: the contrast lives at the site level, so the map
shows both the density and the threat of the region's heritage.

## Threat score

Four independent, public sources form the score (max 10). Three make up the human
threat axis, the fourth the natural hazard. The weights live centrally in
`config.py`.

| Component | Source | Weight |
|---|---|---|
| In-danger flag | UNESCO World Heritage Centre | 3 |
| Travel advisory level (0 to 2) | German Federal Foreign Office | 3 |
| Conflict events within 30 km (log-scaled) | ACLED (DuckDB `ST_Distance`) | 3 |
| Natural hazard (earthquake + river flood) | ThinkHazard! (World Bank GFDRR) | 1 |

The threat is never encoded by colour alone. The app and the artefacts always
carry the level and label as well (accessibility). Only conflict events within
the 30 km evaluation radius of a site are counted and shown, so the events layer
matches exactly what the score counts.

## Data sources

- **UNESCO World Heritage Centre:** site list and the official *In Danger* flag.
- **German Federal Foreign Office:** travel advisory level (0 to 2) per country.
- **ACLED (Armed Conflict Location & Event Data):** geocoded conflict events,
  counted within 30 km. Includes non-lethal strikes (intercepted drones and
  missiles, shelling, explosions without fatalities). Used under an academic
  *Research*-tier licence over a rolling 36-to-12-month window (event-level data
  is released only after a 12-month embargo at this tier).
- **ThinkHazard! / World Bank GFDRR:** earthquake and river-flood hazard per site.
- **Pleiades:** ancient places as historical context.
- **OpenStreetMap:** building footprints for the density heatmap.

ACLED's *Research* licence permits academic use only and forbids public
redistribution, so this repository is **private** and used solely for the course
submission. Raw ACLED events are git-ignored and never committed; only the derived
threat score is used. All other sources are openly licensed.

## Pipeline

Four separate stages, each with a defined input and output. Precompute instead
of computing live.

1. **Ingest** per source (`ingest_*.py`), shared logic in `ingest_common.py`.
2. **Processing** in DuckDB (`process.py`): spatial join and score.
3. **Export** to GeoJSON and PMTiles (`export.py`) as committed artefacts in `artifacts/`.
4. **App** (Flutter, `app/`) reads only the finished artefacts.

Raw data lives outside the repository under `DATA_DIR` (default
`../heritage_data`). Only derived artefacts and curated reference lists are
committed. See `PROJECT_CONTEXT.md` (in German) for the detailed, dated project
log and methodology.

A GitHub Actions workflow (`.github/workflows/daily-update.yml`) refreshes the
time-critical sources daily (travel advisories and ACLED, plus the small UNESCO
inventory), recomputes the score and commits only the aggregated artefacts; raw
ACLED events never leave the ephemeral runner. The heavy OSM and Pleiades
context layers stay static and are rebuilt manually.

## App

The app (`app/`) renders the threat map with MapLibre Native over a monochrome
CARTO basemap. Layers (top to bottom): the scored sites as an inverted
traffic-light ramp (high = red), 3D site markers and Pleiades ancient places as
context, a warm building-density heatmap, and the basemap building footprints
tinted warm at high zoom. Sites and Pleiades places are tappable for a detail
sheet; the legend filters threat classes and toggles the context layers, and a
country-filtered list view ranks the sites by score and jumps back to the map.
Foreground geolocation centres the map on the user and reports the nearest site.
From there or from any site's detail sheet, **Route here** requests a live route
(drive or walk) from the user's position to the site via the OpenRouteService
directions API and draws it on the map with distance and duration. A light/dark
switch drives both the UI theme and the basemap.

| Building block | Choice |
|---|---|
| Framework | Flutter (stable) + Dart 3 |
| Map engine | MapLibre Native (`maplibre_gl`) |
| Location | `geolocator` (foreground) |
| Routing | OpenRouteService directions API (key injected at build time, never in code) |
| State | Riverpod |

## Build

The app builds with the Android toolchain (Flutter 3.44, JDK 21, Android SDK 36);
`maplibre_gl` requires Java 21 source compatibility.

```sh
cd app
flutter pub get
flutter build apk --debug --dart-define=ORS_API_KEY=<your key>
```

The OpenRouteService key comes from [openrouteservice.org/sign-up](https://openrouteservice.org/sign-up)
(free tier) and is injected at build time via `--dart-define`; it is never part
of the source or the repository. Without a key the app still builds and runs,
only the routing action explains how to enable it. On Windows,
`build_app.bat` in the repository root reads `OPENROUTESERVICE_API_KEY` from
`.env` and passes it automatically.

## Tech Stack

Python 3.11, DuckDB (spatial), GeoPandas, Shapely, pyproj, QuackOSM, pandas,
PyArrow, Requests, lxml, pmtiles, Pillow; Flutter, Dart 3, MapLibre Native
(maplibre_gl), Riverpod, geolocator, url_launcher; CARTO basemap, PMTiles
(Protomaps).

## License

MIT License
