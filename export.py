"""Stufe 3, Export.

Verpackt die fertige Ergebnistabelle (site_scores, aus process.py) in die
Formate, die die App liest. Diese Stufe rechnet nichts Neues, sie schreibt die
committeten Laufzeit-Artefakte.

Aktuell implementiert: sites.geojson, die bewerteten UNESCO-Sites als
FeatureCollection (Punktgeometrie, WGS84) mit Threat Score, Klasse, invertierter
Ampel-Farbe (hoch = rot, GEOSPATIAL_DESIGN_GUIDE.md) und einem Metadatenblock.
Die App rendert daraus die Threat-Ebene und das Detail-Sheet.

Die Basiskarte (config.BASEMAP_PMTILES_PATH) wird NICHT hier erzeugt: Strassen,
Wasser, Labels und Gebaeude kommen als fertige Provider-Basemap (Protomaps/
OpenFreeMap, MapLibre-nativ), der Heritage-Kontext (OSM historic, Pleiades) ist ein
eigenes, optionales Overlay (siehe PROJECT_CONTEXT.md). Diese Stufe schreibt nur das
Sites-GeoJSON.

Input:  Tabelle site_scores in config.DUCKDB_PATH
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

# Reihenfolge der Properties je Feature: Identitaet, dann Score-Zerlegung, dann
# Darstellungshilfen. Bewusst explizit statt SELECT *, damit das App-Schema stabil bleibt.
FEATURE_COLUMNS: tuple[str, ...] = (
    "site_id", "name", "country_iso2", "category", "http_url",
    "in_danger", "warning_level", "conflict_count", "eq_level", "fl_level",
    "score_in_danger", "score_travel", "score_conflict", "score_natural",
    "total_score", "threat_level",
)


def _metadata(*, site_count: int, conflict_available: bool) -> dict[str, object]:
    """Metadatenblock fuer das FeatureCollection (GEOSPATIAL_DESIGN_GUIDE.md, Abschnitt 7)."""
    return {
        "title": "Heritage at Risk: Threat Score je UNESCO-Welterbestaette (MENA)",
        "generated": date.today().isoformat(),
        "site_count": site_count,
        "score_max": config.SCORE_MAX,
        "score_components": {
            "in_danger": {"weight": config.SCORE_WEIGHT_UNESCO_IN_DANGER, "source": "UNESCO World Heritage Centre"},
            "travel_warning": {"weight": config.SCORE_WEIGHT_TRAVEL_WARNING, "source": "Auswaertiges Amt"},
            "conflict": {"weight": config.SCORE_WEIGHT_CONFLICT,
                         "source": "UCDP GED (Uppsala Conflict Data Program)",
                         "method": "log-skalierter Subscore toedlicher Ereignisse im Radius",
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
        "license": "Quellen unter ihren jeweiligen Lizenzen; abgeleitetes Artefakt fuer ein akademisches Projekt.",
        "contact": config.USER_AGENT,
        "notes": (
            f"Threat Score 0 bis {config.SCORE_MAX} aus vier gewichteten Quellen. "
            + ("" if conflict_available
               else "Konflikt-Komponente aktuell 0 (ucdp_events.parquet fehlt, siehe PROJECT_CONTEXT.md). ")
            + "Gefaehrdung ist nicht nur farblich, sondern auch ueber threat_level/Label kodiert (Accessibility)."
        ),
    }


def _feature(row: dict[str, object]) -> dict[str, object]:
    """Baut ein GeoJSON-Feature aus einer site_scores-Zeile."""
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
    """Schreibt site_scores als GeoJSON-FeatureCollection nach config.SITES_GEOJSON_PATH."""
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
        raise RuntimeError(f"Keine Ergebnisdatenbank ({config.DUCKDB_PATH}). Zuerst process.py laufen lassen.")

    con = duckdb.connect(str(config.DUCKDB_PATH), read_only=True)
    try:
        tables = {name for (name,) in con.execute("SHOW TABLES").fetchall()}
        if SCORES_TABLE not in tables:
            raise RuntimeError(f"Tabelle {SCORES_TABLE} fehlt. Zuerst process.py laufen lassen.")
        conflict_available = bool(con.execute(
            f"SELECT COUNT(*) FROM {SCORES_TABLE} WHERE conflict_count > 0"
        ).fetchone()[0])
        count = export_sites_geojson(con, conflict_available=conflict_available)
    finally:
        con.close()

    print(f"export: {count} Sites -> {config.SITES_GEOJSON_PATH.name} ({config.SITES_GEOJSON_PATH})")
    print("  Basiskarte: Provider-Basemap (Protomaps/OpenFreeMap), nicht in dieser Stufe erzeugt.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
