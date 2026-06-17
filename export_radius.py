"""Stufe 3, Export der Konflikt-Radien.

Zeichnet je UNESCO-Site den Umkreis, in dem die Konflikt-Komponente Ereignisse
zaehlt (config.CONFLICT_RADIUS_KM), als Polygon-FeatureCollection. Die App legt
das als dezente, schaltbare Ebene ueber die Karte, damit sichtbar wird, welchen
raeumlichen Ausschnitt der Score je Site auswertet (Transparenz der Methodik).

Die Kreise sind geodaetisch korrekt (pyproj.Geod auf dem WGS84-Ellipsoid), nicht
als Pixel-Radius gemalt: ein 30-km-Kreis bleibt 30 km, unabhaengig von Zoom und
Breitengrad. Liest die committeten Site-Koordinaten aus sites.geojson (kein
DuckDB noetig, reine Geometrie).

Input:  config.SITES_GEOJSON_PATH
Output: config.CONFLICT_RADIUS_GEOJSON_PATH
"""

from __future__ import annotations

import json

from pyproj import Geod

import config
import ingest_common

GEOD: Geod = Geod(ellps="WGS84")
CIRCLE_VERTICES: int = 72  # glatt genug, klein genug fuer den Inline-Embed


def _circle_ring(lon: float, lat: float, radius_m: float) -> list[list[float]]:
    """Baut einen geschlossenen, geodaetisch korrekten Kreis-Ring um einen Punkt."""
    ring: list[list[float]] = []
    for vertex in range(CIRCLE_VERTICES):
        azimuth = 360.0 * vertex / CIRCLE_VERTICES
        point_lon, point_lat, _ = GEOD.fwd(lon, lat, azimuth, radius_m)
        ring.append([point_lon, point_lat])
    ring.append(ring[0])  # Ring schliessen
    return ring


def run() -> None:
    ingest_common.ensure_data_dirs()
    if not ingest_common.already_fetched(config.SITES_GEOJSON_PATH):
        raise RuntimeError(f"Keine {config.SITES_GEOJSON_PATH.name}. Zuerst export.py laufen lassen.")

    sites = json.loads(config.SITES_GEOJSON_PATH.read_text(encoding="utf-8"))
    radius_m = config.CONFLICT_RADIUS_KM * 1000.0

    features: list[dict[str, object]] = []
    for site in sites["features"]:
        lon, lat = site["geometry"]["coordinates"]
        properties = site["properties"]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_circle_ring(lon, lat, radius_m)]},
            "properties": {"site_id": properties["site_id"], "name": properties["name"]},
        })

    feature_collection = {
        "type": "FeatureCollection",
        "metadata": {
            "title": f"Konflikt-Auswerteradius je UNESCO-Site ({config.CONFLICT_RADIUS_KM:.0f} km)",
            "radius_km": config.CONFLICT_RADIUS_KM,
            "note": "Geodaetische Kreise (WGS84) um die Site-Punkte; in diesem Umkreis "
                    "zaehlt die Konflikt-Komponente die UCDP-GED-Ereignisse.",
        },
        "features": features,
    }

    config.CONFLICT_RADIUS_GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.CONFLICT_RADIUS_GEOJSON_PATH.write_text(
        json.dumps(feature_collection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"export_radius: {len(features)} Kreise ({config.CONFLICT_RADIUS_KM:.0f} km) "
          f"-> {config.CONFLICT_RADIUS_GEOJSON_PATH.name}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
