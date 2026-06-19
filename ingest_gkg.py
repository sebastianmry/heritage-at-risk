"""Stufe 1, Ingest GDELT GKG 1.0 (Einschlag-/Strike-Erwaehnungen).

Ergaenzt die Konflikt-Komponente (UCDP GED) um den Aspekt, den UCDP bewusst
nicht erfasst: nicht-toedliche bzw. abgefangene Luftschlaege, Drohnen und Raketen
(UCDP-Schwelle >= 1 Todesopfer). Quelle ist der offene, tokenfreie GKG-1.0-
Tagesfeed von GDELT: eine tab-getrennte CSV je Tag mit geokodierten Orts-
erwaehnungen je Nachrichtenartikel.

GKG ist INDIKATIV, nicht behoerdlich-vollstaendig: es zaehlt Medien-Erwaehnungen,
geokodiert nur orts-/stadtgenau und ist verrauscht (Dubletten, Falschtreffer).
Eine Zeile qualifiziert als Strike-Erwaehnung nur, wenn ihre THEMES eine
config.STRIKE_THEMES-Marke enthalten UND ihre Quell-URL ein
config.STRIKE_URL_KEYWORD traegt (verengt auf echte Einschlag-Berichterstattung,
haelt Diplomatie-/Nachrichtenhubs heraus); aus den LOCATIONS werden dann alle Punkte
in der REGION_BBOX als einzelne Erwaehnungen uebernommen (process.py zaehlt sie spaeter
raeumlich je Site, wie die UCDP-Events).

Robust und resumebar: je Tag entsteht ein kleines, gefiltertes Cache-Parquet
(CACHE_DIR/gdelt/YYYYMMDD.parquet); das grosse Roh-ZIP wird nach dem Parsen
geloescht. Ein erneuter Lauf ueberspringt bereits gecachte Tage. Fehlende Tage
(HTTP 404) werden uebersprungen.

Input:  config.GKG_DAILY_URL_TEMPLATE (eine ZIP-CSV je Tag)
Output: RAW_DIR/gdelt/gkg_strikes.parquet (GeoParquet, Punktgeometrie)
"""

from __future__ import annotations

import argparse
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

import config
import ingest_common

GKG_DIR: Path = config.RAW_DIR / "gdelt"
DAILY_CACHE_DIR: Path = config.CACHE_DIR / "gdelt"
STRIKES_PARQUET: Path = GKG_DIR / "gkg_strikes.parquet"

# GKG 1.0 ist tab-getrennt mit Kopfzeile; nur diese Spalten werden gebraucht.
SOURCE_COLUMNS: tuple[str, ...] = ("DATE", "THEMES", "LOCATIONS", "SOURCEURLS")

# Subfeld-Reihenfolge im LOCATIONS-Feld (durch '#' getrennt):
# Type#FullName#CountryCode#ADM1Code#Latitude#Longitude#FeatureID
_LOCATION_LAT_INDEX: int = 4
_LOCATION_LON_INDEX: int = 5

_STRIKE_OUTPUT_COLUMNS: tuple[str, ...] = (
    "strike_date", "location_name", "country_code",
    "latitude", "longitude", "geometry",
)


def _day_range(start: date, end: date) -> list[date]:
    """Alle Tage von start bis end (beide inklusive)."""
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _empty_strikes() -> gpd.GeoDataFrame:
    """Typkorrekte Leermenge im Strike-Schema."""
    return gpd.GeoDataFrame(
        columns=list(_STRIKE_OUTPUT_COLUMNS), geometry="geometry", crs="EPSG:4326",
    )


