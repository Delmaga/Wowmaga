import asyncio
import logging
import discord
from discord.ext import commands

import storage
from bnet import BattleNetClient
from character_card import generate_character_card

log = logging.getLogger("wow-bot.account")

CLASS_COLORS = {
    "Guerrier":(198,155,58),"Warrior":(198,155,58),"Paladin":(244,140,186),
    "Chasseur":(170,211,114),"Hunter":(170,211,114),"Voleur":(255,244,104),"Rogue":(255,244,104),
    "Prêtre":(220,220,220),"Priest":(220,220,220),
    "Chevalier de la mort":(196,30,58),"Death Knight":(196,30,58),
    "Chaman":(0,112,221),"Shaman":(0,112,221),"Mage":(63,199,235),
    "Démoniste":(135,136,238),"Warlock":(135,136,238),"Moine":(0,255,152),"Monk":(0,255,152),
    "Druide":(255,124,10),"Druid":(255,124,10),
    "Chasseur de démons":(163,48,201),"Demon Hunter":(163,48,201),
    "Évocateur":(51,147,127),"Evoker":(51,147,127),
}
CLASS_ICONS = {
    "Guerrier":"⚔️","Warrior":"⚔️","Paladin":"🛡️","Chasseur":"🏹","Hunter":"🏹",
    "Voleur":"🗡️","Rogue":"🗡️","Prêtre":"✨","Priest":"✨",
    "Chevalier de la mort":"💀","Death Knight":"💀","Chaman":"⚡","Shaman":"⚡",
    "Mage":"🔥","Démoniste":"🟣","Warlock":"🟣","Moine":"👊","Monk":"👊",
    "Druide":"🌿","Druid":"🌿","Chasseur de démons":"🔮","Demon Hunter":"🔮",
    "Évocateur":"🐉","Evoker":"🐉",
}
FACTION = {"ALLIANCE":"Alliance 🔵","HORDE":"Horde 🔴"}

def _hex(rgb): return (rgb[0]<<16)|(rgb[1]<<8)|rgb[2]
def _render(media, key="main-raw"):
    for a in (media or {}).get("assets",[]):
        if a.get("key")==key: return a.get("value")
    # Fallback sur inset si main-raw absent
    for a in (media or {}).get("assets",[]):
        if a.get("key")=="inset": return a.get("value")
    return None


async def build_card(c: dict, client: BattleNetClient, discord_user, access_token: str):
    name       = c.get("name","?")
    level      = c.get("level",0)
    classe     = c.get("playable_class",{}).get("name","?")
    race       = c.get("playable_race",{}).get("name","?")
    realm      = c.get("realm",{}).get("name","?")
    realm_slug = c.get("realm",{}).get("slug","")
    faction_t  = c.get("faction",{}).get("type","")

    faction = FACTION.get(faction_t,"Neutre")
    rgb     = CLASS_COLORS.get(classe,(88,101,242))
    color   = _hex(rgb)
    icon    = CLASS_ICONS.get(classe,"🎮")

    try:    prof  = await client.get_character_profile(realm_slug, name)
    except: prof  = {}
    try:    equip = await client.get_character_equipment(realm_slug, name)
    except: equip = {}
    try:    media = await client.get_character_media(realm_slug, name)
    except: media = {}

    prof=prof or {}; equip=equip or {}
    guild   = prof.get("guild",{}).get("name")
    spec    = prof.get("active_spec",{}).get("name")
    e_ilvl  = prof.get("equipped_item_level",0)
    a_ilvl  = prof.get("average_item_level",0)
    achiev  = prof.get("achievement_points",0)
    render  = _render(media,"main-raw") or _render(media,"inset")

    items   = (equip or {}).get("equipped_items",[])

    # ← CORRECTION : l'ID est dans it["item"]["id"], pas it["id"]
    icon_urls = {}
    if items:
        async def _get_icon(it):
            iid = it.get("item",{}).get("id")
            if iid:
                url = await client.get_item_media(iid)
                return iid, url
            return None, None
        results   = await asyncio.gather(*[_get_icon(it) for it in items])
        icon_urls = {iid: url for iid, url in results if iid and url}

    # Générer la grande image unique
    buf = await generate_character_card(
        name=name, classe=classe, spec=spec or "", race=race,
        realm=realm, faction=faction, guild=guild,
        level=int(level), e_ilvl=e_ilvl, a_ilvl=a_ilvl, achiev=achiev,
        class_color=rgb, render_url=render, avatar_url=_render(media,"avatar"),
        items=items, icon_urls=icon_urls,
    )

    card_file  = discord.File(buf, filename="character.png")
    card_embed = discord.Embed(color=color)
    card_embed.set_author(
        name=f"{icon}  {name.upper()}  —  Fiche de {discord_user.display_name}",
        icon_url=discord_user.display_avatar.url,
    )
    card_embed.set_image(url="attachment://character.png")
    card_embed.set_footer(text="World of Warcraft  ·  API Blizzard officielle  ·  /deconnecter-wow pour délier")

    return card_embed, card_file


