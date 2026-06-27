"""
Génère UNE seule grande image pour /comptewow :
  - Render 3D du personnage (gauche)
  - Stats (droite haut)
  - Équipement avec vraies icônes Blizzard (droite bas)
"""
import io
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
W, H      = 1100, 700
ICON_SIZE = 44

QUALITY_COLORS = {
    "LEGENDARY": (255,128,0),
    "EPIC":      (163,53,238),
    "RARE":      (0,112,221),
    "UNCOMMON":  (30,200,0),
    "COMMON":    (140,140,140),
    "POOR":      (100,100,100),
}

SLOT_ORDER = [
    "Head","Neck","Shoulder","Back","Chest","Wrist","Hand","Waist",
    "Legs","Feet","Finger","Trinket","Main-Hand","Off-Hand",
    "Tête","Cou","Épaule","Dos","Torse","Poignet","Mains","Taille",
    "Jambes","Pieds","Doigt","Bibelot","Main droite","Main gauche",
]


def _f(bold=False, size=13):
    try:    return ImageFont.truetype(FONT_PATH+("-Bold" if bold else "")+".ttf", size)
    except: return ImageFont.load_default()


def _bar(draw, x, y, w, h, val, maxi, color, bg=(30,30,40)):
    draw.rounded_rectangle([x,y,x+w,y+h], radius=h//2, fill=bg)
    filled = max(0, min(int((val/maxi)*w), w))
    if filled > 0:
        draw.rounded_rectangle([x,y,x+filled,y+h], radius=h//2, fill=color)


async def _dl(session, url, size=None):
    if not url: return None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status == 200:
                img = Image.open(io.BytesIO(await r.read())).convert("RGBA")
                if size: img = img.resize(size, Image.LANCZOS)
                return img
    except: pass
    return None


def _slot_key(it):
    s = it.get("slot",{}).get("name","")
    try: return SLOT_ORDER.index(s)
    except: return 99


async def generate_character_card(
    name: str,
    classe: str,
    spec: str,
    race: str,
    realm: str,
    faction: str,
    guild: str | None,
    level: int,
    e_ilvl: int,
    a_ilvl: int,
    achiev: int,
    class_color: tuple,
    render_url: str | None,
    avatar_url: str | None,
    items: list,
    icon_urls: dict,         # {item_id: icon_url}
) -> io.BytesIO:

    cr, cg, cb = class_color

    # ── FOND ──────────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H))
    for y in range(H):
        t   = y/H
        col = (int(12+t*8), int(12+t*8), int(18+t*12), 255)
        ImageDraw.Draw(canvas).line([(0,y),(W,y)], fill=col)

    draw = ImageDraw.Draw(canvas)

    # Bordure classe
    draw.rounded_rectangle([2,2,W-3,H-3], radius=12,
                            outline=(cr,cg,cb,180), width=3)

    # ════════════════════════════════════════════════════════════════════
    # PANNEAU GAUCHE — Render 3D du personnage (380px de large)
    # ════════════════════════════════════════════════════════════════════
    RENDER_W = 340

    async with aiohttp.ClientSession() as session:
        # Téléchargements en parallèle : render + toutes les icônes
        render_task = _dl(session, render_url)
        icon_tasks  = {
            iid: _dl(session, url, (ICON_SIZE, ICON_SIZE))
            for iid, url in icon_urls.items()
        }
        render_img, *icon_imgs_list = await asyncio.gather(
            render_task, *icon_tasks.values()
        )
        downloaded_icons = dict(zip(icon_tasks.keys(), icon_imgs_list))

    if render_img:
        # Redimensionner le render pour remplir la hauteur
        rw, rh   = render_img.size
        scale    = H / rh
        new_size = (int(rw*scale), H)
        render_img = render_img.resize(new_size, Image.LANCZOS)
        # Crop centré sur RENDER_W
        left = max(0, (new_size[0]-RENDER_W)//2)
        render_img = render_img.crop((left, 0, left+RENDER_W, H))

        # Dégradé sur le côté droit du render pour fusion douce
        fade = Image.new("RGBA", (RENDER_W, H), (0,0,0,0))
        fd   = ImageDraw.Draw(fade)
        for x in range(80):
            alpha = int((x/80)*220)
            fd.line([(RENDER_W-x-1,0),(RENDER_W-x-1,H)], fill=(12,12,18,alpha))
        render_comp = Image.alpha_composite(render_img, fade)
        canvas.paste(render_comp, (0,0), render_comp)
        draw = ImageDraw.Draw(canvas)

    # Ligne verticale séparatrice
    draw.line([(RENDER_W,20),(RENDER_W,H-20)], fill=(cr,cg,cb,80), width=1)

    # ════════════════════════════════════════════════════════════════════
    # PANNEAU DROIT — Stats + Équipement
    # ════════════════════════════════════════════════════════════════════
    RX = RENDER_W + 20   # x de départ panneau droit
    RW = W - RX - 16    # largeur disponible

    # ── NOM & IDENTITÉ ────────────────────────────────────────────────
    draw.text((RX, 16), name.upper(), font=_f(True,24), fill=(cr,cg,cb))
    sub = f"{spec+' · ' if spec else ''}{classe}  ·  {race}  ·  {faction}"
    draw.text((RX, 48), sub, font=_f(False,13), fill=(170,170,185))
    draw.text((RX, 66), f"🏰  {realm}" + (f"   <{guild}>" if guild else ""),
              font=_f(False,12), fill=(120,120,135))

    draw.line([(RX, 88),(W-16, 88)], fill=(cr,cg,cb,80), width=1)

    # ── STATS ─────────────────────────────────────────────────────────
    sy = 96
    bar_w = RW - 80

    # NIVEAU
    draw.text((RX, sy), "NIVEAU", font=_f(True,11), fill=(150,150,165))
    draw.text((RX+bar_w+4, sy), f"{level}/80", font=_f(True,11), fill=(cr,cg,cb))
    _bar(draw, RX, sy+16, bar_w, 10, level, 80, (cr,cg,cb))

    # ITEM LEVEL
    sy2 = sy+36
    draw.text((RX, sy2), "ITEM LEVEL ÉQUIPÉ", font=_f(True,11), fill=(150,150,165))
    draw.text((RX+bar_w+4, sy2), str(e_ilvl), font=_f(True,11), fill=(255,200,50))
    _bar(draw, RX, sy2+16, bar_w, 10, e_ilvl, 700, (255,200,50))

    # Ilvl moyen + hauts faits inline
    sy3 = sy2+36
    draw.text((RX, sy3), f"Ilvl moyen  {a_ilvl}   ·   Hauts faits  {achiev:,}",
              font=_f(False,12), fill=(130,130,145))

    draw.line([(RX, sy3+20),(W-16, sy3+20)], fill=(cr,cg,cb,60), width=1)

    # ════════════════════════════════════════════════════════════════════
    # ÉQUIPEMENT — grille avec vraies icônes
    # ════════════════════════════════════════════════════════════════════
    EY     = sy3+28          # y départ équipement
    EH     = H - EY - 22    # hauteur dispo
    COLS   = 2
    items_sorted = sorted(items, key=_slot_key)[:16]
    rows   = (len(items_sorted)+COLS-1)//COLS
    ROW_H  = min(int(EH/rows), ICON_SIZE+10)

    col_w  = RW // COLS

    for idx, it in enumerate(items_sorted):
        col_i   = idx % COLS
        row_i   = idx // COLS
        ix      = RX + col_i * col_w
        iy      = EY + row_i * ROW_H

        slot    = it.get("slot",{}).get("name","?")
        iname   = it.get("name","?")
        ilvl    = it.get("level",{}).get("value","?")
        quality = it.get("quality",{}).get("type","COMMON")
        item_id = it.get("id")
        qcol    = QUALITY_COLORS.get(quality,(120,120,120))

        # Fond ligne
        draw.rounded_rectangle([ix+1,iy+1,ix+col_w-4,iy+ROW_H-2],
                                radius=4, fill=(18,18,26,200),
                                outline=(*qcol,60), width=1)

        # Icône
        icon_img = downloaded_icons.get(item_id) if item_id else None
        IS = ICON_SIZE
        if icon_img:
            # Bordure couleur qualité
            bordered = Image.new("RGBA",(IS+4,IS+4),(0,0,0,0))
            ImageDraw.Draw(bordered).rounded_rectangle(
                [0,0,IS+3,IS+3], radius=3, outline=(*qcol,200), width=2)
            bordered.paste(icon_img.resize((IS,IS),Image.LANCZOS),(2,2),
                          icon_img.resize((IS,IS),Image.LANCZOS))
            canvas.paste(bordered,(ix+3,iy+2),bordered)
        else:
            # Placeholder coloré
            ph = Image.new("RGBA",(IS,IS),(20,20,28,255))
            pd = ImageDraw.Draw(ph)
            pd.rounded_rectangle([0,0,IS-1,IS-1],radius=3,outline=(*qcol,150),width=2)
            pd.text((IS//2,IS//2),"?",fill=qcol,anchor="mm",font=_f(True,16))
            canvas.paste(ph,(ix+4,iy+3),ph)

        # Texte
        tx     = ix + IS + 10
        max_ch = (col_w - IS - 14) // 7
        short  = iname if len(iname)<=max_ch else iname[:max_ch-1]+"…"
        draw.text((tx, iy+4),  short,         font=_f(True,12),  fill=(*qcol,255))
        draw.text((tx, iy+20), slot,           font=_f(False,10), fill=(100,100,115))
        draw.text((tx+85,iy+20),f"ilvl {ilvl}",font=_f(True,10), fill=(180,180,195))

    # ── FOOTER ────────────────────────────────────────────────────────
    draw.line([(16,H-20),(W-16,H-20)], fill=(cr,cg,cb,40), width=1)
    draw.text((W//2,H-12),
              "World of Warcraft  ·  API Blizzard Officielle",
              font=_f(False,10), fill=(60,60,72), anchor="mt")

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf,"PNG",optimize=True)
    buf.seek(0)
    return buf
