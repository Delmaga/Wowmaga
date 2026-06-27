"""
/infosemaine  /token  /affixes
+ auto-détection changement affixes chaque reset (mercredi 09h EU)
"""
import os, json, logging, datetime
import aiohttp, discord
from discord.ext import commands, tasks

from bnet import BattleNetClient
from weekly_generator import generate_weekly_image

log    = logging.getLogger("wow-bot.weekly")
REGION = os.getenv("BLIZZARD_REGION","eu")
LOCALE = {"eu":"fr","us":"en"}.get(REGION,"fr")
AFFIX_CACHE_FILE = "affixes_cache.json"


# ── Données Raider.io ──────────────────────────────────────────────────────
async def _fetch_affixes() -> list[dict]:
    url = f"https://raider.io/api/v1/mythic-plus/affixes?region={REGION}&locale={LOCALE}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status==200:
                    return (await r.json()).get("affix_details",[])
    except Exception as e: log.error(f"Affixes: {e}")
    return []

async def _fetch_token() -> tuple[int|None, str]:
    try:
        client = BattleNetClient()
        token  = await client._pub("/data/wow/token/index","dynamic")
        if token and "price" in token:
            return token["price"]//10000, "stable"
    except Exception as e: log.error(f"Token: {e}")
    return None, "stable"

def _reset_info() -> str:
    now   = datetime.datetime.now(tz=datetime.timezone.utc)
    days  = (2 - now.weekday()) % 7
    if days==0 and now.hour>=9: days=7
    reset = (now+datetime.timedelta(days=days)).replace(hour=9,minute=0,second=0,microsecond=0)
    delta = reset - now
    h,r   = divmod(int(delta.total_seconds()),3600)
    return f"Prochain reset EU dans {h}h{r//60:02d}min  (mercredi 09h00 UTC)"

def _load_cached_affixes() -> list:
    if os.path.exists(AFFIX_CACHE_FILE):
        try:
            with open(AFFIX_CACHE_FILE) as f: return json.load(f)
        except: pass
    return []

def _save_cached_affixes(affixes: list):
    with open(AFFIX_CACHE_FILE,"w") as f: json.dump(affixes,f)


# ── Couleurs affixes ───────────────────────────────────────────────────────
AFFIX_COLORS = {
    "Fortifié":(100,180,255),"Fortified":(100,180,255),
    "Tyrannique":(255,100,100),"Tyrannical":(255,100,100),
    "Explosif":(255,140,50),"Explosive":(255,140,50),
    "Sanguinaire":(200,50,50),"Sanguine":(200,50,50),
    "Bouillonnant":(255,200,50),"Bolstering":(255,200,50),
    "Grégaire":(180,255,100),"Rampant":(255,100,200),
    "Incorporel":(200,200,200),"Incorporeal":(200,200,200),
    "Tempête":(150,150,255),"Storming":(150,150,255),
}

AFFIX_EMOJI = {
    "Fortifié":"🏰","Fortified":"🏰",
    "Tyrannique":"👑","Tyrannical":"👑",
    "Explosif":"💥","Explosive":"💥",
    "Sanguinaire":"🩸","Sanguine":"🩸",
    "Bouillonnant":"⬆️","Bolstering":"⬆️",
    "Grégaire":"🐺","Rampant":"🕷️",
    "Incorporel":"👻","Incorporeal":"👻",
    "Tempête":"⛈️","Storming":"⛈️",
}


