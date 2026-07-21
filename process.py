"""Stage 2, processing in DuckDB.

The scientific core of the pipeline. The spatial extension merges the
sources and computes the threat score (0 to config.SCORE_MAX) per UNESCO
site from four independent components:

  1. UNESCO in-danger flag    (weight 3, binary)          reference/unesco_in_danger.csv
  2. Travel advisory level 0-2 (weight 3, linear)          German Federal Foreign Office (CSV)
  3. Conflict                 (weight 3, log-scaled)       UCDP GED within CONFLICT_RADIUS_KM
  4. Natural hazard EQ+FL     (weight 1, levels)           ThinkHazard! (reference/natural_hazard.csv)

The natural hazard component takes the maximum of the earthquake and river
flood level per site (World Bank ThinkHazard!, mapped to [0,1] via
config.NATURAL_HAZARD_LEVEL_SCORES) and scales it with the weight: a site is
at risk if it is strongly exposed to either of the two hazards.

The conflict component counts the UCDP GED conflict events within the
geographic radius per site (ST_Distance_Sphere on ST_Point(lon, lat),
latitude/longitude instead of WKB), log-scales it to [0,1] and scales it
with the conflict weight. Known limitation: UCDP only counts events with at
least 1 fatality.

Source-tolerant: if ucdp_events.parquet is missing, the conflict share
counts as 0 for all sites. The rest still computes. As soon as the file
exists, it is picked up without any code change.

Input:  RAW_DIR/unesco/unesco_sites.parquet, reference/unesco_in_danger.csv,
        RAW_DIR/auswaertiges_amt/travel_warning_levels.csv, reference/natural_hazard.csv,
        optional RAW_DIR/ucdp/ucdp_events.parquet
Output: table site_scores in config.DUCKDB_PATH
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
    """Checks the mandatory inputs upfront (the conflict events are optional)."""
    required = {
        "UNESCO sites": UNESCO_SITES_PARQUET,
        "UNESCO in-danger": config.UNESCO_IN_DANGER_PATH,
        "Travel advisory levels": AA_WARNINGS_CSV,
        "Natural hazards": config.NATURAL_HAZARD_PATH,
    }
    missing = [f"{label} ({path})" for label, path in required.items()
               if not ingest_common.already_fetched(path)]
    if missing:
        raise RuntimeError("Missing inputs for processing: " + "; ".join(missing))


def _threat_level_case(score_column: str) -> str:
    """Builds the CASE expression for the threat level classes from config.THREAT_LEVEL_BREAKS."""
    *lower_breaks, (top_label, _) = config.THREAT_LEVEL_BREAKS
    whens = " ".join(
        f"WHEN {score_column} <= {upper} THEN '{label}'" for label, upper in lower_breaks
    )
    return f"CASE {whens} ELSE '{top_label}' END"


def _points_relation(parquet_path: Path) -> str:
    """SQL source of a point layer, empty (but type-correct) if the file is missing."""
    if ingest_common.already_fetched(parquet_path):
        return f"SELECT latitude, longitude FROM read_parquet('{parquet_path.as_posix()}')"
    return "SELECT NULL::DOUBLE AS latitude, NULL::DOUBLE AS longitude WHERE FALSE"


def _hazard_score_case(level_column: str) -> str:
    """Builds the CASE expression level -> partial score [0,1] from config.NATURAL_HAZARD_LEVEL_SCORES."""
    whens = " ".join(
        f"WHEN '{level}' THEN {score}" for level, score in config.NATURAL_HAZARD_LEVEL_SCORES.items()
    )
    return f"CAST(CASE UPPER({level_column}) {whens} ELSE 0 END AS DOUBLE)"


def _build_score_sql() -> str:
    """Assembles the complete score query as a CREATE OR REPLACE TABLE."""
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
    """Prints a compact summary of the computed score."""
    total = con.execute(f"SELECT COUNT(*) FROM {SCORES_TABLE}").fetchone()[0]
    print(f"process: {total} sites scored, score 0 to {config.SCORE_MAX} -> table {SCORES_TABLE}")
    if not conflict_available:
        print("  Note: no ucdp_events.parquet, conflict component 0 for all sites "
              "(run ingest_ucdp.py first).")

    by_level = con.execute(
        f"SELECT threat_level, COUNT(*) FROM {SCORES_TABLE} GROUP BY threat_level ORDER BY MIN(total_score)"
    ).fetchall()
    print("  Threat level:", ", ".join(f"{level}={count}" for level, count in by_level))

    in_danger = con.execute(f"SELECT COUNT(*) FROM {SCORES_TABLE} WHERE in_danger").fetchone()[0]
    high_hazard = con.execute(
        f"SELECT COUNT(*) FROM {SCORES_TABLE} WHERE eq_level = 'HIG' OR fl_level = 'HIG'"
    ).fetchone()[0]
    print(f"  In-danger: {in_danger}, natural hazard high (EQ or FL = HIG): {high_hazard}")

    if conflict_available:
        with_conflict, max_count = con.execute(
            f"SELECT COUNT(*) FILTER (WHERE conflict_count > 0), MAX(conflict_count) FROM {SCORES_TABLE}"
        ).fetchone()
        print(f"  Conflict (UCDP GED): {with_conflict} sites with events within the "
              f"{config.CONFLICT_RADIUS_KM:.0f} km radius, max {max_count} per site.")

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
                        help="Recompute the score (currently always a full, cheap run).")
    args = parser.parse_args()
    run(recompute=args.recompute)


if __name__ == "__main__":
    main()
