"""Stage 1, ingest natural hazards (ThinkHazard!).

Assigns each UNESCO site an earthquake and a river-flood hazard level (Very
low / Low / Medium / High). Source is the World Bank's (GFDRR) ThinkHazard!,
which maintains the maximum hazard level per administrative division
(earthquake from GEM, flood from a global flood model).

ThinkHazard! has no point-to-area lookup. The path is therefore: site
coordinate -> reverse geocoding (Nominatim) to province/district -> name
search in ThinkHazard! (filtered to the country) -> report JSON per division
code -> EQ and FL level.

The result is a curated, committed CSV (reference/natural_hazard.csv, keyed
per site_id), analogous to unesco_in_danger.csv. process.py only reads this
CSV, no live API access at score time. Regenerate with --refresh (rarely
needed, the levels are static). The match_confidence column documents
whether the site was resolved at district (adm2), province (adm1), or only
country level (country).

Input:  RAW_DIR/unesco/unesco_sites.parquet (site_id, country_iso2, lat/lon)
Output: reference/natural_hazard.csv
"""

from __future__ import annotations

import argparse
import json
import time
import unicodedata
from pathlib import Path

import geopandas as gpd
import pandas as pd

import config
import ingest_common

UNESCO_SITES_PARQUET: Path = config.RAW_DIR / "unesco" / "unesco_sites.parquet"
CACHE_PATH: Path = config.RAW_DIR / "hazard" / "thinkhazard_cache.json"

NOMINATIM_REVERSE_URL: str = f"{config.NOMINATIM_URL}/reverse"
THINKHAZARD_SEARCH_URL: str = "https://thinkhazard.org/en/administrativedivision"
THINKHAZARD_REPORT_URL: str = "https://thinkhazard.org/en/report/{code}.json"

NOMINATIM_MIN_INTERVAL_S: float = 1.1  # usage policy: at most 1 request/s

# ThinkHazard country name (admin0) per region ISO, as lower-case substring(s).
COUNTRY_ADMIN0_HINTS: dict[str, tuple[str, ...]] = {
    "SY": ("syrian", "syria"),
    "LB": ("lebanon",),
    "IL": ("israel",),
    "PS": ("palestin", "west bank", "gaza"),
    "IQ": ("iraq",),
    "IR": ("iran",),
    "YE": ("yemen",),
    "EG": ("egypt",),
    "JO": ("jordan",),
    "SA": ("saudi",),
    "AE": ("emirates",),
    "OM": ("oman",),
    "QA": ("qatar",),
    "BH": ("bahrain",),
}

# Province aliases per country: cleaned Nominatim name (lower) -> ThinkHazard
# spelling. Needed where Nominatim and ThinkHazard's GAUL names transliterate
# or abbreviate differently (e.g. Nominatim "Isfahan" vs. ThinkHazard
# "Esfahan", "North District" vs. "Northern"). The alias drives both the name
# search and the name comparison.
_TERM_ALIASES: dict[str, dict[str, str]] = {
    "SY": {"dar a": "Dara"},
    "LB": {"beqaa": "Bekaa", "keserwan-jbeil": "Mount Lebanon"},
    "IQ": {"nineveh": "Ninewa"},
    "IR": {"isfahan": "Esfahan", "sistan and baluchestan": "Sistan"},
    "IL": {"north": "Northern", "south": "Southern"},
}

# Direct division assignment per site_id, where reverse geocoding does not
# yield a usable administrative division. Palestine: Nominatim only returns
# Oslo zones ("Area A/C/H1") instead of the governorate; ThinkHazard,
# however, lists the districts cleanly under "West Bank and Gaza".
# (code, label)
_DIVISION_OVERRIDES: dict[int, tuple[int, str]] = {
    1433: (3397, "West Bank and Gaza / Bethlehem"),       # Church of the Nativity
    1492: (3397, "West Bank and Gaza / Bethlehem"),       # Battir (Bethlehem Governorate)
    1565: (3394, "West Bank and Gaza / Al Khalil (Hebron)"),
    1687: (3396, "West Bank and Gaza / Ariha (Jericho)"),
    1749: (1291, "West Bank and Gaza / Deir al Balah"),   # Saint Hilarion (Gaza)
}

# Canonical hazard levels; "no-data"/missing becomes NDA (partial score 0).
_LEVEL_CANON: dict[str, str] = {
    "VLO": "VLO", "LOW": "LOW", "MED": "MED", "HIG": "HIG", "no-data": "NDA", "NDA": "NDA",
}

