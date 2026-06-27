import os, json, logging, re, asyncio
import aiohttp, feedparser, discord
from discord.ext import commands, tasks
import storage

log = logging.getLogger("wow-bot.news")

NEWS_FEEDS = [
    {"url":"https://worldofwarcraft.blizzard.com/en-us/news/rss", "source":"Blizzard"},
    {"url":"https://worldofwarcraft.blizzard.com/fr-fr/news/rss",  "source":"Blizzard FR"},
    {"url":"https://www.wowhead.com/news/rss",                     "source":"Wowhead"},
    {"url":"https://judgehype.com/rss/",                           "source":"Judgehype"},
    {"url":"https://www.mmo-champion.com/external.php?do=rss&type=newcontent&sectionid=1&days=0&count=20","source":"MMO-Champion"},
]
HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; WoWBot/2.0)"}

SHOP_KEYWORDS = [
    "expédition","expedition","comptoir","marchand","trading post",
    "tender","rotation","catalogue","sceaux","monture exotique",
]

IMPORTANT_KEYWORDS = [
    "patch","mise à jour","extension","update","hotfix","maintenance",
    "saison","season","bug","problème","issue","downtime","tww","war within",
]

SOURCE_EMOJI = {
    "Blizzard":"🔵","Blizzard FR":"🇫🇷","Wowhead":"⚔️",
    "Judgehype":"🏆","MMO-Champion":"🛡️",
}
SOURCE_COLOR = {
    "Blizzard":0x0078FF,"Blizzard FR":0x0099CC,"Wowhead":0xFF7C0A,
    "Judgehype":0xFFD700,"MMO-Champion":0x8B0000,
}

INTERVAL  = int(os.getenv("NEWS_CHECK_INTERVAL_MINUTES","2"))
SEEN_FILE = "seen_news.json"
# News importantes à ne JAMAIS manquer (re-postées même si déjà vues)
IMPORTANT_SEEN_FILE = "seen_important.json"


def _clean(text: str, limit: int = 400) -> str:
    text = re.sub(r"<[^<]+?>","",text or "").strip()
    text = re.sub(r"\s+"," ",text)
    return text[:limit]+("…" if len(text)>limit else "")

def _is_shop(title, summary):
    txt = (title+" "+summary).lower()
    return any(k in txt for k in SHOP_KEYWORDS)

def _is_important(title, summary):
    txt = (title+" "+summary).lower()
    return any(k in txt for k in IMPORTANT_KEYWORDS)

def _load(path) -> set:
    if os.path.exists(path):
        try:
            with open(path) as f: return set(json.load(f))
        except: pass
    return set()

def _save(path, seen: set):
    with open(path,"w") as f:
        json.dump(list(seen)[-500:], f)


