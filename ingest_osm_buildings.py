"""Stufe 1, Ingest OSM-Gebaeude (Karten-Kontext).

Liest building=* Features via QuackOSM aus den schon vorhandenen Geofabrik-PBF
der Region in GeoParquet. Anders als ingest_osm.py (historic=*, region-weit) wird
die Extraktion raeumlich auf die Umgebung der UNESCO-Sites vorgefiltert: ein
geometry_filter (Union grosszuegiger Puffer um die Site-Punkte) sorgt dafuer, dass
QuackOSM nur Gebaeude nahe der Sites liest. Gebaeude in dichten Altstaedten sind
sehr zahlreich, region-weit waeren es Millionen (siehe PROJECT_CONTEXT.md).

Diese Ebene ist reiner Karten-Kontext (Footprints + Dichte-Schummerung), NICHT
Teil des Threat Scores. Die praezise Beschneidung auf den Site-Radius und die
Dichte-Aggregation passieren in export_buildings.py.

Input:  RAW_DIR/osm/pbf/<land>.osm.pbf (von ingest_osm.py), unesco_sites.parquet
Output: RAW_DIR/osm/parquet/<land>_buildings.parquet
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

# Grober Vorfilter-Puffer um jede Site (Grad). Bewusst etwas groesser als der
# spaetere praezise Clip-Radius (BUILDINGS_NEAR_SITES_KM), damit am Rand nichts
# fehlt; die exakte Beschneidung macht export_buildings.py per ST_Distance_Sphere.
# 1 Breitengrad ~ 111 km, mit 40 % Reserve auf den Clip-Radius.
_PREFILTER_BUFFER_DEG: float = config.BUILDINGS_NEAR_SITES_KM / 111.0 * 1.4


def buildings_tags_filter() -> dict[str, bool]:
    """Filter auf alle Werte der building=* Tags (config.OSM_TAGS_BUILDINGS)."""
    return {tag: True for tag in config.OSM_TAGS_BUILDINGS}


def site_buffer_filter() -> MultiPolygon:
    """Union grosszuegiger Puffer um alle Site-Punkte als raeumlicher Vorfilter."""
    if not ingest_common.already_fetched(SITES_PARQUET):
        raise RuntimeError(f"UNESCO-Sites fehlen ({SITES_PARQUET}). Zuerst ingest_unesco.py laufen lassen.")
    sites = gpd.read_parquet(SITES_PARQUET)
    sites = sites[sites["longitude"].notna() & sites["latitude"].notna()]
    points = gpd.points_from_xy(sites["longitude"], sites["latitude"])
    buffers = [point.buffer(_PREFILTER_BUFFER_DEG) for point in points]
    union = unary_union(buffers)
    return union if union.geom_type == "MultiPolygon" else MultiPolygon([union])


def count_features(parquet_path: Path) -> int:
    """Zaehlt die Zeilen im erzeugten GeoParquet (billige Validierung)."""
    return duckdb.sql(f"SELECT count(*) FROM read_parquet('{parquet_path.as_posix()}')").fetchone()[0]


def ingest_country(key: str, geometry_filter: MultiPolygon, *, refresh: bool = False) -> Path | None:
    """Konvertiert die building=* Features eines Landes im Site-Umkreis."""
    pbf_path = PBF_DIR / f"{key}.osm.pbf"
    if not ingest_common.already_fetched(pbf_path):
        print(f"  {key:12s} uebersprungen, PBF fehlt (zuerst ingest_osm.py laufen lassen)")
        return None

    result_path = PARQUET_DIR / f"{key}_buildings.parquet"
    if ingest_common.already_fetched(result_path) and not refresh:
        print(f"  {key:12s} uebersprungen, {count_features(result_path)} Gebaeude bereits vorhanden")
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
    print(f"  {key:12s} {count_features(result_path)} Gebaeude -> {result_path.name}")
    return result_path


def run(*, refresh: bool = False, only: str | None = None) -> None:
    ingest_common.ensure_data_dirs()
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    countries = config.COUNTRIES
    if only is not None:
        if only not in countries:
            raise SystemExit(f"Unbekanntes Land '{only}'. Bekannt: {', '.join(countries)}")
        countries = {only: countries[only]}

    geometry_filter = site_buffer_filter()
    print(f"OSM-Gebaeude-Ingest fuer {len(countries)} Land/Laender (Filter: {config.BUILDINGS_NEAR_SITES_KM} km um Sites):")
    for key in countries:
        ingest_country(key, geometry_filter, refresh=refresh)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Vorhandene Rohdaten und Parquet neu erzeugen.")
    parser.add_argument("--only", metavar="LAND", help="Nur ein einzelnes Land verarbeiten (z. B. cyprus).")
    args = parser.parse_args()
    run(refresh=args.refresh, only=args.only)


if __name__ == "__main__":
    main()
