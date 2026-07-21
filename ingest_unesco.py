"""Stage 1, ingest UNESCO World Heritage Centre.

Fetches the region's site inventory from the WHC XML: ID, name, country,
category, coordinates, and description. The coordinates are nested inside
geolocations/poi; a site can have several POIs.

The official in-danger flag does not come from this XML. The list's danger
field is demonstrably incomplete (Syria shows 1 of 6 sites, in reality there
are 6). It is only carried along as a reference. The authoritative flag
comes from the curated list (see ingest_unesco_danger / RAW_DIR/unesco). See
PROJECT_CONTEXT.md, Pipeline architecture.

Input:  config.UNESCO_WHC_XML_URL
Output: RAW_DIR/unesco/unesco_sites.parquet (GeoParquet, point geometry)
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

# Country assignment for sites without a usable iso_code in the WHC XML. Old
# City of Jerusalem (WHC 148) is countryless in the XML ("Site proposed by
# Jordan"). For the travel advisory level assignment and grouping it is
# assigned to Israel here. This is a deliberate project assignment, not the
# official UNESCO position.
COUNTRY_OVERRIDES: dict[int, str] = {148: "il"}


def _text(row: etree._Element, name: str) -> str:
    element = row.find(name)
    return (element.text or "").strip() if element is not None else ""


def _strip_html(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", value)).strip()


def _pick_coordinates(row: etree._Element) -> tuple[float, float] | None:
    """Chooses the POI with a region ISO, otherwise the first POI."""
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

        # Special case without iso_code (e.g. Old City of Jerusalem, empty
        # for political reasons): include geographically via the bounding box.
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
        print(f"  Note: {len(without_coordinates)} region site(s) without POI coordinates: "
              f"{', '.join(without_coordinates)}")

    frame = gpd.GeoDataFrame(pd.DataFrame(records), geometry="geometry", crs="EPSG:4326")
    return frame.sort_values("site_id").reset_index(drop=True)


def run(*, refresh: bool = False) -> None:
    ingest_common.ensure_data_dirs()
    UNESCO_DIR.mkdir(parents=True, exist_ok=True)

    if ingest_common.already_fetched(SITES_PARQUET) and not refresh:
        existing = gpd.read_parquet(SITES_PARQUET)
        print(f"UNESCO skipped, {len(existing)} sites already present.")
        return

    response = ingest_common.get_with_retry(config.UNESCO_WHC_XML_URL)
    sites = parse_region_sites(response.content)
    sites.to_parquet(SITES_PARQUET)

    in_danger_raw = int((sites["danger_raw"].str.contains("Y", na=False)).sum())
    print(f"UNESCO ingest: {len(sites)} region sites -> {SITES_PARQUET.name}")
    print(f"  of which currently at risk per the (unreliable) danger field: {in_danger_raw}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Reload the inventory from the WHC.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