async def _fetch_all() -> list:
    async def _one(session, feed):
        try:
            async with session.get(feed["url"],timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status!=200: return []
                text = await r.text()
            parsed = feedparser.parse(text)
            for e in parsed.entries: e["_source"]=feed["source"]
            return parsed.entries
        except Exception as ex:
            log.warning(f"Flux {feed['source']}: {ex}")
            return []
    async with aiohttp.ClientSession(headers=HEADERS) as s:
        results = await asyncio.gather(*[_one(s,f) for f in NEWS_FEEDS])
    out = []
    for r in results: out.extend(r)
    return out


class News(commands.Cog):
    def __init__(self, bot):
        self.bot      = bot
        self.seen_ids = _load(SEEN_FILE)
        self.check_news.start()

    def cog_unload(self):
        self.check_news.cancel()

    def _make_embed(self, entry, ping_shop=False) -> discord.Embed:
        source  = entry.get("_source","WoW")
        title   = entry.get("title","Actu WoW")
        summary = entry.get("summary","")
        color   = SOURCE_COLOR.get(source,0xFFD700)

        # News importantes = couleur rouge vif
        if _is_important(title, summary):
            color = 0xFF3333

        embed = discord.Embed(
            title=title[:256],
            url=entry.get("link"),
            description=_clean(summary),
            color=color,
        )
        embed.set_author(name=f"{SOURCE_EMOJI.get(source,'📰')}  {source}  —  World of Warcraft")

        # Tag visuel
        tags = []
        if _is_important(title, summary): tags.append("🔴 IMPORTANT")
        if _is_shop(title, summary):       tags.append("🛒 COMPTOIR")
        if tags:
            embed.add_field(name="Tags", value="  ·  ".join(tags), inline=False)

        for enc in entry.get("enclosures",[]):
            if enc.get("type","").startswith("image"):
                embed.set_thumbnail(url=enc["href"]); break

        embed.set_footer(text=f"📰 {source}  ·  Vérification toutes les {INTERVAL} min")
        return embed

    @tasks.loop(minutes=INTERVAL)
    async def check_news(self):
        channel_ids = await storage.get_all_news_channels()
        shop_ids    = await storage.get_all_shop_channels()
        if not channel_ids and not shop_ids: return

        all_entries = await _fetch_all()
        new_entries = []
        for e in all_entries:
            eid = e.get("id") or e.get("link")
            if eid and eid not in self.seen_ids:
                new_entries.append(e)
                self.seen_ids.add(eid)

        if not new_entries: return

        for entry in reversed(new_entries):
            title   = entry.get("title","")
            summary = entry.get("summary","")
            embed   = self._make_embed(entry)

            # Poster dans le salon news
            for cid in channel_ids:
                ch = self.bot.get_channel(cid)
                if not ch: continue
                try:
                    # Ping @everyone pour les news importantes
                    content = "@everyone 🔴 **Annonce importante !**" if _is_important(title,summary) else None
                    await ch.send(content=content, embed=embed)
                except discord.HTTPException as ex:
                    log.error(f"News {cid}: {ex}")

            # Poster dans le salon boutique si c'est une rotation
            if _is_shop(title, summary):
                shop_embed = discord.Embed(
                    title=f"🛒  {title[:200]}",
                    url=entry.get("link"),
                    description=_clean(summary, 600),
                    color=0xFF9900,
                )
                shop_embed.set_author(name="🎪  Comptoir de l'Expédition — Nouvelle rotation !")
                shop_embed.set_footer(text="Clique sur le titre pour voir tous les objets disponibles")
                for scid in shop_ids:
                    sch = self.bot.get_channel(scid)
                    if not sch: continue
                    try:
                        await sch.send(
                            content="@everyone 🛒 **Nouvelle rotation du Comptoir !**",
                            embed=shop_embed,
                        )
                    except discord.HTTPException as ex:
                        log.error(f"Boutique {scid}: {ex}")

        _save(SEEN_FILE, self.seen_ids)

    @check_news.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        if not self.seen_ids:
            all_entries = await _fetch_all()
            for e in all_entries:
                eid = e.get("id") or e.get("link")
                if eid: self.seen_ids.add(eid)
            _save(SEEN_FILE, self.seen_ids)
            log.info(f"News: {len(self.seen_ids)} articles marqués comme vus au démarrage.")

    @check_news.error
    async def check_news_error(self, error):
        log.error(f"Erreur task news: {error}")
        self.check_news.restart()

    # ── COMMANDES ─────────────────────────────────────────────────────────
    @discord.app_commands.command(name="newswow",
        description="⚙️ Configure le salon des actualités WoW (admin)")
    @discord.app_commands.describe(salon="Salon pour les actualités")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def newswow(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await storage.set_news_channel(interaction.guild_id, salon.id)
        embed = discord.Embed(title="✅ Salon actualités configuré", color=0x57F287,
            description=(
                f"Actualités WoW → {salon.mention}\n\n"
                "**Sources :**\n"
                +"\n".join(f"{SOURCE_EMOJI.get(f['source'],'📰')} {f['source']}" for f in NEWS_FEEDS)
                +f"\n\n🔴 @everyone sur les annonces importantes\n"
                f"🔄 Vérification toutes les **{INTERVAL} min**"
            ))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @newswow.error
    async def newswow_error(self, i, e):
        if isinstance(e, discord.app_commands.MissingPermissions):
            await i.response.send_message("❌ Permission **Gérer le serveur** requise.", ephemeral=True)

    @discord.app_commands.command(name="boutiqueexpedition",
        description="⚙️ Configure le salon du Comptoir de l'Expédition (admin)")
    @discord.app_commands.describe(salon="Salon dédié à la boutique")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def boutiqueexpedition(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await storage.set_shop_channel(interaction.guild_id, salon.id)
        embed = discord.Embed(title="✅ Salon Comptoir configuré", color=0xFF9900,
            description=(
                f"Rotations du Comptoir → {salon.mention} avec **@everyone**\n\n"
                "Détecte automatiquement : rotations, nouvelles montures, cosmétiques, catalogue."
            ))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @boutiqueexpedition.error
    async def boutique_error(self, i, e):
        if isinstance(e, discord.app_commands.MissingPermissions):
            await i.response.send_message("❌ Permission **Gérer le serveur** requise.", ephemeral=True)

    @discord.app_commands.command(name="dernieresactus",
        description="📰 Affiche les 8 dernières actualités WoW de toutes les sources")
    async def dernieresactus(self, interaction: discord.Interaction):
        await interaction.response.defer()
        all_entries = await _fetch_all()
        if not all_entries:
            await interaction.followup.send("❌ Impossible de récupérer les actus.", ephemeral=True)
            return
        embeds = []
        seen_titles = set()
        for entry in all_entries:
            title = entry.get("title","?")
            if title in seen_titles: continue
            seen_titles.add(title)
            embeds.append(self._make_embed(entry))
            if len(embeds) >= 8: break
        await interaction.followup.send(embeds=embeds)


async def setup(bot):
    await bot.add_cog(News(bot))
