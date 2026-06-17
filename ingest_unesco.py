"""Stufe 1, Ingest UNESCO World Heritage Centre.

Holt das Site-Inventar der Region aus dem WHC-XML: ID, Name, Land, Kategorie,
Koordinaten und Beschreibung. Die Koordinaten stecken verschachtelt in
geolocations/poi, je Site kann es mehrere POI geben.

Das offizielle In-Danger-Flag kommt NICHT aus diesem XML. Das danger-Feld der
Liste ist nachweislich unvollstaendig (Syrien zeigt 1 von 6 Sites, real sind es
6). Es wird nur als Referenz mitgefuehrt. Das maszgebliche Flag kommt aus der
kuratierten Liste (siehe ingest_unesco_danger / RAW_DIR/unesco). Siehe
PROJECT_CONTEXT.md, Abschnitt Validierung der Datengrenzen.

Input:  config.UNESCO_WHC_XML_URL
Output: RAW_DIR/unesco/unesco_sites.parquet (GeoParquet, Punktgeometrie)
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from lxml import etree
from shapely.geometry import Point

import config
import ingest_common

UNESCO_DIR: Path = config.RAW_DIR / "unesco"
SITES_PARQUET: Path = UNESCO_DIR / "unesco_sites.parquet"

REGION_ISO: frozenset[str] = frozenset(iso.lower() for iso in config.COUNTRY_ISO2)

# Laenderzuordnung fuer Sites ohne brauchbares iso_code im WHC-XML. Old City of
# Jerusalem (WHC 148) ist im XML laenderlos ("Site proposed by Jordan"). Fuer die
# Reisewarnstufen-Zuordnung und die Gruppierung wird sie hier Israel zugeordnet.
# Das ist eine bewusste Projektzuordnung, nicht die offizielle UNESCO-Position.
COUNTRY_OVERRIDES: dict[int, str] = {148: "il"}


def _text(row: etree._Element, name: str) -> str:
    element = row.find(name)
    return (element.text or "").strip() if element is not None else ""


def _strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", value)).strip()


def _pick_coordinates(row: etree._Element) -> tuple[float, float] | None:
    """Waehlt den POI mit einem ISO der Region, sonst den ersten POI."""
    pois = row.findall("geolocations/poi")
    if not pois:
        return None

    chosen = next(
        (poi for poi in pois if (poi.findtext("iso2") or "").strip().lower() in REGION_ISO),
        pois[0],
    )
    latitude = poi_text_to_float(chosen.findtext("latitude"))
    longitude = poi_text_to_float(chosen.findtext("longitude"))
    if latitude is None or longitude is None:
        return None
    return latitude, longitude


def poi_text_to_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    return float(value)


def parse_region_sites(xml_bytes: bytes) -> gpd.GeoDataFrame:
    root = etree.fromstring(xml_bytes)
    records: list[dict[str, object]] = []
    without_coordinates: list[str] = []
    lon_min, lat_min, lon_max, lat_max = config.REGION_BBOX

    for row in root.findall(".//row"):
        iso_codes = [code for code in _text(row, "iso_code").split(",") if code]
        iso_match = bool(REGION_ISO.intersection(code.lower() for code in iso_codes))

        coordinates = _pick_coordinates(row)
        name = _text(row, "site")

        # Sonderfall ohne iso_code (z. B. Old City of Jerusalem, politisch
        # bedingt leer): geografisch ueber die Bounding Box einschliessen.
        include = iso_match
        if not iso_match and not iso_codes and coordinates is not None:
            latitude, longitude = coordinates
            include = lon_min <= longitude <= lon_max and lat_min <= latitude <= lat_max
        if not include:
            continue

        if coordinates is None:
            without_coordinates.append(name)
            continue

        latitude, longitude = coordinates
        site_id = int(_text(row, "id_number"))
        country = next(
            (code.lower() for code in iso_codes if code.lower() in REGION_ISO),
            COUNTRY_OVERRIDES.get(site_id, ""),
        )
        records.append(
            {
                "site_id": site_id,
                "name": name,
                "iso_codes": ",".join(iso_codes),
                "country_iso2": country.upper(),
                "category": _text(row, "category"),
                "criteria": _text(row, "criteria_txt"),
                "date_inscribed": _text(row, "date_inscribed"),
                "transnational": _text(row, "transnational") == "1",
                "http_url": _text(row, "http_url"),
                "short_description": _strip_html(_text(row, "short_description")),
                "danger_raw": _text(row, "danger"),
                "latitude": latitude,
                "longitude": longitude,
                "geometry": Point(longitude, latitude),
            }
        )

    if without_coordinates:
        print(f"  Hinweis: {len(without_coordinates)} Region-Site(s) ohne POI-Koordinaten: "
              f"{', '.join(without_coordinates)}")

    frame = gpd.GeoDataFrame(pd.DataFrame(records), geometry="geometry", crs="EPSG:4326")
    return frame.sort_values("site_id").reset_index(drop=True)


def run(*, refresh: bool = False) -> None:
    ingest_common.ensure_data_dirs()
    UNESCO_DIR.mkdir(parents=True, exist_ok=True)

    if ingest_common.already_fetched(SITES_PARQUET) and not refresh:
        existing = gpd.read_parquet(SITES_PARQUET)
        print(f"UNESCO uebersprungen, {len(existing)} Sites bereits vorhanden.")
        return

    response = ingest_common.get_with_retry(config.UNESCO_WHC_XML_URL)
    sites = parse_region_sites(response.content)
    sites.to_parquet(SITES_PARQUET)

    in_danger_raw = int((sites["danger_raw"].str.contains("Y", na=False)).sum())
    print(f"UNESCO-Ingest: {len(sites)} Region-Sites -> {SITES_PARQUET.name}")
    print(f"  davon laut (unzuverlaessigem) danger-Feld aktuell gefaehrdet: {in_danger_raw}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Inventar neu vom WHC laden.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
