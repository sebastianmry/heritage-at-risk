"""Stufe 3, Export der Heritage-Kontextebene.

Schreibt die thematische Overlay-Ebene, die die App unter den bewerteten Sites
zeigt (Detail beim Reinzoomen): Pleiades (antike Orte) als kompaktes GeoJSON-
Artefakt, Punktgeometrie in CRS84.

Anders als sites.geojson (Score-Ebene) traegt diese Ebene keinen Score; sie ist
visueller Kontext. Sie wird auf die Umgebung der bewerteten Sites beschnitten (nur
Orte im CONTEXT_NEAR_SITES_KM-Radius einer UNESCO-Site). Begruendung: Die App zeigt
Kontext nur dort, wo man hinzoomt (man navigiert von Site zu Site), nicht in leerem
Gelaende. Das haelt das Artefakt klein (region-weit waeren es 13.452 Orte) und
fokussiert es auf das Relevante.

Pleiades-Orte, die einen Namens-Doppelpunkt zu einer nahen UNESCO-Site bilden (viele
Welterbestaetten sind selbst antike Orte: Palmyra, Babylon, Damascus ...), werden
verworfen, damit nicht zwei Marker dieselbe Staette zeigen. Bewusst nur bei
Namensidentitaet, nicht per Radius (Details an DEDUP_NEAR_SITES_M unten).

OSM historic wurde als Kontextebene wieder verworfen (zu dicht/rauschig, Pleiades
genuegt; siehe PROJECT_CONTEXT.md, Bewusst verworfene Ansaetze).

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

# Nur Kontext im Umkreis der bewerteten Sites (Begruendung im Modul-Docstring).
CONTEXT_NEAR_SITES_KM: float = 15.0

COORD_PRECISION: int = 5  # ~1 m, genug fuer eine Kontextebene und spart Dateigroesse

# Pleiades-Dublette einer UNESCO-Site: Viele Welterbestaetten sind selbst antike
# Orte und stehen damit auch in Pleiades (Palmyra, Petra, Babylon ...). Liegt ein
# Pleiades-Punkt nahe an einer UNESCO-Site UND traegt denselben Namen, ist es ein
# doppelter Marker fuer dieselbe Staette; dann faellt der Pleiades-Punkt raus (die
# bewertete Site gewinnt). Bewusst NUR bei Namensidentitaet, nicht per Radius:
# rund um eine Site liegen viele eigenstaendige antike Orte (Babylons Tore/Tempel,
# Assur-Archive), die als Kontext erhalten bleiben sollen.
DEDUP_NEAR_SITES_M: float = 2000.0  # Namensvergleich nur fuer plausibel selbe Orte
DEDUP_FUZZY_RATIO: float = 0.85     # Transliterations-Varianten (Bisotun~Bisutun)

# UNESCO-Geruestwoerter, die nicht zum eigentlichen Ortsnamen gehoeren.
_UNESCO_LEAD = re.compile(
    r"^(site of|ancient city of|ancient town of|ancient village[s]? of|ancient|"
    r"historic town of|historic city of|historic|old city of|old town of|"
    r"city of|town of|necropolis of|caves of|biblical tels)\s+",
)


def _norm_name(s: str) -> str:
    """Kleinschreiben, Diakritika folden, auf [a-z0-9]+ reduzieren."""
    decomposed = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def _unesco_name_candidates(name: str) -> set[str]:
    """Kern-Ortsnamen einer UNESCO-Site (Geruest weg, an / : und 'and' gesplittet)."""
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
    """Namensvarianten eines Pleiades-Orts (Klammern/Bracket weg, an / gesplittet)."""
    title = re.sub(r"\[.*?\]|\(.*?\)", " ", title)
    return {n for part in title.split("/") if len(n := _norm_name(part)) >= 3}


def _same_place(unesco_name: str, pleiades_title: str) -> bool:
    """Tragen UNESCO-Site und Pleiades-Ort denselben Ortsnamen (exakt oder fuzzy)?"""
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


def export_pleiades(con: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    """Pleiades-Kontext schreiben; gibt (geschriebene, als Dublette verworfene) zurueck."""
    radius_m = CONTEXT_NEAR_SITES_KM * 1000.0
    # Je Pleiades-Punkt im Kontext-Umkreis: zusaetzlich die Namen der UNESCO-Sites
    # im engen Dedup-Umkreis (fuer den Namens-Identitaetstest in Python).
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
    for title, types, url, lon, lat, near_names in rows:
        if near_names and any(_same_place(name, title or "") for name in near_names):
            dropped += 1  # Namens-Dublette einer UNESCO-Site, nur diese faellt raus
            continue
        features.append(_point_feature(lon, lat, {"title": title or "", "types": types or "", "url": url or ""}))
    written = _write_geojson(PLEIADES_GEOJSON, features, layer="pleiades")
    return written, dropped


def run() -> None:
    ingest_common.ensure_data_dirs()
    if not ingest_common.already_fetched(PLEIADES_PARQUET):
        raise RuntimeError(f"Pleiades fehlt ({PLEIADES_PARQUET}). Zuerst ingest_pleiades.py laufen lassen.")
    if not ingest_common.already_fetched(SITES_PARQUET):
        raise RuntimeError(f"UNESCO-Sites fehlen ({SITES_PARQUET}). Zuerst ingest_unesco.py laufen lassen.")

    con = duckdb.connect()
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute(f"""CREATE TEMP TABLE _sites AS
            SELECT name, longitude AS lon, latitude AS lat FROM read_parquet('{SITES_PARQUET.as_posix()}')
            WHERE longitude IS NOT NULL AND latitude IS NOT NULL""")
        n_pleiades, n_dropped = export_pleiades(con)
    finally:
        con.close()

    print(f"export_context: {n_pleiades} Pleiades-Orte -> {PLEIADES_GEOJSON.name} "
          f"({n_dropped} Namens-Dubletten von UNESCO-Sites verworfen)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
