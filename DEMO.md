# Demo-Leitfaden (Abgabe-Vorführung)

Kurze Klickstrecke für die Vorführung der Heritage-at-Risk-App. Dauer etwa fünf Minuten.
Reihenfolge so gewählt, dass jede Funktion auf der vorigen aufbaut.

## Vorab prüfen

- Pixel per USB verbunden, Bildschirm entsperrt, USB-Debugging erlaubt.
- Debug-APK mit ORS-Key gebaut (`build_app.bat` meldet "ORS-Key aus .env uebernommen").
- Standortfreigabe der App aktiv, damit das Nearest-Site-Panel und die Route funktionieren.

## Ablauf

1. **Einstieg, Threat-Ansicht.** Die Karte öffnet auf der MENA-Region. Jede Stätte trägt
   einen Punkt in der Ampelfarbe ihres Bedrohungswerts. Kurz auf die Legende zeigen: der Wert
   reicht von 0 bis 10, die Stufe steht immer als Text dabei, nicht nur als Farbe.

2. **Site-Detail mit Score-Zerlegung.** Auf eine hoch bewertete Stätte tippen, zum Beispiel
   Ancient Villages of Northern Syria (8,5). Das Sheet zeigt die vier Komponenten einzeln:
   UNESCO-In-Danger, Reisewarnstufe des Auswärtigen Amts, Konfliktereignisse im 30-km-Radius
   und die Naturgefahr mit ausgeschriebener Stufe ("Earthquake medium, Flood very low").
   Die Quelle unten nennt UCDP GED.

3. **Konflikt-Ansicht.** Oben auf den Modus-Umschalter tippen. Die Kopfzeile fasst zusammen,
   wie viele Konfliktereignisse in wie vielen Stätten liegen. Die Punkte färben sich nach Jahr
   (Vorjahr heller, laufendes Jahr dunkelrot).

4. **Konflikt-Overview.** Auf das Balken-Panel tippen. Das Sheet listet die Stätten nach
   Ereigniszahl sortiert, mit Balken in der jeweiligen Threat-Farbe.

5. **Event-Tap.** Auf einen einzelnen Konfliktpunkt tippen. Das Event-Sheet zeigt Gewaltform,
   Datum und die Zahl der Todesopfer (beste Schätzung), Quelle UCDP GED, CC BY 4.0.

6. **Routing.** Zurück zu einer Stätte, im Site-Sheet auf "Route here" tippen. Die Route
   erscheint als Linie, das Panel nennt Distanz und Dauer. Zwischen Fahren und Gehen umschalten.
   Danach über das Nearest-Site-Panel die Route zur nächstgelegenen Stätte zeigen.

7. **Intra-Site-Routing.** In den Pleiades-Kontext hineinzoomen, ein antikes Monument antippen
   und von dort ebenfalls "Route here" auslösen. Das demonstriert die Route zu einem einzelnen
   Punkt innerhalb der Stätte (kein Auto-Profil, nur Fahren und Gehen).

8. **3D-Ebene.** Zum Abschluss die 3D-Modell-Ebene einblenden und Palmyra zeigen.

## Falls kein Gerät zur Hand ist

Screenshots aus `app_icon_preview.png` und ein kurzer Screencast decken die Kernfunktionen ab.
Der Datenstand lässt sich über die Metadaten der Artefakte belegen (`artifacts/*.geojson`,
Feld `generated`).

## Datengrundlage in einem Satz

Der Bedrohungswert je Stätte fasst vier offene Quellen räumlich zusammen: UNESCO-In-Danger,
Reisewarnung des Auswärtigen Amts, UCDP-Konfliktereignisse im 30-km-Radius und ThinkHazard!-
Naturgefahr, gewichtet 3 zu 3 zu 3 zu 1.
