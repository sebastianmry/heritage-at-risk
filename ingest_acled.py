"""Stufe 1, Ingest ACLED (Konflikt-Ereignisse).

Alleinige Quelle der Konflikt-Komponente des Threat Score (Rueckwechsel von UCDP
2026-06-24, Konto auf Research-Stufe freigeschaltet). ACLED erfasst auch
nicht-toedliche Treffer (abgefangene Drohnen/Raketen, Beschuss, Explosionen ohne
Tote), die UCDP mit seiner Schwelle >= 1 Toter verpasst.

LIZENZ: Research-Stufe = rein akademisch, KEINE oeffentliche Veroeffentlichung.
Das Repo bleibt privat, ACLED-Rohevents werden nie oeffentlich weitergegeben
(.gitignore: *.parquet). Siehe config.py (ACLED-Block) und PROJECT_CONTEXT.md.

Auth ueber OAuth2 Password-Grant (config.ACLED_OAUTH_URL): username/password aus
.env liefern einen 24-h-Bearer-Token. Damit wird config.ACLED_API_URL je Land
(ISO-numerisch, config.ACLED_COUNTRY_ISO_NUMERIC) paginiert abgefragt, gefiltert
auf das Konflikt-Fenster (config.CONFLICT_START_DATE bis CONFLICT_END_DATE, also
36 bis 12 Monate zurueck - der punktgenau verfuegbare Bereich der Research-Stufe).

Die Ausgabe teilt das Kern-Spalten-Schema von ingest_ucdp.py
(event_id, event_date, violence_type, country, deaths, latitude, longitude,
geometry), damit process.py / export_events.py drop-in umgestellt werden koennen.
ACLED event_type -> violence_type, fatalities -> deaths. Zusaetzlich (ACLED-only,
fuer Karte und Popup): sub_event_type (Treffertyp), civilian_targeting,
geo_precision, location, admin1, notes, source.

Input:  config.ACLED_OAUTH_URL (Token), config.ACLED_API_URL (read)
Output: RAW_DIR/acled/acled_events.parquet (GeoParquet, Punktgeometrie)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

import config
import ingest_common

ACLED_DIR: Path = config.RAW_DIR / "acled"
EVENTS_PARQUET: Path = ACLED_DIR / "acled_events.parquet"

# Feldauswahl ueber den ACLED-Parameter `fields` (pipe-getrennt): Filterfelder
# (Geometrie, Datum, Typ, ISO) plus Kontext-Attribute fuer Karte und Popup.
# sub_event_type = der eigentliche Treffertyp (Air/drone strike, Shelling, IED ...),
# civilian_targeting = Flag gegen Zivilisten, geo_precision = Koordinatenguete
# (1 exakt ... 3 Provinz-Zentroid), location/admin1 = Ortslabel, notes = Freitext,
# source = Herkunft der Meldung.
ACLED_FIELDS: str = "|".join(
    ("event_id_cnty", "event_date", "event_type", "sub_event_type", "country", "iso",
     "latitude", "longitude", "fatalities", "civilian_targeting", "geo_precision",
     "location", "admin1", "notes", "source")
)


def _get_token() -> str:
    """Holt einen 24-h-Bearer-Token per OAuth2 Password-Grant."""
    if not config.ACLED_EMAIL or not config.ACLED_PASSWORD:
        raise RuntimeError(
            "ACLED_EMAIL/ACLED_PASSWORD fehlen. In .env eintragen (siehe .env.example)."
        )
    response = requests.post(
        config.ACLED_OAUTH_URL,
        data={
            "username": config.ACLED_EMAIL,
            "password": config.ACLED_PASSWORD,
            "grant_type": "password",
            "client_id": "acled",
            "scope": "authenticated",
        },
        headers=config.HTTP_HEADERS,
        timeout=config.HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("ACLED-Token-Antwort ohne access_token.")
    return token


def _fetch_country(iso_numeric: int, token: str) -> list[dict]:
    """Fragt alle Ereignisse eines Landes im Fenster ab (seitenweise paginiert)."""
    headers = {**config.HTTP_HEADERS, "Authorization": f"Bearer {token}"}
    rows: list[dict] = []
    page = 1
    while True:
        params = {
            "iso": str(iso_numeric),
            "event_date": f"{config.CONFLICT_START_DATE}|{config.CONFLICT_END_DATE}",
            "event_date_where": "BETWEEN",
            "fields": ACLED_FIELDS,
            "limit": str(config.ACLED_PAGE_LIMIT),
            "page": str(page),
        }
        response = requests.get(
            config.ACLED_API_URL, params=params, headers=headers,
            timeout=config.HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        batch = response.json().get("data", [])
        rows.extend(batch)
        if len(batch) < config.ACLED_PAGE_LIMIT:
            break
        page += 1
    return rows


def _fetch_all(token: str) -> pd.DataFrame:
    """Sammelt die Ereignisse aller Region-Laender in einen DataFrame."""
    frames: list[pd.DataFrame] = []
    for iso_numeric in config.ACLED_COUNTRY_ISO_NUMERIC:
        country_rows = _fetch_country(iso_numeric, token)
        print(f"  ISO {iso_numeric:>3}: {len(country_rows)} Ereignisse")
        if country_rows:
            frames.append(pd.DataFrame(country_rows))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _filter_to_scope(source_df: pd.DataFrame) -> pd.DataFrame:
    """Beschneidet auf Ereignistyp, Region (BBox) und Zeitfenster [Start, Ende)."""
    if source_df.empty:
        return source_df
    lon_min, lat_min, lon_max, lat_max = config.REGION_BBOX
    longitude = pd.to_numeric(source_df["longitude"], errors="coerce")
    latitude = pd.to_numeric(source_df["latitude"], errors="coerce")
    event_date = pd.to_datetime(source_df["event_date"], errors="coerce")

    in_box = longitude.between(lon_min, lon_max) & latitude.between(lat_min, lat_max)
    in_window = (event_date >= pd.Timestamp(config.CONFLICT_START_DATE)) & (
        event_date < pd.Timestamp(config.CONFLICT_END_DATE)
    )
    relevant_type = source_df["event_type"].isin(config.ACLED_EVENT_TYPES)
    return source_df.loc[in_box & in_window & relevant_type]


def build_events(scoped_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Baut die getypte Punktebene (WGS84) im UCDP-kompatiblen Event-Schema."""
    columns = ["event_id", "event_date", "violence_type", "sub_event_type", "country",
               "deaths", "civilian_targeting", "geo_precision", "location", "admin1",
               "notes", "source", "latitude", "longitude", "geometry"]
    if scoped_df.empty:
        return gpd.GeoDataFrame(columns=columns, geometry="geometry", crs="EPSG:4326")

    events_df = pd.DataFrame(
        {
            "event_id": scoped_df["event_id_cnty"].astype(str),
            "event_date": pd.to_datetime(scoped_df["event_date"], errors="coerce"),
            "violence_type": scoped_df["event_type"].fillna(""),
            "sub_event_type": scoped_df["sub_event_type"].fillna(""),
            "country": scoped_df["country"].fillna(""),
            "deaths": pd.to_numeric(scoped_df["fatalities"], errors="coerce").fillna(0).astype("int64"),
            "civilian_targeting": scoped_df["civilian_targeting"].fillna(""),
            "geo_precision": pd.to_numeric(scoped_df["geo_precision"], errors="coerce").fillna(0).astype("int64"),
            "location": scoped_df["location"].fillna(""),
            "admin1": scoped_df["admin1"].fillna(""),
            "notes": scoped_df["notes"].fillna(""),
            "source": scoped_df["source"].fillna(""),
            "latitude": pd.to_numeric(scoped_df["latitude"], errors="coerce"),
            "longitude": pd.to_numeric(scoped_df["longitude"], errors="coerce"),
        }
    ).dropna(subset=["latitude", "longitude"])

    events_df = events_df.drop_duplicates(subset="event_id")
    geometry = gpd.points_from_xy(events_df["longitude"], events_df["latitude"])
    events_gdf = gpd.GeoDataFrame(events_df, geometry=geometry, crs="EPSG:4326")
    return events_gdf.sort_values("event_date").reset_index(drop=True)


def run(*, refresh: bool = False) -> None:
    ingest_common.ensure_data_dirs()
    ACLED_DIR.mkdir(parents=True, exist_ok=True)

    if ingest_common.already_fetched(EVENTS_PARQUET) and not refresh:
        existing_gdf = gpd.read_parquet(EVENTS_PARQUET)
        print(f"ACLED uebersprungen, {len(existing_gdf)} Ereignisse bereits vorhanden (--refresh erzwingt neu).")
        return

    print(f"ACLED-Abruf {config.CONFLICT_START_DATE} bis {config.CONFLICT_END_DATE} "
          f"({len(config.ACLED_COUNTRY_ISO_NUMERIC)} Laender):")
    raw_df = _fetch_all(_get_token())
    scoped_df = _filter_to_scope(raw_df)
    print(f"  nach Filter (Typ/Region/Fenster): {len(scoped_df)} von {len(raw_df)} Ereignissen")

    events_gdf = build_events(scoped_df)
    events_gdf.to_parquet(EVENTS_PARQUET)
    print(f"ACLED-Ingest: {len(events_gdf)} Ereignisse -> {EVENTS_PARQUET.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Rohdaten und Parquet neu laden.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
