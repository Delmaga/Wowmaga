import io
import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import aiohttp

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans"

def _f(bold=False, size=14):
    try:    return ImageFont.truetype(FONT+("-Bold" if bold else "")+".ttf", size)
    except: return ImageFont.load_default()

def _bar(draw, x, y, w, h, val, maxi, color, bg=(35,35,45)):
    filled = max(0, min(int((val/maxi)*w), w))
    draw.rounded_rectangle([x,y,x+w,y+h], radius=h//2, fill=bg)
    if filled > 0:
        draw.rounded_rectangle([x,y,x+filled,y+h], radius=h//2, fill=color)

def _glow(img, color, radius=8):
    glow = Image.new("RGBA", img.size, (0,0,0,0))
    solid = Image.new("RGBA", img.size, (*color,60))
    glow.paste(solid, mask=solid)
    return Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(radius)))


async def _fetch_avatar(url: str) -> Image.Image | None:
    if not url: return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    data = await r.read()
                    import io as _io
                    return Image.open(_io.BytesIO(data)).convert("RGBA")
    except: pass
    return None


async def generate_stats_image(
    char_name: str,
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
    last_login_ms: int | None,
    class_color: tuple,
    avatar_url: str | None = None,
) -> io.BytesIO:

    W, H = 700, 420
    cr, cg, cb = class_color

    # ── Fond dégradé ──────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H))
    for y in range(H):
        t  = y/H
        r  = int(12 + t*10)
        g  = int(12 + t*10)
        b  = int(18 + t*16)
        ImageDraw.Draw(canvas).line([(0,y),(W,y)], fill=(r,g,b,255))

    # Effet glow classe
    canvas = _glow(canvas, (cr,cg,cb))

    draw = ImageDraw.Draw(canvas)

    # Bordure classe
    draw.rounded_rectangle([2,2,W-3,H-3], radius=14,
                            outline=(cr,cg,cb,200), width=3)

    # ── Avatar ────────────────────────────────────────────────────
    AV = 90
    avatar_img = await _fetch_avatar(avatar_url)
    if avatar_img:
        av = avatar_img.resize((AV,AV), Image.LANCZOS)
        # Cercle masque
        mask = Image.new("L",(AV,AV),0)
        ImageDraw.Draw(mask).ellipse([0,0,AV-1,AV-1], fill=255)
        av.putalpha(mask)
        # Cercle bordure
        ring = Image.new("RGBA",(AV+6,AV+6),(0,0,0,0))
        ImageDraw.Draw(ring).ellipse([0,0,AV+5,AV+5], outline=(cr,cg,cb,220), width=3)
        canvas.paste(ring, (16,16), ring)
        canvas.paste(av, (19,19), av)
        draw = ImageDraw.Draw(canvas)

    # ── Nom & infos ───────────────────────────────────────────────
    tx = AV + 30
    draw.text((tx, 20), char_name.upper(), font=_f(True,26), fill=(cr,cg,cb))
    draw.text((tx, 54), (spec+" · " if spec else "")+classe, font=_f(False,14), fill=(200,200,200))
    draw.text((tx, 74), race+" · "+faction, font=_f(False,13), fill=(150,150,160))
    draw.text((tx, 94), "🏰 "+realm+(f"  ·  <{guild}>" if guild else ""),
              font=_f(False,13), fill=(130,130,145))

    # Ligne séparatrice
    draw.line([(20, 128),(W-20, 128)], fill=(cr,cg,cb,100), width=1)

    # ── BLOCS STATS ───────────────────────────────────────────────
    PAD   = 24
    BAR_W = (W - PAD*3) // 2
    BAR_H = 14
    sy    = 148

    def stat_block(x, y, label, val, val_str, maxi, color):
        draw.text((x, y), label, font=_f(True,12), fill=(180,180,190))
        draw.text((x+BAR_W, y), val_str, font=_f(True,13), fill=color, anchor="ra")
        _bar(draw, x, y+20, BAR_W, BAR_H, val, maxi, color)

    # NIVEAU
    lv_pct = round((level/80)*100)
    stat_block(PAD, sy, "⚔  NIVEAU",
               level, f"{level} / 80  ({lv_pct}%)", 80,
               (cr,cg,cb))

    # ITEM LEVEL
    stat_block(PAD*2+BAR_W, sy, "🛡  ITEM LEVEL ÉQUIPÉ",
               e_ilvl, f"{e_ilvl}  ({round((e_ilvl/700)*100)}%)", 700,
               (255,180,50))

    sy2 = sy + 70

    # ILVL MOYEN
    stat_block(PAD, sy2, "📊  ITEM LEVEL MOYEN",
               a_ilvl, f"{a_ilvl}", 700,
               (100,200,255))

    # HAUTS FAITS
    ach_pct = min(int((achiev/30000)*100),100)
    stat_block(PAD*2+BAR_W, sy2, "🏆  HAUTS FAITS",
               achiev, f"{achiev:,} pts", 30000,
               (255,215,0))

    # ── DERNIÈRE CONNEXION ────────────────────────────────────────
    sy3 = sy2 + 70
    draw.line([(PAD, sy3-10),(W-PAD, sy3-10)], fill=(cr,cg,cb,60), width=1)

    if last_login_ms:
        dt  = datetime.datetime.fromtimestamp(last_login_ms/1000, tz=datetime.timezone.utc)
        txt = dt.strftime("Dernière connexion  :  %d/%m/%Y à %H:%M UTC")
        draw.text((PAD, sy3), "🕐  "+txt, font=_f(False,13), fill=(140,140,155))
    else:
        draw.text((PAD, sy3), "🕐  Dernière connexion : inconnue", font=_f(False,13), fill=(100,100,110))

    # ── Note zone ─────────────────────────────────────────────────
    draw.text((PAD, sy3+28),
              "📍  Localisation actuelle non disponible via l'API Blizzard",
              font=_f(False,11), fill=(80,80,90))

    # ── Footer ────────────────────────────────────────────────────
    draw.line([(PAD,H-36),(W-PAD,H-36)], fill=(cr,cg,cb,60), width=1)
    draw.text((PAD, H-26), "World of Warcraft  ·  Données officielles Blizzard",
              font=_f(False,11), fill=(70,70,80))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf
