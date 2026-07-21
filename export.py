"""Stage 3, export.

Packages the finished result table (site_scores, from process.py) into the
formats the app reads. This stage computes nothing new; it writes the
committed runtime artefacts.

Currently implemented: sites.geojson, the scored UNESCO sites as a
FeatureCollection (point geometry, WGS84) with threat score, class, inverted
traffic-light colour (high = red) and a metadata block. The app renders the
threat layer and the detail sheet from this.

The basemap is not generated here: roads, water, and labels come from
MapTiler at runtime (see app/lib/basemap.dart); the heritage context (OSM,
Pleiades) is its own, separate export (export_buildings.py, export_context.py).
This stage only writes the sites GeoJSON.

Input:  table site_scores in config.DUCKDB_PATH
Output: config.SITES_GEOJSON_PATH
"""

from __future__ import annotations

import argparse
import json
from datetime import date

import duckdb

import config
import ingest_common

SCORES_TABLE: str = "site_scores"

# Order of the properties per feature: identity, then score breakdown, then
# presentation helpers. Deliberately explicit instead of SELECT *, so the
# app schema stays stable.
FEATURE_COLUMNS: tuple[str, ...] = (
    "site_id", "name", "country_iso2", "category", "http_url",
    "in_danger", "warning_level", "conflict_count", "eq_level", "fl_level",
    "score_in_danger", "score_travel", "score_conflict", "score_natural",
    "total_score", "threat_level",
)


def _metadata(*, site_count: int, conflict_available: bool) -> dict[str, object]:
    """Metadata block for the FeatureCollection."""
    return {
        "title": "Heritage at Risk: threat score per UNESCO World Heritage site (MENA)",
        "generated": date.today().isoformat(),
        "site_count": site_count,
        "score_max": config.SCORE_MAX,
        "score_components": {
            "in_danger": {"weight": config.SCORE_WEIGHT_UNESCO_IN_DANGER, "source": "UNESCO World Heritage Centre"},
            "travel_warning": {"weight": config.SCORE_WEIGHT_TRAVEL_WARNING, "source": "German Federal Foreign Office"},
            "conflict": {"weight": config.SCORE_WEIGHT_CONFLICT,
                         "source": "UCDP GED (Uppsala Conflict Data Program)",
                         "method": "log-scaled subscore of the conflict events within the radius",
                         "radius_km": config.CONFLICT_RADIUS_KM},
            "natural_hazard": {"weight": config.SCORE_WEIGHT_NATURAL_HAZARD,
                               "source": "ThinkHazard! (World Bank GFDRR)",
                               "hazards": ["earthquake", "river flood"], "method": "max of EQ/FL level"},
        },
        "threat_levels": [
            {"level": level, "label": config.THREAT_LEVEL_LABELS[level],
             "color": config.THREAT_LEVEL_COLORS[level], "max_score": upper}
            for level, upper in config.THREAT_LEVEL_BREAKS
        ],
        "crs": "urn:ogc:def:crs:OGC:1.3:CRS84",
        "license": "Sources under their respective licences; derived artefact for an academic project.",
        "contact": config.USER_AGENT,
        "notes": (
            f"Threat score 0 to {config.SCORE_MAX} from four weighted sources. "
            + ("" if conflict_available
               else "Conflict component currently 0 (ucdp_events.parquet missing). ")
            + "Danger is encoded not only by colour but also via threat_level/label (accessibility)."
        ),
    }


def _feature(row: dict[str, object]) -> dict[str, object]:
    """Builds a GeoJSON feature from a site_scores row."""
    threat_level = str(row["threat_level"])
    properties = {column: row[column] for column in FEATURE_COLUMNS}
    properties["threat_label"] = config.THREAT_LEVEL_LABELS[threat_level]
    properties["threat_color"] = config.THREAT_LEVEL_COLORS[threat_level]
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
        "properties": properties,
    }


def export_sites_geojson(con: duckdb.DuckDBPyConnection, *, conflict_available: bool) -> int:
    """Writes site_scores as a GeoJSON FeatureCollection to config.SITES_GEOJSON_PATH."""
    columns = ", ".join((*FEATURE_COLUMNS, "latitude", "longitude"))
    cursor = con.execute(f"SELECT {columns} FROM {SCORES_TABLE} ORDER BY total_score DESC, site_id")
    field_names = [description[0] for description in cursor.description]
    rows = [dict(zip(field_names, values)) for values in cursor.fetchall()]

    feature_collection = {
        "type": "FeatureCollection",
        "metadata": _metadata(site_count=len(rows), conflict_available=conflict_available),
        "features": [_feature(row) for row in rows],
    }

    config.SITES_GEOJSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.SITES_GEOJSON_PATH.write_text(
        json.dumps(feature_collection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(rows)


def run() -> None:
    ingest_common.ensure_data_dirs()

    if not ingest_common.already_fetched(config.DUCKDB_PATH):
        raise RuntimeError(f"No result database ({config.DUCKDB_PATH}). Run process.py first.")

    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    try:
        tables = {name for (name,) in con.execute("SHOW TABLES").fetchall()}
        if SCORES_TABLE not in tables:
            raise RuntimeError(f"Table {SCORES_TABLE} missing. Run process.py first.")
        conflict_available = bool(con.execute(
            f"SELECT COUNT(*) FROM {SCORES_TABLE} WHERE conflict_count > 0"
        ).fetchone()[0])
        count = export_sites_geojson(con, conflict_available=conflict_available)
    finally:
        con.close()

    print(f"export: {count} sites -> {config.SITES_GEOJSON_PATH.name} ({config.SITES_GEOJSON_PATH})")
    print("  Basemap: MapTiler at runtime, not generated in this stage.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
