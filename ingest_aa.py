"""Stage 1, ingest German Federal Foreign Office (Auswaertiges Amt).

Fetches the travel and security advisories as a country-level danger
indicator and derives a warning level (0 to 2) per country of the region for
the threat score.

The OpenData API returns four boolean flags per country (warning,
partialWarning, situationWarning, situationPartWarning), not a ready-made
numeric scale. The derivation of the 0-to-2 level lives centrally in
config.AA_WARNING_LEVELS; the highest matching level wins. Rationale there.

Input:  config.AA_TRAVELWARNING_URL, filtered to config.COUNTRY_ISO2
Output: RAW_DIR/auswaertiges_amt/travel_warning_levels.csv
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config
import ingest_common

AA_DIR: Path = config.RAW_DIR / "auswaertiges_amt"
WARNING_LEVELS_CSV: Path = AA_DIR / "travel_warning_levels.csv"

REGION_ISO: frozenset[str] = frozenset(config.COUNTRY_ISO2)


def _epoch_to_date(value: object) -> str:
    """Converts an epoch-seconds value to an ISO date (UTC)."""
    if not value:
        return ""
    return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()


def _warning_level(item: dict[str, object]) -> int:
    """Highest matching level per config.AA_WARNING_LEVELS, otherwise 0."""
    for flag, level in config.AA_WARNING_LEVELS:
        if item.get(flag):
            return level
    return 0


def parse_region_levels(payload: bytes) -> pd.DataFrame:
    """Filters the API response to the region and derives the level per country."""
    response = json.loads(payload.decode("utf-8"))["response"]
    source_last_modified = _epoch_to_date(response.get("lastModified"))

    records: list[dict[str, object]] = []
    for content_id in response.get("contentList", []):
        item = response[content_id]
        country_iso2 = item.get("countryCode")
        if country_iso2 not in REGION_ISO:
            continue
        records.append(
            {
                "country_iso2": country_iso2,
                "country_name": item.get("countryName", ""),
                "warning_level": _warning_level(item),
                "warning": bool(item.get("warning")),
                "partial_warning": bool(item.get("partialWarning")),
                "situation_warning": bool(item.get("situationWarning")),
                "situation_part_warning": bool(item.get("situationPartWarning")),
                "effective": _epoch_to_date(item.get("effective")),
                "source_last_modified": source_last_modified,
            }
        )

    levels_df = pd.DataFrame(records)
    return levels_df.sort_values("country_iso2").reset_index(drop=True)


def run(*, refresh: bool = False) -> None:
    ingest_common.ensure_data_dirs()
    AA_DIR.mkdir(parents=True, exist_ok=True)

    if ingest_common.already_fetched(WARNING_LEVELS_CSV) and not refresh:
        existing_df = pd.read_csv(WARNING_LEVELS_CSV)
        print(f"German Federal Foreign Office skipped, {len(existing_df)} countries already present.")
        return

    response = ingest_common.get_with_retry(config.AA_TRAVELWARNING_URL)
    levels_df = parse_region_levels(response.content)

    missing = REGION_ISO - set(levels_df["country_iso2"])
    if missing:
        print(f"  Warning: {len(missing)} region country/countries missing from the AA response: "
              f"{', '.join(sorted(missing))}")

    levels_df.to_csv(WARNING_LEVELS_CSV, index=False, encoding="utf-8")

    print(f"AA ingest: {len(levels_df)} region countries -> {WARNING_LEVELS_CSV.name}")
    for level in range(config.AA_WARNING_LEVEL_MAX, -1, -1):
        countries = levels_df.loc[levels_df["warning_level"] == level, "country_iso2"]
        if not countries.empty:
            print(f"  Level {level}: {', '.join(countries)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Reload existing raw data.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
