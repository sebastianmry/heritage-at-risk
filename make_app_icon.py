"""Erzeugt das App-Launcher-Icon der Heritage-at-Risk-App.

Minimalistisches Tempelfragment (Architrav auf drei Saeulen, Stufenfundament)
als schwarze Silhouette auf weissem Grund, abgeleitet aus der Handskizze des
Nutzers. Zeichnet rein vektoriell mit Pillow (kein SVG-Rasterizer noetig) und
schreibt die Android-Adaptive-Icon-Dateien direkt in das App-Res-Verzeichnis:

  - mipmap-<dichte>/ic_launcher_foreground.png  (Vordergrund, transparent)
  - mipmap-<dichte>/ic_launcher.png             (Legacy-Vollbild, vor API 26)
  - mipmap-anydpi-v26/ic_launcher.xml + _round  (Adaptive Icon)
  - values/ic_launcher_background.xml           (Hintergrundfarbe)

Das Motiv liegt im zentralen Safe-Zone-Bereich (~66 %), damit jede OEM-Maske
(Kreis, Squircle, Rounded Square) es vollstaendig zeigt.

Output: app/android/app/src/main/res/...
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

RES_DIR: Path = Path(__file__).parent / "app" / "android" / "app" / "src" / "main" / "res"

# Minimalistisch: schwarzes Motiv auf weissem Grund.
BACKGROUND: tuple[int, int, int, int] = (255, 255, 255, 255)   # Hintergrund (weiss)
MOTIF: tuple[int, int, int, int] = (17, 17, 17, 255)       # Motiv (nahezu schwarz)

MASTER: int = 1024  # Kantenlaenge des Render-Masters, danach heruntergerechnet

# Android-Dichtefaktoren: Legacy-Icon (48 dp) und Adaptive-Vordergrund (108 dp).
DENSITY_SCALE: dict[str, float] = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0,
                                   "xxhdpi": 3.0, "xxxhdpi": 4.0}
LEGACY_DP: int = 48
FOREGROUND_DP: int = 108


def _draw_monument(draw: ImageDraw.ImageDraw, void: tuple[int, int, int, int]) -> None:
    """Zeichnet das Tempelfragment (schwarz) und carvt den Verfall mit ``void``.

    ``void`` ist die Wegschneide-Farbe der Bruchstellen: transparent fuer den
    Adaptive-Vordergrund, weiss fuer das Legacy-Vollbild. ImageDraw ersetzt
    Pixel direkt (kein Alpha-Compositing), schneidet also echte Loecher.
    """
    # Stufenfundament (von unten nach oben schmaler), Stylobat als oberste Stufe.
    steps = [(230, 724, 794, 760), (268, 688, 756, 724), (300, 652, 724, 688)]
    for left, top, right, bottom in steps:
        draw.rectangle((left, top, right, bottom), fill=MOTIF)

    # Drei Saeulenschaefte auf dem Stylobat; die weissen Luecken lesen sich als Saeulen.
    shaft_top, shaft_bottom, half = 392, 652, 35
    for center_x in (355, 512, 669):
        draw.rectangle((center_x - half, shaft_top, center_x + half, shaft_bottom), fill=MOTIF)

    # Kapitelle: leicht ueberstehende Bloecke ueber den Schaeften.
    cap_top, cap_bottom, cap_half = 368, 392, 43
    for center_x in (355, 512, 669):
        draw.rectangle((center_x - cap_half, cap_top, center_x + cap_half, cap_bottom), fill=MOTIF)

    # Architrav und schmale Deckplatte (Geison) als oberer Abschluss.
    draw.rectangle((300, 308, 724, 368), fill=MOTIF)
    draw.rectangle((292, 296, 732, 308), fill=MOTIF)

    _carve_damage(draw, void)


def _carve_damage(draw: ImageDraw.ImageDraw, void: tuple[int, int, int, int]) -> None:
    """Schneidet leichten Verfall heraus: gebrochene Ecke, Saeulenriss, Stufenkerbe."""
    # Abgebrochene obere rechte Ecke des Gebaelks (diagonaler Abschlag).
    draw.polygon([(664, 296), (732, 296), (732, 376)], fill=void)
    # Schmaler vertikaler Riss im rechten Schaft.
    draw.rectangle((678, 392, 690, 486), fill=void)
    # Ausgebrochene Kerbe oben am linken Kapitell.
    draw.polygon([(312, 368), (340, 368), (312, 392)], fill=void)
    # Abgeschlagene Ecke unten links an der breitesten Stufe.
    draw.polygon([(230, 740), (230, 760), (262, 760)], fill=void)


def _foreground_master() -> Image.Image:
    """Vordergrund-Master: Motiv auf transparentem Grund (Safe-Zone-konform)."""
    image = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    _draw_monument(ImageDraw.Draw(image), void=(0, 0, 0, 0))
    return image


def _legacy_master() -> Image.Image:
    """Legacy-Master: dasselbe Motiv auf vollflaechigem weissem Grund."""
    image = Image.new("RGBA", (MASTER, MASTER), BACKGROUND)
    _draw_monument(ImageDraw.Draw(image), void=BACKGROUND)
    return image


def _write_scaled(master: Image.Image, base_dp: int, name: str) -> None:
    """Skaliert den Master je Dichte und schreibt mipmap-<dichte>/<name>."""
    for density, scale in DENSITY_SCALE.items():
        size = round(base_dp * scale)
        target_dir = RES_DIR / f"mipmap-{density}"
        target_dir.mkdir(parents=True, exist_ok=True)
        master.resize((size, size), Image.LANCZOS).save(target_dir / name)


def _write_adaptive_xml() -> None:
    """Schreibt die Adaptive-Icon-Definition und die Hintergrundfarbe."""
    adaptive_dir = RES_DIR / "mipmap-anydpi-v26"
    adaptive_dir.mkdir(parents=True, exist_ok=True)
    adaptive_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@color/ic_launcher_background" />\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground" />\n'
        '</adaptive-icon>\n'
    )
    (adaptive_dir / "ic_launcher.xml").write_text(adaptive_xml, encoding="utf-8")
    (adaptive_dir / "ic_launcher_round.xml").write_text(adaptive_xml, encoding="utf-8")

    values_dir = RES_DIR / "values"
    values_dir.mkdir(parents=True, exist_ok=True)
    (values_dir / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        '    <color name="ic_launcher_background">#FFFFFF</color>\n'
        '</resources>\n',
        encoding="utf-8",
    )


def run() -> None:
    _write_scaled(_foreground_master(), FOREGROUND_DP, "ic_launcher_foreground.png")
    _write_scaled(_legacy_master(), LEGACY_DP, "ic_launcher.png")
    _write_adaptive_xml()
    # Ein 512er-Vorschaubild fuers Review (kein App-Asset).
    Image.alpha_composite(
        Image.new("RGBA", (MASTER, MASTER), BACKGROUND), _foreground_master()
    ).resize((512, 512), Image.LANCZOS).save(Path(__file__).parent / "app_icon_preview.png")
    print(f"make_app_icon: Icons geschrieben nach {RES_DIR}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
