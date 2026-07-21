"""Stage 1, ingest OSM.

Reads the historic=* features via QuackOSM from the region's Geofabrik PBFs
into GeoParquet. The raw PBF is stored unchanged per country, so processing
can be repeated without fetching again.

Input:  Geofabrik PBF per country (config.COUNTRIES)
Output: RAW_DIR/osm/pbf/<country>.osm.pbf       (raw)
        RAW_DIR/osm/parquet/<country>_historic.parquet
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
    """Filter on all values of the historic=* tags (config.OSM_TAGS_HISTORIC)."""
    return {tag: True for tag in config.OSM_TAGS_HISTORIC}


def count_features(parquet_path: Path) -> int:
    """Counts the rows in the generated GeoParquet (cheap validation)."""
    return duckdb.sql(f"SELECT count(*) FROM read_parquet('{parquet_path.as_posix()}')").fetchone()[0]


def ingest_country(key: str, url: str, *, refresh: bool = False) -> Path:
    """Downloads a country's PBF and converts the historic=* features."""
    pbf_path = PBF_DIR / f"{key}.osm.pbf"
    ingest_common.download_file(url, pbf_path, refresh=refresh)

    result_path = PARQUET_DIR / f"{key}_historic.parquet"
    if ingest_common.already_fetched(result_path) and not refresh:
        print(f"  {key:12s} skipped, {count_features(result_path)} features already present")
        return result_path

    quackosm.convert_pbf_to_parquet(
        pbf_path,
        tags_filter=historic_tags_filter(),
        keep_all_tags=True,
        result_file_path=result_path,
        ignore_cache=refresh,
        verbosity_mode="silent",
    )
    print(f"  {key:12s} {count_features(result_path)} features -> {result_path.name}")
    return result_path


def run(*, refresh: bool = False, only: str | None = None) -> None:
    ingest_common.ensure_data_dirs()
    PBF_DIR.mkdir(parents=True, exist_ok=True)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    countries = config.COUNTRIES
    if only is not None:
        if only not in countries:
            raise SystemExit(f"Unknown country '{only}'. Known: {', '.join(countries)}")
        countries = {only: countries[only]}

    print(f"OSM ingest for {len(countries)} country/countries:")
    for key, (_iso, url) in countries.items():
        ingest_country(key, url, refresh=refresh)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Regenerate existing raw data and parquet.")
    parser.add_argument("--only", metavar="COUNTRY", help="Process only a single country (e.g. cyprus).")
    args = parser.parse_args()
    run(refresh=args.refresh, only=args.only)


if __name__ == "__main__":
    main()
