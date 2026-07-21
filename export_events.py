"""Stage 3, export of the UCDP conflict events as a map layer.

Writes the UCDP GED events (region + time window, from ingest_ucdp.py) as a
point FeatureCollection that the app overlays on the map as an unobtrusive,
toggleable layer. This makes visible the spatial conflict pattern that the
conflict score component counts per site (methodology transparency,
complements the 30 km evaluation radius from export_radius.py).

Each feature carries `date` (event_date) + `year` for year-wise colouring in
the app, as well as `violence_type` (GED category) and `deaths` (best
estimate). Deliberately kept lean (coordinates rounded to 5 decimal places),
so the bundled asset stays small; the full attributes only live in the
ucdp parquet.

Only events that lie within CONFLICT_RADIUS_KM of a site are exported, i.e.
exactly the events the score also counts (process.py joins via
ST_Distance_Sphere within the same radius). Clusters far from any site
(e.g. Sudan/Ethiopia) therefore drop out of both the map and the score
alike; borderline cases near sites (e.g. Pakistan) remain. Logic via the
radius rather than rigid country borders. The filter is geodetic
(pyproj.Geod on WGS84), like the circles in export_radius.py, and reads the
committed site coordinates from sites.geojson (no DuckDB needed, pure
geometry).

Input:  RAW_DIR/ucdp/ucdp_events.parquet (from ingest_ucdp.py),
        config.SITES_GEOJSON_PATH (from export.py)
Output: config.CONFLICT_EVENTS_GEOJSON_PATH (conflict_events.geojson, UCDP GED content)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod

import config
import ingest_common

CONFLICT_EVENTS_PARQUET: Path = config.RAW_DIR / "ucdp" / "ucdp_events.parquet"
GEOD: Geod = Geod(ellps="WGS84")


def _within_radius_mask(
    event_lons: np.ndarray, event_lats: np.ndarray,
    site_coords: list[tuple[float, float]], radius_m: float,
) -> np.ndarray:
    """True per event that lies within radius_m of at least one site (geodetic)."""
    within = np.zeros(event_lons.shape, dtype=bool)
    for site_lon, site_lat in site_coords:
        origin_lons = np.full(event_lons.shape, site_lon)
        origin_lats = np.full(event_lats.shape, site_lat)
        _, _, distance_m = GEOD.inv(origin_lons, origin_lats, event_lons, event_lats)
        within |= distance_m <= radius_m
    return within


def run() -> None:
    ingest_common.ensure_data_dirs()
    if not ingest_common.already_fetched(CONFLICT_EVENTS_PARQUET):
        raise RuntimeError(f"No {CONFLICT_EVENTS_PARQUET.name}. Run ingest_ucdp.py first.")
    if not ingest_common.already_fetched(config.SITES_GEOJSON_PATH):
        raise RuntimeError(f"No {config.SITES_GEOJSON_PATH.name}. Run export.py first.")

    events = pd.read_parquet(CONFLICT_EVENTS_PARQUET)

    sites = json.loads(config.SITES_GEOJSON_PATH.read_text(encoding="utf-8"))
    site_coords = [
        (site["geometry"]["coordinates"][0], site["geometry"]["coordinates"][1])
        for site in sites["features"]
    ]
    radius_m = config.CONFLICT_RADIUS_KM * 1000.0
    in_radius = _within_radius_mask(
        events["longitude"].to_numpy(dtype=float),
        events["latitude"].to_numpy(dtype=float),
        site_coords, radius_m,
    )
    total_count = len(events)
    events = events.loc[in_radius]

    features: list[dict[str, object]] = []
    for row in events.itertuples(index=False):
        features.append({
            "type": "Feature",
            "geometry": {
                # Rounded to 5 decimal places (~1 m), keeps the app asset small.
                "type": "Point",
                "coordinates": [round(float(row.longitude), 5), round(float(row.latitude), 5)],
            },
            # Lean properties: only what the map needs. year for the
            # colouring, violence_type (GED category) as a context label,
            # deaths (best estimate) as a severity marker. country/event_id
            # stay only in the parquet (ucdp_events.parquet), not in the bundle.
            "properties": {
                "date": str(pd.Timestamp(row.event_date).date()),
                "year": int(pd.Timestamp(row.event_date).year),
                "violence_type": row.violence_type,
                "deaths": int(row.deaths),
            },
        })

    feature_collection = {
        "type": "FeatureCollection",
        "metadata": {
            "title": "UCDP GED conflict events (region + time window)",
            "lookback_months": config.CONFLICT_LOOKBACK_MONTHS,
            "start_date": config.CONFLICT_START_DATE,
            "source": "UCDP GED (Uppsala Conflict Data Program), CC BY 4.0",
            "radius_km": config.CONFLICT_RADIUS_KM,
            "note": "Georeferenced events within the "
                    f"{config.CONFLICT_RADIUS_KM:.0f} km radius of a site; exactly the "
                    "events the conflict score component counts per site.",
        },
        "features": features,
    }

    config.CONFLICT_EVENTS_GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.CONFLICT_EVENTS_GEOJSON_PATH.write_text(
        json.dumps(feature_collection, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"export_events: {len(features)} of {total_count} UCDP events within the "
          f"{config.CONFLICT_RADIUS_KM:.0f} km site radius -> {config.CONFLICT_EVENTS_GEOJSON_PATH.name}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
