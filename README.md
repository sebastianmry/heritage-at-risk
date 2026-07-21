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
UNESCO World Heritage Sites and archaeological sites across the MENA region.
Each site carries a spatially computed threat score from 0 to 10. Stable
countries appear with many low-scoring sites by design: the contrast lives at
the site level, so the map shows both the density and the threat of the
region's heritage.

## Study countries

15 countries across the MENA region and the Gulf: Syria, Lebanon, Israel,
Palestine, Iraq, Iran, Yemen, Jordan, Egypt, Saudi Arabia, the United Arab
Emirates, Oman, Qatar, Bahrain and Kuwait (Kuwait has no UNESCO World Heritage
Site of its own but is kept for regional coverage). The selection deliberately
covers both a crisis core (Syria, Iraq, Yemen, Lebanon, Palestine) and stable
neighbours (the Gulf states, Jordan), so the map reads as density *and*
threat, not threat alone.

## Threat score

Four independent, public sources form the score (max 10). Three make up the human
threat axis, the fourth the natural hazard. The weights live centrally in
`config.py`.

| Component | Source | Weight |
|---|---|---|
| In-danger flag | UNESCO World Heritage Centre | 3 |
| Travel advisory level (0 to 2) | German Federal Foreign Office | 3 |
| Conflict events within 30 km (log-scaled) | UCDP GED (DuckDB `ST_Distance`) | 3 |
| Natural hazard (earthquake + river flood) | ThinkHazard! (World Bank GFDRR) | 1 |

The threat is never encoded by colour alone. The app and the artefacts always
carry the level and label as well (accessibility). Only conflict events within
the 30 km evaluation radius of a site are counted and shown, so the events layer
matches exactly what the score counts.

## Data sources

- **UNESCO World Heritage Centre:** site list and the official *In Danger* flag.
- **German Federal Foreign Office:** travel advisory level (0 to 2) per country.
- **UCDP GED (Uppsala Conflict Data Program):** geocoded conflict events,
  counted within 30 km over a rolling 12-month window. The yearly GED release
  plus the monthly candidate dataset keep the data 4 to 6 weeks behind real
  time, so the score reflects the current situation. Openly licensed (CC BY
  4.0), peer-reviewed and citable.
- **ThinkHazard! / World Bank GFDRR:** earthquake and river-flood hazard per site.
- **Pleiades:** ancient places as historical context.
- **OpenStreetMap:** building footprints for the density heatmap.

All sources are openly licensed and redistributable. (An ACLED *Research*-tier
integration was evaluated in June 2026 and deliberately rolled back: its
12-month embargo on event-level data would have made the "current threat"
claim stale, and its licence would have forced the repository private. The
comparison is documented in `PROJECT_CONTEXT.md`.)

## Pipeline

Four separate stages, each with a defined input and output. Precompute instead
of computing live.

1. **Ingest** per source (`ingest_*.py`), shared logic in `ingest_common.py`.
2. **Processing** in DuckDB (`process.py`): spatial join and score.
3. **Export** to GeoJSON (`export.py`, `export_events.py`, `export_radius.py`, `export_3d.py`) as committed artefacts in `artifacts/`.
4. **App** (Flutter, `app/`) reads only the finished artefacts.

Raw data lives outside the repository under `DATA_DIR` (default
`../heritage_data`). Only derived artefacts and curated reference lists are
committed. See `PROJECT_CONTEXT.md` (in German) for the detailed, dated project
log and methodology.

A GitHub Actions workflow (`.github/workflows/daily-update.yml`) refreshes the
time-critical sources daily (travel advisories and UCDP conflict events, plus
the small UNESCO inventory), recomputes the score and commits only the derived
artefacts, including the app's bundled `app/assets/data/*.geojson`. No secrets
are required; all sources are token-free. The heavy OSM and Pleiades context
layers stay static and are rebuilt manually.

## Data quality and caveats

- **The app does not pull data at runtime.** The GeoJSON artefacts are bundled
  as Flutter assets and compiled into the APK at build time. The workflow
  above keeps the *repository* current, but an already-built or downloaded APK
  only reflects the data as of its own build; it does not update itself. A
  fresh build is needed to pick up newer data.
- **UCDP GED only records events with at least one fatality.** Non-lethal
  incidents (intercepted drones, shelling without deaths) are not counted, so
  the conflict component is a lower bound on nearby violence, not a complete
  incident log.
- **The threat score is UNESCO-World-Heritage-Site-only by design.** Mosul's
  Old City (al-Nuri Mosque), Nimrud and Nineveh suffered severe destruction by
  the so-called Islamic State but are not inscribed World Heritage Sites (only
  on the Tentative List), so they carry no threat score; they still appear as
  unscored context in the 3D-model layer, badged accordingly.
