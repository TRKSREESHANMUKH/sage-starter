"""
scripts/generate_logo_variants.py — Generate all SAGE logo variants from sage_master.png.
"""

from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

MASTER_PATH = Path("assets/logo/sage_master.png")
LOGO_DIR = Path("assets/logo")
STATIC_IMG_DIR = Path("web/static/img")
REPORTS_ASSETS_DIR = Path("reports/assets")

STATIC_IMG_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def generate_variants():
    master = Image.open(MASTER_PATH).convert("RGBA")
    w, h = master.size
    print(f"Master size: {w}x{h}")

    # 1. assets/logo/sage_logo_dark.png (Glowing white/cyan line art for dark surfaces)
    dark_arr = np.array(master).copy()
    r = dark_arr[:, :, 0].astype(np.float32)
    g = dark_arr[:, :, 1].astype(np.float32)
    b = dark_arr[:, :, 2].astype(np.float32)
    a = dark_arr[:, :, 3].astype(np.float32)

    # Detect red tilak pixels to keep red
    is_tilak = (r > 130) & (g < 90) & (b < 90)

    # For wireframe lines (non-tilak), enhance glowing cyan/white
    not_tilak = ~is_tilak
    # Add subtle cool cyan tint to glowing lines
    dark_arr[not_tilak, 1] = np.clip(g[not_tilak] * 1.05 + 5, 0, 255).astype(np.uint8)
    dark_arr[not_tilak, 2] = np.clip(b[not_tilak] * 1.15 + 15, 0, 255).astype(np.uint8)

    dark_logo = Image.fromarray(dark_arr, mode="RGBA")
    dark_logo.save(LOGO_DIR / "sage_logo_dark.png")
    print("Saved assets/logo/sage_logo_dark.png")

    # 2. assets/logo/sage_logo_light.png (Figure inside a subtle rounded-rect badge / squircle)
    badge_size = 512
    badge = Image.new("RGBA", (badge_size, badge_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    radius = 96
    # Draw dark squircle badge background with subtle border
    # Background: dark slate #0f172a, subtle gradient / border #334155
    draw.rounded_rectangle(
        [(16, 16), (badge_size - 16, badge_size - 16)],
        radius=radius,
        fill=(15, 23, 42, 255),
        outline=(51, 65, 85, 255),
        width=3
    )
    # Fit master inside badge
    inner_pad = 60
    fit_w = badge_size - 2 * inner_pad
    fit_h = badge_size - 2 * inner_pad
    aspect = w / h
    if aspect > 1:
        target_w = fit_w
        target_h = int(target_w / aspect)
    else:
        target_h = fit_h
        target_w = int(target_h * aspect)

    scaled_dark = dark_logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    offset_x = (badge_size - target_w) // 2
    offset_y = (badge_size - target_h) // 2
    badge.paste(scaled_dark, (offset_x, offset_y), scaled_dark)
    badge.save(LOGO_DIR / "sage_logo_light.png")
    print("Saved assets/logo/sage_logo_light.png")

    # 3. web/static/img/sage_logo.png (44x44 header icon)
    # 44x44 square with figure centered
    icon_44 = Image.new("RGBA", (44, 44), (0, 0, 0, 0))
    aspect = w / h
    if aspect > 1:
        target_w = 40
        target_h = int(40 / aspect)
    else:
        target_h = 40
        target_w = int(40 * aspect)
    scaled_icon = dark_logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
    ox = (44 - target_w) // 2
    oy = (44 - target_h) // 2
    icon_44.paste(scaled_icon, (ox, oy), scaled_icon)
    icon_44.save(STATIC_IMG_DIR / "sage_logo.png")
    print("Saved web/static/img/sage_logo.png (44x44)")

    # 4. web/static/img/sage_logo_card.png (320px hero illustration for controller dashboard)
    card_w = 320
    card_h = int(card_w / (w / h))
    card_img = dark_logo.resize((card_w, card_h), Image.Resampling.LANCZOS)
    card_img.save(STATIC_IMG_DIR / "sage_logo_card.png")
    print(f"Saved web/static/img/sage_logo_card.png ({card_w}x{card_h})")

    # 5. Favicons and app touch icons
    # Favicon 32x32
    fav_32 = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    aspect = w / h
    tw = 30 if aspect > 1 else int(30 * aspect)
    th = int(30 / aspect) if aspect > 1 else 30
    scaled_fav = dark_logo.resize((tw, th), Image.Resampling.LANCZOS)
    fav_32.paste(scaled_fav, ((32 - tw) // 2, (32 - th) // 2), scaled_fav)
    fav_32.save(STATIC_IMG_DIR / "favicon-32x32.png")

    # Multi-res favicon.ico (16, 32, 48)
    fav_16 = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    tw16 = 15 if aspect > 1 else int(15 * aspect)
    th16 = int(15 / aspect) if aspect > 1 else 15
    fav_16.paste(dark_logo.resize((tw16, th16), Image.Resampling.LANCZOS), ((16 - tw16) // 2, (16 - th16) // 2))

    fav_48 = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
    tw48 = 44 if aspect > 1 else int(44 * aspect)
    th48 = int(44 / aspect) if aspect > 1 else 44
    fav_48.paste(dark_logo.resize((tw48, th48), Image.Resampling.LANCZOS), ((48 - tw48) // 2, (48 - th48) // 2))

    fav_32.save(STATIC_IMG_DIR / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print("Saved web/static/img/favicon.ico and favicon-32x32.png")

    # Apple touch icon (180x180) with squircle badge
    apple_icon = badge.resize((180, 180), Image.Resampling.LANCZOS)
    apple_icon.save(STATIC_IMG_DIR / "apple-touch-icon.png")
    print("Saved web/static/img/apple-touch-icon.png")

    # Android chrome 512x512
    android_icon = badge.resize((512, 512), Image.Resampling.LANCZOS)
    android_icon.save(STATIC_IMG_DIR / "android-chrome-512x512.png")
    print("Saved web/static/img/android-chrome-512x512.png")

    # 6. reports/assets/logo.png (120px wide transparent logo for email & PDF cover)
    rep_w = 120
    rep_h = int(rep_w / (w / h))
    rep_logo = dark_logo.resize((rep_w, rep_h), Image.Resampling.LANCZOS)
    rep_logo.save(REPORTS_ASSETS_DIR / "logo.png")
    print(f"Saved reports/assets/logo.png ({rep_w}x{rep_h})")


if __name__ == "__main__":
    generate_variants()
