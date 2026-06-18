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
UCDP_EVENTS_GEOJSON_PATH: Path = ARTIFACTS_DIR / "ucdp_events.geojson"
GKG_STRIKES_GEOJSON_PATH: Path = ARTIFACTS_DIR / "gkg_strikes.geojson"
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
# Program, CC BY 4.0 / ODbL). Alleinige Quelle der Konflikt-Komponente. Offen
# lizenziert, also auch fuer eine veroeffentlichte Open-Source-App rechtssicher;
# peer-reviewed und zitierbar. Erfasst auch toedliche Luft-/Drohnen-/Raketen-
# schlaege (ohne Waffentyp-Feld, Schwelle >= 1 Todesopfer). Zwei
# tokenfreie Bausteine ueber das UCDP Download Center: der jaehrliche
# Hauptdatensatz (bis Ende Vorjahr) plus der monatliche Candidate (laufendes
# Jahr). Bei einem neuen Release einfach die URLs hochziehen.
UCDP_GED_CSV_URL: str = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
UCDP_CANDIDATE_CSV_URL: str = "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_0_4.csv"

# UCDP type_of_violence-Code -> Klartext (GED-Codebook): bestimmt nur das
# Kontext-Label je Event, nicht den Score (der Join ist rein raeumlich).
UCDP_VIOLENCE_TYPES: dict[int, str] = {
    1: "state-based conflict",
    2: "non-state conflict",
    3: "one-sided violence",
}

# GDELT GKG 1.0: offener, tokenfreier Global-Knowledge-Graph-Tagesfeed. Ergaenzt
# UCDP GED um den Einschlag-Aspekt, den UCDP bewusst NICHT erfasst: nicht-toedliche
# bzw. abgefangene Luftschlaege/Drohnen/Raketen (UCDP-Schwelle >= 1 Todesopfer).
# GKG ist verrauscht (Medien-Erwaehnungen, nur orts-/stadtgenau geokodiert), also
# ein INDIKATIVER Layer, kein behoerdlich-vollstaendiger Datensatz (PROJECT_CONTEXT.md).
# Eine Datei je Tag (~365 fuer das Jahresfenster), tab-getrennt, mit Kopfzeile.
GKG_DAILY_URL_TEMPLATE: str = "http://data.gdeltproject.org/gkg/{date}.gkg.csv.zip"

# Rollendes Einschlag-Fenster, analog zum Konflikt-Fenster (aktuelle Lage, nicht
# Historie). Eigene Konstante, falls Strikes spaeter ein anderes Fenster brauchen.
STRIKE_LOOKBACK_MONTHS: int = 12

# GKG-Themen, die einen Strike-/Gewaltbezug markieren (GKG-1.0-Taxonomie). Eine
# Zeile qualifiziert, wenn ihre THEMES eine dieser Marken enthalten ODER ihre
# Quell-URL ein STRIKE_URL_KEYWORD traegt. Bewusst als Konstante: an echten
# GKG-Daten kalibrierbar, ohne Code-Aenderung (siehe Smoke-Test ingest_gkg.py).
STRIKE_THEMES: tuple[str, ...] = (
    "ARMEDCONFLICT",
    "TAX_TERROR",
    "TERROR",
    "KILL",
    "SIEGE",
    "BLOCKADE",
)

# GKG-Location-Typen, die fuer die Radius-Zaehlung granular genug sind. GKG kodiert
# je Ort einen Typ: 1=Land (Zentroid), 2=US-Bundesstaat, 3=US-Stadt, 4=Weltstadt,
# 5=ADM1-Provinz. Fuer den 30-km-Site-Radius taugen nur STADTGENAUE Orte (3/4);
# Laender-Zentroide (Type 1) liegen auf dem geografischen Mittelpunkt und sind
# reines Rauschen, Provinz-Zentroide (Type 5) sind zu grob (Fehltreffer im Radius).
STRIKE_LOCATION_TYPES: tuple[str, ...] = ("3", "4")

# Schlagwoerter, die in der Artikel-URL einen Einschlag andeuten (GKG 1.0 liefert
# keinen Volltext, aber die URL-Slugs tragen oft die Schlagzeile). Kleinschreibung,
# Substring-Match gegen die SOURCEURL.
STRIKE_URL_KEYWORDS: tuple[str, ...] = (
    "airstrike", "air-strike", "drone", "missile", "rocket",
    "shelling", "bombard", "intercept",
)