def _parse_day(zip_path: Path) -> gpd.GeoDataFrame:
    """Liest eine GKG-1.0-Tages-CSV und filtert auf Strikes in der Region.

    Voll vektorisiert (pandas C-Level): str.contains fuer den Theme-/URL-Filter,
    explode + str.split fuer die Locations. Eine zeilenweise apply/iterrows ueber
    ~40.000 Zeilen je Tag waere ueber das Jahresfenster viel zu langsam.
    """
    source_df = pd.read_csv(
        zip_path, sep="\t", usecols=list(SOURCE_COLUMNS),
        compression="zip", dtype=str, keep_default_na=False, on_bad_lines="skip",
    )

    theme_pattern = "|".join(re.escape(theme) for theme in config.STRIKE_THEMES)
    url_pattern = "|".join(re.escape(keyword) for keyword in config.STRIKE_URL_KEYWORDS)
    theme_hit = source_df["THEMES"].str.contains(theme_pattern, regex=True, na=False)
    url_hit = source_df["SOURCEURLS"].str.lower().str.contains(url_pattern, regex=True, na=False)
    # UND-Logik (nicht ODER): ein Artikel zaehlt nur, wenn er ein explizites
    # Einschlag-Wort in der URL traegt UND konflikt-thematisch ist. Das verengt auf
    # echte Einschlag-Berichterstattung und entfernt zwei Rauschquellen: reine
    # Diplomatie-/Dateline-Hubs (Kairo, Muscat: kein Einschlag-Wort) und Nicht-
    # Konflikt-Nutzung der Woerter ("drone photography", "rocket launch", "missile
    # defense deal": kein Konflikt-Thema).
    qualifying = source_df.loc[theme_hit & url_hit]
    if qualifying.empty:
        return _empty_strikes()

    # Je Artikel eine Erwaehnung je genannten Ort: LOCATIONS in Listen zerlegen und
    # explodieren, dann die '#'-Subfelder spaltenweise aufbrechen.
    exploded = pd.DataFrame({
        "strike_date": qualifying["DATE"],
        "location": qualifying["LOCATIONS"].str.split(";"),
    }).explode("location")
    exploded = exploded.loc[exploded["location"].str.len() > 0]
    if exploded.empty:
        return _empty_strikes()

    fields = exploded["location"].str.split("#", expand=True)
    if fields.shape[1] <= _LOCATION_LON_INDEX:
        return _empty_strikes()

    lon_min, lat_min, lon_max, lat_max = config.REGION_BBOX
    latitude = pd.to_numeric(fields[_LOCATION_LAT_INDEX], errors="coerce")
    longitude = pd.to_numeric(fields[_LOCATION_LON_INDEX], errors="coerce")
    keep = (
        fields[0].isin(config.STRIKE_LOCATION_TYPES)
        & latitude.between(lat_min, lat_max)
        & longitude.between(lon_min, lon_max)
    )
    if not keep.any():
        return _empty_strikes()

    # Auf ORT-TAGE deduplizieren: ein Treffer je Ort je Tag, unabhaengig davon, wie
    # viele Artikel ihn an dem Tag nennen. Das entfernt den Medien-Megafon-Bias
    # (Roh-Erwaehnungen sind ~17x mehr als Ort-Tage: ein Einschlag, ueber den 500
    # Quellen berichten, zaehlt sonst 500x). Die Einheit wird damit defensibel:
    # "an wie vielen Tagen tauchte dieser Ort in Einschlag-Berichterstattung auf".
    strikes_df = pd.DataFrame({
        "strike_date": exploded["strike_date"].to_numpy()[keep.to_numpy()],
        "location_name": fields[1].to_numpy()[keep.to_numpy()],
        "country_code": fields[2].to_numpy()[keep.to_numpy()],
        "latitude": latitude.to_numpy()[keep.to_numpy()],
        "longitude": longitude.to_numpy()[keep.to_numpy()],
    }).drop_duplicates(subset=["strike_date", "latitude", "longitude"])

    geometry = gpd.points_from_xy(strikes_df["longitude"], strikes_df["latitude"])
    return gpd.GeoDataFrame(strikes_df, geometry=geometry, crs="EPSG:4326")


