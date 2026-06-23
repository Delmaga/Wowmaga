"""
Génère une image d'équipement style WoW paper doll.
Chaque slot = icône + nom + ilvl avec couleur de qualité.
"""
import io
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# Couleurs de qualité WoW
QUALITY_COLORS = {
    "LEGENDARY": (255, 128,   0),
    "EPIC":      (163,  53, 238),
    "RARE":      ( 0,  112, 221),
    "UNCOMMON":  ( 30, 255,   0),
    "COMMON":    (157, 157, 157),
    "POOR":      (157, 157, 157),
}

QUALITY_LABEL = {
    "LEGENDARY": "LÉGENDAIRE",
    "EPIC":      "ÉPIQUE",
    "RARE":      "RARE",
    "UNCOMMON":  "PEU COMMUN",
    "COMMON":    "COMMUN",
}

SLOT_ORDER = [
    "Head","Neck","Shoulder","Back","Chest","Wrist",
    "Hand","Waist","Legs","Feet","Finger","Trinket",
    "Main-Hand","Off-Hand",
    # FR
    "Tête","Cou","Épaule","Dos","Torse","Poignet",
    "Mains","Taille","Jambes","Pieds","Doigt","Bibelot",
    "Main droite","Main gauche",
]

ICON_SIZE  = 52
PADDING    = 14
ROW_H      = ICON_SIZE + PADDING + 6
CARD_W     = 780
FONT_TITLE = 15
FONT_NAME  = 13
FONT_SUB   = 11


async def _fetch_bytes(session: aiohttp.ClientSession, url: str) -> bytes | None:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                return await r.read()
    except Exception:
        pass
    return None


async def _fetch_icon(session, item: dict) -> Image.Image | None:
    """Récupère l'icône depuis le CDN Blizzard via l'URL dans media."""
    # L'API renvoie parfois un champ 'media' avec une URL href
    # On construit l'URL de l'icône via le display_string ou on tente via item id
    icon_url = None
    media = item.get("media", {})
    assets = media.get("assets", [])
    for a in assets:
        if a.get("key") in ("icon", ""):
            icon_url = a.get("value")
            break

    if not icon_url:
        return None

    data = await _fetch_bytes(session, icon_url)
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data)).convert("RGBA").resize((ICON_SIZE, ICON_SIZE))
        return img
    except Exception:
        return None


