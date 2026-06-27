import os
import json
import logging
import re
import asyncio
import aiohttp
import feedparser
import discord
from discord.ext import commands, tasks
import storage

log = logging.getLogger("wow-bot.news")

# Flux RSS — Blizzard officiel (EN + FR) + Wowhead + Judgehype + MMO-Champion
NEWS_FEEDS = [
    {"url": "https://worldofwarcraft.blizzard.com/en-us/news/rss",  "source": "Blizzard"},
    {"url": "https://worldofwarcraft.blizzard.com/fr-fr/news/rss",  "source": "Blizzard FR"},
    {"url": "https://www.wowhead.com/news/rss",                     "source": "Wowhead"},
    {"url": "https://judgehype.com/rss/",                           "source": "Judgehype"},
    {"url": "https://www.mmo-champion.com/external.php?do=rss&type=newcontent&sectionid=1&days=0&count=10", "source": "MMO-Champion"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; WoWBot/2.0; +https://discord.com)"
}

INTERVAL  = int(os.getenv("NEWS_CHECK_INTERVAL_MINUTES", "2"))
SEEN_FILE = "seen_news.json"

# Emojis par source
SOURCE_EMOJI = {
    "Blizzard":    "🔵",
    "Blizzard FR": "🇫🇷",
    "Wowhead":     "⚔️",
    "Judgehype":   "🏆",
    "MMO-Champion":"🛡️",
}
SOURCE_COLOR = {
    "Blizzard":    0x0078FF,
    "Blizzard FR": 0x0099CC,
    "Wowhead":     0xFF7C0A,
    "Judgehype":   0xFFD700,
    "MMO-Champion":0x8B0000,
}


# Mots-clés pour détecter les articles de rotation marchands
SHOP_KEYWORDS = [
    "expédition", "expedition", "comptoir", "marchand",
    "trading post", "tender", "rotation", "catalogue",
    "argent céleste", "sceaux", "monture", "mount",
    "cosmétique", "transmog",
]

def _is_shop_article(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in SHOP_KEYWORDS)
    text = re.sub(r"<[^<]+?>", "", text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit] + ("…" if len(text) > limit else "")


def _load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE) as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-500:], f)


async def _fetch_feed(session: aiohttp.ClientSession, feed_info: dict) -> list:
    """Récupère un flux RSS et retourne les entrées avec la source."""
    url    = feed_info["url"]
    source = feed_info["source"]
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return []
            text = await r.text()
        parsed = feedparser.parse(text)
        entries = []
        for e in parsed.entries:
            e["_source"] = source
            entries.append(e)
        return entries
    except Exception as ex:
        log.warning(f"Flux {source} indisponible: {ex}")
        return []


