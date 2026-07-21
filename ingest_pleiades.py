"""Stage 1, ingest Pleiades.

Fetches ancient place names and coordinates (Greek, Persian, Aramaic) to
enrich the sites. Pleiades is global; filtering is applied to the region
bbox.

The raw dump (csv.gz) lands as a cache under RAW_DIR/pleiades, the derived
point layer limited to the region as GeoParquet (Point, WGS84), analogous to
the UNESCO ingest, for the later spatial join.

Input:  config.PLEIADES_PLACES_CSV_URL
Output: RAW_DIR/pleiades/pleiades_places.parquet (GeoParquet, point geometry)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import config
import ingest_common

PLEIADES_DIR: Path = config.RAW_DIR / "pleiades"
DUMP_CSV_GZ: Path = PLEIADES_DIR / "pleiades-places-latest.csv.gz"
PLACES_PARQUET: Path = PLEIADES_DIR / "pleiades_places.parquet"

PLEIADES_BASE_URL: str = "https://pleiades.stoa.org"

# Only the columns relevant to the enrichment, out of the 26-column dump.
SOURCE_COLUMNS: tuple[str, ...] = (
    "id", "title", "description", "featureTypes", "timePeriodsKeys",
    "minDate", "maxDate", "locationPrecision", "path", "reprLat", "reprLong",
)


def parse_region_places(dump_path: Path) -> gpd.GeoDataFrame:
    """Reads the dump, filters to the region bbox and builds a point layer."""
    raw_df = pd.read_csv(dump_path, usecols=list(SOURCE_COLUMNS), low_memory=False)

    raw_df["latitude"] = pd.to_numeric(raw_df["reprLat"], errors="coerce")
    raw_df["longitude"] = pd.to_numeric(raw_df["reprLong"], errors="coerce")
    raw_df = raw_df.dropna(subset=["latitude", "longitude"])

    lon_min, lat_min, lon_max, lat_max = config.REGION_BBOX
    in_region = (
        raw_df["longitude"].between(lon_min, lon_max)
        & raw_df["latitude"].between(lat_min, lat_max)
    )
    # Retracted entries have path /errata/... instead of /places/...; they
    # are deleted duplicates and do not belong in the enrichment layer.
    is_place = raw_df["path"].fillna("").str.startswith("/places/")
    region_df = raw_df.loc[in_region & is_place].copy()

    places_df = pd.DataFrame(
        {
            "place_id": region_df["id"].astype("int64"),
            "title": region_df["title"].fillna(""),
            "description": region_df["description"].fillna(""),
            "feature_types": region_df["featureTypes"].fillna(""),
            "time_periods": region_df["timePeriodsKeys"].fillna(""),
            "min_date": pd.to_numeric(region_df["minDate"], errors="coerce"),
            "max_date": pd.to_numeric(region_df["maxDate"], errors="coerce"),
            "location_precision": region_df["locationPrecision"].fillna(""),
            "pleiades_url": PLEIADES_BASE_URL + region_df["path"].fillna(""),
            "latitude": region_df["latitude"],
            "longitude": region_df["longitude"],
        }
    )
    geometry = gpd.points_from_xy(places_df["longitude"], places_df["latitude"])
    places_gdf = gpd.GeoDataFrame(places_df, geometry=geometry, crs="EPSG:4326")
    return places_gdf.sort_values("place_id").reset_index(drop=True)


def run(*, refresh: bool = False) -> None:
    ingest_common.ensure_data_dirs()
    PLEIADES_DIR.mkdir(parents=True, exist_ok=True)

    if ingest_common.already_fetched(PLACES_PARQUET) and not refresh:
        existing_gdf = gpd.read_parquet(PLACES_PARQUET)
        print(f"Pleiades skipped, {len(existing_gdf)} region places already present.")
        return

    ingest_common.download_file(config.PLEIADES_PLACES_CSV_URL, DUMP_CSV_GZ, refresh=refresh)
    places_gdf = parse_region_places(DUMP_CSV_GZ)
    places_gdf.to_parquet(PLACES_PARQUET)

    print(f"Pleiades ingest: {len(places_gdf)} region places -> {PLACES_PARQUET.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Reload the dump and derived data.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