def _default_icon(quality: str) -> Image.Image:
    """Icône grise par défaut si pas disponible."""
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (30, 30, 35, 255))
    d   = ImageDraw.Draw(img)
    col = QUALITY_COLORS.get(quality, (80, 80, 80))
    d.rectangle([0, 0, ICON_SIZE-1, ICON_SIZE-1], outline=col, width=2)
    d.text((ICON_SIZE//2, ICON_SIZE//2), "?", fill=col, anchor="mm")
    return img


def _rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)


async def generate_equipment_image(
    char_name: str,
    classe: str,
    realm: str,
    equipped_ilvl: int,
    items: list,
    class_color: tuple = (100, 100, 200),
    render_url: str | None = None,
) -> io.BytesIO:

    # Trier les items
    def slot_key(it):
        s = it.get("slot", {}).get("name", "")
        try:    return SLOT_ORDER.index(s)
        except: return 99

    items_sorted = sorted(items, key=slot_key)[:16]
    n_items = len(items_sorted)

    # Layout : 2 colonnes
    cols       = 2
    rows       = (n_items + cols - 1) // cols
    header_h   = 100
    footer_h   = 40
    card_h     = header_h + rows * ROW_H + footer_h + PADDING * 2

    # ── Canvas ────────────────────────────────────────────────────────────────
    img  = Image.new("RGBA", (CARD_W, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fond dégradé sombre
    for y in range(card_h):
        t   = y / card_h
        r   = int(18 + t * 8)
        g   = int(18 + t * 8)
        b   = int(24 + t * 12)
        draw.line([(0, y), (CARD_W, y)], fill=(r, g, b, 255))

    # Bordure colorée (couleur de classe)
    cr, cg, cb = class_color
    _rounded_rect(draw, [0, 0, CARD_W-1, card_h-1], radius=12,
                  fill=None, outline=(cr, cg, cb, 200), width=3)

    # Ligne décorative sous le header
    draw.rectangle([20, header_h - 4, CARD_W - 20, header_h - 2],
                   fill=(cr, cg, cb, 160))

    # ── Polices (système) ─────────────────────────────────────────────────────
    try:
        font_big  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_TITLE + 4)
        font_name = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_NAME)
        font_sub  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",      FONT_SUB)
        font_ilvl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_SUB + 1)
    except Exception:
        font_big = font_name = font_sub = font_ilvl = ImageFont.load_default()

    # ── Header ────────────────────────────────────────────────────────────────
    # Nom du perso
    draw.text((24, 18), char_name.upper(), font=font_big,
              fill=(cr, cg, cb, 255))
    # Sous-titre
    sub = f"{classe}  ·  {realm}  ·  Item Level {equipped_ilvl}"
    draw.text((26, 50), sub, font=font_sub, fill=(180, 180, 180, 255))

    # Barre ilvl
    bar_w  = 300
    bar_h  = 10
    bx, by = 26, 72
    filled = min(int((equipped_ilvl / 700) * bar_w), bar_w)
    draw.rounded_rectangle([bx, by, bx + bar_w, by + bar_h],
                            radius=5, fill=(40, 40, 50, 255))
    if filled > 0:
        draw.rounded_rectangle([bx, by, bx + filled, by + bar_h],
                                radius=5, fill=(cr, cg, cb, 230))
    draw.text((bx + bar_w + 8, by - 1), f"{equipped_ilvl} ilvl",
              font=font_sub, fill=(cr, cg, cb, 255))

    # ── Items ─────────────────────────────────────────────────────────────────
    col_w = (CARD_W - PADDING * 3) // 2

    async with aiohttp.ClientSession() as session:
        icons = await asyncio.gather(*[_fetch_icon(session, it) for it in items_sorted])

    for idx, (it, icon) in enumerate(zip(items_sorted, icons)):
        col = idx % cols
        row = idx // cols
        x   = PADDING + col * (col_w + PADDING)
        y   = header_h + PADDING + row * ROW_H

        slot    = it.get("slot",    {}).get("name", "?")
        iname   = it.get("name",    "?")
        ilvl    = it.get("level",   {}).get("value", 0)
        quality = it.get("quality", {}).get("type", "COMMON")
        qcol    = QUALITY_COLORS.get(quality, (120, 120, 120))

        # Fond de la ligne
        _rounded_rect(draw, [x, y, x + col_w, y + ICON_SIZE + 6],
                      radius=6, fill=(25, 25, 32, 220),
                      outline=(*qcol, 120), width=1)

        # Icône
        icon_img = icon if icon else _default_icon(quality)
        # Bordure colorée autour de l'icône
        border = Image.new("RGBA", (ICON_SIZE + 4, ICON_SIZE + 4), (*qcol, 200))
        border.paste(icon_img, (2, 2))
        img.paste(border, (x + 4, y + 3), border)

        # Texte
        tx = x + ICON_SIZE + 12
        # Nom de l'objet (couleur qualité)
        max_chars = (col_w - ICON_SIZE - 20) // 7
        short_name = iname if len(iname) <= max_chars else iname[:max_chars - 1] + "…"
        draw.text((tx, y + 5), short_name, font=font_name, fill=(*qcol, 255))
        # Slot + ilvl
        draw.text((tx, y + 24), f"{slot}", font=font_sub, fill=(130, 130, 140, 255))
        draw.text((tx + 90, y + 24), f"ilvl {ilvl}", font=font_ilvl, fill=(200, 200, 200, 255))

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_y = card_h - footer_h + 10
    draw.text((24, footer_y),
              "World of Warcraft  ·  Données via l'API Blizzard officielle",
              font=font_sub, fill=(80, 80, 90, 255))

    # Légère vignette sur les bords
    vignette = Image.new("RGBA", (CARD_W, card_h), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for i in range(30):
        alpha = int((30 - i) * 3)
        vd.rounded_rectangle([i, i, CARD_W - i, card_h - i],
                              radius=12, outline=(0, 0, 0, alpha), width=1)
    img = Image.alpha_composite(img, vignette)

    # Export
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf
