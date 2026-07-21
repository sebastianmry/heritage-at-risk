"""Stage 3, export of the conflict radii.

Draws, per UNESCO site, the vicinity within which the conflict component
counts events (config.CONFLICT_RADIUS_KM), as a polygon FeatureCollection.
The app overlays this on the map as an unobtrusive, toggleable layer, so it
becomes visible which spatial extent the score evaluates per site
(methodology transparency).

The circles are geodetically correct (pyproj.Geod on the WGS84 ellipsoid),
not drawn as a pixel radius: a 30 km circle stays 30 km, independent of zoom
and latitude. Reads the committed site coordinates from sites.geojson (no
DuckDB needed, pure geometry).

Input:  config.SITES_GEOJSON_PATH
Output: config.CONFLICT_RADIUS_GEOJSON_PATH
"""

from __future__ import annotations

import json

from pyproj import Geod

import config
import ingest_common

GEOD: Geod = Geod(ellps="WGS84")
CIRCLE_VERTICES: int = 72  # smooth enough, small enough for the inline embed


def _circle_ring(lon: float, lat: float, radius_m: float) -> list[list[float]]:
    """Builds a closed, geodetically correct circle ring around a point."""
    ring: list[list[float]] = []
    for vertex in range(CIRCLE_VERTICES):
        azimuth = 360.0 * vertex / CIRCLE_VERTICES
        point_lon, point_lat, _ = GEOD.fwd(lon, lat, azimuth, radius_m)
        ring.append([point_lon, point_lat])
    ring.append(ring[0])  # close the ring
    return ring


def run() -> None:
    ingest_common.ensure_data_dirs()
    if not ingest_common.already_fetched(config.SITES_GEOJSON_PATH):
        raise RuntimeError(f"No {config.SITES_GEOJSON_PATH.name}. Run export.py first.")

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
            "title": f"Conflict evaluation radius per UNESCO site ({config.CONFLICT_RADIUS_KM:.0f} km)",
            "radius_km": config.CONFLICT_RADIUS_KM,
            "note": "Geodetic circles (WGS84) around the site points; within this "
                    "vicinity the conflict component counts the UCDP GED events.",
        },
        "features": features,
    }

    config.CONFLICT_RADIUS_GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.CONFLICT_RADIUS_GEOJSON_PATH.write_text(
        json.dumps(feature_collection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"export_radius: {len(features)} circles ({config.CONFLICT_RADIUS_KM:.0f} km) "
          f"-> {config.CONFLICT_RADIUS_GEOJSON_PATH.name}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