# Administrative generic terms that are dropped before the name comparison.
_ADMIN_STOPWORDS: frozenset[str] = frozenset((
    "governorate", "province", "district", "region", "county", "subdistrict",
    "muhafazat", "muhafazah", "mohafazat", "qadaa", "qada", "markaz", "nahiyah",
    "city", "municipality", "division", "prefecture", "department", "of", "the",
))


def _normalize(name: str | None) -> str:
    """Folds diacritics, removes generic terms and special characters."""
    if not name:
        return ""
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    tokens = [t for t in "".join(
        ch.lower() if ch.isalnum() else " " for ch in folded
    ).split() if t not in _ADMIN_STOPWORDS]
    return " ".join(tokens)


def _search_term(name: str | None) -> str:
    """Cleaned search term for ThinkHazard: generic terms removed, ASCII only.

    Nominatim returns 'Homs Governorate', 'Khuzestan Province', 'Shush
    County'; the ThinkHazard name search needs the bare core ('Homs').
    Non-ASCII (e.g. Persian place names in the city field) is discarded,
    since it never matches anyway.
    """
    if not name or not name.isascii():
        return ""
    tokens = [t for t in name.replace("'", " ").replace("`", " ").split()
              if t.lower() not in _ADMIN_STOPWORDS]
    return " ".join(tokens)


def _canonical_adm1(iso2: str, adm1: str) -> str:
    """Cleaned province name, mapped to the ThinkHazard spelling via _TERM_ALIASES."""
    cleaned = _search_term(adm1)
    return _TERM_ALIASES.get(iso2, {}).get(cleaned.lower(), cleaned)


def _canonical_level(mnemonic: str | None) -> str:
    return _LEVEL_CANON.get(mnemonic or "NDA", "NDA")


