"""Single Source of Truth fuer Heritage at Risk.

Alle Parameter, Pfade, Quell-Endpunkte, Score-Gewichte und raeumlichen
Schwellen liegen ausschliesslich hier. Kein Stufen-Skript haelt eigene
hartkodierte Werte, jedes importiert aus dieser Datei. Eine Aenderung wirkt
dadurch ueberall.
"""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Pfade
#
# Grosse Rohdaten leben ausserhalb des Repos unter DATA_DIR (Umgebungsvariable
# mit sinnvollem Standard). Abgeleitete, committete Artefakte liegen im Repo
# unter ARTIFACTS_DIR.
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    """Minimaler .env-Loader: KEY=VALUE-Zeilen in os.environ uebernehmen.

    Bewusst ohne externe Abhaengigkeit (kein python-dotenv). Bereits gesetzte
    Umgebungsvariablen haben Vorrang, die Shell bzw. CI ueberschreibt die Datei
    also nicht. Secrets bleiben damit aus dem Code heraus.
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if value:  # leere Eintraege (z. B. DATA_DIR=) nicht setzen, sonst
            os.environ.setdefault(key, value)  # ueberschreiben sie den Standard


_load_dotenv(REPO_ROOT / ".env")

DATA_DIR: Path = Path(os.environ.get("DATA_DIR", REPO_ROOT.parent / "heritage_data"))
RAW_DIR: Path = DATA_DIR / "raw"          # Quellen roh und unveraendert
INTERIM_DIR: Path = DATA_DIR / "interim"  # Zwischenstaende der Verarbeitung
CACHE_DIR: Path = DATA_DIR / "cache"      # inkrementeller Cache je Element

ARTIFACTS_DIR: Path = REPO_ROOT / "artifacts"  # Laufzeit-Artefakte (committet)
REFERENCE_DIR: Path = REPO_ROOT / "reference"  # kuratierte, committete Referenzlisten
DUCKDB_PATH: Path = INTERIM_DIR / "heritage.duckdb"

# Ausgabe-Artefakte, die die App liest (Stufe 3, Export)
SITES_GEOJSON_PATH: Path = ARTIFACTS_DIR / "sites.geojson"
CONFLICT_RADIUS_GEOJSON_PATH: Path = ARTIFACTS_DIR / "conflict_radius.geojson"
CONFLICT_EVENTS_GEOJSON_PATH: Path = ARTIFACTS_DIR / "conflict_events.geojson"
BASEMAP_PMTILES_PATH: Path = ARTIFACTS_DIR / "basemap.pmtiles"

# ---------------------------------------------------------------------------
# Region of Interest: EMENA (Eastern Mediterranean & Near East)
#
# Geofabrik teilt die Region ueber zwei Kontinente. Die PBF-URLs sind noch
# gegen download.geofabrik.de zu verifizieren (siehe PROJECT_CONTEXT.md).
# ---------------------------------------------------------------------------

GEOFABRIK_BASE: str = "https://download.geofabrik.de"

# key -> (ISO-3166-alpha-2, Geofabrik-PBF-URL)
#
# Laenderumfang (2026-06-16, Dichte-Erweiterung): Das fruehere "Threat-Signal"-
# Kriterium (nur Laender mit In-Danger / Reisewarnung >= 1 / Konflikt) ist bewusst
# AUFGEGEBEN. Die Mission hat zwei Achsen, Bedrohung UND Dichte des Welterbes; um die
# Dichte und Abdeckung der weiteren Region zu zeigen, kommen Aegypten, die gesamte
# Arabische Halbinsel (Saudi-Arabien, VAE, Oman, Katar, Bahrain, Kuwait) und Jordanien
# hinzu. Stabile Laender erscheinen damit wieder (viele low-Sites), das ist gewollt.
# Geofabrik bundelt die Golfstaaten in EINEM Extract (asia/gcc-states), daher zeigen
# sechs Keys auf dieselbe PBF-URL. Palaestina hat keinen eigenen PBF-Eintrag, sein OSM
# steckt im israel-and-palestine-Extract; es kommt nur ueber COUNTRY_ISO2 in die Filter.
# Vorher schon raus und weiter draussen: die sichere Nordwest-Flanke (Griechenland,
# Zypern, Tuerkei, Armenien, Aserbaidschan).
COUNTRIES: dict[str, tuple[str, str]] = {
    "syria": ("SY", f"{GEOFABRIK_BASE}/asia/syria-latest.osm.pbf"),
    "lebanon": ("LB", f"{GEOFABRIK_BASE}/asia/lebanon-latest.osm.pbf"),
    "israel": ("IL", f"{GEOFABRIK_BASE}/asia/israel-and-palestine-latest.osm.pbf"),
    "iraq": ("IQ", f"{GEOFABRIK_BASE}/asia/iraq-latest.osm.pbf"),
    "iran": ("IR", f"{GEOFABRIK_BASE}/asia/iran-latest.osm.pbf"),
    "yemen": ("YE", f"{GEOFABRIK_BASE}/asia/yemen-latest.osm.pbf"),
    "jordan": ("JO", f"{GEOFABRIK_BASE}/asia/jordan-latest.osm.pbf"),
    "egypt": ("EG", f"{GEOFABRIK_BASE}/africa/egypt-latest.osm.pbf"),
    "saudi_arabia": ("SA", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "uae": ("AE", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "oman": ("OM", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "qatar": ("QA", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "bahrain": ("BH", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
    "kuwait": ("KW", f"{GEOFABRIK_BASE}/asia/gcc-states-latest.osm.pbf"),
}

# ISO-Codes der Region, fuer den Filter der Auswaertiges-Amt-Hinweise. Palaestina (PS)
# kommt zusaetzlich rein (eigenes Land, OSM via Israel-PBF, kein eigener Eintrag
# in COUNTRIES).
COUNTRY_ISO2: tuple[str, ...] = tuple(iso for iso, _ in COUNTRIES.values()) + ("PS",)

# Grobe Bounding Box der Region (lon_min, lat_min, lon_max, lat_max) in EPSG:4326.
# Dient als billiger Vorfilter, bevor teure Operationen laufen. lat_min auf 12.0
# (Jemen ~12-19 N), lon_min auf 28.0 gesenkt, damit Aegypten (West-WHS wie Abu Mena
# ~29.7 E) hineinfaellt; Ostgrenze 64.0 deckt Oman/VAE/Iran.
REGION_BBOX: tuple[float, float, float, float] = (28.0, 12.0, 64.0, 42.5)

# ---------------------------------------------------------------------------
# Quell-Endpunkte
#
# API-Schluessel kommen ausschliesslich aus Umgebungsvariablen, nie aus dem
# Code.
# ---------------------------------------------------------------------------

# OSM: historic=* und path=* aus der Geofabrik-PBF, via QuackOSM nach GeoParquet
OSM_TAGS_HISTORIC: tuple[str, ...] = ("historic",)
OSM_TAGS_ROUTING: tuple[str, ...] = ("path", "footway", "steps")

# OSM building=*: nur als Karten-Kontext (Footprints im Site-Umkreis + Dichte-
# "Schummerung" ueber historischen Kernen), NICHT Teil des Threat Scores. Die
# Extraktion ist beim Ingest raeumlich auf die Site-Umgebung vorgefiltert
# (geometry_filter), damit nicht ganze Laender voller Gebaeude anfallen.
OSM_TAGS_BUILDINGS: tuple[str, ...] = ("building",)

# Radius um eine UNESCO-Site, in dem Gebaeude als Kontext beruecksichtigt werden.
# Eng gewaehlt: er soll den historischen Kern / die Altstadt erfassen, nicht das
# Umland (sonst Datenvolumen und Renderer-Last, siehe PROJECT_CONTEXT.md).
BUILDINGS_NEAR_SITES_KM: float = 1.2

# Kantenlaenge der Dichte-Gitterzelle (Grad) fuer die Heatmap-Aggregation. Statt
# jedes Gebaeude einzeln einzubetten, werden Gebaeude-Zentroide zu Zellen mit
# Trefferzahl als Gewicht zusammengefasst (kleines Artefakt, echte Dichte). ~150 m.
BUILDINGS_DENSITY_CELL_DEG: float = 0.0015

# UNESCO World Heritage Centre: Site-Metadaten und Koordinaten
UNESCO_WHC_XML_URL: str = "https://whc.unesco.org/en/list/xml/"

# Offizielle Liste des gefaehrdeten Welterbes. Die Seite ist JS-gerendert, die
# Site-IDs werden per Browser gescrapt und als kuratierte, datierte CSV gepflegt.
# Das danger-Feld im list/xml ist unvollstaendig und wird NICHT als Flag genutzt.
UNESCO_DANGER_LIST_URL: str = "https://whc.unesco.org/en/danger-list/"
UNESCO_IN_DANGER_PATH: Path = REFERENCE_DIR / "unesco_in_danger.csv"

# UCDP GED: offene, georeferenzierte Konflikt-Ereignisse (Uppsala Conflict Data
# Program, CC BY 4.0 / ODbL). Alleinige Quelle der Konflikt-Komponente
# (Rueckwechsel von ACLED am 2026-07-08: UCDP hat nur ~4-6 Wochen Lag statt des
# 12-Monats-Embargos der ACLED-Research-Stufe -> der Score beschreibt die
# LAUFENDE Lage, und die offene Lizenz macht Repo und App wieder
# veroeffentlichbar). Peer-reviewed und zitierbar. Erfasst auch toedliche
# Luft-/Drohnen-/Raketenschlaege (ohne Waffentyp-Feld); bekannte Grenze:
# Schwelle >= 1 Todesopfer, nicht-toedliche Treffer fehlen (dokumentiert in
# PROJECT_CONTEXT). Zwei tokenfreie Bausteine ueber das UCDP Download Center:
# der jaehrliche Hauptdatensatz (bis Ende Vorjahr) plus der monatliche
# Candidate (laufendes Jahr, kumulativ). Bei einem neuen Release die URLs
# hochziehen.
UCDP_GED_CSV_URL: str = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
UCDP_CANDIDATE_CSV_URL: str = "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_5.csv"

# UCDP type_of_violence-Code -> Klartext (GED-Codebook): bestimmt nur das
# Kontext-Label je Event, nicht den Score (der Join ist rein raeumlich).
UCDP_VIOLENCE_TYPES: dict[int, str] = {
    1: "state-based conflict",
    2: "non-state conflict",
    3: "one-sided violence",
}

# Konflikt-Zeitfenster: rollendes Fenster ab CONFLICT_LOOKBACK_MONTHS zurueck,
# offen bis heute (UCDP-Lag ~4-6 Wochen, der juengste Monat fehlt bewusst).
# 12 Monate = die laufende Lage statt mehrjaehriger Historie; die lokale,
# AKTUELLE Intensitaets-Differenzierung ist der Mehrwert der georeferenzierten
# Konfliktdaten gegenueber der laenderweiten Reisewarnung. Bewusst rollend:
# jeder Build ist ein Schnappschuss. CONFLICT_WINDOW_END_MONTHS bleibt als
# Konstante erhalten (0 = keine juengere Kante); sie stammt aus dem ACLED-
# Intermezzo (Research-Embargo, 2026-06-24 bis 2026-07-08, siehe
# PROJECT_CONTEXT) und macht ein kuenftiges Embargo-Fenster konfigurierbar.
CONFLICT_LOOKBACK_MONTHS: int = 12     # Fensteranfang (aeltere Kante)
CONFLICT_WINDOW_END_MONTHS: int = 0    # Fensterende (0 = offen bis heute)


def _month_start_months_ago(months: int) -> str:
    today = date.today()
    year, month = today.year, today.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1).isoformat()


CONFLICT_START_DATE: str = _month_start_months_ago(CONFLICT_LOOKBACK_MONTHS)
CONFLICT_END_DATE: str = _month_start_months_ago(CONFLICT_WINDOW_END_MONTHS)

# Auswaertiges Amt: Reise- und Sicherheitshinweise als Laender-Gefaehrdungsindikator.
# Die OpenData-API liefert je Land vier Bool-Flags, keine fertige Zahlenskala.
AA_TRAVELWARNING_URL: str = "https://www.auswaertiges-amt.de/opendata/travelwarning"

# Ableitung der Warnstufe (0-2) aus den vier Bool-Flags der OpenData-API. Eine
# offizielle Zahlenskala existiert nicht, diese Zuordnung ist eine bewusste,
# dokumentierte Projektableitung (PROJECT_CONTEXT.md, Mapping der AA-Warnstufe).
# Drei Stufen reichen, massgeblich ist die Reichweite der Warnung, nicht ob sie
# strukturell oder situationsbedingt ist:
#   2  landesweite Reisewarnung  (warning oder situationWarning)
#   1  Teil-Reisewarnung         (partialWarning oder situationPartWarning)
#   0  keine Warnung
# Die Flags werden in dieser Reihenfolge geprueft, die hoechste zutreffende
# Stufe gewinnt.
AA_WARNING_LEVELS: tuple[tuple[str, int], ...] = (
    ("warning", 2),
    ("situationWarning", 2),
    ("partialWarning", 1),
    ("situationPartWarning", 1),
)
AA_WARNING_LEVEL_MAX: int = 2

# Overture Maps wurde aus dem Projektumfang genommen (2026-06-13). Begruendung in
# PROJECT_CONTEXT.md: Buildings/Places sind reiner Basemap-Kontext, nicht Teil des
# Threat Scores; die Gebaeude liefert die Provider-Basemap (Protomaps/OpenFreeMap,
# MapLibre-nativ) ohne Eigen-Tiling, und der Overture-S3-Pfad war die fragilste
# Quelle (RAM-Crashes, Segfaults, langsame Kalt-Scans). Heritage-Kontext kommt aus
# OSM historic und Pleiades.

# Pleiades: antike Ortsnamen und Koordinaten
PLEIADES_PLACES_CSV_URL: str = "https://atlantides.org/downloads/pleiades/dumps/pleiades-places-latest.csv.gz"

# Naturgefahren je Site (Erdbeben + Flusshochwasser) aus ThinkHazard! der Weltbank.
# Kuratierte, committete CSV (keyed per site_id), erzeugt von ingest_hazard.py.
# Ersetzt im Threat Score die WMF-Watch-Liste (flaggte in der Region nie eine WHS).
NATURAL_HAZARD_PATH: Path = REFERENCE_DIR / "natural_hazard.csv"

# Live-APIs der App (nicht Teil der Pipeline, hier zentral dokumentiert)
NOMINATIM_URL: str = "https://nominatim.openstreetmap.org"
OPENROUTESERVICE_URL: str = "https://api.openrouteservice.org"
OPENROUTESERVICE_API_KEY: str | None = os.environ.get("OPENROUTESERVICE_API_KEY")

# ---------------------------------------------------------------------------
# Threat Score (0 bis SCORE_MAX)
#
# Vier unabhaengige Komponenten, Gewichte 3/3/3/1 (SCORE_MAX 10). Drei bilden die
# menschliche Gefaehrdungsachse (In-Danger-Status, Reisewarnung, Konflikt) mit je 3,
# die vierte die Naturgefahr (Erdbeben + Flusshochwasser) als sekundaerer Modifikator
# mit Gewicht 1. Siehe PROJECT_CONTEXT.md.
# ---------------------------------------------------------------------------

SCORE_WEIGHT_UNESCO_IN_DANGER: int = 3   # offizielles UNESCO-In-Danger-Flag
SCORE_WEIGHT_TRAVEL_WARNING: int = 3     # Reisewarnstufe 0-2, linear skaliert
SCORE_WEIGHT_CONFLICT: int = 3           # UCDP-GED-Ereignisse im Radius (log-skaliert)
SCORE_WEIGHT_NATURAL_HAZARD: int = 1     # Erdbeben + Flusshochwasser (ThinkHazard!), sekundaer

SCORE_MAX: int = (
    SCORE_WEIGHT_UNESCO_IN_DANGER
    + SCORE_WEIGHT_TRAVEL_WARNING
    + SCORE_WEIGHT_CONFLICT
    + SCORE_WEIGHT_NATURAL_HAZARD
)

# Naturgefahr: ThinkHazard!-Stufen (Erdbeben EQ, Flusshochwasser FL) je Site auf
# [0, 1] abgebildet; "no data" (NDA) zaehlt 0. Die Komponente nimmt das MAXIMUM
# beider Gefahren (Worst-Case-Exposition: eine Site ist gefaehrdet, wenn sie EINER
# der beiden Gefahren stark ausgesetzt ist) und skaliert es mit dem Gewicht.
NATURAL_HAZARD_LEVEL_SCORES: dict[str, float] = {
    "VLO": 0.0,        # very low
    "LOW": 1.0 / 3.0,  # low
    "MED": 2.0 / 3.0,  # medium
    "HIG": 1.0,        # high
    "NDA": 0.0,        # no data
}

# Raeumlicher Konflikt-Join: Ereignisse im 30-km-Radius einer Site (DuckDB
# ST_Distance auf geographischen Koordinaten). Bewusst lokal: nur Konflikt im
# unmittelbaren Umfeld der Staette zaehlt, nicht landesweite Lage (die deckt die
# Reisewarnung ab).
CONFLICT_RADIUS_KM: float = 30.0

# Anzahl Ereignisse im Radius, ab der die Konflikt-Komponente voll zaehlt.
# Die Abbildung Ereigniszahl -> Teilscore ist LOGARITHMISCH, nicht linear:
# score = min(ln(1 + count) / ln(1 + CONFLICT_EVENTS_FOR_FULL_SCORE), 1). Begruendung:
# die Ereigniszahl je Site ist stark rechtsschief (Counts ueber Groessenordnungen,
# Gaza als Ausreisser). Eine lineare Schwelle saettigt entweder zu frueh (alle
# betroffenen Sites am Vollwert) oder ein hoher Deckel rechnet die Mehrheitswerte
# klein. Die Log-Skala verteilt die Intensitaet glatt ueber die Spanne und bewahrt
# den raeumlichen Mehrwert der Konfliktdaten gegenueber der laenderweiten
# Reisewarnung. Deckel ~p90 der aktiven Sites, datenverankert am jeweiligen
# echten Lauf (mit Quelle/Fenster/Radius nachzuziehen, revidierbar): 25 am
# 12-Monats-UCDP-Fenster toedlicher Events (geeicht 2026-06-16, beim Rueckwechsel
# 2026-07-08 gegen den frischen Lauf geprueft; das ACLED-Intermezzo nutzte 1000
# am 36-12-Monats-Fenster inkl. nicht-toedlicher Events).
CONFLICT_EVENTS_FOR_FULL_SCORE: int = 25

# ---------------------------------------------------------------------------
# Darstellung: farbcodierte Threat-Level (gruen, gelb, rot)
#
# Bricht den Score in drei Klassen. Die konkreten Farbwerte folgen dem
# GEOSPATIAL_DESIGN_GUIDE.md und werden in der Export-/App-Stufe gesetzt.
# ---------------------------------------------------------------------------

# (label, oberer Grenzwert inklusive)
THREAT_LEVEL_BREAKS: tuple[tuple[str, float], ...] = (
    ("low", 3.0),
    ("medium", 6.0),
    ("high", float(SCORE_MAX)),
)

# Invertierte Ampel: hohe Gefaehrdung = rot, niedrige = gruen (GEOSPATIAL_DESIGN_GUIDE.md,
# rag_colors). Die Farbe ist nur die redundante zweite Kodierung; die App kodiert Threat
# zusaetzlich ueber Symbol und Text (Accessibility, Guide Abschnitt 9), nie ueber Farbe allein.
THREAT_LEVEL_COLORS: dict[str, str] = {
    "low": "#1a9641",     # gruen
    "medium": "#fdae61",  # amber
    "high": "#d7191c",    # rot
}

# Menschenlesbares Label je Klasse (deutsch) fuer Legende und Detail-Sheet.
THREAT_LEVEL_LABELS: dict[str, str] = {
    "low": "niedrig",
    "medium": "mittel",
    "high": "hoch",
}

# ---------------------------------------------------------------------------
# Robuste Datenbeschaffung
# ---------------------------------------------------------------------------

HTTP_TIMEOUT_SECONDS: float = 30.0
HTTP_MAX_RETRIES: int = 5
HTTP_BACKOFF_FACTOR: float = 2.0
HTTP_RETRY_STATUS: tuple[int, ...] = (429, 500, 502, 503, 504)
HTTP_MAX_WORKERS: int = 4  # konservative Parallelitaet

# Identifizierender User-Agent mit Kontakt. WHC blockt anonyme Requests (403),
# Nominatim verlangt ihn laut Nutzungsrichtlinie.
USER_AGENT: str = "HeritageAtRisk/0.1 (academic project; sebastian.macherey@gmail.com)"
HTTP_HEADERS: dict[str, str] = {"User-Agent": USER_AGENT}
