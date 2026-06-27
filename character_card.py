import io, asyncio, aiohttp
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
W, H = 1200, 720

QUALITY_COLORS = {
    "LEGENDARY":(255,128,0),
    "EPIC":     (163,53,238),
    "RARE":     (0,112,221),
    "UNCOMMON": (30,200,0),
    "COMMON":   (150,150,150),
    "POOR":     (100,100,100),
}
SLOT_ORDER = [
    "Head","Neck","Shoulder","Back","Chest","Wrist","Hand","Waist",
    "Legs","Feet","Finger","Trinket","Main-Hand","Off-Hand",
    "Tête","Cou","Épaule","Dos","Torse","Poignet","Mains","Taille",
    "Jambes","Pieds","Doigt","Bibelot","Main droite","Main gauche",
]

def _f(bold=False, size=14):
    try:    return ImageFont.truetype(FONT+("-Bold" if bold else "")+".ttf", size)
    except: return ImageFont.load_default()

def _bar(draw, x, y, w, h, val, maxi, color, bg=(30,30,42)):
    draw.rounded_rectangle([x,y,x+w,y+h], radius=h//2, fill=bg)
    f = max(0, min(int((val/maxi)*w), w))
    if f > 0:
        draw.rounded_rectangle([x,y,x+f,y+h], radius=h//2, fill=color)

def _slot_key(it):
    s = it.get("slot",{}).get("name","")
    try:    return SLOT_ORDER.index(s)
    except: return 99

async def _dl(session, url, size=None):
    if not url: return None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                img = Image.open(io.BytesIO(await r.read())).convert("RGBA")
                if size: img = img.resize(size, Image.LANCZOS)
                return img
    except: pass
    return None


async def generate_character_card(
    name, classe, spec, race, realm, faction, guild,
    level, e_ilvl, a_ilvl, achiev, class_color,
    render_url, avatar_url, items, icon_urls,
) -> io.BytesIO:

    cr, cg, cb = class_color
    RENDER_W   = 360

    # ── Fond sombre ────────────────────────────────────────────────────────
    canvas = Image.new("RGB", (W, H), (10, 10, 16))
    draw   = ImageDraw.Draw(canvas)

    # Dégradé subtil de haut en bas
    for y in range(H):
        t   = y/H
        col = (int(10+t*6), int(10+t*6), int(16+t*10))
        draw.line([(0,y),(W,y)], fill=col)

    # ── RENDER 3D ─────────────────────────────────────────────────────────
    async with aiohttp.ClientSession() as session:
        render_img = await _dl(session, render_url)
        icon_imgs  = {}
        if icon_urls:
            tasks  = {iid: _dl(session, url, (48,48)) for iid,url in icon_urls.items()}
            results = await asyncio.gather(*tasks.values())
            icon_imgs = dict(zip(tasks.keys(), results))

    if render_img:
        # Mettre à l'échelle pour remplir toute la hauteur
        rw, rh   = render_img.size
        scale    = H / rh
        nw, nh   = int(rw*scale), H
        render_img = render_img.resize((nw, nh), Image.LANCZOS)
        # Crop centré
        lx = max(0, (nw-RENDER_W)//2)
        render_img = render_img.crop((lx, 0, lx+RENDER_W, H))
        # Fondu droite
        fade = Image.new("RGBA", (RENDER_W, H), (0,0,0,0))
        fd   = ImageDraw.Draw(fade)
        for x in range(120):
            a = int((x/120)**1.5 * 255)
            fd.line([(RENDER_W-x-1,0),(RENDER_W-x-1,H)], fill=(10,10,16,a))
        base = render_img.convert("RGBA")
        comp = Image.alpha_composite(base, fade).convert("RGB")
        canvas.paste(comp, (0,0))
        draw = ImageDraw.Draw(canvas)

    # Bordure classe (ligne verticale + bordure générale)
    draw.line([(RENDER_W, 0),(RENDER_W, H)], fill=(cr,cg,cb,100), width=2)
    draw.rectangle([0,0,W-1,H-1], outline=(cr,cg,cb), width=2)

    # ════════════════════════════════════════════════════════
    # PANNEAU DROIT — Stats + Équipement
    # ════════════════════════════════════════════════════════
    RX  = RENDER_W + 28
    RW  = W - RX - 20

    # ── NOM (grand, lisible) ──────────────────────────────────────────────
    draw.text((RX, 18), name.upper(), font=_f(True, 30), fill=(cr,cg,cb))

    sub = f"{spec+' · ' if spec else ''}{classe}  ·  {race}  ·  {faction}"
    draw.text((RX, 58), sub, font=_f(False, 16), fill=(200, 200, 215))

    realm_txt = f"🏰  {realm}" + (f"     ⚔  <{guild}>" if guild else "")
    draw.text((RX, 84), realm_txt, font=_f(False, 14), fill=(140, 140, 160))

    # Séparateur
    draw.line([(RX, 112),(W-20, 112)], fill=(cr,cg,cb,120), width=1)

    # ── STATS ─────────────────────────────────────────────────────────────
    BW = RW - 90

    # NIVEAU
    draw.text((RX, 122), "NIVEAU", font=_f(True, 13), fill=(160,160,180))
    draw.text((RX+BW+4, 122), f"{level} / 80", font=_f(True, 14), fill=(cr,cg,cb))
    _bar(draw, RX, 140, BW, 13, level, 80, (cr,cg,cb))
    pct = round((int(level)/80)*100)
    draw.text((RX+BW//2, 140), f"{pct}%", font=_f(False,11), fill=(200,200,215), anchor="mt")

    # ITEM LEVEL
    draw.text((RX, 164), "ITEM LEVEL ÉQUIPÉ", font=_f(True, 13), fill=(160,160,180))
    draw.text((RX+BW+4, 164), str(e_ilvl), font=_f(True, 14), fill=(255,200,50))
    _bar(draw, RX, 182, BW, 13, e_ilvl, 700, (255,200,50))

    # Ilvl moyen + hauts faits
    draw.text((RX, 206),
              f"Ilvl moyen  {a_ilvl}     ·     Hauts faits  {achiev:,}",
              font=_f(False, 14), fill=(160,160,180))

    draw.line([(RX, 230),(W-20, 230)], fill=(cr,cg,cb,80), width=1)

    # ════════════════════════════════════════════════════════
    # ÉQUIPEMENT — 2 colonnes, icônes + texte lisible
    # ════════════════════════════════════════════════════════
    EY     = 238
    EH     = H - EY - 24
    COLS   = 2
    IS     = 46         # taille icône

    items_sorted = sorted(items, key=_slot_key)[:16]
    rows   = (len(items_sorted)+COLS-1)//COLS
    ROW_H  = max(IS + 14, EH // max(rows,1))
    COL_W  = RW // COLS

    for idx, it in enumerate(items_sorted):
        ci = idx % COLS
        ri = idx // COLS
        ix = RX + ci * COL_W
        iy = EY + ri * ROW_H

        # Données item — ID est dans it["item"]["id"]
        item_id = it.get("item",{}).get("id") or it.get("media",{}).get("id")
        slot    = it.get("slot",{}).get("name","?")
        iname   = it.get("name","?")
        ilvl    = it.get("level",{}).get("value","?")
        quality = it.get("quality",{}).get("type","COMMON")
        qcol    = QUALITY_COLORS.get(quality,(140,140,140))

        # Fond de la ligne
        draw.rounded_rectangle(
            [ix+2, iy+2, ix+COL_W-4, iy+ROW_H-4],
            radius=6, fill=(18,18,28), outline=(*qcol,80), width=1
        )

        # ── Icône ──────────────────────────────────────────────────────
        icon_img = icon_imgs.get(item_id) if item_id else None
        ix_icon  = ix + 6
        iy_icon  = iy + (ROW_H - IS) // 2

        if icon_img:
            # Fond icône + bordure qualité
            bg_icon = Image.new("RGB", (IS, IS), (20,20,30))
            bg_icon.paste(icon_img.convert("RGB"), (0,0))
            canvas.paste(bg_icon, (ix_icon, iy_icon))
            draw.rectangle(
                [ix_icon, iy_icon, ix_icon+IS-1, iy_icon+IS-1],
                outline=(*qcol, 200), width=2
            )
        else:
            # Placeholder bien visible
            draw.rounded_rectangle(
                [ix_icon, iy_icon, ix_icon+IS, iy_icon+IS],
                radius=4, fill=(25,25,38), outline=(*qcol,150), width=2
            )
            draw.text((ix_icon+IS//2, iy_icon+IS//2), "?",
                      font=_f(True,20), fill=qcol, anchor="mm")

        # ── Texte item ─────────────────────────────────────────────────
        tx     = ix_icon + IS + 10
        avail  = COL_W - IS - 22
        max_ch = avail // 8
        short  = iname if len(iname)<=max_ch else iname[:max_ch-1]+"…"

        # Nom en couleur qualité, bien lisible
        draw.text((tx, iy + 8),  short,          font=_f(True,14),  fill=(*qcol,255))
        # Slot en gris clair
        draw.text((tx, iy + 28), slot,            font=_f(False,12), fill=(150,150,168))
        # Ilvl bien visible
        draw.text((tx+avail-55, iy+28), f"ilvl {ilvl}", font=_f(True,12), fill=(220,220,235))

    # ── FOOTER ────────────────────────────────────────────────────────────
    draw.line([(16,H-22),(W-16,H-22)], fill=(cr,cg,cb,50), width=1)
    draw.text((W//2, H-13),
              "World of Warcraft  ·  API Blizzard Officielle",
              font=_f(False,11), fill=(70,70,85), anchor="mt")

    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf
