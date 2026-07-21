"""Stage 3, export of the heritage context layer.

Writes the thematic overlay layer that the app shows underneath the scored
sites (detail when zooming in): Pleiades (ancient places) as a compact
GeoJSON artefact, point geometry in CRS84.

Unlike sites.geojson (score layer), this layer carries no score; it is
visual context. It is clipped to the vicinity of the scored sites (only
places within the CONTEXT_NEAR_SITES_KM radius of a UNESCO site). Rationale:
the app shows context only where you zoom in (you navigate from site to
site), not on empty terrain. This keeps the artefact small (region-wide it
would be 13,452 places) and focuses it on what's relevant.

Pleiades places that form a name duplicate of a nearby UNESCO site (many
World Heritage sites are themselves ancient places: Palmyra, Babylon,
Damascus ...) are dropped, so that two markers don't show the same site.
Deliberately only on name identity, not by radius (details at
DEDUP_NEAR_SITES_M below).

OSM historic was dropped again as a context layer (too dense/noisy, Pleiades
suffices; see PROJECT_CONTEXT.md, Deliberately dropped approaches).

Input:  RAW_DIR/pleiades/pleiades_places.parquet, RAW_DIR/unesco/unesco_sites.parquet
Output: config.ARTIFACTS_DIR/pleiades.geojson
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from pathlib import Path

import duckdb

import config
import ingest_common

PLEIADES_PARQUET: Path = config.RAW_DIR / "pleiades" / "pleiades_places.parquet"
SITES_PARQUET: Path = config.RAW_DIR / "unesco" / "unesco_sites.parquet"

PLEIADES_GEOJSON: Path = config.ARTIFACTS_DIR / "pleiades.geojson"

# Only context within the vicinity of the scored sites (rationale in the module docstring).
CONTEXT_NEAR_SITES_KM: float = 15.0

COORD_PRECISION: int = 5  # ~1 m, enough for a context layer and saves file size

# Pleiades duplicate of a UNESCO site: many World Heritage sites are
# themselves ancient places and therefore also appear in Pleiades (Palmyra,
# Petra, Babylon ...). If a Pleiades point lies near a UNESCO site and
# carries the same name, it is a duplicate marker for the same site; then
# the Pleiades point is dropped (the scored site wins). Deliberately only on
# name identity, not by radius: around a site there are many independent
# ancient places (Babylon's gates/temples, Assur archives) that should
# remain as context.
DEDUP_NEAR_SITES_M: float = 2000.0  # name comparison only for plausibly-same places
DEDUP_FUZZY_RATIO: float = 0.85     # transliteration variants (Bisotun~Bisutun)

# UNESCO boilerplate words that are not part of the actual place name.
_UNESCO_LEAD = re.compile(
    r"^(site of|ancient city of|ancient town of|ancient village[s]? of|ancient|"
    r"historic town of|historic city of|historic|old city of|old town of|"
    r"city of|town of|necropolis of|caves of|biblical tels)\s+",
)


def _norm_name(s: str) -> str:
    """Lowercases, folds diacritics, reduces to [a-z0-9]+."""
    decomposed = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


# Placeholder titles that Pleiades assigns to unnamed/unresolved places; dropped.
_PLACEHOLDER_TITLES = re.compile(r"^(unknown|untitled|unnamed)\b", re.I)


def _ascii_fold_title(title: str) -> str:
    """Folds diacritics but keeps upper/lower case and word boundaries.

    Unlike _norm_name (which lowercases and breaks apart for comparison),
    the name stays readable: "Arbela" from "Arbela", "Abu Fanduwa" from "Abu
    Fanduwa", "Al-Hilah" from "Al-Hilah". Special characters that cannot be
    decomposed (Ayn/Hamza modifiers) are then discarded as non-ASCII.
    """
    decomposed = unicodedata.normalize("NFKD", title)
    folded = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_only = folded.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_only).strip()


# Pleiades place-type slugs mapped to readable labels. What's missing here
# gets generically prettified (hyphens to spaces, first letter capitalized).
_TYPE_LABELS: dict[str, str] = {
    "archive-repository": "Archive/Repository",
    "architecturalcomplex": "Architectural complex",
    "settlement-modern": "Modern settlement",
    "production": "Production site",
    "urban": "Urban area",
    "findspot": "Find spot",
    "water-inland": "Inland water",
    "water-open": "Open water",
}


def _clean_types(raw_types: str) -> str:
    """Makes Pleiades type slugs readable: strip numeric suffix, drop 'unlocated', map."""
    labels: list[str] = []
    for token in re.split(r"[;,]", raw_types):
        slug = re.sub(r"-\d+$", "", token.strip().lower())  # strip disambiguation number
        if not slug or slug == "unlocated":
            continue
        label = _TYPE_LABELS.get(slug) or slug.replace("-", " ").replace("_", " ").capitalize()
        if label not in labels:
            labels.append(label)
    return ", ".join(labels)


def _unesco_name_candidates(name: str) -> set[str]:
    """Core place names of a UNESCO site (boilerplate stripped, split on / : and 'and')."""
    name = re.sub(r"\(.*?\)", " ", name)
    name = re.sub(r"\s+and its .*$", "", name, flags=re.I)
    name = re.sub(r"\s+[-–]\s+.*$", "", name)
    out: set[str] = set()
    for part in re.split(r"[/:]|\s+and\s+", name, flags=re.I):
        n = _UNESCO_LEAD.sub("", _norm_name(part), count=1)
        n = re.sub(r" old town$", "", n).strip()
        if len(n) >= 3:
            out.add(n)
    return out


def _pleiades_name_candidates(title: str) -> set[str]:
    """Name variants of a Pleiades place (brackets/parentheses stripped, split on /)."""
    title = re.sub(r"\[.*?\]|\(.*?\)", " ", title)
    return {n for part in title.split("/") if len(n := _norm_name(part)) >= 3}


def _same_place(unesco_name: str, pleiades_title: str) -> bool:
    """Do the UNESCO site and the Pleiades place share the same place name (exact or fuzzy)?"""
    unis = _unesco_name_candidates(unesco_name)
    ples = _pleiades_name_candidates(pleiades_title)
    for u in unis:
        for p in ples:
            if u == p or difflib.SequenceMatcher(None, u, p).ratio() >= DEDUP_FUZZY_RATIO:
                return True
    return False


def _write_geojson(path: Path, features: list[dict[str, object]], *, layer: str) -> int:
    collection = {"type": "FeatureCollection", "metadata": {"layer": layer}, "features": features}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(features)


def _point_feature(lon: float, lat: float, properties: dict[str, object]) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, COORD_PRECISION), round(lat, COORD_PRECISION)]},
        "properties": properties,
    }


def export_pleiades(con: duckdb.DuckDBPyConnection) -> tuple[int, int, int]:
    """Writes the Pleiades context; returns (written, name duplicates, placeholders)."""
    radius_m = CONTEXT_NEAR_SITES_KM * 1000.0
    # For each Pleiades point within the context vicinity: also the names of
    # the UNESCO sites within the narrow dedup vicinity (for the name
    # identity test in Python).
    rows = con.execute(f"""
        WITH pts AS (
            SELECT title, feature_types AS types, pleiades_url AS url, longitude AS lon, latitude AS lat
            FROM read_parquet('{PLEIADES_PARQUET.as_posix()}')
            WHERE longitude IS NOT NULL AND latitude IS NOT NULL
        ),
        near AS (
            SELECT * FROM pts p
            WHERE EXISTS (SELECT 1 FROM _sites s
                          WHERE ST_Distance_Sphere(ST_Point(p.lon, p.lat), ST_Point(s.lon, s.lat)) <= {radius_m})
        )
        SELECT n.title, n.types, n.url, n.lon, n.lat,
               (SELECT list(s.name) FROM _sites s
                WHERE ST_Distance_Sphere(ST_Point(n.lon, n.lat), ST_Point(s.lon, s.lat)) <= {DEDUP_NEAR_SITES_M}) AS near_names
        FROM near n
        ORDER BY n.title
    """).fetchall()
    features: list[dict[str, object]] = []
    dropped = 0
    dropped_placeholder = 0
    for title, types, url, lon, lat, near_names in rows:
        if near_names and any(_same_place(name, title or "") for name in near_names):
            dropped += 1  # name duplicate of a UNESCO site, only this one is dropped
            continue
        clean_title = _ascii_fold_title(title or "")
        if not clean_title or _PLACEHOLDER_TITLES.match(clean_title):
            dropped_placeholder += 1  # unnamed/unresolved Pleiades place
            continue
        features.append(_point_feature(lon, lat, {
            "title": clean_title,
            "types": _clean_types(types or ""),
            "url": url or "",
        }))
    written = _write_geojson(PLEIADES_GEOJSON, features, layer="pleiades")
    return written, dropped, dropped_placeholder


def run() -> None:
    ingest_common.ensure_data_dirs()
    if not ingest_common.already_fetched(PLEIADES_PARQUET):
        raise RuntimeError(f"Pleiades missing ({PLEIADES_PARQUET}). Run ingest_pleiades.py first.")
    if not ingest_common.already_fetched(SITES_PARQUET):
        raise RuntimeError(f"UNESCO sites missing ({SITES_PARQUET}). Run ingest_unesco.py first.")

    con = duckdb.connect()
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute(f"""CREATE TEMP TABLE _sites AS
            SELECT name, longitude AS lon, latitude AS lat FROM read_parquet('{SITES_PARQUET.as_posix()}')
            WHERE longitude IS NOT NULL AND latitude IS NOT NULL""")
        n_pleiades, n_dropped, n_placeholder = export_pleiades(con)
    finally:
        con.close()

    print(f"export_context: {n_pleiades} Pleiades places -> {PLEIADES_GEOJSON.name} "
          f"({n_dropped} name duplicates of UNESCO sites, {n_placeholder} placeholders dropped)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