class CharacterSelect(discord.ui.Select):
    def __init__(self, characters, client, discord_user, access_token):
        self.characters   = characters
        self.client       = client
        self.discord_user = discord_user
        self.access_token = access_token
        options = [
            discord.SelectOption(
                label=f"{c.get('name')} — Niv. {c.get('level','?')}",
                description=f"{c.get('playable_class',{}).get('name','?')} · {c.get('realm',{}).get('name','?')}",
                value=str(i),
                emoji="🔵" if c.get("faction",{}).get("type")=="ALLIANCE" else "🔴",
            )
            for i,c in enumerate(characters[:25])
        ]
        super().__init__(placeholder="⚔️  Choisir un personnage…", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        c = self.characters[int(self.values[0])]
        embed, f = await build_card(c, self.client, self.discord_user, self.access_token)
        view = discord.ui.View(timeout=300)
        view.add_item(CharacterSelect(self.characters, self.client, self.discord_user, self.access_token))
        await interaction.edit_original_response(embeds=[embed], attachments=[f], view=view)


class Account(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="comptewow", description="✨ Affiche ta fiche de personnage WoW")
    async def comptewow(self, interaction: discord.Interaction):
        await interaction.response.defer()

        link = await storage.get_user_link(interaction.user.id)
        if not link:
            client = BattleNetClient()
            url    = client.get_authorize_url(storage.sign_state(interaction.user.id))
            view   = discord.ui.View()
            view.add_item(discord.ui.Button(label="🔗 Connecter mon compte Battle.net",
                                            url=url, style=discord.ButtonStyle.link))
            embed = discord.Embed(
                title="🔐 Connexion Battle.net requise",
                description=(
                    "```\n"
                    "Connecte ton compte Battle.net\n"
                    "pour afficher ta fiche.\n"
                    "──────────────────────────────\n"
                    "✅ Connexion officielle Blizzard\n"
                    "✅ Mot de passe jamais vu\n"
                    "──────────────────────────────\n"
                    "↳ Retape /comptewow après connexion\n"
                    "```"
                ), color=0x0078FF,
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

        client = BattleNetClient(region=link["region"])
        try:    data = await client.get_account_wow_profile(link["access_token"])
        except Exception as e:
            log.error(f"Profil {interaction.user.id}: {e}")
            await storage.delete_user_link(interaction.user.id)
            await interaction.followup.send(
                embed=discord.Embed(title="❌ Session expirée",
                    description="Retape `/comptewow` pour te reconnecter.", color=0xFF0000),
                ephemeral=True); return

        characters = []
        for acc in (data or {}).get("wow_accounts",[]):
            characters.extend(acc.get("characters",[]))
        characters.sort(key=lambda c: c.get("level",0), reverse=True)

        if not characters:
            await interaction.followup.send("Aucun personnage trouvé.", ephemeral=True); return

        embed, f = await build_card(characters[0], client, interaction.user, link["access_token"])
        view = discord.ui.View(timeout=300)
        if len(characters) > 1:
            view.add_item(CharacterSelect(characters, client, interaction.user, link["access_token"]))
        await interaction.followup.send(embed=embed, file=f, view=view)

    @discord.app_commands.command(name="deconnecter-wow", description="Délie ton compte Battle.net")
    async def deconnecter_wow(self, interaction: discord.Interaction):
        await storage.delete_user_link(interaction.user.id)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ Compte délié", color=0x57F287), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Account(bot))
