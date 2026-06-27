"""Génère l'image de la semaine WoW (Token, Affixes M+, Événements)."""
import io
from PIL import Image, ImageDraw, ImageFont

AFFIX_COLORS = {
    "Fortifié":    (100,180,255), "Fortified":  (100,180,255),
    "Tyrannique":  (255,100,100), "Tyrannical": (255,100,100),
    "Explosif":    (255,140, 50), "Explosive":  (255,140, 50),
    "Sanguinaire": (200, 50, 50), "Sanguine":   (200, 50, 50),
    "Bouillonnant":(255,200, 50), "Bolstering": (255,200, 50),
    "Éclaboussant":(100,220,255), "Spiteful":   (100,220,255),
    "Grégaire":    (180,255,100), "Incorporel": (200,200,200),
    "Tempête":     (150,150,255),
}

def _f(bold=False, size=14):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans"
    try:    return ImageFont.truetype(path+("-Bold" if bold else "")+".ttf", size)
    except: return ImageFont.load_default()

def _rounded_rect(draw, xy, r, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


async def generate_weekly_image(
    token_price: int | None,
    token_trend: str,        # "up" | "down" | "stable"
    affixes: list[dict],     # [{"name": "...", "description": "..."}]
    events: list[str],       # noms des événements actifs
    reset_day: str,
    class_color: tuple = (255, 178, 0),
) -> io.BytesIO:
    W, H   = 720, 500
    cr, cg, cb = class_color

    # ── Fond ──────────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H))
    for y in range(H):
        t   = y / H
        col = (int(12+t*10), int(12+t*10), int(18+t*14), 255)
        ImageDraw.Draw(canvas).line([(0,y),(W,y)], fill=col)

    draw = ImageDraw.Draw(canvas)

    # Bordure or
    _rounded_rect(draw, [2,2,W-3,H-3], 14, outline=(cr,cg,cb,180), width=3)

    # ── TITRE ─────────────────────────────────────────────────────────────
    draw.text((W//2, 22), "⚔  INFOS DE LA SEMAINE  ⚔",
              font=_f(True,20), fill=(cr,cg,cb), anchor="mt")
    draw.text((W//2, 50), reset_day,
              font=_f(False,12), fill=(140,140,155), anchor="mt")
    draw.line([(20,68),(W-20,68)], fill=(cr,cg,cb,100), width=1)

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 1 : WoW TOKEN
    # ══════════════════════════════════════════════════════════════════════
    sx, sy = 20, 82
    _rounded_rect(draw, [sx,sy,sx+330,sy+110], 8,
                  fill=(20,20,30,220), outline=(cr,cg,cb,60), width=1)

    draw.text((sx+12, sy+10), "💰  WOW TOKEN", font=_f(True,13), fill=(cr,cg,cb))
    draw.line([(sx+10,sy+30),(sx+320,sy+30)], fill=(cr,cg,cb,50), width=1)

    if token_price:
        price_str = f"{token_price:,}".replace(",",".")+" po"
        trend_col = (50,220,50) if token_trend=="up" else (220,50,50) if token_trend=="down" else (180,180,180)
        trend_sym = "▲" if token_trend=="up" else "▼" if token_trend=="down" else "●"
        draw.text((sx+12, sy+42), price_str, font=_f(True,28), fill=(255,215,0))
        draw.text((sx+12, sy+78), f"{trend_sym} Prix actuel en pièces d'or",
                  font=_f(False,12), fill=trend_col)
        draw.text((sx+12, sy+95), "Utilisable pour 30 jours de jeu",
                  font=_f(False,11), fill=(100,100,110))
    else:
        draw.text((sx+12, sy+50), "Indisponible", font=_f(False,14), fill=(100,100,110))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 2 : AFFIXES M+
    # ══════════════════════════════════════════════════════════════════════
    ax, ay = 370, 82
    _rounded_rect(draw, [ax,ay,ax+330,ay+110], 8,
                  fill=(20,20,30,220), outline=(100,100,200,60), width=1)

    draw.text((ax+12, ay+10), "⚡  AFFIXES MYTHIC+", font=_f(True,13), fill=(100,150,255))
    draw.line([(ax+10,ay+30),(ax+320,ay+30)], fill=(100,100,200,50), width=1)

    if affixes:
        for i, affix in enumerate(affixes[:4]):
            aname = affix.get("name","?")
            acol  = AFFIX_COLORS.get(aname, (180,180,200))
            fy    = ay + 38 + i * 18
            draw.text((ax+12, fy), f"•  {aname}", font=_f(True,13), fill=acol)
    else:
        draw.text((ax+12, ay+50), "Indisponible", font=_f(False,13), fill=(100,100,110))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 3 : ÉVÉNEMENTS EN JEU
    # ══════════════════════════════════════════════════════════════════════
    ey_start = sy + 125
    _rounded_rect(draw, [20, ey_start, W-20, ey_start+160], 8,
                  fill=(20,20,30,220), outline=(255,180,50,60), width=1)

    draw.text((32, ey_start+10), "📅  ÉVÉNEMENTS EN COURS", font=_f(True,13), fill=(255,180,50))
    draw.line([(22,ey_start+30),(W-22,ey_start+30)], fill=(255,180,50,50), width=1)

    if events:
        cols  = 2
        col_w = (W - 60) // cols
        for i, ev in enumerate(events[:8]):
            col_i = i % cols
            row_i = i // cols
            ex    = 32 + col_i * col_w
            ey_   = ey_start + 40 + row_i * 28
            draw.text((ex, ey_), f"✦  {ev}", font=_f(False,13), fill=(220,200,160))
    else:
        draw.text((32, ey_start+55),
                  "Aucun événement récupéré — l'API Blizzard\nne liste pas les événements en cours.",
                  font=_f(False,12), fill=(100,100,110))

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4 : INFOS RESET
    # ══════════════════════════════════════════════════════════════════════
    ry = ey_start + 175
    _rounded_rect(draw, [20, ry, W-20, ry+80], 8,
                  fill=(20,20,30,220), outline=(100,200,100,60), width=1)

    draw.text((32, ry+10), "🔄  RESET HEBDOMADAIRE", font=_f(True,13), fill=(100,200,100))
    draw.line([(22,ry+30),(W-22,ry+30)], fill=(100,200,100,50), width=1)

    infos_reset = [
        "✓  Raids : Mercredi 09h00 (EU)",
        "✓  Mythic+ : Mercredi 09h00 (EU)",
        "✓  Réputation hebdo remise à zéro",
        "✓  Coffres hebdomadaires disponibles",
    ]
    for i, info in enumerate(infos_reset):
        col_i = i % 2
        row_i = i // 2
        draw.text((32 + col_i*340, ry+38 + row_i*22),
                  info, font=_f(False,12), fill=(160,200,160))

    # ── Footer ─────────────────────────────────────────────────────────────
    draw.line([(20,H-28),(W-20,H-28)], fill=(cr,cg,cb,50), width=1)
    draw.text((W//2, H-18),
              "World of Warcraft  ·  Données Blizzard & Raider.io",
              font=_f(False,10), fill=(65,65,78), anchor="mt")

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "PNG", optimize=True)
    buf.seek(0)
    return buf
