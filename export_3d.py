"""Stufe 3, Export der 3D-Modell-Ebene.

Schreibt eine kuratierte Karten-Ebene mit Staetten, fuer die es ein gutes
oeffentliches 3D-Modell gibt (Laserscan, Photogrammetrie oder Rekonstruktion).
Quelle ist die manuell gepflegte `reference/heritage_3d_models.csv` (wie die
In-Danger-Liste): Name, Koordinaten, Quelle, Modell-URL, Lizenz/Notiz.

Die Ebene traegt keinen Threat Score; sie ist Kontext und Vertiefung. Sie umfasst
zwei Arten von Punkten:

  * is_whs=true  -- bewertete UNESCO-Welterbestaetten mit Modell (Palmyra, Babylon ...)
  * is_whs=false -- bewusst zerstoerte, aber NICHT eingeschriebene Ikonen unserer
                    Laender (Mosul al-Nuri, Nimrud, Nineveh). Sie fehlen dem
                    Score-Set (UNESCO-WHS-only), gehoeren aber sichtbar dazu; in der
                    App klar als "nicht gescort" gekennzeichnet.

Aufgenommen werden nur Eintraege der aktuell konfigurierten Laender (config.COUNTRY_ISO2),
damit die Ebene konsistent zum Scope bleibt.

Die App zeigt je Punkt ein eigenes Symbol; ein Tap oeffnet ein Sheet mit Metadaten
und einem Link, der das Modell im Browser oeffnet (v1, dependency-arm).

Input:  reference/heritage_3d_models.csv
Output: config.ARTIFACTS_DIR/heritage_3d.geojson
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path

import config

MODELS_CSV: Path = config.REFERENCE_DIR / "heritage_3d_models.csv"
MODELS_GEOJSON: Path = config.ARTIFACTS_DIR / "heritage_3d.geojson"

COORD_PRECISION: int = 5

# Property-Reihenfolge im GeoJSON (stabil, lesbar).
PROPERTIES: tuple[str, ...] = (
    "name", "country_iso2", "is_whs", "unesco_site_id",
    "source", "author", "license", "model_url", "coord_source", "note",
)


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _ascii_fold(text: str) -> str:
    """Diakritika folden, Gross-/Kleinschreibung erhalten (lesbarer ASCII-Name)."""
    decomposed = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", folded.encode("ascii", "ignore").decode("ascii")).strip()


def _feature(row: dict[str, str]) -> dict[str, object]:
    lon = round(float(row["longitude"]), COORD_PRECISION)
    lat = round(float(row["latitude"]), COORD_PRECISION)
    props: dict[str, object] = {}
    for key in PROPERTIES:
        value = (row.get(key) or "").strip()
        if key == "is_whs":
            props[key] = _to_bool(value)
        elif key == "unesco_site_id":
            props[key] = int(value) if value else None
        elif key == "name":
            props[key] = _ascii_fold(value)
        else:
            props[key] = value
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def export_models() -> tuple[int, int]:
    """CSV lesen, auf Scope-Laender filtern, GeoJSON schreiben. Gibt (geschrieben, uebersprungen)."""
    if not MODELS_CSV.exists():
        raise RuntimeError(f"3D-Liste fehlt ({MODELS_CSV}).")

    features: list[dict[str, object]] = []
    skipped = 0
    with MODELS_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            iso = (row.get("country_iso2") or "").strip().upper()
            if iso not in config.COUNTRY_ISO2:
                skipped += 1  # ausserhalb des aktuellen Scope (z. B. Afghanistan spaeter)
                continue
            if not (row.get("model_url") or "").strip():
                skipped += 1
                continue
            features.append(_feature(row))

    features.sort(key=lambda f: (not f["properties"]["is_whs"], f["properties"]["name"]))
    collection = {
        "type": "FeatureCollection",
        "metadata": {
            "layer": "heritage_3d",
            "title": "Heritage at Risk - 3D models",
            "description": "Curated sites with a public 3D model (laser scan, photogrammetry or "
                           "reconstruction). Context layer, no threat score. is_whs=false marks "
                           "destroyed non-WHS icons (e.g. Old City of Mosul).",
            "sources": "CyArk / Open Heritage 3D, Sketchfab (Global Digital Heritage, Tech 4 "
                       "Heritage, arck-project, Rekrei)",
        },
        "features": features,
    }
    MODELS_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    MODELS_GEOJSON.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return len(features), skipped


def run() -> None:
    written, skipped = export_models()
    print(f"export_3d: {written} 3D-Modelle -> {MODELS_GEOJSON.name} "
          f"({skipped} ausserhalb Scope/ohne URL uebersprungen)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
