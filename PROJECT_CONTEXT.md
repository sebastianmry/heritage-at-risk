# PROJECT_CONTEXT: Heritage at Risk

Diese Datei ist die Single Source of Truth des Projekts. Sie haelt Entscheidungen,
Begruendungen, den aktuellen Stand und bekannte Eigenheiten fest, inklusive der
bewusst verworfenen Ansaetze. Sie waechst mit dem Projekt mit. Die fachliche Skizze
steht im PDF der Projektskizze.

## Worum es geht

Heritage at Risk ist eine mobile Location-Based App (Flutter/Android), die UNESCO World
Heritage Sites und archaeologische Staetten der MENA-Region thematisch kartiert. Jede Site
traegt einen raeumlich berechneten Threat Score von 0 bis 10 (Summe der vier Gewichte).

Laenderauswahl (Stand 2026-06-16, **Dichte-Erweiterung**): Das fruehere Threat-Signal-
Kriterium (nur Laender mit In-Danger / Reisewarnung >= 1 / Konflikt) ist bewusst AUFGEGEBEN.
Die Mission hat zwei Achsen, Bedrohung UND Dichte des Welterbes; um die Dichte und Abdeckung
der weiteren Region zu zeigen, sind zu den sieben Kernlaendern (Syrien, Libanon, Israel,
Palaestina, Irak, Iran, Jemen) **Aegypten, die gesamte Arabische Halbinsel (Saudi-Arabien,
VAE, Oman, Katar, Bahrain, Kuwait) und Jordanien** hinzugekommen. Stabile Laender erscheinen
damit wieder mit vielen low-Sites, das ist gewollt: der Score-Kontrast lebt auf der Site-Ebene.
Weiter draussen bleibt die sichere Nordwest-Flanke (GR/CY/TR/AM/AZ). Kuwait hat keine WHS.
Stand: **100 Sites**, davon 19 In-Danger. Threat-Level-Verteilung mit allen vier Komponenten
inkl. UCDP-Konflikt (2026-06-16): low 34, medium 42, high 24.

## Threat Score

Vier unabhaengige, oeffentliche Quellen bilden den Score (max 10). Drei bilden die
menschliche Gefaehrdungsachse, die vierte die Naturgefahr. Die Gewichte liegen zentral in
[config.py](config.py).

| Komponente | Quelle | Gewicht |
|---|---|---|
| In-Danger-Flag | UNESCO World Heritage Centre | 3 |
| Reisewarnstufe (0 bis 2) | Auswaertiges Amt | 3 |
| Konflikt-Ereignisse im 30-km-Radius (log-skaliert) | ACLED, DuckDB ST_Distance | 3 |
| Naturgefahr (Erdbeben + Flusshochwasser, Max der Stufen) | ThinkHazard! (Weltbank GFDRR) | 1 |

## Pipeline

Vier getrennte Stufen, jede mit definiertem Input und Output. Vorrechnen statt live rechnen.

1. **Ingest** je Quelle (`ingest_*.py`), gemeinsame Logik in [ingest_common.py](ingest_common.py).
2. **Verarbeitung** in DuckDB ([process.py](process.py)), raeumlicher Join und Score.
3. **Export** nach GeoJSON und PMTiles ([export.py](export.py)) als committete Artefakte.
4. **App** (Flutter), liest ausschliesslich die fertigen Artefakte.

## Stand

Datum: 2026-06-12.

Schritt 1 des Bauplans (Geruest) steht. Angelegt sind die zentrale `config.py`, die
`.gitignore` nach dem ignore-all-then-un-ignore-Muster, `.env.example`, die gepinnten
`requirements-pipeline.txt`, die `environment.yml` sowie die Stufen-Skripte.

Die conda-Env `heritage` (python 3.12, geopandas, duckdb, pyarrow, shapely, pyproj, requests,
lxml ueber conda-forge, quackosm und pmtiles ueber pip) ist eingerichtet. Aufruf der Skripte
ueber `C:/Users/sebas/miniforge3/envs/heritage/python.exe`.

Schritt 2, OSM-Ingest: abgeschlossen. `ingest_osm.py` laedt die Geofabrik-PBF je Land roh nach
`RAW_DIR/osm/pbf/` und konvertiert die historic=* Features via QuackOSM nach GeoParquet unter
`RAW_DIR/osm/parquet/`. Schema sauber (feature_id, tags als MAP, geometry in CRS84). Der volle
Lauf ueber alle 11 Laender ergab rund 46.805 Features (Griechenland 13.821, Tuerkei 13.465,
Israel/Palaestina 4.279, Iran 4.146, Irak 3.520, Armenien 2.519, Syrien 1.334, Zypern 1.117,
Aserbaidschan 1.073, Jordanien 1.016, Libanon 515). Die Idempotenz hat sich bestaetigt, ein
bereits vorhandenes Land (Zypern) wurde uebersprungen statt neu gerechnet.

Dieser historic=* Layer ist die ergaenzende Staetten- und Monument-Ebene (auch fuer Intra-Site).
Die UNESCO-Kernsites mit dem In-Danger-Flag kommen separat aus der WHC-Quelle.

Schritt 2, UNESCO: abgeschlossen (Inventar und In-Danger-Flag).

Inventar: `ingest_unesco.py` laedt das WHC-XML (mit identifizierendem User-Agent, sonst 403),
filtert auf die Region und legt 116 Sites als GeoParquet ab
(`RAW_DIR/unesco/unesco_sites.parquet`, Punktgeometrie in WGS84). Koordinaten stammen aus
geolocations/poi, je Site wird der POI mit passendem Region-ISO gewaehlt. Eine abgeleitete Spalte
`country_iso2` haelt das primaere Land je Site fuer den spaeteren Reisewarnstufen-Join. Sonderfall
ohne iso_code (Old City of Jerusalem, politisch bedingt leer) wird geografisch ueber die Bounding
Box eingeschlossen und per Override Israel zugeordnet (bewusste Projektzuordnung, nicht die
offizielle UNESCO-Position).

Vollstaendigkeit geprueft (2026-06-12): Es fehlt keine WHC-Site der 11 Laender. Weitere 40 Sites
mit POI in der groben Bounding Box gehoeren zu Nachbarlaendern (Aegypten, Georgien, Bahrain,
Bulgarien u. a.) und sind bewusst ausserhalb des Projektgebiets. Die Skizze nannte ~125 Sites als
Schaetzung, der praezise aktuelle Stand fuer genau diese 11 Laender ist 116.

Verteilung: Iran 28, Tuerkei 22, Griechenland 20, Israel 10 (inkl. Jerusalem), Jordanien 7,
Libanon 6, Irak 6, Syrien 6, Aserbaidschan 5, Zypern 3, Armenien 3.

In-Danger-Flag: kuratierte, datierte Liste `reference/unesco_in_danger.csv` (committet), per
Browser von whc.unesco.org/en/danger-list gescrapt (2026-06-12). 53 Sites weltweit, davon 11 in
der Region: Syrien alle 6 (Damaskus, Aleppo, Bosra, Palmyra, Crac des Chevaliers, Ancient
Villages), Irak 3 (Samarra, Hatra, Ashur), Libanon 1 (Rachid Karami Fair Tripoli), Jerusalem 1.
Das bestaetigt die Skizze (Syrien 6) und widerlegt die Hypothese einer Entfernung 2025/26.

Schritt 2, Auswaertiges Amt: abgeschlossen (Reisewarnstufe 0 bis 2 je Land).

`ingest_aa.py` holt die OpenData-Reise- und Sicherheitshinweise und legt je Region-Land eine
Warnstufe als CSV ab (`RAW_DIR/auswaertiges_amt/travel_warning_levels.csv`). Die API liefert je
Land vier Bool-Flags (warning, partialWarning, situationWarning, situationPartWarning), keine
fertige Zahlenskala. Die Ableitung der Stufe steckt zentral in `config.AA_WARNING_LEVELS`, die
hoechste zutreffende Stufe gewinnt. Drei Stufen reichen, massgeblich ist die Reichweite der
Warnung, nicht ob sie strukturell oder situationsbedingt ist: 2 = landesweite Reisewarnung
(warning oder situationWarning), 1 = Teil-Reisewarnung (partialWarning oder situationPartWarning),
0 = keine Warnung.

Voller Lauf (2026-06-12): alle 11 Region-Laender vorhanden, keine fehlen. Stufe 2 Irak, Iran,
Libanon, Syrien; Stufe 1 Armenien, Aserbaidschan, Israel; Stufe 0 Zypern, Griechenland, Jordanien,
Tuerkei. Die API fuehrt Palaestina (PS) als eigene volle Reisewarnung, doch PS ist nicht Teil von
`COUNTRY_ISO2`; die Jerusalem-Site ist bewusst Israel (Stufe 1) zugeordnet (siehe Sonderfall oben).
Die Idempotenz hat sich bestaetigt, der zweite Lauf hat die vorhandene CSV uebersprungen.

Schritt 2, Pleiades: abgeschlossen. `ingest_pleiades.py` laedt den globalen Places-Dump (csv.gz),
filtert auf die Region-BBox und legt 13.452 antike Orte als GeoParquet ab
(`RAW_DIR/pleiades/pleiades_places.parquet`, Punktgeometrie, WGS84). Zurueckgezogene Eintraege
(path /errata/ statt /places/, 47 Stueck) werden verworfen. Abweichung vom Stub bewusst: Ausgabe
als GeoParquet statt CSV, konsistent zum UNESCO-Ingest und passend fuer den raeumlichen Join.

Overture Maps: aus dem Projektumfang genommen (2026-06-13, siehe Bewusst verworfene Ansaetze).
`ingest_overture.py`, der Overture-Config-Block und die Rohdaten (`RAW_DIR/overture/`) sind entfernt.
Gebaeude und allgemeiner Karten-Hintergrund kommen aus der Provider-Basemap (Protomaps/OpenFreeMap),
Heritage-Kontext aus OSM historic und Pleiades.

Schritt 2, ACLED: OAuth2-Ingest implementiert, blockiert durch fehlende Konto-Freischaltung.

`ingest_acled.py` holt per OAuth2-Password-Grant einen 24-h-Bearer-Token (E-Mail + Passwort aus
`.env`) und fragt den read-Endpunkt je Land (ISO-numerisch, inkl. Palaestina 275) paginiert ab dem
`ACLED_START_DATE` (2022-01-01) ab, Ausgabe als GeoParquet. `config.py` laedt `.env` jetzt selbst
(minimaler Loader, kein python-dotenv). Verifiziert (2026-06-12): Token-Abruf liefert 200 und einen
gueltigen Token, aber der read-Endpunkt gibt `403 "Access denied"` - mit Token UND per
Cookie-Methode im eingeloggten Browser, bei zwei frischen Konten (gmail und BHT-Instituts-Mail).
Das ist kein Code-Problem, sondern fehlende Daten-/API-Freischaltung neuer ACLED-Konten (Aktivierung
braucht Zeit bzw. manuelle Pruefung). Sobald der Zugang aktiv ist, laeuft das Skript unveraendert.

Retest 2026-06-13: unveraendert 403. Jetzt praezise diagnostiziert: Token-Abruf 200, das JWT traegt
aber nur `scope: ["authenticated"]` (Account-ID `sub: 201977`, `aud: acled`), keine Daten-Zugriffsstufe;
der read-Endpunkt antwortet `403 {"message":"Access denied"}` (`x-consumer-id: acled`). Laut ACLED-Doku
wird einem Konto nach der Registrierung eine Access-Stufe in der myACLED-Plattform zugewiesen,
Freischaltungen koennen "one working day" dauern. Die Konten sind Fr 2026-06-12 angelegt, der 13.06. ist
ein Samstag, ein Werktag ist also noch nicht vergangen. Naechste Schritte: (1) im myACLED-Dashboard die
zugewiesene Access-Stufe und offene Schritte (Terms/Access-Policy) pruefen, (2) bis Mo/Di warten,
(3) sonst access@acleddata.com kontaktieren (Account-ID 201977, "authenticated token, read 403").

