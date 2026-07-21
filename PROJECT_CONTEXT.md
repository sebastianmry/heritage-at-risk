# Project context: Heritage at Risk
Threat mapping of UNESCO World Heritage and archaeological sites in the MENA region

## 1. Study scope

100 UNESCO World Heritage Sites and archaeological sites across 15 MENA and
Gulf countries (Syria, Lebanon, Israel, Palestine, Iraq, Iran, Yemen, Jordan,
Egypt, Saudi Arabia, the United Arab Emirates, Oman, Qatar, Bahrain and
Kuwait). `config.py` is the single source of truth: country list, source
endpoints, spatial thresholds and score weights all live there, so no
pipeline stage script keeps its own hard-coded values.

---

## 2. Pipeline architecture

### Stage 1: `ingest_*.py` (data acquisition)
Thin per-source fetchers over shared logic in `ingest_common.py` (retry with
backoff, hard timeouts, resume via existence check).

- `ingest_unesco.py` — site inventory from the WHC XML (id, name, country,
  category, coordinates). The XML's own `danger` field is demonstrably
  incomplete (it lists only 1 of Syria's 6 officially endangered sites), so
  the authoritative in-danger flag instead comes from a curated, yearly
  scrape of the rendered danger-list page (`reference/unesco_in_danger.csv`).
  The Old City of Jerusalem is listed by the WHC without a country code; it
  is assigned to Israel via `COUNTRY_OVERRIDES` purely for grouping and the
  travel-advisory join, not as a position on status.
- `ingest_aa.py` — German Federal Foreign Office travel advisories. The
  OpenData API returns four boolean flags per country, not a ready-made
  scale; the 0-2 warning level is derived centrally in
  `config.AA_WARNING_LEVELS` (highest matching level wins).
- `ingest_ucdp.py` — UCDP GED conflict events (CC BY 4.0, peer-reviewed,
  georeferenced), the sole conflict source. The yearly GED release plus the
  monthly candidate dataset together cover the region up to a ~6-week lag.
- `ingest_hazard.py` — ThinkHazard! (World Bank GFDRR) earthquake and
  river-flood levels. No point lookup exists, so each site is reverse-geocoded
  (Nominatim) to its province/district and matched to that division's hazard
  report; the result is a curated, committed CSV
  (`reference/natural_hazard.csv`), read only, never a live call at score time.
- `ingest_pleiades.py` — ancient place names/coordinates, filtered to the
  region bbox, for historical context.
- `ingest_osm.py` / `ingest_osm_buildings.py` — `historic=*` and `building=*`
  features via QuackOSM from Geofabrik PBFs. Buildings are spatially
  pre-filtered to the vicinity of the sites (region-wide would be millions of
  polygons); both layers are pure map context, not score inputs.

### Stage 2: `process.py` (DuckDB, spatial extension)
Computes the threat score (0-10) per site from four independent components:

| Component | Weight | Scaling |
|---|---|---|
| UNESCO in-danger flag | 3 | binary |
| Travel advisory level (0-2) | 3 | linear |
| Conflict events within 30 km | 3 | log-scaled |
| Natural hazard (max of earthquake, river flood) | 1 | level-mapped |

The three human-threat components (in-danger flag, travel advisory,
conflict) carry equal weight; natural hazard carries less weight because it
is a slower-moving background risk rather than an acute, current one. The
conflict count uses `ST_Distance_Sphere` on `ST_Point(lon, lat)` within
`CONFLICT_RADIUS_KM`; if `ucdp_events.parquet` is missing, that component
simply scores 0 for every site rather than failing the run.

### Stage 3: `export*.py` (artefact generation)
Packages the finished `site_scores` table and supporting sources into the
GeoJSON artefacts the app reads; computes nothing new.

- `export.py` — `sites.geojson`: scored sites with threat class, inverted
  traffic-light colour (high = red) and a metadata block.
- `export_events.py` / `export_radius.py` — the UCDP events and the 30 km
  evaluation circles (geodetic, via `pyproj.Geod`, so radius stays exact at
  any latitude/zoom), so the map shows exactly what the score counts.
- `export_3d.py` — curated 3D-model layer (`reference/heritage_3d_models.csv`),
  including destroyed-but-not-inscribed icons (Mosul al-Nuri, Nimrud,
  Nineveh) that carry no score but are labelled accordingly.
- `export_context.py` — Pleiades ancient places near the sites, deduplicated
  against sites that share a name (Palmyra, Babylon, Damascus ...).
- `export_buildings.py` — old-town/density shading: OSM buildings and
  historic objects near the sites, aggregated into a weighted grid cell by
  cell rather than embedded as raw footprints (too numerous for the
  renderer), so remote ruins without modern development still register.

### Stage 4: `app/` (Flutter)
Reads only the finished artefacts (`app/assets/data/*.geojson`), no live
computation or network calls beyond routing and geolocation. See
[README.md](README.md) for the app's own architecture.

---

## 3. Deployment & automation

`.github/workflows/daily-update.yml` refreshes only the time-critical,
lightweight sources daily (AA travel advisories, UCDP conflict events, plus
the small UNESCO inventory), recomputes the score and commits only the
derived artefacts, including the app's bundled GeoJSON assets. No secrets
are required; all sources are token-free. Heavy sources (OSM PBFs, Pleiades,
natural hazard) stay static and are rebuilt manually, since they change
rarely and are expensive to refetch.

---

## 4. Deliberately dropped approaches

- **ACLED as the conflict source.** Evaluated first, then replaced by UCDP
  GED. ACLED's Research tier embargoes event-level data for 12 months, which
  would make the "current threat" claim in the score stale, and its licence
  would have forced the repository private. UCDP GED has only a 4-6 week lag
  and an open licence (CC BY 4.0), so it became the sole conflict source.
- **World Monuments Watch as a score component.** The WMF Watch List and the
  project's sites turned out to be almost disjoint sets in the region; an
  identity join flagged almost none of them. Distance- or country-based
  matching would have produced false positives or diluted the signal, so the
  component was replaced by the ThinkHazard! natural-hazard component
  instead.
- **Overture Maps as a buildings/places source.** Dropped in favour of the
  provider basemap (which already ships buildings) and OSM plus Pleiades for
  heritage context. The Overture access path was also the most fragile part
  of the pipeline (repeated crashes, slow cold scans).
- **OSM `historic=*` as a second context layer.** Tried alongside Pleiades,
  then dropped: too dense and noisy region-wide, and Pleiades alone gives
  clearer ancient-place context. The ingest script is kept, since
  `historic=*` objects still feed the density heatmap in
  `export_buildings.py`.
- **Raw building footprints as a map layer.** Considered, then replaced by an
  aggregated density grid: footprints in the site vicinity would be tens of
  thousands of polygons, too numerous to embed and too heavy for the
  renderer.
