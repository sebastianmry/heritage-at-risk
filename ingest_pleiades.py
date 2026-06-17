"""Stufe 1, Ingest Pleiades.

Holt antike Ortsnamen und Koordinaten (griechisch, persisch, aramaeisch) zur
Anreicherung der Sites. Pleiades ist global; gefiltert wird auf die Region-BBox.

Der Roh-Dump (csv.gz) landet als Cache unter RAW_DIR/pleiades, die abgeleitete,
auf die Region begrenzte Punktebene als GeoParquet (Point, WGS84) analog zum
UNESCO-Ingest fuer den spaeteren raeumlichen Join.

Input:  config.PLEIADES_PLACES_CSV_URL
Output: RAW_DIR/pleiades/pleiades_places.parquet (GeoParquet, Punktgeometrie)
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

# Nur die fuer die Anreicherung relevanten Spalten aus dem 26-spaltigen Dump.
SOURCE_COLUMNS: tuple[str, ...] = (
    "id", "title", "description", "featureTypes", "timePeriodsKeys",
    "minDate", "maxDate", "locationPrecision", "path", "reprLat", "reprLong",
)


def parse_region_places(dump_path: Path) -> gpd.GeoDataFrame:
    """Liest den Dump, filtert auf die Region-BBox und baut eine Punktebene."""
    raw_df = pd.read_csv(dump_path, usecols=list(SOURCE_COLUMNS), low_memory=False)

    raw_df["latitude"] = pd.to_numeric(raw_df["reprLat"], errors="coerce")
    raw_df["longitude"] = pd.to_numeric(raw_df["reprLong"], errors="coerce")
    raw_df = raw_df.dropna(subset=["latitude", "longitude"])

    lon_min, lat_min, lon_max, lat_max = config.REGION_BBOX
    in_region = (
        raw_df["longitude"].between(lon_min, lon_max)
        & raw_df["latitude"].between(lat_min, lat_max)
    )
    # Zurueckgezogene Eintraege haben path /errata/... statt /places/...; sie
    # sind geloeschte Dubletten und gehoeren nicht in die Anreicherungsebene.
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
        print(f"Pleiades uebersprungen, {len(existing_gdf)} Region-Orte bereits vorhanden.")
        return

    ingest_common.download_file(config.PLEIADES_PLACES_CSV_URL, DUMP_CSV_GZ, refresh=refresh)
    places_gdf = parse_region_places(DUMP_CSV_GZ)
    places_gdf.to_parquet(PLACES_PARQUET)

    print(f"Pleiades-Ingest: {len(places_gdf)} Region-Orte -> {PLACES_PARQUET.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Dump und Ableitung neu laden.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