Retest 2026-06-14 (So): unveraendert. Token-Abruf 200, JWT weiterhin nur `scope: ["authenticated"]`
(`sub: 201977`, `aud: acled`), read-Endpunkt `403 {"message":"Access denied"}` (`x-consumer-id: acled`).
Erwartbar, da seit der Konto-Anlage (Fr 12.06.) nur Wochenende vergangen ist, noch kein Werktag.
Naechster sinnvoller Versuch Mo/Di (15./16.06.); bleibt es 403, access@acleddata.com kontaktieren.

Schritt 2, WMF Watch List: abgeschlossen (kuratierte Referenzdaten).

`reference/wmf_watch_list.csv` (committet, manuell gepflegt) haelt die regionsrelevanten Eintraege der
World Monuments Watch. Die Watch erscheint biennal mit je 25 globalen Sites; beruecksichtigt sind die
drei juengsten Zyklen 2020, 2022 und 2025 (kein 2024er Zyklus, biennaler Sprung 2022 -> 2025). Ein
einzelner Zyklus traegt zu wenige Regions-Sites fuer eine Score-Komponente; fruehere Watch-Sites
bleiben WMF-Anliegen, daher das Drei-Zyklen-Fenster (revidierbare Projektentscheidung, datiert
2026-06-13). In den 11 Laendern liegen vier Eintraege: Mam Rashan Shrine/Sinjar (IQ, 2020), Heritage
Buildings of Beirut (LB, 2022), Serifos Historic Mining Landscape (GR, 2025), City of Antakya (TR, 2025).

Die WMF-CSV traegt eigene Koordinaten (Spalte `coord_source` dokumentiert die Genauigkeit je Punkt,
verifiziert vs. Naeherungs-Zentroid) fuer die spaetere App-Kartenebene, und eine optionale Spalte
`unesco_site_id`, die nur gefuellt ist, wenn ein WMF-Eintrag selbst eine unserer 116 WHS ist. Gaza
Historic Urban Fabric (2025) wurde geprueft und bewusst ausgelassen: es liegt in Palaestina (PS), das
nicht zu `COUNTRY_ISO2` gehoert (gleiche Grenze wie bei den PS-UNESCO-Sites).

WMF-Join-Regel (Entscheidung 2026-06-13): site-genau ueber **Identitaet** (`unesco_site_id`), nicht
ueber Naehe oder landesweit. Begruendung: WMF-Watch-Sites und unsere 116 WHS sind in der Region fast
disjunkte Mengen. Distanz jedes WMF-Eintrags zur naechsten WHS: Beirut->Byblos 24,5 km, Antakya->Ancient
Villages of Northern Syria 65,8 km, Serifos->Delos 93,3 km, Mam Rashan->Hatra 112,0 km. Ein Naehe-Match
(25 km) haette nur Byblos geflaggt, und das fehlerhaft (der Eintrag ist "Heritage Buildings of Beirut",
nicht Byblos). Ein landesweiter Match (jede Site eines Landes mit WMF-Eintrag) haette 54 von 116 Sites
geflaggt (alle in GR/IQ/LB/TR), das Signal verwaessert und die landesweite Reisewarnung dupliziert.
Daher Identitaet: aktuell flaggt keiner der vier Eintraege eine WHS, die Komponente ist 0 von 116
(ehrlich und sauber; springt an, sobald eine Region-WHS auf die Watch kommt und `unesco_site_id`
gefuellt wird). Die WMF-Daten bleiben ueber die Koordinaten als eigene App-Ebene nutzbar.

Schritt 3, Verarbeitung/Score (process.py): abgeschlossen (ACLED-tolerant).

`process.py` fuehrt die Quellen in DuckDB (Spatial) zusammen und schreibt je UNESCO-Site den Threat
Score in die Tabelle `site_scores` (config.DUCKDB_PATH). Vier Komponenten gemaess config-Gewichten:
In-Danger (3, binaer, Join per site_id an unesco_in_danger.csv), Reisewarnstufe (3, linear
warning_level/AA_WARNING_LEVEL_MAX), Konflikt (3, linear COUNT ACLED im CONFLICT_RADIUS_KM bis
CONFLICT_EVENTS_FOR_FULL_SCORE), WMF-Watch (1, binaer, Eintrag im WMF_MATCH_RADIUS_KM). Die raeumlichen
Komponenten zaehlen Punkte ueber `ST_Distance_Sphere(ST_Point(lon,lat), ...)`; die WKB-Geometrie der
Parquets wird bewusst NICHT dekodiert, die latitude/longitude-Spalten genuegen (robuster, kein
GeoParquet-WKB-Roundtrip). Output-Spalten tragen je Komponente Flag/Count und Teilscore plus
`total_score` und `threat_level` (Klassen aus THREAT_LEVEL_BREAKS).

ACLED-Toleranz: fehlt `acled_events.parquet`, liefert die events-CTE eine typkorrekte Leermenge und die
Konflikt-Komponente wird fuer alle Sites 0; der Rest rechnet durch. Faellt ohne Codeaenderung ein,
sobald die Datei existiert.

Voller Lauf (2026-06-13, ohne ACLED, WMF identitaetsbasiert): 116 Sites bewertet. Threat-Level low=105,
medium=11 (kein high, da die Konflikt-Komponente mangels ACLED noch 0 ist). In-Danger 11 (deckt sich mit
der Danger-CSV), WMF-Watch 0 (kein WMF-Eintrag ist eine WHS, siehe WMF-Join-Regel oben). Spitze: die
syrischen In-Danger-Sites und Samarra (IQ) mit 6.0 (In-Danger 3 + Reisewarnung Stufe 2 = 3). Max-Score
6.0, sauber <= SCORE_MAX 10. Der Konflikt-Join wurde mangels echter ACLED-Daten mit synthetischen Events
gegengeprueft (Punkte nahe Palmyra/Aleppo ergaben korrekt 3 bzw. 1 Treffer im 50-km-Radius); der
ACLED-Pfad ist damit verifiziert.

Schritt 3, Export (export.py): GeoJSON abgeschlossen, PMTiles offen.

`export.py` liest site_scores und schreibt `artifacts/sites.geojson` (committet): die 116 Sites als
FeatureCollection (Punkt, CRS84) mit expliziter, stabiler Property-Reihenfolge (Identitaet, Score-
Zerlegung je Komponente, total_score, threat_level) plus Darstellungshilfen `threat_label` (deutsch) und
`threat_color`. Die Farbe ist die invertierte Ampel (hoch = rot `#d7191c`, mittel `#fdae61`, niedrig
`#1a9641`, GEOSPATIAL_DESIGN_GUIDE.md), zentral in `config.THREAT_LEVEL_COLORS`/`THREAT_LEVEL_LABELS`;
Threat ist redundant ueber threat_level/Label kodiert, nie nur ueber Farbe (Accessibility). Ein
`metadata`-Block im FeatureCollection haelt Titel, Datum, Score-Komponenten samt Gewichten/Quellen,
Threat-Klassen, CRS, Lizenz und Kontakt (Guide Abschnitt 7). Geschrieben via Python json mit
`ensure_ascii=False`, UTF-8 verifiziert (Goebekli Tepe, Catalhoeyuek, Masjed-e Jame korrekt). Voller
Lauf 2026-06-13: 116 Features.

PMTiles-Kontext-Tileset (`config.BASEMAP_PMTILES_PATH`): noch offen, bewusst nicht erzwungen.

Inhalt geklaert (Entscheidung 2026-06-13, aktualisiert nach Overture-Streichung): Wir produzieren KEINE
allgemeine Basiskarte (Strassen, Wasser, Labels, Gebaeude) - die kommt als fertige Provider-Basemap
(Protomaps oder OpenFreeMap, beide MapLibre-nativ, open, ohne API-Key, offline-tauglich; enthalten
bereits Gebaeude mit Hoehen). MapLibre ist nur die Render-Engine, nicht die Kartendaten. Das loest auch
das Tiler-Problem, weil der fertige Regions-Extract geladen statt selbst getilet wird.

Unser eigener Heritage-Kontext kommt aus `export_context.py` als committetes GeoJSON-Overlay
`artifacts/pleiades.geojson` (antike Orte). Es ist auf die **Umgebung der Sites** beschnitten (nur Orte
im `CONTEXT_NEAR_SITES_KM`-Radius, aktuell 15 km, einer UNESCO-Site). Begruendung: region-weit waeren es
13.452 Orte; der Umkreis-Filter passt zum App-Verhalten (Kontext nur dort, wo man hinzoomt) und ergibt
bei 15 km region-weit ~1.500 Orte. OSM historic war zwischenzeitlich als zweite Kontextebene drin, wurde
aber wieder verworfen (zu dicht/rauschig, Pleiades genuegt; siehe Bewusst verworfene Ansaetze). Die
bewerteten Sites bleiben als score-gestyltes GeoJSON. `config.BASEMAP_PMTILES_PATH` zeigt auf den
Provider-Basemap-Extract; ein eigener Tiler ist fuer das kleine Overlay nicht noetig.