class News(commands.Cog):
    def __init__(self, bot):
        self.bot      = bot
        self.seen_ids = _load_seen()
        self.check_news.start()

    def cog_unload(self):
        self.check_news.cancel()

    async def _fetch_all(self) -> list:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            results = await asyncio.gather(*[
                _fetch_feed(session, feed) for feed in NEWS_FEEDS
            ])
        all_entries = []
        for entries in results:
            all_entries.extend(entries)
        return all_entries

    @tasks.loop(minutes=INTERVAL)
    async def check_news(self):
        channel_ids = await storage.get_all_news_channels()
        if not channel_ids:
            return

        all_entries = await self._fetch_all()
        new_entries = []
        for entry in all_entries:
            eid = entry.get("id") or entry.get("link")
            if eid and eid not in self.seen_ids:
                new_entries.append(entry)
                self.seen_ids.add(eid)

        if not new_entries:
            return

        for entry in reversed(new_entries):
            source = entry.get("_source", "WoW")
            emoji  = SOURCE_EMOJI.get(source, "📰")
            color  = SOURCE_COLOR.get(source, 0xFFD700)

            embed = discord.Embed(
                title       = entry.get("title", "Nouvelle actu WoW"),
                url         = entry.get("link"),
                description = _clean(entry.get("summary", "")),
                color       = color,
            )
            embed.set_author(name=f"{emoji}  {source}  —  World of Warcraft")

            # Image de prévisualisation si disponible
            for enclosure in entry.get("enclosures", []):
                if enclosure.get("type", "").startswith("image"):
                    embed.set_thumbnail(url=enclosure["href"])
                    break

            embed.set_footer(text="📰 Actualités WoW  ·  Nouvelles toutes les quelques minutes")

            for cid in channel_ids:
                ch = self.bot.get_channel(cid)
                if ch:
                    try:    await ch.send(embed=embed)
                    except discord.HTTPException as e:
                        log.error(f"Envoi news {cid}: {e}")

            # ── Salon boutique expédition ──────────────────────────
            title   = entry.get("title","")
            summary = entry.get("summary","")
            if _is_shop_article(title, summary):
                shop_ids = await storage.get_all_shop_channels()
                shop_embed = discord.Embed(
                    title       = f"🛒  {title}",
                    url         = entry.get("link"),
                    description = _clean(summary, 500),
                    color       = 0xFF9900,
                )
                shop_embed.set_author(name="🎪  Comptoir de l'Expédition — Nouvelle rotation !")
                shop_embed.set_footer(text="Clique sur le titre pour voir tous les objets disponibles")
                for scid in shop_ids:
                    sch = self.bot.get_channel(scid)
                    if sch:
                        try:
                            await sch.send(content="@everyone 🛒 **Nouvelle rotation du Comptoir !**", embed=shop_embed)
                        except discord.HTTPException as e:
                            log.error(f"Envoi boutique {scid}: {e}")

        _save_seen(self.seen_ids)

    @check_news.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        # Premier démarrage : marquer tout comme vu pour ne pas spammer
        if not self.seen_ids:
            all_entries = await self._fetch_all()
            for e in all_entries:
                eid = e.get("id") or e.get("link")
                if eid:
                    self.seen_ids.add(eid)
            _save_seen(self.seen_ids)
            log.info(f"News: {len(self.seen_ids)} articles marqués comme vus au démarrage.")

    @check_news.error
    async def check_news_error(self, error):
        log.error(f"Erreur task news: {error}")

    # ── Commandes ───────────────────────────────────────────────────────
    @discord.app_commands.command(
        name="boutiqueexpedition",
        description="⚙️ Configure le salon des rotations du Comptoir de l'Expédition (admin)"
    )
    @discord.app_commands.describe(salon="Salon dédié aux rotations de la boutique")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def boutiqueexpedition(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await storage.set_shop_channel(interaction.guild_id, salon.id)
        embed = discord.Embed(
            title="✅  Salon Comptoir de l'Expédition configuré",
            description=(
                f"Les rotations de marchands seront postées dans {salon.mention} avec un **@everyone**.\n\n"
                f"**Détection automatique des articles :**\n"
                f"🛒 Nouvelles rotations du Comptoir\n"
                f"🐴 Nouvelles montures disponibles\n"
                f"👗 Nouveaux cosmétiques/transmogs\n"
                f"💰 Changements de catalogue\n\n"
                f"*Source : Wowhead & Blizzard officiel*"
            ),
            color=0xFF9900,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @boutiqueexpedition.error
    async def boutique_error(self, interaction, error):
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Permission **Gérer le serveur** requise.", ephemeral=True)

    @discord.app_commands.command(
        name="newswow",
        description="⚙️ Configure le salon des actualités WoW (admin requis)"
    )
    @discord.app_commands.describe(salon="Salon où seront postées les actualités")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def newswow(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await storage.set_news_channel(interaction.guild_id, salon.id)
        embed = discord.Embed(
            title="✅  Salon des actualités configuré",
            description=(
                f"Les actualités WoW seront postées dans {salon.mention}.\n\n"
                f"**Sources surveillées :**\n"
                + "\n".join(f"{SOURCE_EMOJI.get(f['source'],'📰')}  {f['source']}" for f in NEWS_FEEDS)
                + f"\n\n🔄 Vérification toutes les **{INTERVAL} minutes**."
            ),
            color=0x57F287,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @newswow.error
    async def newswow_error(self, interaction, error):
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Permission **Gérer le serveur** requise.", ephemeral=True)

    @discord.app_commands.command(
        name="dernieresactus",
        description="📰 Affiche les 5 dernières actualités WoW"
    )
    async def dernieresactus(self, interaction: discord.Interaction):
        await interaction.response.defer()
        all_entries = await self._fetch_all()
        if not all_entries:
            await interaction.followup.send("❌ Impossible de récupérer les actus.", ephemeral=True)
            return

        embeds = []
        seen   = set()
        for entry in all_entries[:20]:
            title = entry.get("title","?")
            if title in seen:
                continue
            seen.add(title)
            source = entry.get("_source","WoW")
            embed  = discord.Embed(
                title=title,
                url=entry.get("link"),
                description=_clean(entry.get("summary","")),
                color=SOURCE_COLOR.get(source, 0xFFD700),
            )
            embed.set_author(name=f"{SOURCE_EMOJI.get(source,'📰')}  {source}")
            embeds.append(embed)
            if len(embeds) >= 5:
                break

        await interaction.followup.send(embeds=embeds)


async def setup(bot):
    await bot.add_cog(News(bot))