- **The UNESCO danger-list flag comes from a curated, dated CSV, not the WHC
  API.** The `danger` field in the official WHC XML export is demonstrably
  incomplete (it lists only 1 of Syria's 6 officially endangered sites), so
  the authoritative in-danger flag is scraped once a year from the rendered
  danger list page instead and kept in `reference/`.
- **ThinkHazard! hazard levels are administrative-division granularity, not
  point estimates.** Each site is reverse-geocoded to its province/district
  and matched to that division's hazard report; there is no finer point
  lookup. The flood component in particular models river flooding, not flash
  floods, so it rates Yemen's mud-brick sites (Shibam, Zabid) lower than their
  real flood exposure.
- **Old City of Jerusalem is assigned to Israel for grouping purposes only.**
  The WHC lists the site without a country code ("proposed by Jordan"); the
  project resolves it via the region bounding box for its travel-advisory
  join. This is a project-internal grouping decision, not a position on
  status.

## App

The app (`app/`) renders the threat map with MapLibre Native over a MapTiler
`dataviz` basemap (light/dark variant), falling back to keyless CARTO
Positron/Dark Matter without a MapTiler key. A segmented switch flips between
two views on the same map: **Threat** (the scored sites as an inverted
traffic-light ramp, high = red, plus 3D site markers, Pleiades ancient places
and a warm heritage/old-town density heatmap as context) and **Conflict**
(UCDP GED events, coloured by year, plus each site's 30 km evaluation
radius). Sites, Pleiades places, 3D markers and conflict events are all
tappable for a detail sheet; the legend filters threat classes and toggles
context layers, and a country-filtered list view ranks the sites by score and
jumps back to the map. On open, the camera fits the full extent of all sites
with a slim margin, so the map starts zoomed to the whole region instead of a
fixed default. Foreground geolocation centres the map on the user and reports
the nearest site. From there or from any site's, Pleiades' or 3D model's
detail sheet, **Route here** requests a live route (drive or walk) via the
OpenRouteService directions API and draws it on the map with distance and
duration. A single light/dark switch drives the basemap tiles and the whole
app's chrome together (cards, legend, sheets, dialogs).

| Building block | Choice |
|---|---|
| Framework | Flutter (stable) + Dart 3 |
| Map engine | MapLibre Native (`maplibre_gl`) |
| Location | `geolocator` (foreground) |
| Routing | OpenRouteService directions API (key injected at build time, never in code) |
| State | Riverpod |

Screenshots: `mockups/` (map prototype) and the submission PDF; see `DEMO.md`
for a click-through of the threat view, site detail, conflict view with event
tap, the light/dark switch and routing.

## Build

The app builds with the Android toolchain (Flutter 3.44, JDK 21, Android SDK 36);
`maplibre_gl` requires Java 21 source compatibility.

```sh
cd app
flutter pub get
flutter build apk --debug --dart-define=ORS_API_KEY=<your key> --dart-define=MAPTILER_KEY=<your key>
```

The OpenRouteService and MapTiler keys are injected at build time via
`--dart-define`; they are never part of the source or the repository. Without
either key the app still builds and runs: routing explains how to enable it,
and the basemap falls back to keyless CARTO Positron/Dark Matter. On Windows,
`build_app.bat` in the repository root reads `OPENROUTESERVICE_API_KEY` and
`MAPTILER_API_KEY` from `.env` and passes both automatically. A ready-to-run
APK is attached to the repository's [Releases](https://github.com/sebastianmry/heritage-at-risk/releases)
if you just want to install it.

## Tech Stack

Python 3.11, DuckDB (spatial), GeoPandas, Shapely, pyproj, QuackOSM, pandas,
PyArrow, Requests, lxml, Pillow; Flutter, Dart 3, MapLibre Native
(maplibre_gl), Riverpod, geolocator, url_launcher; MapTiler `dataviz`
basemap with a keyless CARTO Positron/Dark Matter fallback.

## References

- Pleiades. (n.d.). *Pleiades: A gazetteer of past places.* Institute for the
  Study of the Ancient World, New York University. https://pleiades.stoa.org
- Sundberg, R., & Melander, E. (2013). Introducing the UCDP Georeferenced
  Event Dataset. *Journal of Peace Research, 50*(4), 523-532.
  https://doi.org/10.1177/0022343313484347
- ThinkHazard! (n.d.). *ThinkHazard! country and hazard risk profiles.* World
  Bank Global Facility for Disaster Reduction and Recovery (GFDRR).
  https://thinkhazard.org
- UNESCO World Heritage Centre. (n.d.). *World Heritage List.* United Nations
  Educational, Scientific and Cultural Organization. https://whc.unesco.org
- OpenStreetMap contributors. (n.d.). *OpenStreetMap.*
  https://www.openstreetmap.org

## Data licences and attribution

| Source | Licence |
|---|---|
| UNESCO World Heritage Centre | Public, cited per WHC terms of use |
| German Federal Foreign Office (travel advisories) | Public OpenData |
| UCDP GED (Uppsala Conflict Data Program) | CC BY 4.0 |
| ThinkHazard! (World Bank GFDRR) | CC BY 4.0 |
| Pleiades | CC BY 3.0 |
| OpenStreetMap (building density) | ODbL |
| MapTiler basemap | © MapTiler © OpenStreetMap contributors, shown via the in-app attribution control |
| CARTO basemap (fallback) | © CARTO © OpenStreetMap contributors, shown via the in-app attribution control |
| OpenRouteService (routing) | © openrouteservice.org / HeiGIT, attribution shown in the route panel |

## License

MIT License (code). Bundled third-party data keeps its own licence, listed
above; the source citation for each lives in the metadata block of its
GeoJSON artefact.

## About

Academic project by Sebastian Macherey for the module *Geodatenhaltung und
-vernetzung* (M.Sc. Geoinformation, Berliner Hochschule für Technik),
supervised by Prof. Dr. Roland Wagner. Repository:
[github.com/sebastianmry/heritage-at-risk](https://github.com/sebastianmry/heritage-at-risk).