# Zeitfenster der Konflikt-Ereignisse: rollendes Fenster der juengsten
# CONFLICT_LOOKBACK_MONTHS Monate (Start = erster Tag des Monats vor N Monaten,
# inklusive, YYYY-MM-DD). Der Threat Score soll die AKTUELLE Gefaehrdung zeigen,
# nicht die gesamte Konflikthistorie. Ein einzelner Monat waere aber zu rauschig
# (Konflikt ist episodisch, Schaeden kumulieren), daher ein mehrjaehriges
# Aktuell-Fenster statt eines festen Jahres; 36 Monate decken die laufende
# Eskalation (u. a. ab Okt. 2023) ab. Bewusst rollend: jeder Build ist ein
# Schnappschuss der vorangehenden N Monate (etwas geringere Exakt-Reproduzier-
# barkeit, dafuer immer aktuell). CONFLICT_EVENTS_FOR_FULL_SCORE ggf. mit dem
# Fenster nachjustieren.
# 12 Monate: bewusst aktuelles Fenster (die laufende Lage, nicht die mehrjaehrige
# Historie); der Log-Deckel ist am p90 dieses Fensters kalibriert.
CONFLICT_LOOKBACK_MONTHS: int = 12


def _conflict_start_date(months: int) -> str:
    today = date.today()
    year, month = today.year, today.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1).isoformat()


CONFLICT_START_DATE: str = _conflict_start_date(CONFLICT_LOOKBACK_MONTHS)
STRIKE_START_DATE: str = _conflict_start_date(STRIKE_LOOKBACK_MONTHS)

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
# die UCDP-Ereigniszahl je Site ist stark rechtsschief (im 12-Monats-Fenster/30-km-Radius
# bei den betroffenen Sites Median 8, p90 ~26, ein Gaza-Ausreisser ~1850). Eine lineare
# Schwelle saettigt entweder zu frueh (alle betroffenen Sites am Vollwert) oder ein hoher
# Deckel rechnet die einstelligen Mehrheitswerte klein. Die Log-Skala verteilt die
# Intensitaet glatt ueber die Spanne und bewahrt den raeumlichen Mehrwert der Konflikt-
# daten gegenueber der laenderweiten Reisewarnung. Deckel 25 ~ p90 der aktiven Sites:
# "25+ toedliche Ereignisse in 30 km ueber 12 Monate = maximale lokale Konflikt-
# Exposition" (datenverankert, mit Fenster/Radius nachzuziehen, revidierbar).
CONFLICT_EVENTS_FOR_FULL_SCORE: int = 25

# Kombinierte Konflikt-Komponente (UCDP GED + GDELT-GKG-Einschlaege). Beide Quellen
# zaehlen Punkte im CONFLICT_RADIUS_KM je Site, werden aber EINZELN log-skaliert auf
# [0,1] (jede mit eigenem Saettigungs-Schwellwert, da ihre Mengenskalen voellig
# verschieden sind: UCDP toedlich/duenn, GKG verrauscht/dicht). Die beiden Subscores
# werden UCDP-verankert gemischt, dann mit SCORE_WEIGHT_CONFLICT skaliert:
#   conflict_factor = CONFLICT_UCDP_BLEND * ucdp_sub + (1-CONFLICT_UCDP_BLEND) * strike_sub
# So bleibt das saubere, peer-reviewte UCDP-Signal der Anker, und GKG hebt gezielt die
# Sites, die UCDP verpasst (nicht-toedliche/abgefangene Einschlaege), ohne dass das
# Medien-Rauschen die Basis dominiert.
#
# Einheit der GKG-Seite sind ORT-TAGE (ein Treffer je Ort je Tag, in ingest_gkg.py
# dedupliziert), NICHT Roh-Erwaehnungen: das entfernt den Medien-Megafon-Bias
# (Roh-Erwaehnungen waren ~17x mehr; ein Einschlag mit 500 Quellen zaehlte sonst 500x).
# STRIKE_DAYS_FOR_FULL_SCORE am p90 der aktiven Sites kalibriert (wie
# CONFLICT_EVENTS_FOR_FULL_SCORE). Datenverankert 2026-06-18 am 12-Monats-Lauf
# (383 Tage, 160.747 Ort-Tage): p90 der 95 aktiven Sites ~ 4.500 Ort-Tage im 30-km-
# Radius -> Deckel 4.500. (Roh-Erwaehnungen waeren 90.000 gewesen, aber megafon-verzerrt.)
CONFLICT_UCDP_BLEND: float = 0.6
STRIKE_DAYS_FOR_FULL_SCORE: int = 4500

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
