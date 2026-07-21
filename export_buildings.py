"""Stage 3, export of the old town and site density shading.

Writes a map context layer from two OSM sources, clipped to the narrow site
vicinity (config.BUILDINGS_NEAR_SITES_KM) and without a threat score (pure
presentation):

  * buildings (ingest_osm_buildings.py, <country>_buildings.parquet) -> urban fabric/old town
  * historic objects (ingest_osm.py, <country>_historic.parquet, historic=*:
    archaeological_site, ruins, monument, castle ...) -> ancient structures

building_density.geojson  Density "shading": the centroids of both sources
                          aggregated into a grid (config.BUILDINGS_DENSITY_CELL_DEG),
                          one weighted point per cell (weight = sum of hits).
                          Historic objects count HISTORIC_WEIGHT times, so that
                          remote ruins (Palmyra, Petra) without modern development
                          also glow, not just dense modern cities. Feeds the warm
                          MapLibre heatmap over the historic cores.

Aggregation instead of raw embedding is deliberate: per-site footprints are far
too numerous to embed as a map layer without overloading the renderer.

Input:  RAW_DIR/osm/parquet/<country>_{buildings,historic}.parquet, unesco_sites.parquet
Output: config.ARTIFACTS_DIR/building_density.geojson
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

import config
import ingest_common

BUILDINGS_DIR: Path = config.RAW_DIR / "osm" / "parquet"
SITES_PARQUET: Path = config.RAW_DIR / "unesco" / "unesco_sites.parquet"

DENSITY_GEOJSON: Path = config.ARTIFACTS_DIR / "building_density.geojson"

COORD_PRECISION: int = 5  # ~1 m, enough for a context layer and saves file size

# Historic objects count more heavily than a single building, so that remote
# find sites (few ruins, hardly any modern development) also glow visibly.
HISTORIC_WEIGHT: int = 4


def _write_geojson(path: Path, features: list[dict[str, object]], *, layer: str) -> int:
    collection = {"type": "FeatureCollection", "metadata": {"layer": layer}, "features": features}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(features)


def _country_parquets(suffix: str) -> list[str]:
    """Existing <country>_<suffix>.parquet files of the currently configured countries."""
    paths = []
    for country in config.COUNTRIES:
        path = BUILDINGS_DIR / f"{country}_{suffix}.parquet"
        if path.exists() and path.stat().st_size > 0:
            paths.append(path.as_posix())
    return paths


def export_density(con: duckdb.DuckDBPyConnection, radius_m: float) -> tuple[int, int]:
    """Aggregates building and historic centroids into a weighted density grid."""
    buildings = _country_parquets("buildings")
    if not buildings:
        raise RuntimeError(f"No building parquets in {BUILDINGS_DIR}. Run ingest_osm_buildings.py first.")
    historic = _country_parquets("historic")

    cell = config.BUILDINGS_DENSITY_CELL_DEG
    # Both sources with weight in one CTE: buildings w=1, historic w=HISTORIC_WEIGHT.
    src_parts = [
        f"SELECT ST_X(ST_Centroid(geometry)) AS lon, ST_Y(ST_Centroid(geometry)) AS lat, "
        f"1 AS w FROM read_parquet({buildings!r})"
    ]
    if historic:
        src_parts.append(
            f"SELECT ST_X(ST_Centroid(geometry)) AS lon, ST_Y(ST_Centroid(geometry)) AS lat, "
            f"{HISTORIC_WEIGHT} AS w FROM read_parquet({historic!r})"
        )
    src_sql = "\n            UNION ALL\n            ".join(src_parts)

    rows = con.execute(f"""
        WITH src AS (
            {src_sql}
        ),
        near AS (
            SELECT lon, lat, w FROM src c
            WHERE EXISTS (SELECT 1 FROM _sites s
                          WHERE ST_Distance_Sphere(ST_Point(c.lon, c.lat), ST_Point(s.lon, s.lat)) <= {radius_m})
        )
        SELECT floor(lon / {cell}) * {cell} + {cell} / 2 AS gx,
               floor(lat / {cell}) * {cell} + {cell} / 2 AS gy,
               sum(w) AS n
        FROM near
        GROUP BY gx, gy
        ORDER BY n DESC
    """).fetchall()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(gx, COORD_PRECISION), round(gy, COORD_PRECISION)]},
            "properties": {"w": int(n)},
        }
        for gx, gy, n in rows
    ]
    max_weight = max((int(n) for _, _, n in rows), default=0)
    return _write_geojson(DENSITY_GEOJSON, features, layer="building_density"), max_weight


def run() -> None:
    ingest_common.ensure_data_dirs()
    if not ingest_common.already_fetched(SITES_PARQUET):
        raise RuntimeError(f"UNESCO sites missing ({SITES_PARQUET}). Run ingest_unesco.py first.")

    radius_m = config.BUILDINGS_NEAR_SITES_KM * 1000.0
    con = duckdb.connect()
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute(f"""CREATE TEMP TABLE _sites AS
            SELECT longitude AS lon, latitude AS lat FROM read_parquet('{SITES_PARQUET.as_posix()}')
            WHERE longitude IS NOT NULL AND latitude IS NOT NULL""")
        n_cells, max_weight = export_density(con, radius_m)
    finally:
        con.close()

    de_mb = DENSITY_GEOJSON.stat().st_size / 1_048_576
    print(f"export_buildings: {n_cells} density cells (max {max_weight} buildings/cell) "
          f"-> {DENSITY_GEOJSON.name} ({de_mb:.2f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
