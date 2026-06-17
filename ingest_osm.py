"""Stufe 1, Ingest OSM.

Liest die historic=* Features via QuackOSM aus den Geofabrik-PBF der Region in
GeoParquet. Die rohe PBF wird je Land unveraendert abgelegt, damit die
Verarbeitung ohne erneuten Abruf wiederholbar ist.

Input:  Geofabrik-PBF je Land (config.COUNTRIES)
Output: RAW_DIR/osm/pbf/<land>.osm.pbf       (roh)
        RAW_DIR/osm/parquet/<land>_historic.parquet
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import quackosm

import config
import ingest_common

OSM_DIR: Path = config.RAW_DIR / "osm"
PBF_DIR: Path = OSM_DIR / "pbf"
PARQUET_DIR: Path = OSM_DIR / "parquet"


def historic_tags_filter() -> dict[str, bool]:
    """Filter auf alle Werte der historic=* Tags (config.OSM_TAGS_HISTORIC)."""
    return {tag: True for tag in config.OSM_TAGS_HISTORIC}


def count_features(parquet_path: Path) -> int:
    """Zaehlt die Zeilen im erzeugten GeoParquet (billige Validierung)."""
    return duckdb.sql(f"SELECT count(*) FROM read_parquet('{parquet_path.as_posix()}')").fetchone()[0]


def ingest_country(key: str, url: str, *, refresh: bool = False) -> Path:
    """Laedt die PBF eines Landes und konvertiert die historic=* Features."""
    pbf_path = PBF_DIR / f"{key}.osm.pbf"
    ingest_common.download_file(url, pbf_path, refresh=refresh)

    result_path = PARQUET_DIR / f"{key}_historic.parquet"
    if ingest_common.already_fetched(result_path) and not refresh:
        print(f"  {key:12s} uebersprungen, {count_features(result_path)} Features bereits vorhanden")
        return result_path

    quackosm.convert_pbf_to_parquet(
        pbf_path,
        tags_filter=historic_tags_filter(),
        keep_all_tags=True,
        result_file_path=result_path,
        ignore_cache=refresh,
        verbosity_mode="silent",
    )
    print(f"  {key:12s} {count_features(result_path)} Features -> {result_path.name}")
    return result_path


def run(*, refresh: bool = False, only: str | None = None) -> None:
    ingest_common.ensure_data_dirs()
    PBF_DIR.mkdir(parents=True, exist_ok=True)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    countries = config.COUNTRIES
    if only is not None:
        if only not in countries:
            raise SystemExit(f"Unbekanntes Land '{only}'. Bekannt: {', '.join(countries)}")
        countries = {only: countries[only]}

    print(f"OSM-Ingest fuer {len(countries)} Land/Laender:")
    for key, (_iso, url) in countries.items():
        ingest_country(key, url, refresh=refresh)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Vorhandene Rohdaten und Parquet neu erzeugen.")
    parser.add_argument("--only", metavar="LAND", help="Nur ein einzelnes Land verarbeiten (z. B. cyprus).")
    args = parser.parse_args()
    run(refresh=args.refresh, only=args.only)


if __name__ == "__main__":
    main()
