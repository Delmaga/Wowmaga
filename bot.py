import os
import asyncio
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv

import storage
from web_server import start_web_server

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("wow-bot")

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info(f"Connecté : {bot.user}")
    synced = await bot.tree.sync()
    log.info(f"{len(synced)} commande(s) synchronisée(s).")


async def main():
    await storage.init_db()
    await start_web_server()
    async with bot:
        await bot.load_extension("cogs.news")
        await bot.load_extension("cogs.account")
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN manquant.")
    asyncio.run(main())