class Weekly(commands.Cog):
    def __init__(self, bot):
        self.bot            = bot
        self.cached_affixes = _load_cached_affixes()
        self.check_affixes.start()

    def cog_unload(self):
        self.check_affixes.cancel()

    # ── AUTO-DÉTECTION CHANGEMENT AFFIXES ─────────────────────────────────
    @tasks.loop(minutes=5)
    async def check_affixes(self):
        new_affixes = await _fetch_affixes()
        if not new_affixes: return

        old_names = [a.get("name") for a in self.cached_affixes]
        new_names = [a.get("name") for a in new_affixes]

        if old_names == new_names: return  # pas de changement

        log.info(f"Affixes changés : {old_names} → {new_names}")
        self.cached_affixes = new_affixes
        _save_cached_affixes(new_affixes)

        # Poster dans les salons news
        from storage import get_all_news_channels
        channel_ids = await get_all_news_channels()

        embed = self._make_affix_embed(new_affixes)
        embed.set_author(name="🔄  Les affixes Mythic+ ont changé !")

        for cid in channel_ids:
            ch = self.bot.get_channel(cid)
            if ch:
                try: await ch.send(content="⚡ **Nouveaux affixes M+ cette semaine !**", embed=embed)
                except: pass

    @check_affixes.before_loop
    async def before_affixes(self):
        await self.bot.wait_until_ready()
        if not self.cached_affixes:
            self.cached_affixes = await _fetch_affixes()
            _save_cached_affixes(self.cached_affixes)

    # ── BUILDER EMBED AFFIXES ──────────────────────────────────────────────
    def _make_affix_embed(self, affixes: list) -> discord.Embed:
        embed = discord.Embed(
            title="⚡  Affixes Mythic+ de la semaine",
            color=0x6464FF,
        )
        embed.add_field(
            name="Région",
            value=f"**{REGION.upper()}**  ·  Reset mercredi 09h00 EU",
            inline=False,
        )
        for affix in affixes:
            name = affix.get("name","?")
            desc = affix.get("description","Pas de description.")
            emoji= AFFIX_EMOJI.get(name,"◈")
            col  = AFFIX_COLORS.get(name,(180,180,200))
            embed.add_field(
                name=f"{emoji}  {name}",
                value=f"*{desc[:200]}*",
                inline=False,
            )
        embed.set_footer(text="Source : Raider.io  ·  Mis à jour automatiquement chaque semaine")
        return embed

    # ── /infosemaine ──────────────────────────────────────────────────────
    @discord.app_commands.command(name="infosemaine",
        description="📅 Toutes les infos de la semaine (token, affixes, reset)")
    async def infosemaine(self, interaction: discord.Interaction):
        await interaction.response.defer()
        token_price, token_trend = await _fetch_token()
        affixes                  = self.cached_affixes or await _fetch_affixes()
        reset_str                = _reset_info()

        buf = await generate_weekly_image(
            token_price=token_price, token_trend=token_trend,
            affixes=affixes, events=[], reset_day=reset_str,
        )
        file  = discord.File(buf, filename="semaine.png")
        embed = discord.Embed(
            title="📅  Infos de la semaine — World of Warcraft",
            description=reset_str, color=0xFFD700,
        )
        embed.set_image(url="attachment://semaine.png")
        embed.set_footer(text="Sources : Blizzard API · Raider.io")
        await interaction.followup.send(embed=embed, file=file)

    # ── /token ────────────────────────────────────────────────────────────
    @discord.app_commands.command(name="token",
        description="💰 Prix actuel du WoW Token")
    async def token(self, interaction: discord.Interaction):
        await interaction.response.defer()
        price, _ = await _fetch_token()

        embed = discord.Embed(color=0xFFD700)
        embed.set_author(name="💰  WoW Token — Prix en temps réel")

        if price:
            # Barre visuelle (700k max)
            pct    = min(int((price/700000)*20),20)
            bar    = "█"*pct+"░"*(20-pct)
            budget = "🟢 Peu cher" if price<150000 else "🟡 Moyen" if price<300000 else "🔴 Cher"
            embed.title = f"**{price:,} po**".replace(",",".")
            embed.description = (
                f"```\n"
                f"  Prix actuel   {price:,} pièces d'or\n"
                f"  [{bar}]\n"
                f"  Budget        {budget.split()[1]}\n"
                f"  Région        {REGION.upper()}\n"
                f"  Équivaut à    30 jours de jeu ou\n"
                f"                13 € en crédit Battle.net\n"
                f"```"
            )
            embed.add_field(
                name="ℹ️  C'est quoi le WoW Token ?",
                value=(
                    "Le WoW Token s'achète en argent réel (~13€) et se revend en pièces d'or "
                    "à d'autres joueurs. Il peut aussi être échangé contre du crédit Battle.net."
                ),
                inline=False,
            )
            embed.set_footer(text="Source : API officielle Blizzard  ·  Prix mis à jour en temps réel")
        else:
            embed.title       = "Prix indisponible"
            embed.description = "Impossible de récupérer le prix du WoW Token."
            embed.color       = 0xFF0000

        await interaction.followup.send(embed=embed)

    # ── /affixes ──────────────────────────────────────────────────────────
    @discord.app_commands.command(name="affixes",
        description="⚡ Affixes Mythic+ de la semaine avec explications")
    async def affixes(self, interaction: discord.Interaction):
        await interaction.response.defer()
        affixes = self.cached_affixes or await _fetch_affixes()
        if not affixes:
            await interaction.followup.send(
                embed=discord.Embed(title="❌ Indisponible",
                    description="Impossible de récupérer les affixes.", color=0xFF0000))
            return
        embed = self._make_affix_embed(affixes)
        embed.description = (
            "Les affixes sont des **modificateurs hebdomadaires** qui rendent les "
            "donjons Mythic+ plus difficiles. Ils changent chaque **mercredi à 09h00 EU**."
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Weekly(bot))