Pleiades-Dedup (2026-06-15): Viele Welterbestaetten sind selbst antike Orte und stehen damit auch in
Pleiades (Palmyra, Babylon, Damascus, Persepolis ...), was zwei Marker fuer dieselbe Staette ergibt.
`export_context.py` verwirft einen Pleiades-Punkt, wenn er im `DEDUP_NEAR_SITES_M`-Umkreis (2 km) einer
UNESCO-Site liegt UND denselben Namen traegt (Geruestwoerter wie "Site of"/"Ancient City of" gestrippt,
an `/`/`:`/`and` gesplittet, Diakritika gefoldet, exakt oder Fuzzy >= 0,85 fuer Transliterationen wie
Bisotun~Bisutun). Bewusst NUR ueber Namensidentitaet, nicht per Radius: rund um eine Site liegen viele
eigenstaendige antike Orte (Babylons Tore und Tempel, die Assur-Archive, Palmyra-Monumente), die als
Kontext erhalten bleiben. Voller Lauf: 27 Dubletten verworfen, 591 Pleiades-Orte bleiben (74-Site-Set).
Harte Transliterationen ohne Treffer (Erbil~Qa`lah Arbil, Shahr-i Sokhta~Shahr-e Sukhteh, Tyre~Tyrus)
bleiben bewusst drin (im Zweifel behalten ist die sichere Richtung).

Basemap-Stil gewaehlt (2026-06-13): minimalistisch-modern, monochrom, damit die threat-farbigen Sites
herausstechen (Farbe = Datenkodierung). Konkret CARTO Positron (hell) und Dark Matter (dunkel), beide
MapLibre-nativ und ohne API-Key. Fuer den Prototyp direkt von CARTO geladen; fuer die spaetere
Offline-Flutter-App das gleiche Look-and-feel als selbstgehostetes Protomaps-PMTiles.

Karten-Prototyp gebaut: `mockups/heritage_map_prototype.html` (eigenstaendig, im Browser zu oeffnen),
erzeugt per `mockups/build_map_prototype.py` aus `artifacts/{sites,pleiades,building_density}.geojson` (bei
Datenaenderung neu ausfuehren; schreibt auch `mockups/index.html` fuer den lokalen Vorschau-Server).
MapLibre GL JS, CARTO-Basemap. Ebenen (von oben): die 116 Sites als Threat-Hero (invertierte Ampel,
Punktgroesse zusaetzlich nach Score); Pleiades (Indigo) als dezenter Kontext, bewusst ausserhalb des
Threat-Ramps; die Bebauungsdichte-Schummerung (warme Heatmap aus building_density, ab Zoom 6,5,
ausblendend bei sehr hohem Zoom); und die warm eingefaerbten Gebaeude der Basemap (ab hohem Zoom).
Kontextebenen erscheinen progressiv beim Reinzoomen. Hell/Dunkel-Umschalter (per `transformStyle` atomar,
kein Layer-Verlust; die Basemap-Gebaeude werden nach dem Wechsel auf `idle` neu eingefaerbt, da sie beim
`style.load` noch nicht zuverlaessig abfragbar sind), Legende mit Klassen-Filter und Kontext-Toggles
(inkl. Gebaeude-Toggle), Detail-Popups (Score-Zerlegung bzw. Pleiades-Info). Daten liegen in
`<script type="application/json">`-Bloecken; sites sofort geparst, die uebrigen Ebenen erst nach dem ersten
Frame. Im Browser-Render verifiziert (2026-06-14, hell und dunkel, ueber Damaskus und Zypern reingezoomt:
Schummerung sitzt ueber den historischen Kernen, Basemap-Gebaeude warm, Theme-Wechsel und Gebaeude-Toggle
korrekt, keine Konsolenfehler). Datei ~1,0 MB.

Buildings- und Schummerung-Feature (Anforderung 2026-06-13): abgeschlossen am 2026-06-14.

Stufe 1 `ingest_osm_buildings.py` extrahiert building=* je Land via QuackOSM aus den schon vorhandenen
Geofabrik-PBFs, raeumlich vorgefiltert auf die Site-Umgebung (geometry_filter = Union grosszuegiger
Puffer um die Site-Punkte), Ausgabe `RAW_DIR/osm/parquet/<land>_buildings.parquet`. So fallen statt
Millionen Gebaeude je Land nur die nahe der Sites an (Voller Lauf 2026-06-14: ~131.000 Gebaeude im
Umkreis, Griechenland 33.157, Syrien 27.409, Israel 20.192, Libanon 15.529, Tuerkei 11.737, Irak 11.411,
Iran 5.194, Jordanien 2.086, Aserbaidschan 1.705, Armenien 1.323, Zypern 1.128). Idempotent und
land-einzeln (`--only`); der QuackOSM-Lauf vertraegt einen Abbruch (ein Laptop-Absturz hatte ein
Temp-Parquet beschaedigt, der Retest der betroffenen Laender lief sauber durch).

Stufe 3 `export_buildings.py` aggregiert die Gebaeude-Zentroide im `BUILDINGS_NEAR_SITES_KM`-Radius (1,2 km)
zu einem Dichte-Gitter (`BUILDINGS_DENSITY_CELL_DEG`, ~150 m) und schreibt ein gewichtetes
`artifacts/building_density.geojson` (5.959 Zellen, max 328 Gebaeude/Zelle, 0,58 MB). Das ist die
"Schummerung": eine warme MapLibre-Heatmap (Glut-Look, Transparent ueber Gold/Amber bis Tief-Ember) ab
mittlerem Zoom, die bei sehr hohem Zoom ausblendet. Die Aggregation statt Roh-Embed ist Absicht.

Gebaeude-Footprints kommen NICHT aus eigenen Daten, sondern aus der Provider-Basemap: CARTO Positron und
Dark Matter fuehren beide eine `building`/`building-top`-Ebene. Der Prototyp faerbt sie bei hohem Zoom warm
ein (Sandton je Theme) und macht sie per Legende schaltbar. Begruendung: ein eigener Footprint-Export im
Site-Radius waere ~88.000 Polygone / ~17 MB (auch bei 0,5 km noch ~18.700), zu gross fuer den Inline-Embed
und der Renderer-Last nicht wert; die Basemap hat die Geometrie ohnehin (Entscheidung 2026-06-14, siehe
Bewusst verworfene Ansaetze). Der Score bleibt unberuehrt, das ist reine Darstellung.

Schritt 4, Flutter-App: BUILD VERIFIZIERT UND AUF GERAET (2026-06-14). Debug-APK baut, installiert und
laeuft auf dem physischen Pixel 8; die Threat-Karte rendert nativ.

**Toolchain eingerichtet (2026-06-14):** Flutter 3.44.2 stable (Dart 3.12.2) unter `C:\flutter`, Microsoft
OpenJDK **21** (`C:\Java\jdk-21.0.11+10`; war zuerst JDK 17, siehe unten), Android SDK (`C:\Android`: cmdline-tools/latest, platform-tools,
platforms android-35+36, build-tools 35+36, NDK 28.2.13676358, CMake 3.22.1, alle Lizenzen akzeptiert), PowerShell 7.6.2 (`C:\PowerShell7`).
`flutter doctor`: Flutter + Android-Toolchain gruen. Test-Ziel ist ein physisches Android-Handy (kein Emulator).
Drei Windows/Git-Bash-Stolpersteine geloest (Details in der Memory `flutter-toolchain-setup.md`): (1) sauberer
Windows-PATH noetig, sonst ueberdeckt MSYS-`timeout` die Windows-`timeout.exe`; (2) Windows PowerShell 5.1 crasht
sporadisch mit AccessViolation beim Engine-Versions-Check, daher PowerShell 7 (Flutter nutzt `pwsh` automatisch,
wenn auf PATH); (3) `cmd //c` mit geschachtelten Quotes bricht, lieber `.bat`-Helfer. **Aufruf immer ueber den
Wrapper:** `cmd //c "C:\Users\sebas\heritage_win_env.bat flutter.bat <args>"` (in Git-Bash `//c`, nicht `/c`).

**App-Projekt:** `app/` im Repo (`flutter create --org de.bht --project-name heritage_at_risk --platforms android`,
applicationId `de.bht.heritage_at_risk`). Konfiguriert: `pubspec.yaml` mit `maplibre_gl: ^0.26.1` und
`flutter_riverpod: ^2.6.1`; die drei Artefakte als gebuendelte Assets unter `app/assets/data/`
(sites/pleiades/building_density.geojson, beim Datenneubau neu kopieren). Android: INTERNET- und
Location-Permissions im Manifest, `minSdk = maxOf(24, flutter.minSdkVersion)`, Kotlin 2.3.20 (schon ok fuer maplibre).

**App-v1-Code geschrieben** (mirror des Karten-Prototyps, gegen die echte maplibre_gl-0.26.1-API verifiziert):
`lib/main.dart` (Root mit Hell/Dunkel-Zustand fuer UI-Theme + Basemap, ProviderScope fuer spaeteres Riverpod),
`lib/theme.dart` (zentrale Farben: BHT-Petrol fuers UI, invertierte Ampel fuer Threat, Pleiades-Indigo),
`lib/basemap.dart` (CARTO Positron/Dark-Matter-URLs), `lib/map/map_screen.dart` (laedt die drei GeoJSON-Assets,
Ebenen: Dichte-Heatmap ab Zoom 6, Pleiades-Circles ab Zoom 7, Sites-Circles als Threat-Hero mit
`circle-color = get threat_color` und score-abhaengigem Radius; Tap -> queryRenderedFeatures -> Detail-Sheet;
Threat-Filter via setFilter `in/literal`; Pleiades/Dichte via setLayerVisibility; Hell/Dunkel via styleString-Wechsel
und Re-Add in onStyleLoadedCallback), `lib/map/site_detail_sheet.dart` (Score-Zerlegung der vier Komponenten),
`lib/map/threat_legend.dart` (Klassen-Filter + Kontext-Toggles). `test/widget_test.dart` auf schlanke Logik-Tests
umgestellt. `import 'dart:math' show Point;` noetig, da maplibre_gl `Point` nicht re-exportiert.

**Build-Lauf erledigt (2026-06-14):** `flutter analyze` sauber, dann `flutter build apk --debug` und Install
aufs Pixel 8. Zwei Huerden auf dem Weg, beide geloest:

- **JDK 17 -> 21 noetig.** `maplibre_gl 0.26.1` erzwingt in seiner `android/build.gradle` fest
  `JavaVersion.VERSION_21` (sourceCompatibility/targetCompatibility/kotlinOptions.jvmTarget). JDK 17 bricht
  mit `invalid source release: 21` ab (ein JDK kann nur bis zur eigenen Version `--release`n). Loesung:
  Microsoft OpenJDK 21 (`C:\Java\jdk-21.0.11+10`) installiert, im Wrapper `heritage_win_env.bat` JAVA_HOME +
  PATH umgestellt. Unsere App bleibt auf Java 17 (`app/build.gradle.kts`), JDK 21 baut das Plugin auf 21 und
  die App auf 17 problemlos.
- **JVM-Crashes des Gradle/Kotlin-Daemons (Hardware-Instabilitaet).** Der Daemon verschwand mehrfach mit
  `EXCEPTION_ACCESS_VIOLATION` in `jvm.dll` an wechselnden Stellen (vtable chunks, C2 ClassReader,
  resolve_virtual_call) zu wechselnden Zeitpunkten (26/105/557 s). Das ist KEIN Speicher- oder Single-Bug,
  sondern stochastisch -> passt zu den schon dokumentierten sporadischen `AccessViolation`-Crashes von
  PowerShell 5.1 auf genau diesem Laptop (Verdacht defektes RAM, MemTest steht aus). Abmilderung in
  `app/android/gradle.properties`: Heap 8G->4G, Metaspace 4G->2G, CodeCache 512m->256m, **`-XX:TieredStopAtLevel=1`**
  (C2-JIT aus, nur C1). Damit kam der Build viel weiter; ein letzter Kotlin-Daemon-Crash wurde von Flutters
  Auto-Retry ("Retrying Gradle Build: #1") aufgefangen, der zweite Versuch lief durch:
  `Built build\app\outputs\flutter-apk\app-debug.apk` (~180 MB).

**Install/Run verifiziert (2026-06-14):** Pixel 8 (shiba) per USB, USB-Debugging autorisiert (`adb devices` = `device`).
Install via `adb install -r` von einem Pfad OHNE Leerzeichen (das verschachtelte `cmd //c`-Quoting zerbricht
Leerzeichen-Pfade -> APK nach `C:\Users\sebas\app-debug.apk` kopieren). Start via `adb shell monkey -p de.bht.heritage_at_risk`.
Logcat sauber (kein FATAL/AndroidRuntime), MapLibre-RenderThread parst den CARTO-Style, App rendert. Screenshot
bestaetigt v1: App-Bar (BHT-Petrol) + Hell/Dunkel-Toggle, CARTO-Positron-Basemap mit Gebaeuden, Threat-Site
(orange/Mittel) + Pleiades-Punkt (indigo), Legende (Threat-Level + Kontext). Die "Mbgl-HttpRequest Canceled"-
und "line dasharray"-Warnungen kommen vom CARTO-Style und sind harmlos.

**Zwei Geraete-Bugs gefixt (2026-06-14), beide am Pixel 8 verifiziert:**
- **Sites-Tap oeffnete kein Detail-Sheet.** Ursache: `addCircleLayer` ist per Default interaktiv
  (`enableInteraction: true`), deshalb feuert MapLibre-Native bei einem Treffer `feature#onTap` und NICHT
  `map#onMapClick` (nur bei Leer-Tap). Die App lauschte aber nur auf `onMapClick` + `queryRenderedFeatures` ->
  bei Site-Treffer passierte nie etwas, bei Leer-Tap fand die Query nichts. Fix in `map_screen.dart`:
  `controller.onFeatureTapped.add(_onFeatureTapped)` in `onMapCreated`; bei `layerId == sites` die Properties
  ueber `queryRenderedFeaturesInRect` (kleines Toleranz-Rechteck statt Einzel-Pixel) holen und das Sheet oeffnen.
  `onMapClick`-Pfad entfernt. Verifiziert: Damascus (6.0) und Goereme (0.0) zeigen korrekte Score-Zerlegung.
- **Gebaeude fehlten.** App-v1 hat die Basemap-Gebaeude nie angefasst (anders als der Prototyp). Fix:
  `_styleBasemapBuildings()` ermittelt nach jedem Style-Load via `getLayerIds()` alle Ebenen mit "building" im
  Namen und faerbt sie warm (`setLayerProperties(FillLayerProperties(fillColor: ...))`, Ton je Theme aus
  `AppColors.buildingWarm*Hex`), defensiv per try/catch (Nicht-Fill-Ebenen ueberspringen). Neuer Legenden-Toggle
  "Gebaeude (ab hohem Zoom)" (`_toggleBuildings` -> setLayerVisibility). Verifiziert: warme Footprints ab hohem
  Zoom (Ort Arsal). Hinweis: Gebaeude erscheinen erst bei hohem Zoom (CARTO-Building-Ebene hat eigene minzoom).

`flutter analyze` sauber, APK neu gebaut/installiert.

**Englische UI, Pleiades-Tap, Kontext-Ueberschrift (2026-06-14), am Pixel verifiziert:**
- **Pleiades klickbar.** Die Pleiades-Ebene war `enableInteraction: false` -> kein Tap. Jetzt interaktiv;
  `_onFeatureTapped` routet `layerId == pleiades` auf das neue `PleiadesSheet` (`lib/map/pleiades_sheet.dart`,
  zeigt Name/Typ/Hinweis "Context layer, no threat score" + Pleiades-URL zum Kopieren). Sites und Pleiades teilen
  sich `_showDetailAt(point, layerId)`. Vom Nutzer bestaetigt.
- **Komplett englische UI.** Alle sichtbaren Strings + Code-Kommentare auf Englisch: Legende (Threat level,
  High/Medium/Low, Context, Ancient places (Pleiades), Building density, Buildings (high zoom)), Detail-Sheets
  (Yes/No, Level X, X events, Sources ...), Tooltip (Light/Dark theme). Threat-Label kommt jetzt aus
  `AppColors.threatLabel(level)` (Englisch) statt aus dem deutschen Daten-Feld `threat_label`.
- **Kontext-Ueberschrift.** Neues `_ContextPanel` oben (mirror des Prototyp-Titelpanels): Kurzbeschreibung
  ("Threat score 0-10 per UNESCO World Heritage Site ... from four weighted sources.") + Site-Zaehler
  ("116 sites · conflict data pending (ACLED)"). Count als Parameter (nicht const), damit er bei setState neu baut.

**Git-Repo angelegt (2026-06-14).** `git init` (Branch `master`), erster Commit `755273a` (59 Dateien). Die
`.gitignore` (vorher nur Python-Pipeline) wurde um die App-Quellen erweitert (Dart/Gradle/kts/xml/json/png/jar/
properties + `app/assets/**`) und schliesst Build-Output, `local.properties`, `.dart_tool`, `.gradle`, `.claude/`
und transiente Logs aus. Verifiziert: keine APK/Rohdaten/Caches im Commit. Englisches `README.md` im Repo-Wurzel;
PROJECT_CONTEXT.md bleibt bewusst deutsch (Arbeitsdokument). Push zu GitHub macht der Nutzer
selbst (noch kein Remote).

**Mission praezisiert (2026-06-14):** Das Projekt soll die aussergewoehnliche *Dichte* an Weltkulturerbe der
Region sichtbar machen UND ihre Bedrohung (Zerstoerung wie durch den IS: Palmyra, Mossul, Nimrud, Hatra).
Aufteilung: die Dichte traegt die App (volle Karte + Heritage-Heatmap + Zahlen), die Bedrohung soll u. a. das
App-Icon tragen (zerstoertes/bedrohtes Monument).

**Laender-Refokus auf die Krisenregion (2026-06-14), Pipeline neu gelaufen, NOCH NICHT als APK gebaut/getestet:**
- `config.py` umgestellt: GR/CY/TR/AM/AZ raus (sichere Nordwest-Flanke, ~53 "niedrig"-Sites), Jemen (YE) und
  Palaestina (PS, eigenes Land, OSM via Israel-PBF) rein. `COUNTRY_ISO2` + `("PS",)`, `REGION_BBOX` lat_min auf 12
  (Jemen), `ACLED_COUNTRY_ISO_NUMERIC` neu (inkl. 887 YE). Begruendung im COUNTRIES-Kommentar.
- Pipeline mit `--refresh`/`--recompute` neu: UNESCO **74 Sites** (statt 116), AA 8 Laender (6 davon Stufe 2:
  IQ/IR/LB/PS/SY/YE; IL Stufe 1; JO Stufe 0), process 74 bewertet (Threat low=56, medium=18, In-Danger **18**,
  ACLED weiter 0). `unesco_in_danger.csv` ist weltweit vollstaendig -> Jemen/Palaestina-Flags greifen automatisch.
- Pleiades neu (618 Orte um die 74 Sites), in der App **groesser/praesenter** (Radius/Deckkraft hoch, ab Zoom 6,
  weisser Rand).
- **Heatmap kombiniert jetzt Gebaeude + historic** (`export_buildings.py` erweitert: `<land>_historic.parquet`
  mit `HISTORIC_WEIGHT=4` zusaetzlich zu `<land>_buildings.parquet`, beide Zentroide ins Dichtegitter). Damit
  gluehen auch abgelegene Ruinen (Palmyra), nicht nur moderne Staedte. Legende: "Heritage & old town density".
  Layer-Reihenfolge unten->oben: Heatmap, Pleiades, Sites (Sites oben). Jemen-Gebaeude fehlen (QuackOSM crasht an
  arabischem UTF-8: `Invalid string encoding "\xD8\xA7"`); Jemen ist aber ueber `yemen_historic.parquet` (716) in
  der Heatmap. Artefakte nach `app/assets/data/` kopiert.

**Stand 2026-06-15:** Laender-Refokus am Pixel 8 verifiziert (Debug-APK neu gebaut/installiert, 74 Sites,
groessere Pleiades, kombinierte Heatmap rendern, Kopfzeile "74 sites"). Drei kleine Fixes committet: (1)
Region-Label EMENA->MENA (Kontextpanel + Doc-Kommentar), (2) Querformat-Overflow behoben (Legende und beide
Detail-Sheets in `SingleChildScrollView`, scrollen statt RenderFlex-Overflow bei kleiner Hoehe; per erzwungener
Geraeterotation verifiziert), (3) Pleiades-Dedup gegen UNESCO-Namensdubletten (siehe Pleiades-Abschnitt, 27 raus).

**Stand 2026-06-15 (spaeter):** Jordanien per Threat-Signal-Kriterium entfernt (siehe "Worum es geht"):
config.py (COUNTRIES + ACLED-Numerik), `ingest_unesco.py --refresh` -> 67 Sites, dann process/export/
export_context/export_buildings neu, Assets kopiert, APK gebaut/installiert, am Pixel verifiziert (67 Sites,
Jordanien-Raum leer). Petra faellt damit weg (bewusst akzeptiert).

**3D-Modell-Ebene (v1) fertig + am Pixel verifiziert (2026-06-15).** Kuratierte `reference/heritage_3d_models.csv`
(Name, country_iso2, is_whs, unesco_site_id, lat/lon, coord_source, source, author, license, model_url, note) ->
`export_3d.py` (filtert auf config.COUNTRY_ISO2) -> `artifacts/heritage_3d.geojson` (7 Eintraege). App: cyan
Ring-Layer (`models3d`) ueber den Sites, Legenden-Toggle "3D models", Tap -> `Model3DSheet` (Metadaten + "View 3D
model"-Button, oeffnet die Modellseite extern via **url_launcher**; dafuer Dependency + Manifest-`<queries>`
https-VIEW ergaenzt). Traegt zweierlei: gescorte WHS mit Modell (Palmyra, Babylon, Baalbek, Persepolis) UND
bewusst zerstoerte **Nicht-WHS-Ikonen unserer Laender** (Mosul/al-Nuri, Nimrud, Nineveh), per Badge klar als "Not
scored" gekennzeichnet -- so werden die beruehmten zerstoerten Staetten sichtbar, die als Nicht-WHS sonst durchs
Raster fallen (Datengrenze, siehe unten). Quellen: CyArk/Open Heritage 3D (openheritage3d.org/data) + Sketchfab
(Global Digital Heritage, Tech 4 Heritage, arck-project, Rekrei/Project Mosul). Nur verifizierte Links, keine
erfundenen URLs. Erweiterbar (Aleppo/Bam/Shibam etc. spaeter ergaenzen). Optionales v2: Sketchfab-iframe in
webview_flutter (Modell rotiert in-App).

**Datengrenze Mosul/Nimrud/Nineveh (2026-06-15):** Das Score-Set ist UNESCO-WHS-only. Mosuls Altstadt (al-Nuri-
Moschee), Nimrud und Nineveh sind trotz schwerer IS-Zerstoerung KEINE eingeschriebenen Welterbestaetten (nur
Tentativliste) und daher nicht im Threat-Score. Sie erscheinen jetzt als Nicht-WHS-Kontext in der 3D-Ebene.

**Aufgeschobene Scope-Option (2026-06-15):** Afghanistan (Bamiyan + Minarett von Jam, beide In-Danger; Pleiades
deckt Baktrien ab -- 461 Orte im globalen Dump, unser Parquet ist bei 64°E geclippt) und Libyen (alle 5 WHS
In-Danger) wuerden das Threat-Signal-Kriterium erfuellen, liegen aber ausserhalb "Vorderasien". Nutzer-Entscheid:
erst mal bei den 7 Laendern bleiben, Afghanistan/Libyen evtl. spaeter. Beim Reinnehmen: bbox nach Osten/Westen,
PBF + Ingest + In-Danger-CSV ergaenzen, 3D-Ebene um Bamiyan erweitern.

**ACLED-Retest 2026-06-15 (Mo, erster Werktag):** unveraendert. Token 200, JWT weiterhin nur scope
`["authenticated"]` (sub 201977, aud acled), read-Endpunkt 403 "Access denied" (x-consumer-id acled). Keine Mail
erhalten. Naechster Schritt: noch 1-2 Tage, dann access@acleddata.com kontaktieren.

**ACLED-Retest 2026-06-16 (Di, zweiter Werktag):** unveraendert (Token 200, scope `["authenticated"]`, read 403).
Jetzt zwei Werktage seit Konto-Anlage (Fr 12.06.) ohne Freischaltung -> **access@acleddata.com anschreiben**
(Account-ID 201977, "authenticated token, read 403"). E-Mail liegt beim Nutzer.

**Naturgefahr-Komponente ersetzt WMF (2026-06-16, Code+Daten fertig, `flutter analyze` sauber, APK gebaut, am
Geraet NOCH NICHT verifiziert).** WMF-Watch war strukturell totes Gewicht (Identitaets-Join flaggte 0 von 67;
WMF-Sites und unsere WHS sind in der Region disjunkt). Ersetzt durch **Naturgefahr = max(Erdbeben, Flusshochwasser)**,
Gewicht **2** (SCORE_MAX 10 -> 11). Quelle **ThinkHazard!** (Weltbank GFDRR; EQ aus GEM, FL aus Flutmodell), Stufen
VLO/LOW/MED/HIG je Site, ueber `config.NATURAL_HAZARD_LEVEL_SCORES` (0 / 1/3 / 2/3 / 1) auf [0,1] gemappt, NDA=0.
- **`ingest_hazard.py`** (neu): Site-Koordinate -> Reverse-Geocoding (Nominatim, 1 Anfrage/s) zu Provinz/Distrikt ->
  ThinkHazard-Namenssuche `/administrativedivision?q=` (aufs Land gefiltert) -> Report-JSON `/report/{code}.json` ->
  EQ+FL-Stufe. ThinkHazard hat KEINEN Punkt-Lookup, daher dieser Weg. Ergebnis: kuratierte, committete
  `reference/natural_hazard.csv` (keyed per site_id, Spalte `match_confidence`), die `process.py` liest (kein
  Live-API zur Score-Zeit). Cache unter `RAW_DIR/hazard/`. Aufloesung: **adm2=32, adm1=29, override=5, country=1**
  (nur Socotra, ThinkHazard kennt die Insel nicht). Provinz-Aliase (Nominatim vs. GAUL-Schreibweise, z. B.
  Isfahan->Esfahan, North->Northern) + site_id-Overrides fuer Palaestina (Nominatim liefert nur Oslo-Zonen "Area
  A/C", ThinkHazard hat "West Bank and Gaza"/Bethlehem/Hebron/Jericho/Deir al Balah) sind in `ingest_hazard.py`
  dokumentiert.
- **Pipeline-Aenderungen:** config (SCORE_WEIGHT_NATURAL_HAZARD=2, NATURAL_HAZARD_PATH, NATURAL_HAZARD_LEVEL_SCORES,
  SCORE_MAX=11; WMF-Gewicht/Pfad raus), process.py (hazard-CTE statt wmf-CTE; `GREATEST(eq,fl)*Gewicht` als
  `score_natural`, auf DOUBLE gecastet sonst DECIMAL-JSON-Crash; Spalten `eq_level`/`fl_level` ersetzen `wmf_watch`),
  export.py (FEATURE_COLUMNS + Metadaten: natural_hazard/ThinkHazard, "0 bis 11"). App: `site_detail_sheet.dart`
  zeigt "Natural hazard (quake/flood)" mit "EQ <Stufe> · FL <Stufe>" statt WMF-Zeile, Badge "/ 11", Quellenzeile
  "ThinkHazard! (World Bank)"; Kopfzeile zahlenneutral. `reference/wmf_watch_list.csv` geloescht, WMF-Reste im
  Mockup-Generator/export_3d-Doc entfernt.
- **Score-Wirkung (ohne ACLED):** low 7 (Israel), medium 44 (Laender mit voller Reisewarnung ohne In-Danger,
  differenziert ueber Naturgefahr: Iran 4.33 vs 5.0), high 16 (= die In-Danger-Sites; Aleppo/Samarra 8.0, syrische
  Sites 7.33). Klassengrenzen (3/6) unveraendert gelassen: Scores clustern in Luecken, ein Reskalieren auf max 11
  (3,3/6,6) aendert nichts. Kombination per **max** (Worst-Case-Exposition) bewusst statt Mittel.
- **OFFEN dabei:** neue APK ist gebaut, aber Install scheiterte (`NO_CERTIFICATES` truncated copy, dann adb-Daemon
  startet host-seitig nicht mehr -> Laptop-Neustart noetig). Danach `adb install -r` von `C:\Users\sebas\app-debug.apk`
  und Detail-Sheet/Verteilung am Pixel verifizieren. Datengrenze: ThinkHazard-Flusshochwasser bewertet die
  Jemen-Lehm-WHS (Shibam/Zabid) niedrig (river flood, nicht Sturzflut); bewusst ehrlich uebernommen.

**Konfliktquelle FINAL zurueck auf UCDP GED + Intra-Site-Routing (2026-07-08, zweite Session,
Nutzer-Entscheid).** Grund fuer den Rueckwechsel von ACLED: (1) **Aktualitaet** - die ACLED-Research-Stufe
gibt Event-Level erst nach 12-Monats-Embargo frei, der Score beschrieb also die Lage von vor ueber einem
Jahr; UCDP GED + monatlicher Candidate liegen nur ~4-6 Wochen zurueck, der Score traegt wieder die
LAUFENDE Lage. (2) **Lizenz** - UCDP ist CC BY 4.0, das Repo kann wieder OEFFENTLICH werden und der
CI-Tagesjob braucht keine Secrets mehr. Die UCDP-Luecke (nur Events mit >= 1 Toten) ist bewusst
akzeptiert und in README/Info-Sheet dokumentiert; das ACLED-Intermezzo bleibt als dokumentierter
Quellenvergleich in der History.
- **Pipeline:** config (UCDP-Kommentar, Candidate-URL v26_0_4 -> **v26_0_5**, Fenster 36-12 -> **12-0
  Monate**, Deckel 1000 -> **25**), ACLED-Block + ingest_acled.py GELOESCHT, .env.example ohne
  ACLED-Creds. process.py/export.py/export_events.py auf ucdp_events.parquet; Event-Properties jetzt
  date/year/violence_type/deaths. Lauf 2026-07-08: **2.513 Events ab 2025-07-01** (GED 2.200 +
  Candidate 313), davon **1.780 im 30-km-Siteradius** (2025: 1.606, 2026: 174). Kalibrierung geprueft:
  aktive Sites 37, Median 5, **p90 = 20,4** -> Deckel 25 bleibt. **Verteilung low 34 / medium 45 /
  high 21**; Top: Bosra 9.47, Saint Hilarion/Gaza 9.33, Battir 9.18, Damaskus 8.95, Marib (YE) 8.87.
- **App:** Alle ACLED-Labels auf UCDP GED (info_sheet inkl. Fenster-Text, conflict_overview, site_detail,
  map_screen, event sheet mit violence_type + "Fatalities (best estimate)", ohne civilian_targeting).
  **Jahresrampe von 3 auf 2 Klassen:** das rollende 12-Monats-Fenster spannt genau zwei Kalenderjahre;
  `AppColors.eventYearPrevious/Current` (#FB6A4A/#A50F15), Match-Expression + Legende dynamisch auf
  `DateTime.now().year` (kein jaehrliches Nachpflegen).
- **Intra-Site-Routing:** "Route here" jetzt auch im Pleiades- und im 3D-Modell-Sheet (Ziel-Koordinaten
  aus der Feature-Geometrie, gemeinsame onRoute-Fabrik in _showDetailAt). Damit Fussrouten innerhalb
  grosser Staetten zu einzelnen Monumenten. Kein Auto-Profil (Nutzer-Entscheid), Events sind keine Ziele.
- **CI-Tagesjob** auf ingest_ucdp.py umgestellt, Secrets-Zeilen raus (tokenfrei), Hinweis auf die
  versionierte Candidate-URL.
- **Geraetetest per adb (NEU: Claude testet selbst am angeschlossenen Pixel, Screenshots via screencap):**
  Threat-Ansicht (100 Sites/19 in danger), Konflikt-Ansicht ("1780 conflict events (UCDP)", Zwei-Jahres-
  Legende 2025/2026), Site-Sheet (Ancient Villages 8.5, UCDP-Events-Zeile, neue Hazard-Labels, Route-
  Button) und der Routing-Fallback ohne Key (SnackBar mit dart-define-Hinweis) VERIFIZIERT. Dabei
  **zwei echte Tap-Bugs gefunden + gefixt:** (1) Der Event-Tap-Pfad nutzte den onMapClick-Punkt direkt
  fuers queryRenderedFeaturesInRect; robuster ist toScreenLocation(latLng) (garantiert derselbe
  Pixel-Raum), Toleranz-Rect skaliert jetzt mit devicePixelRatio. (2) **Root cause per Logcat:** die
  gestrichelte **Radius-Linien-Ebene war interaktiv** (addLineLayer-Default) und schluckte Taps in
  Site-Naehe (feature#onTap ohne Handler unterdrueckt map#onMapClick) -> enableInteraction: false.
  **OFFEN: Event-Tap mit dem Fix am Geraet nachtesten** (Pixel war zum Schluss gesperrt; Fix-APK ist
  schon installiert).
- **WICHTIG fuers Veroeffentlichen:** Die Git-HISTORY enthaelt noch ACLED-abgeleitete
  conflict_events.geojson-Staende (Commits 825bab9..fd7dd33). Vor einem Public-Schalten entweder
  History bereinigen (filter-repo/squash) oder ein frisches oeffentliches Repo vom aktuellen Stand
  aufsetzen. Entscheidung liegt bei Sebastian.

**Routing-Komponente v1 + Event-Sheet + Abgabe-Politur (2026-07-08, `flutter analyze` sauber, Tests
gruen, Debug-APK gebaut, am Geraet NOCH NICHT verifiziert).** Autonome Session vor der Abgabe:
- **Routing (README-Plan umgesetzt, Prof-Schwerpunkt):** Neues `app/lib/map/route_service.dart` spricht die
  OpenRouteService Directions API v2 direkt (`POST /v2/directions/{profile}/geojson`, Authorization-Header,
  Timeout 20 s, 404 = "keine Route" sauber gemappt). Profile Drive (`driving-car`) und Walk (`foot-walking`).
  **Key-Handling gemaess Security-Leitlinie:** `String.fromEnvironment('ORS_API_KEY')`, injiziert zur Build-Zeit
  via `--dart-define`; neues `build_app.bat` (Repo-Wurzel) liest `OPENROUTESERVICE_API_KEY` aus `.env` und baut
  die Debug-APK damit. Ohne Key baut und laeuft die App, die Routing-Aktion erklaert dann den Setup-Weg.
  Der urspruengliche Proxy-Plan ist damit bewusst abgeloest (kein Backend fuer eine Uni-Abgabe; dart-define
  haelt den Key trotzdem aus Code und Repo). **UI:** "Route here"-Button im Site-Detail-Sheet (Sheet liefert
  Koordinaten aus der getappten Feature-Geometrie) und Route-Chip im Nearest-Site-Panel; gemeinsamer
  Standort-Flow (`_getPosition()`, aus `_locateMe` extrahiert). Route als Linien-Layer (weisses Casing +
  kraeftiges Blau `#2166AC`, ColorBrewer-blau, bewusst ausserhalb Threat-Rampe und Event-Rot), Kamera fittet
  auf die Route, `_RoutePanel` zeigt Distanz/Dauer + Drive/Walk-Umschalter (re-request) + Clear + ORS-Attribution.
  Route ueberlebt den Theme-Wechsel (Source wird im Style-Load mit dem gehaltenen `_route`-State neu gesetzt).
  Neue Dependency `http ^1.2.2`. **OFFEN: ORS-Key besorgen (openrouteservice.org/sign-up, free tier), in `.env`
  eintragen, mit build_app.bat bauen und am Pixel verifizieren.**
- **Hazard-Labels laienverstaendlich** (To-do erledigt): Detail-Sheet zeigt "Earthquake medium · Flood low"
  statt "EQ Med · FL Low"; Zeile heisst schlicht "Natural hazard".
- **Event-Sheet-Feinschliff:** Jahres-Punkt im ConflictEventSheet traegt jetzt die Rampenfarbe des getappten
  Events (vorher fix 2024er-Orange).
- README (App-Abschnitt, Routing-Zeile, Build mit dart-define/build_app.bat) und `.env.example` aktualisiert.
- **CI-Tagesjob gebaut** (`.github/workflows/daily-update.yml`, Plan von 2026-06-18): Cron 04:30 UTC +
  workflow_dispatch; fluechtiger Runner ingestet UNESCO/AA/ACLED nach `DATA_DIR=runner.temp` (ACLED-Rohevents
  verlassen den Runner nie), rechnet process/export/export_events/export_radius, spiegelt die GeoJSONs nach
  app/assets/data/ und committet nur die aggregierten Artefakte (github-actions[bot]). Schwere OSM-/Pleiades-
  Quellen bleiben bewusst statisch. export.py stempelt das Laufdatum -> ein Commit pro Tag, akzeptiert.
  **OFFEN: Repo-Secrets `ACLED_API_EMAIL`/`ACLED_API_PASSWORD` setzen, pushen, ersten Lauf per
  workflow_dispatch testen.**

**Konflikt-Komponente: Rueckwechsel UCDP GED -> ACLED (2026-06-24, Pipeline gelaufen, `flutter analyze`
sauber, Debug-APK gebaut, am Geraet NOCH NICHT verifiziert).** Loest den UCDP-Stand darunter ab. ACLED-Zugang
am 2026-06-23 auf **Research-Stufe** bewilligt (Auflage: nur akademisch, NICHT oeffentlich -> GitHub-Repo
bleibt PRIVAT, ACLED-Rohevents gitignored/local-only, sauber attribuiert). Grund fuer ACLED statt UCDP:
ACLED erfasst auch NICHT-toedliche Treffer (abgefangene Drohnen/Raketen, Beschuss/Explosionen ohne Tote),
die UCDP mit seiner Schwelle >= 1 Toter verpasst.
- **Fenster 36 -> 12 Monate** (statt 12-0): Research liefert georeferenzierte Event-Level-Daten erst ab
  > 12 Monaten; die juengsten 12 Monate nur aggregiert ohne Koordinaten (nicht radius-joinbar). 36-12 ist
  der punktgenau verfuegbare Bereich. Lauf 2026-06-24: Fenster 2023-06-01..2025-06-01, 148.181 Roh -> **88.265
  Events** nach Filter (Typ/Region/Fenster), davon **41.334** im 30-km-Siteradius (-> Karten-Asset).
- **`ingest_acled.py`** (OAuth2 Password-Grant, `ACLED_OAUTH_URL`/`ACLED_API_URL`, Credentials in `.env` als
  `ACLED_API_EMAIL`/`ACLED_API_PASSWORD`): Felder erweitert um `sub_event_type` (Treffertyp: Air/drone strike,
  Shelling, IED, Armed clash ...), `civilian_targeting`, `geo_precision`, `location`, `admin1`, `notes`,
  `source`. Ausgabe UCDP-schema-kompatibel -> `RAW_DIR/acled/acled_events.parquet`.
- **Pipeline-Aenderungen:** process.py (`CONFLICT_EVENTS_PARQUET` -> acled-Pfad, Report/Doku), export_events.py
  (liest acled-parquet; jedes Feature traegt `year` 2023/24/25 plus sub_event_type/civilian_targeting/
  geo_precision/location/notes; Metadaten ACLED), export.py (Score-Sidecar-Quelle ACLED). **App-Seite:**
  Konflikt-Punkte jahrweise eingefaerbt (sequenzielle Rot-Rampe, neuer = intensiver, `AppColors.eventYear*`,
  Match-Expression auf `year` in map_screen.dart); Legende um Jahres-Farbskala ergaenzt (`_LegendYearRamp`);
  alle "UCDP GED"/"lethal events (>=1 death)"/"Uppsala"-Labels auf ACLED korrigiert (info_sheet,
  conflict_overview_sheet, site_detail_sheet, map_screen).
- **Dateiname:** Artefakt/Asset heisst `conflict_events.geojson` (Inhalt ACLED); umbenannt von
  `ucdp_events.geojson` (2026-06-24). Config-Konstante `CONFLICT_EVENTS_GEOJSON_PATH`, App-Source/-Layer
  `conflict-events`/`conflict-events-circles`. Das UCDP-Roh-Parquet (`ucdp_events.parquet`, Fallback-Pfad)
  behaelt seinen Namen.
- **Kalibrierung pruefen:** max ~19.100 Events/Site (Aleppo) >> `CONFLICT_EVENTS_FOR_FULL_SCORE`=1000 ->
  Log-Deckel saturiert frueh; p90 dieses Laufs ggf. nachziehen.

**Konflikt-Komponente: Wechsel von ACLED auf UCDP GED (2026-06-16, Pipeline gelaufen, `flutter analyze`
sauber, APK noch nicht neu gebaut/getestet).** ACLED bleibt dauerhaft blockiert: Nicht nur die API
(Token nur `scope: authenticated`, read 403), sondern auch das Data Export Tool UND die Event-Data-Files
unter download-data-files geben "not available at your current access level". Das Konto hat schlicht keine
Daten-Zugriffsstufe, weder per API noch manuell. Die fruehere Annahme "manueller Download geht" hat sich
nicht bestaetigt. Manueller Import waere ueber das neue [ingest_acled_manual.py](ingest_acled_manual.py)
moeglich (liest einen ACLED-CSV-Export, filtert auf Region+Fenster, teilt sich `build_events` mit dem
API-Pfad), bleibt aber mangels Datei ungenutzt.

Ersatz durch **UCDP GED** (Uppsala Conflict Data Program), nach Pruefung gegen ACLED, GDELT, GTD und
Liveuamap gewaehlt: offen lizenziert (CC BY 4.0 / ODbL, also auch fuer eine veroeffentlichte App
rechtssicher), praezise georeferenziert (sauberer Radius-Join, anders als GDELTs Zentroid-Rauschen),
peer-reviewed und zitierbar, aktuell (Candidate-Datensatz). GTD ist bei ~2020 eingefroren, Liveuamap
hat keinen offenen Bulk. Zur Publikationsfrage: ACLED verbietet Roh-Weitergabe und ist nicht-kommerziell
eine Grauzone; die App liefert ohnehin nur den abgeleiteten Score (kein Event-Parquet im Asset), aber UCDP
macht die Veroeffentlichung lizenzsauber.
- **`ingest_ucdp.py`** (neu): laedt tokenfrei den GED-Hauptdatensatz (`config.UCDP_GED_CSV_URL`, ZIP, 1989
  bis Ende 2025) und den monatlichen GED-Candidate (`config.UCDP_CANDIDATE_CSV_URL`, laufendes Jahr),
  filtert beide auf `REGION_BBOX` + `CONFLICT_START_DATE` und schreibt `RAW_DIR/ucdp/ucdp_events.parquet`
  (Schema: event_id, event_date, violence_type, country, deaths, lat/lon, geometry). Voller Lauf 2026-06-16
  mit dem finalen 12-Monats-Fenster: 2.650 GED + 340 Candidate = **2.990 Ereignisse** ab 2025-06-01,
  Abdeckung bis April 2026 (UCDP-Lag ~6 Wochen, Mai/Juni fehlen bewusst). Syrien ist entgegen der alten
  Codebook-Notiz enthalten. Gotcha: `ingest_common.download_file` (streamend) lieferte beim `--refresh`
  einmal einen Zip mit `Bad CRC-32`; sauberer Neudownload (Invoke-WebRequest / erneuter Lauf) behebt das.
- **Pipeline-Aenderungen:** config (UCDP-Block mit URLs + `UCDP_VIOLENCE_TYPES`; Fenster-Konstanten quellen-
  neutral umbenannt `ACLED_*` -> `CONFLICT_LOOKBACK_MONTHS`/`CONFLICT_START_DATE`; ACLED-Block als
  dokumentierter Fallback behalten), process.py (liest `ucdp_events.parquet` statt `acled_events.parquet`,
  Toleranz + Report quellenneutral), export.py (Metadaten-Quelle "UCDP GED (Uppsala)"). App: Detail-Sheet
  und Kopfzeile zeigen "UCDP GED" statt "ACLED", Quellenzeile aktualisiert (zugleich Lizenz-Attribution).
- **Parameter-Feinjustierung (2026-06-16, Nutzer-Entscheid):** Fenster **36 -> 12 Monate**
  (`CONFLICT_LOOKBACK_MONTHS = 12`, bewusst die laufende Lage statt mehrjaehriger Historie), Radius
  **50 -> 30 km** (`CONFLICT_RADIUS_KM = 30`, nur Konflikt im unmittelbaren Umfeld; landesweite Lage deckt die
  Reisewarnung ab), Max-Score **11 -> 10** ueber Naturgefahr-Gewicht **2 -> 1** (stellt die fruehere 0-10-Skala
  wieder her, drei menschliche Achsen je 3, Naturgefahr als sekundaerer Modifikator). `SCORE_MAX` ist die
  Summe der Gewichte, faellt also automatisch.
- **Konflikt-Score logarithmisch statt linear** (Entscheidung 2026-06-16). Die UCDP-Ereigniszahl je Site ist
  stark rechtsschief (im 12-Monats-Fenster/30-km-Radius bei den betroffenen Sites Median 8, p90 ~26, ein
  Gaza-Ausreisser ~1850). Eine lineare Schwelle saettigt entweder zu frueh oder ein hoher Deckel rechnet die
  einstelligen Mehrheitswerte klein. Neu: `score = min(ln(1+count)/ln(1+C), 1) * 3`, Deckel
  `C = CONFLICT_EVENTS_FOR_FULL_SCORE = 25` (~p90 der aktiven Sites, datenverankert; mit Fenster/Radius
  nachzuziehen). Begruendung: Count-Daten ueber Groessenordnungen gehoeren log-transformiert, und die lokale
  Intensitaets-Differenzierung ist der einzige Mehrwert der georeferenzierten Konfliktdaten gegenueber der
  laenderweiten Reisewarnung.
- **Reisewarnung bewusst laenderweit (2026-06-16 geprueft, Nutzer-Entscheid).** Erwaegung sub-nationaler
  Reisewarnungen (Kurdistan stabiler als Zentralirak, Suedlibanon gefaehrlicher als Norden, Aleppo nach Assads
  Sturz ruhiger). Ergebnis: NICHT umgesetzt. Die AA-OpenData-API liefert keine maschinenlesbaren Regionen, und
  vor allem traegt die **Konfliktkomponente diese sub-nationale, aktuelle Differenzierung bereits** (belegt:
  Tyros/Suedlibanon 147 Events vs. Norden <=10; Aleppo 6 vs. Damaskus 19/Bosra 20). Eine sub-nationale
  Reisewarnung wuerde dasselbe Signal doppelt zaehlen und die Komponenten-Unabhaengigkeit untergraben; die
  Reisewarnung bleibt die unabhaengige nationale/institutionelle Achse. FCDO-Umstieg (regionsscharf) verworfen
  (Doppelzaehlung, britische statt deutscher Behoerdensicht, ebenfalls nur Fliesstext). Kurdistan/Erbil bleibt
  als einzige Restluecke akzeptiert (Erbil ist trotz flacher Stufe 2 nur medium 4.68).
- **Score-Wirkung (final, mit UCDP-Konflikt, log, 12 Mon./30 km, Max 10):** 38 von 67 Sites mit Konflikt im
  Radius. Verteilung **low 2, medium 41, high 24**. Top: Bosra 9.47, Damaskus 9.43, Battir (PS) 9.33,
  Saint Hilarion/Gaza (PS) 9.33, Hebron 8.99. Palaestina (Gaza/Westbank) und Syrien dominieren die aktuelle
  Lage, plausibel. Max beobachtet 9.47 <= 10. App-Detail-Sheet: Badge "/ 10", "Conflicts 30 km (UCDP GED)",
  Ganzzahl-Anzeige fuer Level und Events (vorher "2.0"/"282.0"). Artefakt `artifacts/sites.geojson` neu
  exportiert und nach `app/assets/data/` kopiert.
- **OFFEN dabei:** APK neu bauen und am Pixel verifizieren (Detail-Sheet "UCDP GED" + "/ 10" + 30 km, neue
  Scores/Verteilung). Bei kuenftigem UCDP-Release die zwei URLs in config hochziehen. ACLED-Freischaltung
  optional weiter verfolgen (Mail an access@acleddata.com), dann waere ein Quellenvergleich moeglich.

**Konflikt-Radius als Karten-Ebene (2026-06-16, fertig, am Pixel).** `export_radius.py` (neu) zeichnet je Site
ein geodaetisch korrektes Pufferpolygon (pyproj.Geod, 72 Ecken) im `config.CONFLICT_RADIUS_KM`-Umkreis und
schreibt `artifacts/conflict_radius.geojson` (committet, + `config.CONFLICT_RADIUS_GEOJSON_PATH`, als App-Asset
gebuendelt). App: gestrichelte Linien-Ebene `conflict-radius-line` (Farbe #D85A30, unter den Site-Markern),
**default AUS**, per Legenden-Toggle "Conflict radius (30 km)" zuschaltbar. Macht sichtbar, welchen Ausschnitt
der Score je Site auswertet (Methodik-Transparenz). Bei Daten-/Radiusaenderung `export_radius.py` neu laufen.

**Erbil/Kurdistan-Reisewarnung geprueft, KEIN Override (2026-06-16).** Erwogen: Erbil von der vollen Irak-Stufe 2
auf 1 senken (AA behandelt die Region Kurdistan strukturell milder, Direktfluege aus Europa). Verworfen, weil das
AA Stand Juni 2026 AKUT auch fuer Erbil warnt (Personalabzug Generalkonsulat, Ausreiseempfehlung, im Zuge der
regionalen Eskalation). Die volle Stufe 2 ist also gerade sachlich korrekt; ein Override wuerde die Lage
beschoenigen. Das kurz gebaute Override-Geruest (reference/travel_warning_overrides.csv + process-Join) wurde
sauber wieder entfernt (kein Zombie-Code). Reisewarnung bleibt durchgaengig laenderweit.

**App-Display-Fixes (2026-06-16):** Detail-Sheet zeigt Ganzzahlen statt "2.0"/"282.0" (`.toInt()` fuer
warning_level und conflict_count), Badge "/ 10" statt "/ 11", Titel "Conflicts 30 km (UCDP GED)".

**Dichte-Erweiterung Stage 1 erledigt (2026-06-16, am Pixel verifiziert, 100 Sites).** Threat-Signal-Kriterium
aufgegeben (siehe "Worum es geht"), config erweitert: COUNTRIES um Jordanien, Aegypten und sechs Golf-Keys
(SA/AE/OM/QA/BH/KW, die alle auf den EINEN Geofabrik-Extract `asia/gcc-states` zeigen), `REGION_BBOX` lon_min
30 -> 28 (Aegypten), `ACLED_COUNTRY_ISO_NUMERIC` um die neuen Codes. `COUNTRY_ISO2` waechst automatisch auf 15
Laender + PS. Neu gelaufen: ingest_unesco (**100 Sites**, +33: EG 7, SA 8, JO 7, OM 5, BH 3, AE 2, QA 1,
Kuwait 0 WHS), ingest_aa (15 Laender; Golf meist Stufe 0, Aegypten 1), ingest_pleiades reclip (8.593 Region-Orte
roh, export_context -> 772 nach Dedup), ingest_ucdp re-filter auf neue BBox (3.058 Events), process/export/
export_radius, Assets kopiert (sites, pleiades, conflict_radius). Verteilung low 34 / medium 42 / high 24,
In-Danger 19. **In-Danger-Korrektur:** `reference/unesco_in_danger.csv` war faktisch region-gefiltert (kein
Aegypten); Abu Mena (site_id 90, Danger-Liste seit 2001) ergaenzt -> In-Danger 18 -> 19. Unter den neuen
Laendern ist Abu Mena der einzige Danger-Fall. CSV beim Editieren auf LF normalisiert (gemischte CRLF/LF
sprengten den DuckDB-CSV-Sniffer).

**ROHDATEN-PFAD geklaert (2026-06-17).** Kurzzeitiger Fehlalarm "Rohdaten verloren": Der Default-Pfad
(`REPO_ROOT.parent/heritage_data`, also `Documents/heritage_data`) war leer, weil das volle Set in den
Repo-Unterordner `Geodatenhaltung und -vernetzung/heritage_data` (gitignored, 1,7 GB inkl. OSM-PBFs + Pleiades)
verschoben worden war. `DATA_DIR` in `.env` stand auf leer -> Pipeline fand es nicht. **Fix: `.env` `DATA_DIR=`
auf den In-Repo-Pfad gesetzt.** In der vermeintlichen Notlage wurden unesco/aa/ucdp/hazard frisch neu-ingestet (in
den Default-Pfad); Ergebnis identisch (3.058 UCDP etc.), die 40-MB-Teilkopie unter `Documents/heritage_data` kann
geloescht werden. Lehre: Rohdaten sind reproduzierbar, aber DATA_DIR muss auf das In-Repo-Set zeigen.

**Dichte-Erweiterung Stages 2-4:**
- **Stage 3 (Naturgefahr) ERLEDIGT (2026-06-17).** `ingest_hazard.py` um `COUNTRY_ADMIN0_HINTS` fuer die 7 neuen
  Laender (EG/JO/SA/AE/OM/QA/BH) ergaenzt, `--refresh` gelaufen -> `reference/natural_hazard.csv` jetzt 100 Sites
  (Konfidenz adm1=46, adm2=32, country=17, override=5). Die 33 neuen Sites tragen jetzt Hazard statt NDA=0.
  process/export neu, `app/assets/data/sites.geojson` aktualisiert. **Neue Verteilung low 32 / medium 44 / high 24**
  (vorher 34/42/24; 2 neue Sites von low nach medium durch die Hazard-Komponente). In-Danger weiter 19, Top-5
  unveraendert (Bosra 9.47 ...). **Bekannte Grenze:** 16 der 33 neuen Sites loesten nur auf Landesebene auf
  (ThinkHazards Namenssuche fand keine adm1/adm2 fuer die Golf/SA/EG-Provinzen) -> Landesmaximalwert smeart
  (z. B. Petra FL=HIG vom Jordan-Aggregat). Ehrlich via `match_confidence`, bei Gewicht 1 + stabilen Laendern
  kaum score-relevant; optionale spaetere Verfeinerung via Provinz-Aliase/Overrides fuer SA/EG.
- **Stage 4 (3D-Modelle) ERLEDIGT (2026-06-17).** `reference/heritage_3d_models.csv` um vier WHS-Ikonen erweitert
  (7 -> **11** Eintraege), alle Links per WebFetch verifiziert: Petra/Ad-Deir (CyArk
  `cyark.org/projects/petra-ad-deir/overview`), Giza-Pyramidenkomplex (Sketchfab Arqueomodel3D, gleicher Autor wie
  Baalbek), Abu Simbel/Great Temple (Sketchfab v777, CC BY-NC-ND), Hegra/Qasr al-Farid (Sketchfab Novxlab). Giza
  bewusst auf die Pyramiden-Koordinaten (29.9773/31.1325, `approx_giza_pyramids`) statt den Memphis-WHS-Zentroid,
  weil das Modell die Pyramiden zeigt. Verworfen: "Great Sphinx" vom Watt Institution (war eine 1903er-Bronze-
  *Skulptur*, nicht das Monument). export_3d -> `heritage_3d.geojson` (11 Features), Asset kopiert; kein App-Code
  noetig (Model3DSheet + url_launcher tragen schon). Erweiterbar (Bahla Fort etc. spaeter).
- **Stage 2 (Heatmap) ERLEDIGT (2026-06-17).** Fehlend waren nur Aegypten + Golf (Jordanien hatte schon Parquets
  aus der fruehen Session, die alten GR/TR/AM/AZ/CY-Parquets ignoriert `export_buildings` ohnehin, da es nur ueber
  `config.COUNTRIES` iteriert). **Golf-Dedup geloest ohne Code-Aenderung:** nur `--only saudi_arabia` verarbeitet
  (die gcc-PBF deckt mit dem alle-Sites-`geometry_filter` schon alle Golf-Sites ab); die anderen 5 Golf-Keys
  uebersprungen -> nur `saudi_arabia_{historic,buildings}.parquet` existiert -> kein 6-faches Zaehlen. Laeufe (kein
  UTF-8-Crash, anders als befuerchtet): egypt historic 9.872 / buildings 4.331, gcc historic 4.456 / buildings 6.170.
  `export_buildings.py` neu -> `building_density.geojson` **5.095 Zellen** (max 328/Zelle, 0,50 MB) ueber alle 15
  Laender, Asset kopiert. Geofabrik gab beim ersten Versuch transientes 502/503 (Server-seitig), Re-Run lief sauber.

**Gotchas (2026-06-16):**
- **APK-Install:** Flutters Kopie nach `app/build/app/outputs/flutter-apk/app-debug.apk` war beschaedigt
  (`INSTALL_PARSE_FAILED_NO_CERTIFICATES`, v2-Signatur-Digest stimmt nicht; passt zur RAM-Instabilitaet). Die
  **Gradle-Original-APK unter `app/build/app/outputs/apk/debug/app-debug.apk` war intakt** und liess sich per
  `adb push` + `pm install -r` installieren. Im Zweifel die Gradle-Datei nehmen. (Streaming-Install generell mit
  `adb install -r --no-streaming` umgehen.)
- **UCDP-Download:** `ingest_common.download_file` (streamend) lieferte beim `--refresh` einmal einen Zip mit
  `Bad CRC-32`; sauberer Neudownload (Invoke-WebRequest oder erneuter Lauf) behebt das. Zum Re-Filtern OHNE
  Re-Download: `ucdp_events.parquet` loeschen und `ingest_ucdp.py` ohne `--refresh` laufen lassen (nutzt den
  validen Roh-Cache).

**Commit-Stand:** Der 100-Sites-Stand (UCDP + Naturgefahr + Dichte-Erweiterung Stage 1) ist committet
(`0d8ff7d`). Stage 3 (Naturgefahr fuer die 33 neuen Sites) wird mit diesem Eintrag committet: geaendert
`ingest_hazard.py` (neue admin0-Hints), `reference/natural_hazard.csv` (67 -> 100 Sites), `artifacts/sites.geojson`,
`app/assets/data/sites.geojson`, PROJECT_CONTEXT.md. Rohdaten (RAW_DIR) bleiben gitignored.

**OFFEN / als Naechstes:**
1. **Restliche Interaktion am Geraet durchklicken** (Threat-Filter, Dichte/Gebaeude-Toggles, Hell/Dunkel,
   Pleiades/Sites-Tap mit den neuen 67-Set-Daten) + neue Naturgefahr-APK installieren/verifizieren (s. o.).
2. **App-Icon (in Arbeit, Design noch nicht final).** Richtung steht: ein **verbindender Bogen + detaillierter
   gruener Pfau** (Pfau = jesidischer Tawusi Melek), dessen Federaugen Gemeinschafts-Symbole tragen. Zugesagte
   Endfassung (Konzept v8, noch zu rendern + zu bauen): Davidstern (Judentum) ergaenzen, **Persepolis-Saeulen im
   Hintergrund**, **klare Sonne in eigener Farbe** als Krone, **Faravahar** (persisch/Persepolis) und das
   **Nazar-Blauauge** (geteiltes Schutzamulett ueber Islam/Judentum/Christentum). Schon im Pfau: Kreuz, Halbmond,
   Drusen-5-Farben-Stern, Sonne, natuerliche Pfauenaugen. Danach: SVG finalisieren, daraus Android-Launcher-Icons
   generieren (mipmap-PNGs + adaptive; evtl. vereinfachte Maskenvariante), volles Emblem als Splash/About-Asset.
   Tool-Hinweis: SVG ist fuers Icon das richtige Medium (Vektor, scharf in jeder Dichte); KI-Raster nur fuer eine
   optionale malerische Hero-Grafik.
3. **Kopfzeile mission-tragend (erledigt 2026-06-16, `flutter analyze` sauber, APK noch nicht neu gebaut/getestet).**
   `_ContextPanel` zeigt jetzt als erste, betonte Zeile "67 World Heritage Sites · 18 in danger" (titleSmall/w600),
   darunter die Score-Kurzbeschreibung und als dezente Subzeile die Quellenangabe "Conflict data: UCDP GED
   (Uppsala)" (seit dem ACLED->UCDP-Wechsel, s. o.; zugleich Lizenz-Attribution). Der
   In-Danger-Zaehler wird in `_ensureDataLoaded` aus `sites.geojson` abgeleitet (Property `in_danger == true`,
   neuer State `_inDangerCount`), analog zum Site-Zaehler. Naechster Geraete-Build verifiziert die Anzeige.
4. **Geolocation v1 ERLEDIGT (2026-06-17, `flutter analyze` sauber, APK gebaut, am Geraet NOCH NICHT verifiziert).**
   `geolocator: ^13.0.2` ergaenzt (Manifest hatte ACCESS_FINE/COARSE_LOCATION schon). Standort-FAB (`my_location`)
   in `map_screen.dart`: `_locateMe()` prueft Service + Permission (request bei denied), holt `getCurrentPosition`,
   setzt `_myLocationEnabled=true` (Eigenstandort-Punkt), zentriert Kamera (Zoom 7) und berechnet die naechste
   gescorte Site (`Geolocator.distanceBetween` ueber die gebuendelten Sites, kein Backend). Ergebnis im
   schliessbaren `_NearestSitePanel` (rechts ueber dem FAB): "Nearest site · X.X km", Name + Threat-Label.
   Fehlerfaelle (Service aus, Permission denied) als SnackBar. Spaeter: Routing/3D.
5. **UCDP-Ereignis-Ebene ERLEDIGT (2026-06-17, `flutter analyze` sauber, APK gebaut, am Geraet NOCH NICHT
   verifiziert).** Neues `export_events.py` -> `artifacts/ucdp_events.geojson` (3.058 Punkte, ~0,56 MB, Properties
   event_date/violence_type/deaths) aus `ucdp_events.parquet`, als App-Asset gebuendelt. App-Ebene `ucdp-events-circles`
   (kleine Kreuze-rote Punkte `#B2182B`, unter den Site-Markern, **non-interactive**, default AUS), Legenden-Toggle
   "Conflict events (UCDP)". Ergaenzt den schon vorhandenen 30-km-Konfliktpuffer (`conflict-radius-line`) -> zusammen
   der Kern des "ist es sicher dort"-Nutzens. Bei Daten-/Fensteraenderung `export_events.py` neu laufen.
   ACLED-Freischaltung optional weiter verfolgen; sie wuerde nur einen Quellenvergleich erlauben, nicht mehr
   gebraucht (UCDP ist die aktive, offen lizenzierte Quelle).

## Entscheidungen und Begruendungen

- **Repo-Wurzel im Projektordner.** Das Repo liegt direkt in `Geodatenhaltung und -vernetzung`.
- **Rohdaten ausserhalb des Repos.** Grosse Rohdaten liegen unter `DATA_DIR` (Umgebungsvariable,
  Standard `../heritage_data`). Nur abgeleitete Artefakte unter `artifacts/` werden committet.
- **WMF-Watch-List (UEBERHOLT, aus dem Score entfernt 2026-06-16).** War als 4. Score-Komponente (Gewicht 1,
  Identitaets-Join) gedacht, flaggte aber strukturell 0 von 67 (WMF-Watch-Sites und unsere WHS sind in der Region
  disjunkt). Ersetzt durch die Naturgefahr-Komponente (ThinkHazard!, s. Stand-Abschnitt + Bewusst verworfene
  Ansaetze). `reference/wmf_watch_list.csv` und alle WMF-Verdrahtungen wurden entfernt. Der untenstehende
  WMF-Watch-List- und WMF-Join-Regel-Abschnitt bleibt als historischer Entscheidungs-Beleg stehen.
- **In-Danger-Flag aus kuratierter, datierter CSV.** Das danger-Feld des WHC-XML ist
  nachweislich unvollstaendig (Syrien 1 von 6 Sites statt 6). Das maszgebliche Flag kommt daher
  aus einer kleinen, datierten CSV mit den offiziellen Danger-Site-IDs, analog zur WMF-Liste,
  einmal jaehrlich nach der WHC-Sitzung gepflegt. Beschafft per Browser-Scrape der offiziellen,
  JS-gerenderten Seite whc.unesco.org/en/danger.
- **App-Abhaengigkeiten getrennt.** Die App-Seite ist Flutter und pflegt ihre Pakete spaeter in
  einer `pubspec.yaml`. Die `requirements-pipeline.txt` deckt nur die Python-Pipeline ab.

## Offene Punkte und zu verifizieren

- **Geofabrik-PBF-URLs.** Verifiziert am 2026-06-12, alle 11 liefern HTTP 200. Tuerkei und
  Zypern liegen bei Geofabrik unter `europe/`, die uebrigen unter `asia/`. Israel und Palaestina
  kommen als gemeinsames Extract.
- **ACLED-Zugang umgestellt (2026-06-12).** Der in `config.ACLED_API_URL` hinterlegte Legacy-Host
  `api.acleddata.com/acled/read` ist tot (DNS loest nicht mehr auf), das alte key+email-Schema
  existiert nicht mehr. Die aktive API ist `https://acleddata.com/api/acled/read` mit OAuth2: per
  `POST https://acleddata.com/oauth/token` (`client_id=acled`, `grant_type=password`, E-Mail +
  Passwort) einen Bearer-Token holen und damit abrufen (verifiziert: Token-Endpunkt verlangt
  `client_id`, der read-Endpunkt liefert ohne Auth 403). Zu tun bei der ACLED-Umsetzung: URL und
  Credential-Variablen in `config.py` und `.env.example` anpassen (Key -> Passwort), `.env`-Laden
  verdrahten (`python-dotenv` ist nicht installiert, `config.py` liest aktuell nur `os.environ`).
  Erledigt am 2026-06-12: ACLED-Ingest implementiert, `config.py` laedt `.env` selbst. Bleibt: read-
  Endpunkt 403 bis zur Konto-Freischaltung (siehe Stand ACLED).
- **Pleiades-Dump-URL.** Den genauen Pfad des aktuellen CSV-Dumps verifizieren.
- **Versions-Pins.** Erledigt am 2026-06-12. `requirements-pipeline.txt` und `environment.yml`
  spiegeln die tatsaechlich installierten Versionen der Env `heritage` (u. a. duckdb 1.5.3,
  quackosm 0.17.1, geopandas 1.1.3).
- **Mapping der AA-Warnstufe.** Erledigt am 2026-06-12. Die Ableitung der Stufe 0 bis 3 liegt in
  `config.AA_WARNING_LEVELS` und ist im Stand-Abschnitt begruendet. `ingest_aa.py` setzt sie um.
- **Proxy-Backend.** Framework und Hosting fuer den ORS/Nominatim-Proxy festlegen (Kandidaten:
  FastAPI auf einem kleinen Host oder eine Serverless-Funktion). Erst relevant ab der App-Stufe.

## App-Architektur und Tech-Stack

Zielplattform ist Android, eine Flutter-Codebase. Die App liest ausschliesslich die committeten
Artefakte und spricht fuer Live-Funktionen ein schlankes Proxy-Backend an.

| Baustein | Wahl | Begruendung |
|---|---|---|
| Framework | Flutter (stable) + Dart 3.x | Cross-Platform aus einer Codebase, starke Geo-Plugins |
| Karten-Engine | MapLibre Native (`maplibre_gl`) | rendert PMTiles und Vektor-Tiles GPU-beschleunigt, datengetriebenes Threat-Styling, Pitch/3D |
| Ortung | `geolocator`, nur Vordergrund | Proximity-Alerts als billiger Distanz-Check gegen die gebuendelten Sites |
| Routing | OpenRouteService ueber Proxy | Intra-Site-Navigation auf OSM-path-Daten |
| 3D | `model_viewer_plus` (glTF in WebView) | optionaler CyArk-Layer fuer wenige Sites, Flutter rendert kein WebGL nativ |
| State | Riverpod | schlank fuer diesen Umfang |
| Lints/Tests | `flutter_lints`, `flutter_test`, `integration_test` | headless vor jedem Push (QA-Schritt) |

Ein erstes high-fidelity App-Mockup liegt unter `mockups/heritage_at_risk_app_v1.html` (eigenstaendig
im Browser zu oeffnen). Es zeigt die Kartenansicht mit threat-codierten Sites (invertierte Ampel:
hoch = rot), den 50-km-Konfliktpuffer um eine ausgewaehlte Site mit ACLED-Ereignissen, die
Filter-Chips und das Detail-Bottom-Sheet mit der Score-Zerlegung aus den vier Quellen. Folgt dem
GEOSPATIAL_DESIGN_GUIDE.md (Accessibility: Threat nicht nur ueber Farbe, sondern auch Symbol/Text;
Distinct-Palette: UI in BHT-Petrol/Teal, Daten in der Ampel).

## Security-Leitlinien

- **Pipeline-Secrets bleiben in der Pipeline.** ACLED-Key und Email leben nur in CI (GitHub
  Secrets) und lokaler `.env`. Die App sieht sie nie, sie liest nur fertige Artefakte.
- **Proxy-Backend fuer Live-Keys.** Ein schlanker eigener Dienst haelt den
  OpenRouteService-Key und reicht Anfragen durch. Kein Live-Key liegt im APK. Nominatim laeuft
  ueber denselben Proxy mit gueltigem User-Agent gemaess Nutzungsrichtlinie.
- **Standortdaten bleiben auf dem Geraet.** Kein Telemetrie-Versand, nur Vordergrund-Ortung,
  klare Begruendungs-Strings in den Permissions.
- **OSM-Erfassung ueber OAuth 2.0.** Niemals Nutzer-Passwoerter speichern, Tokens in
  `flutter_secure_storage`.
- **Netzwerk gehaertet.** HTTPS-only, kein Cleartext-Traffic, Release mit eigenem Signing-Key
  und R8/ProGuard.
- **Supply Chain.** Dart-Pakete gepinnt wie die Python-Seite, regelmaessig auf Updates geprueft.

## Validierung der Datengrenzen

Der Threat Score wird an Stichproben gegen die offizielle UNESCO-In-Danger-Liste und die
Reisewarnstufen geprueft. Liegt eine Site auffaellig daneben, wird der Grund untersucht und hier
festgehalten. Deckt eine Quelle eine Region nicht ab oder bleibt ein Join zu grob, gehoert dieser
Befund mit Begruendung in diese Datei.

Dokumentierte Datengrenze (2026-06-12): Das danger-Feld im WHC-XML `list/xml` bildet den
aktuellen In-Danger-Status nicht zuverlaessig ab. Stichprobe Syrien zeigt nur 1 von 6 offiziell
gefaehrdeten Sites (nur "Ancient Villages of Northern Syria", Y 2013). Die offizielle, JS-
gerenderte Seite whc.unesco.org/en/danger-list dagegen fuehrt alle 6 syrischen Sites. Konsequenz:
das Feld dient nur als Referenz, das maszgebliche Flag kommt aus der kuratierten Danger-CSV. Die
Liste wird einmal jaehrlich nach der WHC-Sitzung neu gescrapt und in reference/ aktualisiert.

Dokumentierter Sonderfall (2026-06-12): Old City of Jerusalem (WHC 148) hat im WHC-XML ein leeres
iso_code-Feld (states = "Jerusalem (Site proposed by Jordan)"). Der reine ISO-Filter wuerde die
Site ausschliessen, obwohl sie geografisch und thematisch klar zur Region gehoert und auf der
Danger-Liste steht. Loesung: Sites ohne iso_code werden ueber die Region-Bounding-Box geprueft
(verifiziert als einziger solcher Fall) und per Override (`COUNTRY_OVERRIDES` in `ingest_unesco.py`)
Israel zugeordnet. Das ist eine bewusste Projektzuordnung fuer Gruppierung und Reisewarnstufen-Join,
nicht die offizielle UNESCO-Position, die die Site keinem Land zuweist.

## Bewusst verworfene Ansaetze

- **WMF-Watch-List als Score-Komponente (verworfen 2026-06-16).** Identitaets-Join flaggte 0 von 67 (disjunkte
  Mengen), Naehe-/landesweiter Match wurde schon frueher verworfen (Fehltreffer bzw. Verwaesserung). Damit war die
  Komponente totes Gewicht. Ersetzt durch die Naturgefahr (ThinkHazard! EQ+FL, Gewicht 2). Auch erwogen und
  verworfen: reiner Erdbeben-Single-Hazard (zu schmal), "dokumentierte Zerstoerung"-Flag (ueberlappt In-Danger
  stark, kaum neue Information), WMF als reine Kartenebene (kein Score-Mehrwert; vorerst ganz raus). Naturgefahr
  per **max(EQ,FL)** statt Mittel (Worst-Case-Exposition). Details im Stand-Abschnitt "Naturgefahr-Komponente".
- **Overture Maps als eigene Datenquelle (verworfen 2026-06-13).** Places (fertig) und Buildings
  (in Arbeit) waren reiner Basemap-Kontext, NICHT Teil des Threat Scores. Buildings holt die
  Provider-Basemap (Protomaps/OpenFreeMap) ohnehin mit (inkl. Hoehen), und der Overture-S3-Pfad war
  die fragilste Quelle des Projekts (zwei RAM-Crashes, zwei Segfaults beim Geometrie-Sort des
  Buildings-Themes, langsame Kalt-Scans >6 min). Der Nutzen rechtfertigte den Aufwand nicht. Falls
  spaeter doch eigene Gebaeude noetig sind, ist OSM `building=*` via QuackOSM aus den schon
  vorhandenen Geofabrik-PBFs der ruhigere Weg (lokal, kein S3). Overtures saubere Places-Taxonomie
  bliebe nur fuer ein moegliches "kulturelle POI in der Naehe"-Feature interessant. `ingest_overture.py`,
  der Config-Block und `RAW_DIR/overture/` wurden entfernt.
- **WMF per Naehe- oder landesweitem Match (verworfen 2026-06-13).** Siehe Stand WMF Watch List:
  Naehe (25 km) erzeugt Fehltreffer (Byblos via Beirut), landesweit verwaessert und dupliziert die
  Reisewarnung (54/116). WMF ist daher site-genau ueber Identitaet (`unesco_site_id`).
- **OSM historic als Kontextebene (verworfen 2026-06-13).** War kurz als zweite Karten-Kontextebene
  (Teal) neben Pleiades drin (benannte ikonische historic=*-Typen, ST_Centroid, 24.558 region-weit /
  5.506 im 15-km-Umkreis). Verworfen: zu dicht und rauschig, Pleiades allein gibt den antiken Kontext
  klarer. Der region-weite Voll-Embed (38k Features, 6 MB) hatte zudem den Renderer zum Absturz
  gebracht (daher generell der Umkreis-Filter `CONTEXT_NEAR_SITES_KM`). `osm_historic.geojson` und der
  OSM-Teil von `export_context.py`/dem Prototyp-Generator wurden entfernt; der OSM-Ingest selbst
  (`ingest_osm.py`, historic=*) bleibt fuer moegliche spaetere Verwendung bestehen.
- **Eigene Gebaeude-Footprints als Kartenebene (verworfen 2026-06-14).** `export_buildings.py` hatte
  zunaechst auch die Footprint-Polygone im Site-Radius als `artifacts/buildings.geojson` ausgegeben. Das
  waren region-weit ~88.000 Polygone / ~17 MB (selbst bei 0,5 km noch ~18.700), zu gross fuer den
  Inline-Embed des Prototyps und der Renderer-Last nicht wert. Stattdessen liefern die Footprints die
  Provider-Basemaps (CARTO Positron/Dark Matter haben eine `building`-Ebene), warm eingefaerbt. Der
  Footprint-Export wurde aus `export_buildings.py` entfernt; es bleibt nur die Dichte-Aggregation
  (`building_density.geojson`), die die Basemap nicht hat. Die rohen `*_buildings.parquet` bleiben unter
  RAW_DIR fuer eine moegliche spaetere PMTiles-Footprint-Ebene erhalten.
