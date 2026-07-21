"""Stage 3, export of the 3D model layer.

Writes a curated map layer with sites for which a good public 3D model
exists (laser scan, photogrammetry, or reconstruction). Source is the
manually maintained `reference/heritage_3d_models.csv` (like the in-danger
list): name, coordinates, source, model URL, licence/note.

The layer carries no threat score; it is context and depth. It comprises
two kinds of points:

  * is_whs=true  -- scored UNESCO World Heritage sites with a model (Palmyra, Babylon ...)
  * is_whs=false -- deliberately destroyed but not inscribed icons of our
                    countries (Mosul al-Nuri, Nimrud, Nineveh). They are
                    missing from the score set (UNESCO WHS only), but
                    visibly belong; in the app they are clearly labelled
                    "not scored".

Only entries of the currently configured countries (config.COUNTRY_ISO2)
are included, so the layer stays consistent with the scope.

The app shows its own symbol per point; a tap opens a sheet with metadata
and a link that opens the model in the browser (v1, dependency-lean).

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

# Property order in the GeoJSON (stable, readable).
PROPERTIES: tuple[str, ...] = (
    "name", "country_iso2", "is_whs", "unesco_site_id",
    "source", "author", "license", "model_url", "coord_source", "note",
)


def _to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _ascii_fold(text: str) -> str:
    """Folds diacritics, keeps upper/lower case (readable ASCII name)."""
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
    """Reads the CSV, filters to scope countries, writes GeoJSON. Returns (written, skipped)."""
    if not MODELS_CSV.exists():
        raise RuntimeError(f"3D list missing ({MODELS_CSV}).")

    features: list[dict[str, object]] = []
    skipped = 0
    with MODELS_CSV.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            iso = (row.get("country_iso2") or "").strip().upper()
            if iso not in config.COUNTRY_ISO2:
                skipped += 1  # outside the current scope (e.g. Afghanistan later)
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
    print(f"export_3d: {written} 3D models -> {MODELS_GEOJSON.name} "
          f"({skipped} outside scope/without URL skipped)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()


if __name__ == "__main__":
    main()
