"""Stufe 2, Verarbeitung in DuckDB.

Die wissenschaftliche Mitte der Pipeline. Die Spatial Extension fuehrt die
Quellen zusammen und berechnet je UNESCO-Site den Threat Score (0 bis
config.SCORE_MAX) aus vier unabhaengigen Komponenten:

  1. UNESCO In-Danger-Flag   (Gewicht 3, binaer)        reference/unesco_in_danger.csv
  2. Reisewarnstufe 0-2      (Gewicht 3, linear)        Auswaertiges Amt (CSV)
  3. Konflikt               (Gewicht 3, log-skaliert)   UCDP GED im CONFLICT_RADIUS_KM
  4. Naturgefahr EQ+FL       (Gewicht 2, Stufen)        ThinkHazard! (reference/natural_hazard.csv)

Die Naturgefahr nimmt das Maximum aus Erdbeben- und Flusshochwasser-Stufe je Site
(ThinkHazard! der Weltbank, ueber config.NATURAL_HAZARD_LEVEL_SCORES auf [0,1]
abgebildet) und skaliert es mit dem Gewicht: eine Site ist gefaehrdet, wenn sie
EINER der beiden Gefahren stark ausgesetzt ist. Diese Komponente loest die
WMF-Watch-Liste ab, die in der Region strukturell nie eine WHS flaggte
(PROJECT_CONTEXT.md, Bewusst verworfene Ansaetze).

Die Konflikt-Komponente zaehlt die toedlichen UCDP-GED-Ereignisse im geografischen
Radius je Site (ST_Distance_Sphere auf ST_Point(lon, lat), latitude/longitude statt
WKB), log-skaliert auf [0,1] und mit dem Konflikt-Gewicht skaliert.

Quellen-tolerant: fehlt ucdp_events.parquet, zaehlt der Konflikt-Anteil fuer alle
Sites 0. Der Rest rechnet durch. Sobald die Datei existiert, faellt sie ohne
Codeaenderung ein.

Input:  RAW_DIR/unesco/unesco_sites.parquet, reference/unesco_in_danger.csv,
        RAW_DIR/auswaertiges_amt/travel_warning_levels.csv, reference/natural_hazard.csv,
        optional RAW_DIR/ucdp/ucdp_events.parquet
Output: Tabelle site_scores in config.DUCKDB_PATH
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

import config
import ingest_common

UNESCO_SITES_PARQUET: Path = config.RAW_DIR / "unesco" / "unesco_sites.parquet"
AA_WARNINGS_CSV: Path = config.RAW_DIR / "auswaertiges_amt" / "travel_warning_levels.csv"
CONFLICT_EVENTS_PARQUET: Path = config.RAW_DIR / "ucdp" / "ucdp_events.parquet"

SCORES_TABLE: str = "site_scores"


def _require_inputs() -> None:
    """Prueft die zwingenden Eingaben vorab (die Konflikt-Events sind optional)."""
    required = {
        "UNESCO-Sites": UNESCO_SITES_PARQUET,
        "UNESCO In-Danger": config.UNESCO_IN_DANGER_PATH,
        "Reisewarnstufen": AA_WARNINGS_CSV,
        "Naturgefahren": config.NATURAL_HAZARD_PATH,
    }
    missing = [f"{label} ({path})" for label, path in required.items()
               if not ingest_common.already_fetched(path)]
    if missing:
        raise RuntimeError("Fehlende Eingaben fuer die Verarbeitung: " + "; ".join(missing))


def _threat_level_case(score_column: str) -> str:
    """Baut den CASE-Ausdruck der Threat-Level-Klassen aus config.THREAT_LEVEL_BREAKS."""
    *lower_breaks, (top_label, _) = config.THREAT_LEVEL_BREAKS
    whens = " ".join(
        f"WHEN {score_column} <= {upper} THEN '{label}'" for label, upper in lower_breaks
    )
    return f"CASE {whens} ELSE '{top_label}' END"


def _points_relation(parquet_path: Path) -> str:
    """SQL-Quelle einer Punktebene, leer (aber typkorrekt) wenn die Datei fehlt."""
    if ingest_common.already_fetched(parquet_path):
        return f"SELECT latitude, longitude FROM read_parquet('{parquet_path.as_posix()}')"
    return "SELECT NULL::DOUBLE AS latitude, NULL::DOUBLE AS longitude WHERE FALSE"


def _hazard_score_case(level_column: str) -> str:
    """Baut den CASE-Ausdruck Stufe -> Teilscore [0,1] aus config.NATURAL_HAZARD_LEVEL_SCORES."""
    whens = " ".join(
        f"WHEN '{level}' THEN {score}" for level, score in config.NATURAL_HAZARD_LEVEL_SCORES.items()
    )
    return f"CAST(CASE UPPER({level_column}) {whens} ELSE 0 END AS DOUBLE)"


def _build_score_sql() -> str:
    """Setzt die komplette Score-Abfrage als CREATE OR REPLACE TABLE zusammen."""
    conflict_radius_m = config.CONFLICT_RADIUS_KM * 1000.0

    return f"""
    CREATE OR REPLACE TABLE {SCORES_TABLE} AS
    WITH sites AS (
        SELECT site_id, name, country_iso2, category, http_url, latitude, longitude
        FROM read_parquet('{UNESCO_SITES_PARQUET.as_posix()}')
    ),
    in_danger AS (
        SELECT DISTINCT site_id FROM read_csv_auto('{config.UNESCO_IN_DANGER_PATH.as_posix()}')
    ),
    warnings AS (
        SELECT country_iso2, warning_level
        FROM read_csv_auto('{AA_WARNINGS_CSV.as_posix()}')
    ),
    hazard AS (
        SELECT site_id,
               UPPER(eq_level) AS eq_level,
               UPPER(fl_level) AS fl_level
        FROM read_csv_auto('{config.NATURAL_HAZARD_PATH.as_posix()}')
    ),
    events AS (
        {_points_relation(CONFLICT_EVENTS_PARQUET)}
    ),
    conflict AS (
        SELECT s.site_id, COUNT(e.longitude) AS conflict_count
        FROM sites s
        LEFT JOIN events e
            ON ST_Distance_Sphere(ST_Point(s.longitude, s.latitude),
                                  ST_Point(e.longitude, e.latitude)) <= {conflict_radius_m}
        GROUP BY s.site_id
    ),
    scored AS (
        SELECT
            s.site_id, s.name, s.country_iso2, s.category, s.http_url,
            s.latitude, s.longitude,
            (s.site_id IN (SELECT site_id FROM in_danger)) AS in_danger,
            COALESCE(w.warning_level, 0) AS warning_level,
            c.conflict_count,
            COALESCE(h.eq_level, 'NDA') AS eq_level,
            COALESCE(h.fl_level, 'NDA') AS fl_level,
            CASE WHEN s.site_id IN (SELECT site_id FROM in_danger)
                 THEN {config.SCORE_WEIGHT_UNESCO_IN_DANGER} ELSE 0 END AS score_in_danger,
            COALESCE(w.warning_level, 0) * 1.0 / {config.AA_WARNING_LEVEL_MAX}
                * {config.SCORE_WEIGHT_TRAVEL_WARNING} AS score_travel,
            LEAST(LN(1 + c.conflict_count) / LN(1 + {config.CONFLICT_EVENTS_FOR_FULL_SCORE}), 1.0)
                * {config.SCORE_WEIGHT_CONFLICT} AS score_conflict,
            GREATEST({_hazard_score_case("h.eq_level")}, {_hazard_score_case("h.fl_level")})
                * {config.SCORE_WEIGHT_NATURAL_HAZARD} AS score_natural
        FROM sites s
        LEFT JOIN warnings w ON s.country_iso2 = w.country_iso2
        LEFT JOIN conflict c ON s.site_id = c.site_id
        LEFT JOIN hazard h ON s.site_id = h.site_id
    )
    SELECT
        *,
        ROUND(score_in_danger + score_travel + score_conflict + score_natural, 2) AS total_score,
        {_threat_level_case("(score_in_danger + score_travel + score_conflict + score_natural)")}
            AS threat_level
    FROM scored
    ORDER BY total_score DESC, site_id
    """


def _report(con: duckdb.DuckDBPyConnection, *, conflict_available: bool) -> None:
    """Druckt eine kompakte Zusammenfassung des berechneten Scores."""
    total = con.execute(f"SELECT COUNT(*) FROM {SCORES_TABLE}").fetchone()[0]
    print(f"process: {total} Sites bewertet, Score 0 bis {config.SCORE_MAX} -> Tabelle {SCORES_TABLE}")
    if not conflict_available:
        print("  Hinweis: kein ucdp_events.parquet, Konflikt-Komponente fuer alle Sites 0 "
              "(zuerst ingest_ucdp.py laufen lassen, siehe PROJECT_CONTEXT.md).")

    by_level = con.execute(
        f"SELECT threat_level, COUNT(*) FROM {SCORES_TABLE} GROUP BY threat_level ORDER BY MIN(total_score)"
    ).fetchall()
    print("  Threat-Level:", ", ".join(f"{level}={count}" for level, count in by_level))

    in_danger = con.execute(f"SELECT COUNT(*) FROM {SCORES_TABLE} WHERE in_danger").fetchone()[0]
    high_hazard = con.execute(
        f"SELECT COUNT(*) FROM {SCORES_TABLE} WHERE eq_level = 'HIG' OR fl_level = 'HIG'"
    ).fetchone()[0]
    print(f"  In-Danger: {in_danger}, Naturgefahr hoch (EQ oder FL = HIG): {high_hazard}")

    if conflict_available:
        with_conflict, max_count = con.execute(
            f"SELECT COUNT(*) FILTER (WHERE conflict_count > 0), MAX(conflict_count) FROM {SCORES_TABLE}"
        ).fetchone()
        print(f"  Konflikt (UCDP GED): {with_conflict} Sites mit Ereignissen im "
              f"{config.CONFLICT_RADIUS_KM:.0f}-km-Radius, max {max_count} je Site.")

    top = con.execute(
        f"SELECT name, country_iso2, total_score, threat_level FROM {SCORES_TABLE} LIMIT 5"
    ).fetchall()
    print("  Top 5:")
    for name, iso, score, level in top:
        print(f"    {score:>5}  {level:<6}  {iso}  {name}")


def run(*, recompute: bool = False) -> None:
    ingest_common.ensure_data_dirs()
    _require_inputs()

    conflict_available = ingest_common.already_fetched(CONFLICT_EVENTS_PARQUET)
    config.DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(config.DUCKDB_PATH))
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute(_build_score_sql())
        _report(con, conflict_available=conflict_available)
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recompute", action="store_true",
                        help="Score neu rechnen (aktuell stets voller, guenstiger Durchlauf).")
    args = parser.parse_args()
    run(recompute=args.recompute)


if __name__ == "__main__":
    main()
