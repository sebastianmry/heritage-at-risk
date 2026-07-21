"""Stage 1, ingest OSM buildings (map context).

Reads building=* features via QuackOSM from the region's already-existing
Geofabrik PBFs into GeoParquet. Unlike ingest_osm.py (historic=*,
region-wide), the extraction is spatially pre-filtered to the vicinity of
the UNESCO sites: a geometry_filter (union of generous buffers around the
site points) ensures that QuackOSM only reads buildings near the sites.
Buildings in dense old towns are very numerous; region-wide it would be
millions.

This layer is pure map context (footprints + density shading), not part of
the threat score. The precise clipping to the site radius and the density
aggregation happen in export_buildings.py.

Input:  RAW_DIR/osm/pbf/<country>.osm.pbf (from ingest_osm.py), unesco_sites.parquet
Output: RAW_DIR/osm/parquet/<country>_buildings.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import geopandas as gpd
import quackosm
from shapely.geometry import MultiPolygon
from shapely.ops import unary_union

import config
import ingest_common

OSM_DIR: Path = config.RAW_DIR / "osm"
PBF_DIR: Path = OSM_DIR / "pbf"
PARQUET_DIR: Path = OSM_DIR / "parquet"

SITES_PARQUET: Path = config.RAW_DIR / "unesco" / "unesco_sites.parquet"

# Coarse pre-filter buffer around each site (degrees). Deliberately a bit
# larger than the later precise clip radius (BUILDINGS_NEAR_SITES_KM), so
# nothing is missing at the edge; export_buildings.py does the exact
# clipping via ST_Distance_Sphere. 1 degree of latitude ~ 111 km, with a
# 40% margin on the clip radius.
_PREFILTER_BUFFER_DEG: float = config.BUILDINGS_NEAR_SITES_KM / 111.0 * 1.4


def buildings_tags_filter() -> dict[str, bool]:
    """Filter on all values of the building=* tags (config.OSM_TAGS_BUILDINGS)."""
    return {tag: True for tag in config.OSM_TAGS_BUILDINGS}


def site_buffer_filter() -> MultiPolygon:
    """Union of generous buffers around all site points as a spatial pre-filter."""
    if not ingest_common.already_fetched(SITES_PARQUET):
        raise RuntimeError(f"UNESCO sites missing ({SITES_PARQUET}). Run ingest_unesco.py first.")
    sites = gpd.read_parquet(SITES_PARQUET)
    sites = sites[sites["longitude"].notna() & sites["latitude"].notna()]
    points = gpd.points_from_xy(sites["longitude"], sites["latitude"])
    buffers = [point.buffer(_PREFILTER_BUFFER_DEG) for point in points]
    union = unary_union(buffers)
    return union if union.geom_type == "MultiPolygon" else MultiPolygon([union])


def count_features(parquet_path: Path) -> int:
    """Counts the rows in the generated GeoParquet (cheap validation)."""
    return duckdb.sql(f"SELECT count(*) FROM read_parquet('{parquet_path.as_posix()}')").fetchone()[0]


def ingest_country(key: str, geometry_filter: MultiPolygon, *, refresh: bool = False) -> Path | None:
    """Converts a country's building=* features within the site vicinity."""
    pbf_path = PBF_DIR / f"{key}.osm.pbf"
    if not ingest_common.already_fetched(pbf_path):
        print(f"  {key:12s} skipped, PBF missing (run ingest_osm.py first)")
        return None

    result_path = PARQUET_DIR / f"{key}_buildings.parquet"
    if ingest_common.already_fetched(result_path) and not refresh:
        print(f"  {key:12s} skipped, {count_features(result_path)} buildings already present")
        return result_path

    quackosm.convert_pbf_to_parquet(
        pbf_path,
        tags_filter=buildings_tags_filter(),
        geometry_filter=geometry_filter,
        keep_all_tags=False,
        result_file_path=result_path,
        ignore_cache=refresh,
        verbosity_mode="silent",
    )
    print(f"  {key:12s} {count_features(result_path)} buildings -> {result_path.name}")
    return result_path


def run(*, refresh: bool = False, only: str | None = None) -> None:
    ingest_common.ensure_data_dirs()
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    countries = config.COUNTRIES
    if only is not None:
        if only not in countries:
            raise SystemExit(f"Unknown country '{only}'. Known: {', '.join(countries)}")
        countries = {only: countries[only]}

    geometry_filter = site_buffer_filter()
    print(f"OSM buildings ingest for {len(countries)} country/countries (filter: {config.BUILDINGS_NEAR_SITES_KM} km around sites):")
    for key in countries:
        ingest_country(key, geometry_filter, refresh=refresh)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Regenerate existing raw data and parquet.")
    parser.add_argument("--only", metavar="COUNTRY", help="Process only a single country (e.g. cyprus).")
    args = parser.parse_args()
    run(refresh=args.refresh, only=args.only)


if __name__ == "__main__":
    main()