class _Cache:
    """Lean JSON cache so reruns do not hit the APIs again."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, object] = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def get(self, key: str) -> object | None:
        return self.data.get(key)

    def set(self, key: str, value: object) -> None:
        self.data[key] = value

    def flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")


def _reverse_geocode(lat: float, lon: float, cache: _Cache) -> dict[str, str]:
    """Fetches the address/administrative fields of a coordinate from Nominatim."""
    key = f"geo:{lat:.5f},{lon:.5f}"
    cached = cache.get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    time.sleep(NOMINATIM_MIN_INTERVAL_S)
    response = ingest_common.get_with_retry(
        NOMINATIM_REVERSE_URL,
        params={
            "lat": str(lat), "lon": str(lon), "format": "jsonv2",
            "zoom": "10", "addressdetails": "1", "accept-language": "en",
        },
    )
    address = response.json().get("address", {})
    cache.set(key, address)
    return address


def _thinkhazard_search(term: str, cache: _Cache) -> list[dict[str, object]]:
    """Searches for administrative divisions by name in ThinkHazard!."""
    if not term:
        return []
    key = f"search:{term.lower()}"
    cached = cache.get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    response = ingest_common.get_with_retry(THINKHAZARD_SEARCH_URL, params={"q": term})
    results = response.json().get("data", [])
    cache.set(key, results)
    return results


def _thinkhazard_levels(code: int, cache: _Cache) -> dict[str, str]:
    """Reads the hazard levels (mnemonic per hazard) of a division code."""
    key = f"report:{code}"
    cached = cache.get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    response = ingest_common.get_with_retry(THINKHAZARD_REPORT_URL.format(code=code))
    levels = {
        item["hazardtype"]["mnemonic"]: item["hazardlevel"]["mnemonic"]
        for item in response.json()
    }
    cache.set(key, levels)
    return levels


def _admin_fields(address: dict[str, str]) -> tuple[str, str, str]:
    """Extracts province (adm1), district (adm2) and place from the Nominatim fields."""
    adm1 = address.get("state") or address.get("region") or address.get("province") or ""
    adm2 = (address.get("county") or address.get("state_district")
            or address.get("city_district") or address.get("district") or "")
    city = (address.get("city") or address.get("town")
            or address.get("municipality") or address.get("village") or "")
    return adm1, adm2, city


def _matches_country(result: dict[str, object], iso2: str) -> bool:
    admin0 = str(result.get("admin0", "")).lower()
    return any(hint in admin0 for hint in COUNTRY_ADMIN0_HINTS.get(iso2, ()))


def _choose_division(
    iso2: str, adm1: str, adm2: str, cache: _Cache
) -> tuple[dict[str, object] | None, str]:
    """Chooses the best ThinkHazard division for a site, with a confidence label."""
    def _country_fallback() -> tuple[dict[str, object] | None, str]:
        for hint in COUNTRY_ADMIN0_HINTS.get(iso2, ()):
            for result in _thinkhazard_search(hint, cache):
                if _matches_country(result, iso2) and not result.get("admin1"):
                    return result, "country"
        return None, "none"

    canon_adm1 = _canonical_adm1(iso2, adm1)
    pool: dict[int, dict[str, object]] = {}
    for term in (_search_term(adm2), canon_adm1):
        for result in _thinkhazard_search(term, cache):
            if _matches_country(result, iso2):
                pool[int(result["code"])] = result

    if not pool:
        return _country_fallback()

    norm_adm1, norm_adm2 = _normalize(canon_adm1), _normalize(adm2)

    def _name_hit(candidate: str, target: str) -> bool:
        return bool(candidate and target) and (
            candidate == target or candidate in target or target in candidate)

    best_score, best_result = -1, None
    for result in pool.values():
        r_adm1, r_adm2 = _normalize(str(result.get("admin1", ""))), _normalize(str(result.get("admin2", "")))
        score = 0
        if _name_hit(r_adm2, norm_adm2):
            score += 100
        if _name_hit(r_adm1, norm_adm1):
            score += 50
        if score < 100 and not result.get("admin2"):
            score += 1  # for a pure adm1 hit, prefer the province unit
        if score > best_score:
            best_score, best_result = score, result

    if best_score >= 100:
        return best_result, "adm2"
    if best_score >= 50:
        return best_result, "adm1"
    return _country_fallback()  # country matches, name doesn't -> honestly fall back to country level


def _division_label(result: dict[str, object]) -> str:
    parts = [str(result.get(level, "")) for level in ("admin0", "admin1", "admin2")]
    return " / ".join(part for part in parts if part)


def run(*, refresh: bool = False) -> None:
    output_path = config.NATURAL_HAZARD_PATH
    if ingest_common.already_fetched(output_path) and not refresh:
        existing = pd.read_csv(output_path)
        print(f"Natural hazards skipped, {len(existing)} sites already present.")
        return

    if not ingest_common.already_fetched(UNESCO_SITES_PARQUET):
        raise RuntimeError(f"UNESCO sites missing ({UNESCO_SITES_PARQUET}). Run ingest_unesco.py first.")

    sites_gdf = gpd.read_parquet(UNESCO_SITES_PARQUET)
    cache = _Cache(CACHE_PATH)
    records: list[dict[str, object]] = []

    try:
        for row in sites_gdf.itertuples(index=False):
            site_id = int(row.site_id)
            eq_level, fl_level, division_label, code = "NDA", "NDA", "", None

            if site_id in _DIVISION_OVERRIDES:
                code, division_label = _DIVISION_OVERRIDES[site_id]
                confidence = "override"
            else:
                address = _reverse_geocode(float(row.latitude), float(row.longitude), cache)
                adm1, adm2, _ = _admin_fields(address)
                result, confidence = _choose_division(row.country_iso2, adm1, adm2, cache)
                code = int(result["code"]) if result is not None else None
                division_label = _division_label(result) if result is not None else ""

            if code is not None:
                levels = _thinkhazard_levels(code, cache)
                eq_level = _canonical_level(levels.get("EQ"))
                fl_level = _canonical_level(levels.get("FL"))

            records.append({
                "site_id": int(row.site_id),
                "name": row.name,
                "country_iso2": row.country_iso2,
                "eq_level": eq_level,
                "fl_level": fl_level,
                "division_code": code,
                "division": division_label,
                "match_confidence": confidence,
            })
            print(f"  {row.country_iso2}  EQ={eq_level:<3} FL={fl_level:<3} [{confidence}]  {row.name}")
    finally:
        cache.flush()

    hazard_df = pd.DataFrame.from_records(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    hazard_df.to_csv(output_path, index=False, encoding="utf-8")

    coarse = hazard_df[hazard_df["match_confidence"].isin(["country", "none"])]
    print(f"\nNatural hazard ingest: {len(hazard_df)} sites -> {output_path.name}")
    by_conf = hazard_df["match_confidence"].value_counts().to_dict()
    print("  Confidence:", ", ".join(f"{k}={v}" for k, v in by_conf.items()))
    if not coarse.empty:
        print(f"  Country level only ({len(coarse)}):")
        for rec in coarse.itertuples(index=False):
            print(f"    [{rec.match_confidence}] {rec.country_iso2} {rec.name} -> {rec.division or '(no match)'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Regenerate the existing CSV.")
    args = parser.parse_args()
    run(refresh=args.refresh)


if __name__ == "__main__":
    main()
