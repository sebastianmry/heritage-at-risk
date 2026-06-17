"""Stufe 3, Export der UCDP-Konfliktereignisse als Kartenebene.

Schreibt die UCDP-GED-Ereignisse (Region + Zeitfenster, aus ingest_ucdp.py) als
Punkt-FeatureCollection, die die App als dezente, schaltbare Ebene ueber die
Karte legt. So wird das raeumliche Konfliktmuster sichtbar, das die Konflikt-
Score-Komponente je Site zaehlt (Methodik-Transparenz, ergaenzt den
30-km-Auswerteradius aus export_radius.py).

Exportiert werden NUR Ereignisse, die im CONFLICT_RADIUS_KM einer Site liegen,
also genau die Events, die der Score auch zaehlt (process.py joint per
ST_Distance_Sphere im selben Radius). Weit von jeder Site entfernte Cluster
(z. B. Sudan/Aethiopien) fallen damit aus Karte und Score gleichermassen heraus;
Grenzfaelle nahe an Sites (z. B. Pakistan) bleiben. Logik ueber den Radius statt
ueber starre Laendergrenzen. Der Filter ist geodaetisch (pyproj.Geod auf WGS84),
wie die Kreise in export_radius.py, und liest die committeten Site-Koordinaten
aus sites.geojson (kein DuckDB noetig, reine Geometrie).

Die App rendert die Ereignisse nur als Punkte (kein Tap-Sheet); die Properties
bleiben schlank (Datum, Gewalttyp, Tote), damit der Inline-Embed klein bleibt.

Input:  RAW_DIR/ucdp/ucdp_events.parquet (aus ingest_ucdp.py),
        config.SITES_GEOJSON_PATH (aus export.py)
Output: config.UCDP_EVENTS_GEOJSON_PATH
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod

import config
import ingest_common

UCDP_EVENTS_PARQUET: Path = config.RAW_DIR / "ucdp" / "ucdp_events.parquet"
GEOD: Geod = Geod(ellps="WGS84")


def _within_radius_mask(
    event_lons: np.ndarray, event_lats: np.ndarray,
    site_coords: list[tuple[float, float]], radius_m: float,
) -> np.ndarray:
    """True je Event, das in radius_m um mindestens eine Site liegt (geodaetisch)."""
    within = np.zeros(event_lons.shape, dtype=bool)
    for site_lon, site_lat in site_coords:
        origin_lons = np.full(event_lons.shape, site_lon)
        origin_lats = np.full(event_lats.shape, site_lat)
        _, _, distance_m = GEOD.inv(origin_lons, origin_lats, event_lons, event_lats)
        within |= distance_m <= radius_m
    return within


def run() -> None:
    ingest_common.ensure_data_dirs()
    if not ingest_common.already_fetched(UCDP_EVENTS_PARQUET):
        raise RuntimeError(f"Keine {UCDP_EVENTS_PARQUET.name}. Zuerst ingest_ucdp.py laufen lassen.")
    if not ingest_common.already_fetched(config.SITES_GEOJSON_PATH):
        raise RuntimeError(f"Keine {config.SITES_GEOJSON_PATH.name}. Zuerst export.py laufen lassen.")

    events = pd.read_parquet(UCDP_EVENTS_PARQUET)

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
                "type": "Point",
                "coordinates": [float(row.longitude), float(row.latitude)],
            },
            "properties": {
                "event_date": pd.Timestamp(row.event_date).strftime("%Y-%m-%d"),
                "violence_type": row.violence_type,
                "deaths": int(row.deaths),
            },
        })

    feature_collection = {
        "type": "FeatureCollection",
        "metadata": {
            "title": "UCDP-GED-Konfliktereignisse (Region + Zeitfenster)",
            "lookback_months": config.CONFLICT_LOOKBACK_MONTHS,
            "start_date": config.CONFLICT_START_DATE,
            "source": "UCDP GED (Uppsala Conflict Data Program), CC BY 4.0",
            "radius_km": config.CONFLICT_RADIUS_KM,
            "note": "Georeferenzierte Ereignisse im "
                    f"{config.CONFLICT_RADIUS_KM:.0f}-km-Radius einer Site; genau die "
                    "Events, die die Konflikt-Score-Komponente je Site zaehlt.",
        },
        "features": features,
    }

    config.UCDP_EVENTS_GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.UCDP_EVENTS_GEOJSON_PATH.write_text(
        json.dumps(feature_collection, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"export_events: {len(features)} von {total_count} UCDP-Ereignissen im "
          f"{config.CONFLICT_RADIUS_KM:.0f}-km-Siteradius -> {config.UCDP_EVENTS_GEOJSON_PATH.name}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
