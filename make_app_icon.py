"""Generates the app launcher icon of the Heritage at Risk app.

Minimalist temple fragment (architrave on three columns, stepped
foundation) as a black silhouette on a white background, derived from the
user's hand sketch. Draws purely vectorially with Pillow (no SVG rasterizer
needed) and writes the Android adaptive icon files directly into the app's
res directory:

  - mipmap-<density>/ic_launcher_foreground.png  (foreground, transparent)
  - mipmap-<density>/ic_launcher.png             (legacy full image, pre API 26)
  - mipmap-anydpi-v26/ic_launcher.xml + _round  (adaptive icon)
  - values/ic_launcher_background.xml           (background colour)

The motif sits within the central safe-zone area (~66%), so every OEM mask
(circle, squircle, rounded square) shows it in full.

Output: app/android/app/src/main/res/...
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

RES_DIR: Path = Path(__file__).parent / "app" / "android" / "app" / "src" / "main" / "res"

# Minimalist: black motif on a white background.
BACKGROUND: tuple[int, int, int, int] = (255, 255, 255, 255)   # background (white)
MOTIF: tuple[int, int, int, int] = (17, 17, 17, 255)       # motif (near black)

MASTER: int = 1024  # edge length of the render master, downscaled afterwards

# Android density factors: legacy icon (48 dp) and adaptive foreground (108 dp).
DENSITY_SCALE: dict[str, float] = {"mdpi": 1.0, "hdpi": 1.5, "xhdpi": 2.0,
                                   "xxhdpi": 3.0, "xxxhdpi": 4.0}
LEGACY_DP: int = 48
FOREGROUND_DP: int = 108


def _draw_monument(draw: ImageDraw.ImageDraw, void: tuple[int, int, int, int]) -> None:
    """Draws the temple fragment (black) and carves the decay with ``void``.

    ``void`` is the cut-away colour of the breakage points: transparent for
    the adaptive foreground, white for the legacy full image. ImageDraw
    replaces pixels directly (no alpha compositing), so it cuts real holes.
    """
    # Stepped foundation (narrower from bottom to top), stylobate as the topmost step.
    steps = [(230, 724, 794, 760), (268, 688, 756, 724), (300, 652, 724, 688)]
    for left, top, right, bottom in steps:
        draw.rectangle((left, top, right, bottom), fill=MOTIF)

    # Three column shafts on the stylobate; the white gaps read as columns.
    shaft_top, shaft_bottom, half = 392, 652, 35
    for center_x in (355, 512, 669):
        draw.rectangle((center_x - half, shaft_top, center_x + half, shaft_bottom), fill=MOTIF)

    # Capitals: slightly protruding blocks above the shafts.
    cap_top, cap_bottom, cap_half = 368, 392, 43
    for center_x in (355, 512, 669):
        draw.rectangle((center_x - cap_half, cap_top, center_x + cap_half, cap_bottom), fill=MOTIF)

    # Architrave and narrow cover slab (geison) as the top finish.
    draw.rectangle((300, 308, 724, 368), fill=MOTIF)
    draw.rectangle((292, 296, 732, 308), fill=MOTIF)

    _carve_damage(draw, void)


def _carve_damage(draw: ImageDraw.ImageDraw, void: tuple[int, int, int, int]) -> None:
    """Cuts out light decay: broken corner, column crack, step notch."""
    # Broken-off upper right corner of the entablature (diagonal chip).
    draw.polygon([(664, 296), (732, 296), (732, 376)], fill=void)
    # Narrow vertical crack in the right shaft.
    draw.rectangle((678, 392, 690, 486), fill=void)
    # Chipped-out notch at the top of the left capital.
    draw.polygon([(312, 368), (340, 368), (312, 392)], fill=void)
    # Broken-off corner at the bottom left of the widest step.
    draw.polygon([(230, 740), (230, 760), (262, 760)], fill=void)


def _foreground_master() -> Image.Image:
    """Foreground master: motif on a transparent background (safe-zone compliant)."""
    image = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    _draw_monument(ImageDraw.Draw(image), void=(0, 0, 0, 0))
    return image


def _legacy_master() -> Image.Image:
    """Legacy master: the same motif on a full-bleed white background."""
    image = Image.new("RGBA", (MASTER, MASTER), BACKGROUND)
    _draw_monument(ImageDraw.Draw(image), void=BACKGROUND)
    return image


def _write_scaled(master: Image.Image, base_dp: int, name: str) -> None:
    """Scales the master per density and writes mipmap-<density>/<name>."""
    for density, scale in DENSITY_SCALE.items():
        size = round(base_dp * scale)
        target_dir = RES_DIR / f"mipmap-{density}"
        target_dir.mkdir(parents=True, exist_ok=True)
        master.resize((size, size), Image.LANCZOS).save(target_dir / name)


def _write_adaptive_xml() -> None:
    """Writes the adaptive icon definition and the background colour."""
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
    # A 512px preview image for review (not an app asset).
    Image.alpha_composite(
        Image.new("RGBA", (MASTER, MASTER), BACKGROUND), _foreground_master()
    ).resize((512, 512), Image.LANCZOS).save(Path(__file__).parent / "app_icon_preview.png")
    print(f"make_app_icon: icons written to {RES_DIR}")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
