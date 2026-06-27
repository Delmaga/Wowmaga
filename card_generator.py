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
    "POOR":      (100, 100, 100),
}

SLOT_ORDER = [
    "Head","Neck","Shoulder","Back","Chest","Wrist","Hand","Waist",
    "Legs","Feet","Finger","Trinket","Main-Hand","Off-Hand",
    "Tête","Cou","Épaule","Dos","Torse","Poignet","Mains","Taille",
    "Jambes","Pieds","Doigt","Bibelot","Main droite","Main gauche",
]

ICON_SIZE = 52
PAD       = 12
COL_W     = 368
CARD_W    = COL_W * 2 + PAD * 3
HEADER_H  = 90
ROW_H     = ICON_SIZE + PAD + 2


def _slot_key(it):
    s = it.get("slot", {}).get("name", "")
    try:    return SLOT_ORDER.index(s)
    except: return 99


def _f(bold=False, size=13):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
    try:    return ImageFont.truetype(path + ("-Bold" if bold else "") + ".ttf", size)
    except: return ImageFont.load_default()


async def _fetch_img(session: aiohttp.ClientSession, url: str, size: int) -> Image.Image | None:
    if not url:
        return None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                data = await r.read()
                img  = Image.open(io.BytesIO(data)).convert("RGBA")
                return img.resize((size, size), Image.LANCZOS)
    except Exception:
        pass
    return None


def _placeholder(quality: str) -> Image.Image:
    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (28, 28, 35, 255))
    d   = ImageDraw.Draw(img)
    col = QUALITY_COLORS.get(quality, (100, 100, 100))
    d.rectangle([0, 0, ICON_SIZE-1, ICON_SIZE-1], outline=col, width=2)
    d.text((ICON_SIZE//2, ICON_SIZE//2), "?", fill=col, anchor="mm",
           font=_f(True, 20))
    return img


async def generate_equipment_image(
    char_name: str,
    classe: str,
    realm: str,
    equipped_ilvl: int,
    items: list,
    class_color: tuple = (100, 100, 200),
    icon_urls: dict | None = None,   # {item_id: url}
) -> io.BytesIO:

    items_sorted = sorted(items, key=_slot_key)[:16]
    rows         = (len(items_sorted) + 1) // 2
    card_h       = HEADER_H + rows * ROW_H + PAD * 2 + 30
    cr, cg, cb   = class_color

    # ── Fond ──────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (CARD_W, card_h))
    for y in range(card_h):
        t   = y / card_h
        col = (int(14+t*10), int(14+t*10), int(20+t*14), 255)
        ImageDraw.Draw(canvas).line([(0, y), (CARD_W, y)], fill=col)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([2, 2, CARD_W-3, card_h-3],
                            radius=10, outline=(cr,cg,cb,200), width=3)

    # ── Header ────────────────────────────────────────────────────
    draw.text((PAD+4, 10), char_name.upper(), font=_f(True, 18), fill=(cr,cg,cb))
    draw.text((PAD+4, 36), f"{classe}  ·  {realm}", font=_f(False, 12), fill=(180,180,180))

    bw     = CARD_W - PAD*2 - 90
    filled = min(int((equipped_ilvl/700)*bw), bw)
    draw.rounded_rectangle([PAD, 62, PAD+bw, 76], radius=5, fill=(35,35,45))
    if filled > 0:
        draw.rounded_rectangle([PAD, 62, PAD+filled, 76], radius=5, fill=(cr,cg,cb))
    draw.text((PAD+bw+8, 62), f"ilvl {equipped_ilvl}", font=_f(True,12), fill=(cr,cg,cb))
    draw.line([(PAD, HEADER_H-4),(CARD_W-PAD, HEADER_H-4)], fill=(cr,cg,cb,80), width=1)

    # ── Téléchargement de toutes les icônes en parallèle ──────────
    urls_to_fetch = []
    for it in items_sorted:
        item_id = it.get("id")
        url     = (icon_urls or {}).get(item_id) if icon_urls else None
        # Fallback : parfois l'URL est dans media.assets directement
        if not url:
            for a in it.get("media", {}).get("assets", []):
                if a.get("key") in ("icon", ""):
                    url = a.get("value")
                    break
        urls_to_fetch.append(url)

    async def _none(): return None

    async with aiohttp.ClientSession() as session:
        icons = await asyncio.gather(*[
            _fetch_img(session, u, ICON_SIZE) if u else _none()
            for u in urls_to_fetch
        ])

    # ── Dessin des items ──────────────────────────────────────────
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

        # Fond ligne
        draw.rounded_rectangle([x, y, x+COL_W-PAD, y+ICON_SIZE+4],
                                radius=6, fill=(20,20,28,230),
                                outline=(*qcol, 70), width=1)

        # ── Icône avec bordure qualité ────────────────────────────
        icon_img = icon if icon else _placeholder(quality)

        # Bordure colorée autour de l'icône
        border_size = ICON_SIZE + 6
        border      = Image.new("RGBA", (border_size, border_size), (0,0,0,0))
        bd          = ImageDraw.Draw(border)
        bd.rounded_rectangle([0,0,border_size-1,border_size-1],
                              radius=4, outline=(*qcol,230), width=2)
        bd.rounded_rectangle([2,2,border_size-3,border_size-3],
                              radius=3, fill=(15,15,20,200))
        border.paste(icon_img, (3, 3), icon_img)
        canvas.paste(border, (x+4, y+2), border)

        # ── Texte : nom + slot + ilvl ─────────────────────────────
        tx      = x + ICON_SIZE + 14
        max_ch  = (COL_W - ICON_SIZE - 22) // 7
        name_sh = iname if len(iname) <= max_ch else iname[:max_ch-1]+"…"

        draw.text((tx, y+5),  name_sh,          font=_f(True,13),  fill=(*qcol,255))
        draw.text((tx, y+25), slot,              font=_f(False,11), fill=(110,110,125))
        draw.text((tx+110, y+25), f"ilvl {ilvl}", font=_f(True,11),  fill=(200,200,210))

    # ── Footer ────────────────────────────────────────────────────
    draw.line([(PAD,card_h-28),(CARD_W-PAD,card_h-28)], fill=(cr,cg,cb,50), width=1)
    draw.text((PAD, card_h-20),
              "World of Warcraft  ·  Données via l'API officielle Blizzard",
              font=_f(False, 10), fill=(65,65,78))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf
