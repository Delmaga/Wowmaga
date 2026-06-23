import io
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFont

QUALITY_COLORS = {
    "LEGENDARY": (255, 128,   0),
    "EPIC":      (163,  53, 238),
    "RARE":      (  0, 112, 221),
    "UNCOMMON":  ( 30, 200,   0),
    "COMMON":    (150, 150, 150),
}

SLOT_ORDER = [
    "Head","Neck","Shoulder","Back","Chest","Wrist","Hand","Waist",
    "Legs","Feet","Finger","Trinket","Main-Hand","Off-Hand",
    "Tête","Cou","Épaule","Dos","Torse","Poignet","Mains","Taille",
    "Jambes","Pieds","Doigt","Bibelot","Main droite","Main gauche",
]

ICON_SIZE = 48
PAD       = 12
COL_W     = 360
CARD_W    = COL_W * 2 + PAD * 3
HEADER_H  = 90
ROW_H     = ICON_SIZE + PAD


def _slot_key(it):
    s = it.get("slot", {}).get("name", "")
    try:    return SLOT_ORDER.index(s)
    except: return 99


async def _fetch_icon(session: aiohttp.ClientSession, url: str) -> Image.Image | None:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
            if r.status == 200:
                data = await r.read()
                img = Image.open(io.BytesIO(data)).convert("RGBA")
                return img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    except Exception:
        pass
    return None


def _placeholder(quality: str) -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (28, 28, 35, 255))
    d   = ImageDraw.Draw(img)
    col = QUALITY_COLORS.get(quality, (100, 100, 100))
    d.rectangle([0, 0, ICON_SIZE-1, ICON_SIZE-1], outline=col, width=2)
    d.text((ICON_SIZE//2, ICON_SIZE//2), "?", fill=col, anchor="mm")
    return img


def _try_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:    return ImageFont.truetype(path, size)
    except: return ImageFont.load_default()


async def generate_equipment_image(
    char_name: str,
    classe: str,
    realm: str,
    equipped_ilvl: int,
    items: list,
    class_color: tuple = (100, 100, 200),
) -> io.BytesIO:

    items_sorted = sorted(items, key=_slot_key)[:16]
    rows         = (len(items_sorted) + 1) // 2
    card_h       = HEADER_H + rows * ROW_H + PAD * 2 + 30

    # ── Polices ───────────────────────────────────────────────────────
    FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
    f_title   = _try_font(FONT_PATH + "-Bold.ttf", 18)
    f_sub     = _try_font(FONT_PATH + ".ttf",      12)
    f_name    = _try_font(FONT_PATH + "-Bold.ttf", 13)
    f_small   = _try_font(FONT_PATH + ".ttf",      11)

    # ── Fond ──────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (CARD_W, card_h), (0, 0, 0, 0))
    for y in range(card_h):
        t   = y / card_h
        col = (int(15 + t*10), int(15 + t*10), int(20 + t*15), 255)
        ImageDraw.Draw(canvas).line([(0,y),(CARD_W,y)], fill=col)

    draw = ImageDraw.Draw(canvas)
    cr, cg, cb = class_color

    # Bordure classe
    draw.rounded_rectangle([0, 0, CARD_W-1, card_h-1],
                            radius=10, outline=(cr, cg, cb, 220), width=3)

    # ── Header ────────────────────────────────────────────────────────
    draw.text((PAD+4, 10), char_name.upper(), font=f_title, fill=(cr, cg, cb))
    draw.text((PAD+4, 36), f"{classe}  ·  {realm}", font=f_sub, fill=(180,180,180))

    # Barre ilvl
    bw     = CARD_W - PAD*2 - 80
    filled = min(int((equipped_ilvl / 700) * bw), bw)
    draw.rounded_rectangle([PAD, 60, PAD+bw, 74], radius=4, fill=(35,35,45))
    if filled > 0:
        draw.rounded_rectangle([PAD, 60, PAD+filled, 74], radius=4, fill=(cr, cg, cb))
    draw.text((PAD+bw+8, 59), f"ilvl {equipped_ilvl}", font=f_small, fill=(cr,cg,cb))

    # Séparateur
    draw.line([(PAD, HEADER_H-4), (CARD_W-PAD, HEADER_H-4)], fill=(cr,cg,cb,100), width=1)

    # ── Icônes ────────────────────────────────────────────────────────
    icon_urls = []
    for it in items_sorted:
        url = None
        for asset in it.get("media", {}).get("assets", []):
            if asset.get("key") in ("icon", ""):
                url = asset.get("value")
                break
        icon_urls.append(url)

    async with aiohttp.ClientSession() as session:
        icons = await asyncio.gather(*[
            _fetch_icon(session, u) if u else asyncio.coroutine(lambda: None)()
            for u in icon_urls
        ])

    for idx, (it, icon) in enumerate(zip(items_sorted, icons)):
        col_i   = idx % 2
        row_i   = idx // 2
        x       = PAD + col_i * (COL_W + PAD)
        y       = HEADER_H + PAD + row_i * ROW_H

        slot    = it.get("slot",    {}).get("name", "?")
        iname   = it.get("name",    "?")
        ilvl    = it.get("level",   {}).get("value", "?")
        quality = it.get("quality", {}).get("type", "COMMON")
        qcol    = QUALITY_COLORS.get(quality, (120,120,120))

        # Fond item
        draw.rounded_rectangle([x, y, x+COL_W-PAD, y+ICON_SIZE+2],
                                radius=6, fill=(22,22,30,230), outline=(*qcol,80), width=1)

        # Icône avec bordure qualité
        icon_img = icon if icon else _placeholder(quality)
        border   = Image.new("RGBA", (ICON_SIZE+4, ICON_SIZE+4), (*qcol, 180))
        border.paste(icon_img, (2,2), icon_img)
        canvas.paste(border, (x+4, y+1), border)

        # Textes
        tx      = x + ICON_SIZE + 10
        max_ch  = (COL_W - ICON_SIZE - 20) // 7
        name_sh = iname if len(iname) <= max_ch else iname[:max_ch-1]+"…"
        draw.text((tx, y+4),  name_sh, font=f_name,  fill=(*qcol, 255))
        draw.text((tx, y+24), slot,    font=f_small, fill=(120,120,130))
        draw.text((tx+100, y+24), f"ilvl {ilvl}", font=f_small, fill=(200,200,200))

    # Export PNG
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf
