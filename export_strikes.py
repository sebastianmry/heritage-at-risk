"""Stufe 3, Export der GDELT-GKG-Einschlag-Erwaehnungen als Kartenebene.

Schwesterstufe zu export_events.py (UCDP). Schreibt die GKG-Strike-Erwaehnungen
(aus ingest_gkg.py) als Punkt-FeatureCollection, die die App als dezente,
schaltbare Ebene legt. Sie macht das raeumliche Einschlag-Muster sichtbar, das in
die kombinierte Konflikt-Score-Komponente je Site einfliesst (Methodik-Transparenz).

Zwei bewusste Abweichungen vom UCDP-Export:
  - GKG ist verrauscht und stapelt viele Erwaehnungen auf dieselbe Stadtkoordinate.
    Statt jede Erwaehnung einzeln zu inlinen, AGGREGIERT diese Stufe je eindeutiger
    Koordinate und fuehrt die Erwaehnungszahl als Gewicht (`mentions`) mit. Das haelt
    das Artefakt klein und die Karte lesbar (ein Punkt je Ort, groessenskalierbar).
  - Exportiert werden nur Orte im CONFLICT_RADIUS_KM einer Site, also genau die
    Punkte, die der Score auch zaehlt (wie export_events.py).

Input:  RAW_DIR/gdelt/gkg_strikes.parquet (aus ingest_gkg.py),
        config.SITES_GEOJSON_PATH (aus export.py)
Output: config.GKG_STRIKES_GEOJSON_PATH
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod

import config
import ingest_common

STRIKES_PARQUET: Path = config.RAW_DIR / "gdelt" / "gkg_strikes.parquet"
GEOD: Geod = Geod(ellps="WGS84")


def _within_radius_mask(
    point_lons: np.ndarray, point_lats: np.ndarray,
    site_coords: list[tuple[float, float]], radius_m: float,
) -> np.ndarray:
    """True je Punkt, der in radius_m um mindestens eine Site liegt (geodaetisch)."""
    within = np.zeros(point_lons.shape, dtype=bool)
    for site_lon, site_lat in site_coords:
        origin_lons = np.full(point_lons.shape, site_lon)
        origin_lats = np.full(point_lats.shape, site_lat)
        _, _, distance_m = GEOD.inv(origin_lons, origin_lats, point_lons, point_lats)
        within |= distance_m <= radius_m
    return within


def run() -> None:
    ingest_common.ensure_data_dirs()
    if not ingest_common.already_fetched(STRIKES_PARQUET):
        raise RuntimeError(f"Keine {STRIKES_PARQUET.name}. Zuerst ingest_gkg.py laufen lassen.")
    if not ingest_common.already_fetched(config.SITES_GEOJSON_PATH):
        raise RuntimeError(f"Keine {config.SITES_GEOJSON_PATH.name}. Zuerst export.py laufen lassen.")

    strikes = pd.read_parquet(STRIKES_PARQUET, columns=["latitude", "longitude", "location_name"])

    sites = json.loads(config.SITES_GEOJSON_PATH.read_text(encoding="utf-8"))
    site_coords = [
        (site["geometry"]["coordinates"][0], site["geometry"]["coordinates"][1])
        for site in sites["features"]
    ]
    radius_m = config.CONFLICT_RADIUS_KM * 1000.0
    in_radius = _within_radius_mask(
        strikes["longitude"].to_numpy(dtype=float),
        strikes["latitude"].to_numpy(dtype=float),
        site_coords, radius_m,
    )
    total_count = len(strikes)
    strikes = strikes.loc[in_radius]

    # Je eindeutiger Koordinate aggregieren: Anzahl der Ort-Tage als Gewicht (die
    # Eingabe hat einen Treffer je Ort je Tag, size == Tage), haeufigster Name als Label.
    aggregated = (
        strikes.groupby(["longitude", "latitude"])
        .agg(
            days=("location_name", "size"),
            location_name=("location_name", lambda names: names.mode().iat[0] if not names.mode().empty else ""),
        )
        .reset_index()
        .sort_values("days", ascending=False)
    )

    features: list[dict[str, object]] = []
    for row in aggregated.itertuples(index=False):
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row.longitude), float(row.latitude)],
            },
            "properties": {
                "location_name": row.location_name,
                "days": int(row.days),
            },
        })

    feature_collection = {
        "type": "FeatureCollection",
        "metadata": {
            "title": "GDELT-GKG-Einschlag-Erwaehnungen (Region + Zeitfenster, je Ort aggregiert)",
            "lookback_months": config.STRIKE_LOOKBACK_MONTHS,
            "start_date": config.STRIKE_START_DATE,
            "source": "GDELT Project, GKG 1.0 (open data)",
            "radius_km": config.CONFLICT_RADIUS_KM,
            "note": "Indikative, medienbasierte Einschlag-Berichterstattung (stadtgenau) "
                    f"im {config.CONFLICT_RADIUS_KM:.0f}-km-Radius einer Site; je Ort "
                    "aggregiert (days = Tage mit Berichterstattung, ein Treffer je Ort je "
                    "Tag, Medien-Megafon entfernt). Fliesst kombiniert mit UCDP in die "
                    "Konflikt-Score-Komponente ein.",
        },
        "features": features,
    }

    config.GKG_STRIKES_GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.GKG_STRIKES_GEOJSON_PATH.write_text(
        json.dumps(feature_collection, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"export_strikes: {len(features)} Orte aus {total_count} GKG-Ort-Tagen im "
          f"{config.CONFLICT_RADIUS_KM:.0f}-km-Siteradius -> {config.GKG_STRIKES_GEOJSON_PATH.name}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