def _download_day(day: date) -> Path | None:
    """Laedt das GKG-Tages-ZIP in den Roh-Ordner; None bei fehlendem Tag (404)."""
    GKG_DIR.mkdir(parents=True, exist_ok=True)
    url = config.GKG_DAILY_URL_TEMPLATE.format(date=day.strftime("%Y%m%d"))
    zip_path = GKG_DIR / f"{day.strftime('%Y%m%d')}.gkg.csv.zip"
    part_path = zip_path.with_suffix(zip_path.suffix + ".part")

    last_error: Exception | None = None
    for attempt in range(config.HTTP_MAX_RETRIES):
        try:
            with requests.get(
                url, stream=True, headers=config.HTTP_HEADERS,
                timeout=config.HTTP_TIMEOUT_SECONDS,
            ) as response:
                if response.status_code == 404:
                    return None
                if response.status_code in config.HTTP_RETRY_STATUS:
                    last_error = requests.HTTPError(f"transienter Status {response.status_code}")
                else:
                    response.raise_for_status()
                    with part_path.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=1 << 20):
                            handle.write(chunk)
                    part_path.replace(zip_path)
                    return zip_path
        except requests.RequestException as error:
            last_error = error
        time.sleep(config.HTTP_BACKOFF_FACTOR ** attempt)

    raise RuntimeError(f"GKG-Tagesdownload fehlgeschlagen ({day}): {url}") from last_error


def _process_day(day: date, *, refresh: bool) -> gpd.GeoDataFrame:
    """Liefert die gecachten Strike-Punkte eines Tages (laedt und parst bei Bedarf)."""
    cache_path = DAILY_CACHE_DIR / f"{day.strftime('%Y%m%d')}.parquet"
    if ingest_common.already_fetched(cache_path) and not refresh:
        return gpd.read_parquet(cache_path)

    zip_path = _download_day(day)
    if zip_path is None:
        day_strikes_gdf = _empty_strikes()
    else:
        day_strikes_gdf = _parse_day(zip_path)
        zip_path.unlink(missing_ok=True)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    day_strikes_gdf.to_parquet(cache_path)
    return day_strikes_gdf


def run(*, refresh: bool = False) -> None:
    ingest_common.ensure_data_dirs()
    GKG_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if ingest_common.already_fetched(STRIKES_PARQUET) and not refresh:
        existing_gdf = gpd.read_parquet(STRIKES_PARQUET)
        print(f"GKG uebersprungen, {len(existing_gdf)} Strike-Erwaehnungen vorhanden (--refresh erzwingt neu).")
        return

    start = datetime.strptime(config.STRIKE_START_DATE, "%Y-%m-%d").date()
    days = _day_range(start, date.today())
    print(f"GKG-Ingest: {len(days)} Tage ab {config.STRIKE_START_DATE} (Tages-Cache, resumebar).")

    daily_frames: list[gpd.GeoDataFrame] = []
    for processed, day in enumerate(days, start=1):
        day_strikes_gdf = _process_day(day, refresh=refresh)
        daily_frames.append(day_strikes_gdf)
        if processed % 30 == 0 or processed == len(days):
            running_total = sum(len(frame) for frame in daily_frames)
            print(f"  {processed}/{len(days)} Tage, {running_total} Strike-Erwaehnungen bisher.")

    non_empty = [frame for frame in daily_frames if not frame.empty]
    if not non_empty:
        strikes_gdf = _empty_strikes()
    else:
        combined_df = pd.concat(non_empty, ignore_index=True)
        # Finaler Ort-Tag-Dedup ueber alle Tage: kollabiert auch aeltere Tages-Caches,
        # die noch artikel-granular (mit source_url) gecacht wurden, sauber auf einen
        # Treffer je Ort je Tag. Spalte source_url wird dabei verworfen, falls vorhanden.
        combined_df = combined_df.drop(columns=["source_url"], errors="ignore")
        combined_df = combined_df.drop_duplicates(subset=["strike_date", "latitude", "longitude"])
        combined_df["event_date"] = pd.to_datetime(combined_df["strike_date"], format="%Y%m%d", errors="coerce")
        strikes_gdf = gpd.GeoDataFrame(
            combined_df.sort_values("event_date").reset_index(drop=True),
            geometry="geometry", crs="EPSG:4326",
        )

    strikes_gdf.to_parquet(STRIKES_PARQUET)
    print(f"GKG-Ingest: {len(strikes_gdf)} Ort-Tage in der Region -> {STRIKES_PARQUET.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Tages-Cache und Parquet neu aufbauen.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
