"""Single source of truth for Heritage at Risk.

All parameters, paths, source endpoints, score weights and spatial thresholds
live exclusively here. No pipeline stage script keeps its own hard-coded
values, every one imports from this file. A change therefore takes effect
everywhere.
"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
#
# Large raw data lives outside the repo under DATA_DIR (environment variable
# with a sensible default). Derived, committed artefacts live in the repo
# under ARTIFACTS_DIR.
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: apply KEY=VALUE lines to os.environ.

    Deliberately without an external dependency (no python-dotenv). Already
    set environment variables take precedence, so the shell or CI never gets
    overridden by the file. Secrets stay out of the code this way.
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if value:  # do not set empty entries (e.g. DATA_DIR=), or they would
            os.environ.setdefault(key, value)  # override the default


_load_dotenv(REPO_ROOT / ".env")

DATA_DIR: Path = Path(os.environ.get("DATA_DIR", REPO_ROOT.parent / "heritage_data"))
RAW_DIR: Path = DATA_DIR / "raw"          # sources, raw and unmodified
INTERIM_DIR: Path = DATA_DIR / "interim"  # intermediate processing state
CACHE_DIR: Path = DATA_DIR / "cache"      # incremental cache per item

ARTIFACTS_DIR: Path = REPO_ROOT / "artifacts"  # runtime artefacts (committed)
REFERENCE_DIR: Path = REPO_ROOT / "reference"  # curated, committed reference lists
DUCKDB_PATH: Path = INTERIM_DIR / "heritage.duckdb"

# Output artefacts the app reads (stage 3, export)
SITES_GEOJSON_PATH: Path = ARTIFACTS_DIR / "sites.geojson"
CONFLICT_RADIUS_GEOJSON_PATH: Path = ARTIFACTS_DIR / "conflict_radius.geojson"
CONFLICT_EVENTS_GEOJSON_PATH: Path = ARTIFACTS_DIR / "conflict_events.geojson"

# ---------------------------------------------------------------------------
# Region of interest: EMENA (Eastern Mediterranean & Near East)
#
# Geofabrik splits the region across two continents.
# ---------------------------------------------------------------------------

GEOFABRIK_BASE: str = "https://download.geofabrik.de"

# key -> (ISO 3166 alpha-2, Geofabrik PBF URL)
#
# Country scope: the mission has two axes, threat and density of the World
# Heritage, so beyond the crisis-adjacent countries the scope also covers
# Egypt, the entire Arabian Peninsula (Saudi Arabia, UAE, Oman, Qatar,
# Bahrain, Kuwait) and Jordan, to show the density and coverage of the wider
# region. Stable countries therefore appear with many low-scoring sites,
# which is intentional. Geofabrik bundles the Gulf states in one extract
# (asia/gcc-states), hence six keys point to the same PBF URL. Palestine has
# no PBF entry of its own; its OSM data sits inside the israel-and-palestine
# extract and only enters via COUNTRY_ISO2 in the filter. Out of scope: the
# secure north-west flank (Greece, Cyprus, Turkey, Armenia, Azerbaijan).
COUNTRIES: dict[str, tuple[str, str]] = {
    "syria": ("SY", f"{GEOFABRIK_BASE}/asia/syria-latest.osm.pbf"),
    "lebanon": ("LB", f"{GEOFABRIK_BASE}/asia/lebanon-latest.osm.pbf"),
    "israel": ("IL", f"{GEOFABRIK_BASE}/asia/israel-and-palestine-latest.osm.pbf"),
    "iraq": ("IQ", f"{GEOFABRIK_BASE}/asia/iraq-latest.osm.pbf"),
    "iran": ("IR", f"{GEOFABRIK_BASE}/asia/iran-latest.osm.pbf"),
    "yemen": ("YE", f"{GEOFABRIK_BASE}/asia/yemen-latest.osm.pbf"),
    "jordan": ("JO", f"{GEOFABRIK_BASE}/asia/jordan-latest.osm.pbf"),
    "egypt": ("EG", f"{GEOFABRIK_BASE}/africa/egypt-latest.osm.pbf"),
    "saudi_arabia": ("SA", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "uae": ("AE", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "oman": ("OM", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "qatar": ("QA", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "bahrain": ("BH", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "kuwait": ("KW", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
}

# ISO codes of the region, for filtering the German Federal Foreign Office
# advisories. Palestine (PS) is added on top (its own country, OSM via the
# Israel PBF, no separate entry in COUNTRIES).
COUNTRY_ISO2: tuple[str, ...] = tuple(iso for iso, _ in COUNTRIES.values()) + ("PS",)

# Rough bounding box of the region (lon_min, lat_min, lon_max, lat_max) in
# EPSG:4326. Serves as a cheap pre-filter before expensive operations run.
# lat_min lowered to 12.0 (Yemen ~12-19 N), lon_min lowered to 28.0 so Egypt
# (western WHS such as Abu Mena ~29.7 E) falls inside; the eastern bound 64.0
# covers Oman/UAE/Iran.
REGION_BBOX: tuple[float, float, float, float] = (28.0, 12.0, 64.0, 42.5)

# ---------------------------------------------------------------------------
# Source endpoints
#
# API keys come exclusively from environment variables, never from the code.
# ---------------------------------------------------------------------------

# OSM: historic=* and path=* from the Geofabrik PBF, via QuackOSM to GeoParquet
OSM_TAGS_HISTORIC: tuple[str, ...] = ("historic",)
OSM_TAGS_ROUTING: tuple[str, ...] = ("path", "footway", "steps")

# OSM building=*: map context only (footprints in the site vicinity plus the
# density "glow" over historic cores), not part of the threat score. The
# extraction is spatially pre-filtered to the site vicinity at ingest time
# (geometry_filter), so entire countries' worth of buildings do not pile up.
OSM_TAGS_BUILDINGS: tuple[str, ...] = ("building",)

# Radius around a UNESCO site within which buildings are considered as
# context. Kept narrow: it should capture the historic core / old town, not
# the surrounding countryside, otherwise data volume and renderer load grow
# too far.
BUILDINGS_NEAR_SITES_KM: float = 1.2

# Edge length of the density grid cell (degrees) for the heatmap aggregation.
# Instead of embedding every building individually, building centroids are
# aggregated into cells with the hit count as weight (small artefact, real
# density). ~150 m.
BUILDINGS_DENSITY_CELL_DEG: float = 0.0015

# UNESCO World Heritage Centre: site metadata and coordinates
UNESCO_WHC_XML_URL: str = "https://whc.unesco.org/en/list/xml/"

# Official list of endangered World Heritage. The page is JS-rendered, so the
# site IDs are scraped via browser and maintained as a curated, dated CSV.
# The danger field in list/xml is incomplete and is not used as the flag.
UNESCO_DANGER_LIST_URL: str = "https://whc.unesco.org/en/danger-list/"
UNESCO_IN_DANGER_PATH: Path = REFERENCE_DIR / "unesco_in_danger.csv"

# UCDP GED: open, georeferenced conflict events (Uppsala Conflict Data
# Program, CC BY 4.0 / ODbL). Sole source of the conflict component: a ~4-6
# week lag keeps the score describing the current situation, and the open
# licence keeps the repo and app publishable. Peer-reviewed and citable.
# Also captures lethal air/drone/missile strikes (no weapon-type field);
# known limitation: threshold >= 1 fatality, non-lethal hits are missing.
# Two token-free building blocks via the UCDP Download Center: the yearly
# main dataset (up to the end of the previous year) plus the monthly
# candidate (current year, cumulative). Bump the URLs on a new release.
UCDP_GED_CSV_URL: str = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
UCDP_CANDIDATE_CSV_URL: str = "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_5.csv"

# UCDP type_of_violence code -> plain text (GED codebook): only determines the
# context label per event, not the score (the join is purely spatial).
UCDP_VIOLENCE_TYPES: dict[int, str] = {
    1: "state-based conflict",
    2: "non-state conflict",
    3: "one-sided violence",
}

# Conflict time window: rolling window starting CONFLICT_LOOKBACK_MONTHS back,
# open until today (UCDP lag ~4-6 weeks, the most recent month is deliberately
# missing). 12 months means the current situation rather than a multi-year
# history; the local, current intensity differentiation is the added value of
# the georeferenced conflict data over the country-wide travel advisory.
# Deliberately rolling: every build is a snapshot. CONFLICT_WINDOW_END_MONTHS
# is kept as a constant (0 = no more recent edge) so a future embargo window
# on the data stays configurable without further code changes.
CONFLICT_LOOKBACK_MONTHS: int = 12     # window start (older edge)
CONFLICT_WINDOW_END_MONTHS: int = 0    # window end (0 = open until today)


def _month_start_months_ago(months: int) -> str:
    today = date.today()
    year, month = today.year, today.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1).isoformat()


CONFLICT_START_DATE: str = _month_start_months_ago(CONFLICT_LOOKBACK_MONTHS)
CONFLICT_END_DATE: str = _month_start_months_ago(CONFLICT_WINDOW_END_MONTHS)

# German Federal Foreign Office (Auswaertiges Amt): travel and security
# advisories as a country-level danger indicator. The OpenData API returns
# four boolean flags per country, not a ready-made numeric scale.
AA_TRAVELWARNING_URL: str = "https://www.auswaertiges-amt.de/opendata/travelwarning"

# Derivation of the warning level (0-2) from the OpenData API's four boolean
# flags. No official numeric scale exists; this mapping is a deliberate
# project derivation. Three levels are enough; what matters is the reach of
# the advisory, not whether it is structural or situational:
#   2  country-wide travel warning  (warning or situationWarning)
#   1  partial travel warning       (partialWarning or situationPartWarning)
#   0  no warning
# The flags are checked in this order; the highest matching level wins.
AA_WARNING_LEVELS: tuple[tuple[str, int], ...] = (
    ("warning", 2),
    ("situationWarning", 2),
    ("partialWarning", 1),
    ("situationPartWarning", 1),
)
AA_WARNING_LEVEL_MAX: int = 2

# Pleiades: ancient place names and coordinates
PLEIADES_PLACES_CSV_URL: str = "https://atlantides.org/downloads/pleiades/dumps/pleiades-places-latest.csv.gz"

# Natural hazards per site (earthquake + river flood) from the World Bank's
# ThinkHazard!. Curated, committed CSV (keyed per site_id), generated by
# ingest_hazard.py.
NATURAL_HAZARD_PATH: Path = REFERENCE_DIR / "natural_hazard.csv"

# Live APIs of the app (not part of the pipeline, documented centrally here)
NOMINATIM_URL: str = "https://nominatim.openstreetmap.org"
OPENROUTESERVICE_URL: str = "https://api.openrouteservice.org"
OPENROUTESERVICE_API_KEY: str | None = os.environ.get("OPENROUTESERVICE_API_KEY")

# ---------------------------------------------------------------------------
# Threat score (0 to SCORE_MAX)
#
# Four independent components, weights 3/3/3/1 (SCORE_MAX 10). Three make up
# the human threat axis (in-danger status, travel advisory, conflict) at 3
# each, the fourth is the natural hazard (earthquake + river flood) as a
# secondary modifier with weight 1.
# ---------------------------------------------------------------------------

SCORE_WEIGHT_UNESCO_IN_DANGER: int = 3   # official UNESCO in-danger flag
SCORE_WEIGHT_TRAVEL_WARNING: int = 3     # travel advisory level 0-2, linearly scaled
SCORE_WEIGHT_CONFLICT: int = 3           # UCDP GED events in radius (log-scaled)
SCORE_WEIGHT_NATURAL_HAZARD: int = 1     # earthquake + river flood (ThinkHazard!), secondary

SCORE_MAX: int = (
    SCORE_WEIGHT_UNESCO_IN_DANGER
    + SCORE_WEIGHT_TRAVEL_WARNING
    + SCORE_WEIGHT_CONFLICT
    + SCORE_WEIGHT_NATURAL_HAZARD
)

# Natural hazard: ThinkHazard! levels (earthquake EQ, river flood FL) per site
# mapped to [0, 1]; "no data" (NDA) counts as 0. The component takes the
# maximum of both hazards (worst-case exposure: a site is at risk if it is
# strongly exposed to either hazard) and scales it by the weight.
NATURAL_HAZARD_LEVEL_SCORES: dict[str, float] = {
    "VLO": 0.0,        # very low
    "LOW": 1.0 / 3.0,  # low
    "MED": 2.0 / 3.0,  # medium
    "HIG": 1.0,        # high
    "NDA": 0.0,        # no data
}

# Spatial conflict join: events within a 30 km radius of a site (DuckDB
# ST_Distance on geographic coordinates). Deliberately local: only conflict in
# the site's immediate vicinity counts, not the country-wide situation (that
# is covered by the travel advisory).
CONFLICT_RADIUS_KM: float = 30.0

# Number of events within the radius from which the conflict component counts
# in full. The mapping event count -> partial score is logarithmic, not
# linear: score = min(ln(1 + count) / ln(1 + CONFLICT_EVENTS_FOR_FULL_SCORE),
# 1). Rationale: the event count per site is strongly right-skewed. A linear
# threshold either saturates too early (all affected sites at full value) or,
# with a high cap, shrinks the majority of values. The log scale spreads the
# intensity smoothly across the range and preserves the spatial added value
# of the conflict data over the country-wide travel advisory. Cap set at the
# ~p90 of the active sites on the 12-month UCDP window of lethal events.
CONFLICT_EVENTS_FOR_FULL_SCORE: int = 25

# ---------------------------------------------------------------------------
# Presentation: colour-coded threat levels (green, yellow, red)
#
# Breaks the score into three classes and sets the colour and label used in
# the export and the app.
# ---------------------------------------------------------------------------

# (label, inclusive upper bound)
THREAT_LEVEL_BREAKS: tuple[tuple[str, float], ...] = (
    ("low", 3.0),
    ("medium", 6.0),
    ("high", float(SCORE_MAX)),
)

# Inverted traffic light: high danger = red, low = green. Colour is only the
# redundant second encoding; the app also always encodes threat via symbol
# and text, never via colour alone.
THREAT_LEVEL_COLORS: dict[str, str] = {
    "low": "#1a9641",     # green
    "medium": "#fdae61",  # amber
    "high": "#d7191c",    # red
}

# Human-readable label per class for the legend and detail sheet.
THREAT_LEVEL_LABELS: dict[str, str] = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}

# ---------------------------------------------------------------------------
# Robust data fetching
# ---------------------------------------------------------------------------

HTTP_TIMEOUT_SECONDS: float = 30.0
HTTP_MAX_RETRIES: int = 5
HTTP_BACKOFF_FACTOR: float = 2.0
HTTP_RETRY_STATUS: tuple[int, ...] = (429, 500, 502, 503, 504)
HTTP_MAX_WORKERS: int = 4  # conservative parallelism

# Identifying user agent with contact. WHC blocks anonymous requests (403),
# Nominatim requires one per its usage policy.
USER_AGENT: str = "HeritageAtRisk/0.1 (academic project; sebastian.macherey@gmail.com)"
HTTP_HEADERS: dict[str, str] = {"User-Agent": USER_AGENT}
