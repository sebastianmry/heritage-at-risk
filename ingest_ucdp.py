"""Stufe 1, Ingest UCDP GED (Konflikt-Ereignisse).

Alleinige Quelle der Konflikt-Komponente des Threat Score. UCDP GED ist offen
lizenziert (CC BY 4.0), georeferenziert und peer-reviewed, also auch fuer eine
veroeffentlichte Open-Source-App rechtssicher.

Zwei Bausteine, beide tokenfrei ueber das UCDP Download Center:
  - GED-Hauptdatensatz (config.UCDP_GED_CSV_URL, ZIP): 1989 bis Ende Vorjahr.
  - GED-Candidate (config.UCDP_CANDIDATE_CSV_URL, CSV): das laufende Jahr, monatlich.
Zusammen decken sie das rollende Konflikt-Fenster bis fast an die Gegenwart
(UCDP hat ~6 Wochen Lag, der letzte Monat fehlt also bewusst).

Gefiltert wird auf die REGION_BBOX und das CONFLICT_START_DATE; der Score-Join
in process.py ist rein raeumlich (Punkte im CONFLICT_RADIUS_KM je Site).

Input:  config.UCDP_GED_CSV_URL (ZIP), config.UCDP_CANDIDATE_CSV_URL (CSV)
Output: RAW_DIR/ucdp/ucdp_events.parquet (GeoParquet, Punktgeometrie)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

import config
import ingest_common

UCDP_DIR: Path = config.RAW_DIR / "ucdp"
EVENTS_PARQUET: Path = UCDP_DIR / "ucdp_events.parquet"
GED_ZIP: Path = UCDP_DIR / "ged_full.zip"
CANDIDATE_CSV: Path = UCDP_DIR / "ged_candidate.csv"

# Schlanke Feldauswahl: Geometrie und Zeit fuer den Filter, Typ und Tote als Kontext.
SOURCE_COLUMNS: tuple[str, ...] = (
    "id", "date_start", "type_of_violence", "country", "latitude", "longitude", "best",
)


def _read_source(path: Path, *, compression: str | None = None) -> pd.DataFrame:
    """Liest eine GED-CSV (auch aus dem ZIP) auf die noetigen Spalten beschnitten."""
    return pd.read_csv(
        path,
        usecols=list(SOURCE_COLUMNS),
        compression=compression,
        dtype=str,
        keep_default_na=False,
    )


def _filter_to_scope(source_df: pd.DataFrame) -> pd.DataFrame:
    """Beschneidet auf Region (BBox) und Zeitfenster."""
    lon_min, lat_min, lon_max, lat_max = config.REGION_BBOX
    longitude = pd.to_numeric(source_df["longitude"], errors="coerce")
    latitude = pd.to_numeric(source_df["latitude"], errors="coerce")
    event_date = pd.to_datetime(source_df["date_start"], errors="coerce")

    in_box = longitude.between(lon_min, lon_max) & latitude.between(lat_min, lat_max)
    in_window = event_date >= pd.Timestamp(config.CONFLICT_START_DATE)
    return source_df.loc[in_box & in_window]


def build_events(scoped_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Baut die getypte Punktebene (WGS84) im Projekt-Schema der Konflikt-Events."""
    if scoped_df.empty:
        return gpd.GeoDataFrame(
            columns=["event_id", "event_date", "violence_type", "country",
                     "deaths", "latitude", "longitude", "geometry"],
            geometry="geometry", crs="EPSG:4326",
        )

    violence_code = pd.to_numeric(scoped_df["type_of_violence"], errors="coerce").astype("Int64")
    events_df = pd.DataFrame(
        {
            "event_id": scoped_df["id"].astype(str),
            "event_date": pd.to_datetime(scoped_df["date_start"], errors="coerce"),
            "violence_type": violence_code.map(config.UCDP_VIOLENCE_TYPES).fillna(""),
            "country": scoped_df["country"].fillna(""),
            "deaths": pd.to_numeric(scoped_df["best"], errors="coerce").fillna(0).astype("int64"),
            "latitude": pd.to_numeric(scoped_df["latitude"], errors="coerce"),
            "longitude": pd.to_numeric(scoped_df["longitude"], errors="coerce"),
        }
    ).dropna(subset=["latitude", "longitude"])

    events_df = events_df.drop_duplicates(subset="event_id")
    geometry = gpd.points_from_xy(events_df["longitude"], events_df["latitude"])
    events_gdf = gpd.GeoDataFrame(events_df, geometry=geometry, crs="EPSG:4326")
    return events_gdf.sort_values("event_date").reset_index(drop=True)


def run(*, refresh: bool = False) -> None:
    ingest_common.ensure_data_dirs()
    UCDP_DIR.mkdir(parents=True, exist_ok=True)

    if ingest_common.already_fetched(EVENTS_PARQUET) and not refresh:
        existing_gdf = gpd.read_parquet(EVENTS_PARQUET)
        print(f"UCDP uebersprungen, {len(existing_gdf)} Ereignisse bereits vorhanden (--refresh erzwingt neu).")
        return

    ingest_common.download_file(config.UCDP_GED_CSV_URL, GED_ZIP, refresh=refresh)
    ingest_common.download_file(config.UCDP_CANDIDATE_CSV_URL, CANDIDATE_CSV, refresh=refresh)

    ged_df = _filter_to_scope(_read_source(GED_ZIP, compression="zip"))
    candidate_df = _filter_to_scope(_read_source(CANDIDATE_CSV))
    print(f"  GED-Hauptdatensatz: {len(ged_df)} Ereignisse in Region+Fenster")
    print(f"  GED-Candidate:      {len(candidate_df)} Ereignisse in Region+Fenster")

    events_gdf = build_events(pd.concat([ged_df, candidate_df], ignore_index=True))
    events_gdf.to_parquet(EVENTS_PARQUET)
    print(f"UCDP-Ingest: {len(events_gdf)} Ereignisse ab {config.CONFLICT_START_DATE} -> {EVENTS_PARQUET.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Rohdaten und Parquet neu laden.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
