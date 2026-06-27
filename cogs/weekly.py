"""
Commandes hebdomadaires WoW :
  /infosemaine  — image complète (token + affixes + events + reset)
  /token        — prix WoW Token en direct
  /affixes      — affixes M+ de la semaine
"""
import os
import logging
import datetime
import aiohttp
import discord
from discord.ext import commands

from bnet import BattleNetClient
from weekly_generator import generate_weekly_image

log = logging.getLogger("wow-bot.weekly")

RAIDERIO_URL = "https://raider.io/api/v1/mythic-plus/affixes"
REGION       = os.getenv("BLIZZARD_REGION", "eu")
LOCALE_MAP   = {"eu": "fr", "us": "en", "kr": "kr", "tw": "tw"}


async def _fetch_affixes() -> list[dict]:
    locale = LOCALE_MAP.get(REGION, "fr")
    url    = f"{RAIDERIO_URL}?region={REGION}&locale={locale}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("affix_details", [])
    except Exception as e:
        log.error(f"Affixes: {e}")
    return []


async def _fetch_token() -> tuple[int | None, str]:
    """Retourne (prix, tendance). Tendance = 'up'|'down'|'stable'."""
    try:
        client = BattleNetClient()
        token  = await client._pub("/data/wow/token/index", "dynamic")
        if token and "price" in token:
            price = token["price"] // 10000  # convertir en pièces d'or
            return price, "stable"
    except Exception as e:
        log.error(f"Token: {e}")
    return None, "stable"


def _reset_info() -> str:
    now    = datetime.datetime.now(tz=datetime.timezone.utc)
    # Reset EU = mercredi 09h00 UTC
    days   = (2 - now.weekday()) % 7
    if days == 0 and now.hour >= 9:
        days = 7
    reset  = now + datetime.timedelta(days=days)
    reset  = reset.replace(hour=9, minute=0, second=0, microsecond=0)
    delta  = reset - now
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m      = rem // 60
    return f"Prochain reset EU dans {h}h{m:02d}min  (mercredi 09h00 UTC)"


class Weekly(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /infosemaine ──────────────────────────────────────────────────────
    @discord.app_commands.command(
        name="infosemaine",
        description="📅 Affiche toutes les infos de la semaine WoW (token, affixes, reset…)"
    )
    async def infosemaine(self, interaction: discord.Interaction):
        await interaction.response.defer()

        token_price, token_trend = await _fetch_token()
        affixes                  = await _fetch_affixes()
        reset_str                = _reset_info()

        # Événements : l'API Blizzard ne les expose pas en temps réel —
        # on met un message clair à la place
        events = ["Consultez le calendrier in-game pour les événements actifs"]

        buf = await generate_weekly_image(
            token_price  = token_price,
            token_trend  = token_trend,
            affixes      = affixes,
            events       = events,
            reset_day    = reset_str,
        )
        file  = discord.File(buf, filename="semaine.png")
        embed = discord.Embed(
            title       = "⚔️  Infos de la semaine — World of Warcraft",
            description = reset_str,
            color       = 0xFFD700,
        )
        embed.set_image(url="attachment://semaine.png")
        embed.set_footer(text="Sources : Blizzard API · Raider.io  ·  Mise à jour à chaque commande")
        await interaction.followup.send(embed=embed, file=file)

    # ── /token ────────────────────────────────────────────────────────────
    @discord.app_commands.command(
        name="token",
        description="💰 Prix actuel du WoW Token en pièces d'or"
    )
    async def token(self, interaction: discord.Interaction):
        await interaction.response.defer()
        price, _ = await _fetch_token()

        embed = discord.Embed(color=0xFFD700)
        embed.set_author(name="💰  WoW Token — Prix actuel")

        if price:
            embed.title       = f"{price:,} pièces d'or".replace(",",".")
            embed.description = (
                "```\n"
                f"  Région       : {REGION.upper()}\n"
                f"  Prix actuel  : {price:,} po\n"
                "  Équivaut à   : 30 jours de jeu\n"
                "```"
            )
            embed.set_footer(text="Données en direct via l'API officielle Blizzard")
        else:
            embed.title       = "Prix indisponible"
            embed.description = "Impossible de récupérer le prix du token."
            embed.color       = 0xFF0000

        await interaction.followup.send(embed=embed)

    # ── /affixes ──────────────────────────────────────────────────────────
    @discord.app_commands.command(
        name="affixes",
        description="⚡ Affixes Mythic+ de la semaine"
    )
    async def affixes(self, interaction: discord.Interaction):
        await interaction.response.defer()
        affixes = await _fetch_affixes()

        AFFIX_COLORS = {
            "Fortifié":0x64B4FF,"Fortified":0x64B4FF,
            "Tyrannique":0xFF6464,"Tyrannical":0xFF6464,
            "Explosif":0xFF8C32,"Explosive":0xFF8C32,
        }

        embed = discord.Embed(
            title = f"⚡  Affixes Mythic+ — {REGION.upper()}",
            color = 0x6464FF,
        )

        if affixes:
            for affix in affixes:
                name = affix.get("name","?")
                desc = affix.get("description","Pas de description.")
                icon = affix.get("icon","")
                col  = AFFIX_COLORS.get(name, 0xAAAAAA)
                embed.add_field(
                    name  = f"◈  {name}",
                    value = f"*{desc[:150]}*",
                    inline= False,
                )
            embed.set_footer(text="Source : Raider.io  ·  Reset mercredi 09h00 EU")
        else:
            embed.description = "Impossible de récupérer les affixes. Réessaie dans quelques instants."
            embed.color       = 0xFF0000

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Weekly(bot))
