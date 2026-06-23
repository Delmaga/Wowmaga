import os
import json
import logging
import re
import feedparser
import discord
from discord.ext import commands, tasks

import storage

log = logging.getLogger("wow-bot.news")

NEWS_FEEDS = [
    "https://www.wowhead.com/news/rss",
    "https://worldofwarcraft.blizzard.com/en-us/news/rss",
]
INTERVAL = int(os.getenv("NEWS_CHECK_INTERVAL_MINUTES", "30"))
SEEN_FILE = "seen_news.json"


def _load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def _save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-300:], f)


def _clean(text: str, limit: int = 300) -> str:
    text = re.sub("<[^<]+?>", "", text or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


class News(commands.Cog):
    def __init__(self, bot):
        self.bot      = bot
        self.seen_ids = _load_seen()
        self.check_news.start()

    def cog_unload(self):
        self.check_news.cancel()

    @tasks.loop(minutes=INTERVAL)
    async def check_news(self):
        channel_ids = await storage.get_all_news_channels()
        if not channel_ids:
            return
        new_entries = []
        for url in NEWS_FEEDS:
            try:
                for entry in feedparser.parse(url).entries:
                    eid = entry.get("id", entry.get("link"))
                    if eid and eid not in self.seen_ids:
                        new_entries.append(entry)
                        self.seen_ids.add(eid)
            except Exception as e:
                log.error(f"Flux {url}: {e}")

        for entry in reversed(new_entries):
            embed = discord.Embed(
                title=entry.get("title", "Actu WoW"),
                url=entry.get("link"),
                description=_clean(entry.get("summary", "")),
                color=discord.Color.gold(),
            )
            embed.set_footer(text="World of Warcraft — Actualités")
            for cid in channel_ids:
                ch = self.bot.get_channel(cid)
                if ch:
                    try:    await ch.send(embed=embed)
                    except: pass

        if new_entries:
            _save_seen(self.seen_ids)

    @check_news.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        if not self.seen_ids:
            for url in NEWS_FEEDS:
                try:
                    for entry in feedparser.parse(url).entries:
                        self.seen_ids.add(entry.get("id", entry.get("link")))
                except Exception:
                    pass
            _save_seen(self.seen_ids)

    @discord.app_commands.command(name="newswow", description="Configure le salon des actualités WoW (admin)")
    @discord.app_commands.describe(salon="Salon où poster les actus")
    @discord.app_commands.checks.has_permissions(manage_guild=True)
    async def newswow(self, interaction: discord.Interaction, salon: discord.TextChannel):
        await storage.set_news_channel(interaction.guild_id, salon.id)
        await interaction.response.send_message(
            f"✅ Actualités WoW → {salon.mention}", ephemeral=True
        )

    @newswow.error
    async def newswow_error(self, interaction, error):
        if isinstance(error, discord.app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Permission **Gérer le serveur** requise.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(News(bot))
