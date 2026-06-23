import logging
import discord
from discord.ext import commands

import storage
from bnet import BattleNetClient
from card_generator import generate_equipment_image

log = logging.getLogger("wow-bot.account")

CLASS_COLORS = {
    "Guerrier": (198,155,58),  "Warrior":       (198,155,58),
    "Paladin":  (244,140,186),
    "Chasseur": (170,211,114), "Hunter":        (170,211,114),
    "Voleur":   (255,244,104), "Rogue":         (255,244,104),
    "Prêtre":   (220,220,220), "Priest":        (220,220,220),
    "Chevalier de la mort": (196,30,58), "Death Knight": (196,30,58),
    "Chaman":   (0,112,221),   "Shaman":        (0,112,221),
    "Mage":     (63,199,235),
    "Démoniste":(135,136,238), "Warlock":       (135,136,238),
    "Moine":    (0,255,152),   "Monk":          (0,255,152),
    "Druide":   (255,124,10),  "Druid":         (255,124,10),
    "Chasseur de démons": (163,48,201), "Demon Hunter": (163,48,201),
    "Évocateur":(51,147,127),  "Evoker":        (51,147,127),
}

CLASS_ICONS = {
    "Guerrier":"⚔️","Warrior":"⚔️","Paladin":"🛡️",
    "Chasseur":"🏹","Hunter":"🏹","Voleur":"🗡️","Rogue":"🗡️",
    "Prêtre":"✨","Priest":"✨","Chevalier de la mort":"💀","Death Knight":"💀",
    "Chaman":"⚡","Shaman":"⚡","Mage":"🔥","Démoniste":"🟣","Warlock":"🟣",
    "Moine":"👊","Monk":"👊","Druide":"🌿","Druid":"🌿",
    "Chasseur de démons":"🔮","Demon Hunter":"🔮","Évocateur":"🐉","Evoker":"🐉",
}

FACTION = {
    "ALLIANCE": ("Alliance","🔵"),
    "HORDE":    ("Horde",   "🔴"),
}


def _rgb_to_hex(rgb: tuple) -> int:
    return (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]


def _render(media: dict, key: str = "inset") -> str | None:
    for a in (media or {}).get("assets", []):
        if a.get("key") == key:
            return a.get("value")
    return None


def _bar(val: int, maxi: int, n: int = 18) -> str:
    f = max(0, min(round((val / maxi) * n), n))
    return "▰" * f + "▱" * (n - f)


async def build_embeds(c: dict, client: BattleNetClient):
    name       = c.get("name", "?")
    level      = c.get("level", 0)
    classe     = c.get("playable_class", {}).get("name", "?")
    race       = c.get("playable_race",  {}).get("name", "?")
    realm      = c.get("realm", {}).get("name", "?")
    realm_slug = c.get("realm", {}).get("slug", "")
    faction_t  = c.get("faction", {}).get("type", "")

    fname, ficon = FACTION.get(faction_t, ("Neutre", "⚪"))
    rgb          = CLASS_COLORS.get(classe, (88,101,242))
    color        = _rgb_to_hex(rgb)
    icon         = CLASS_ICONS.get(classe, "🎮")

    try:    prof  = await client.get_character_profile(realm_slug, name)
    except: prof  = {}
    try:    equip = await client.get_character_equipment(realm_slug, name)
    except: equip = {}
    try:    media = await client.get_character_media(realm_slug, name)
    except: media = {}

    prof  = prof  or {}
    equip = equip or {}

    guild   = prof.get("guild", {}).get("name")
    spec    = prof.get("active_spec", {}).get("name")
    e_ilvl  = prof.get("equipped_item_level", 0)
    a_ilvl  = prof.get("average_item_level",  0)
    achiev  = prof.get("achievement_points",   0)
    render  = _render(media, "inset") or _render(media, "main-raw")
    avatar  = _render(media, "avatar")

    embeds = []

    # ── CARTE 1 : HERO ────────────────────────────────────────────────────────
    hero = discord.Embed(color=color)
    hero.set_author(
        name="⚔️  World of Warcraft — Fiche de Personnage",
        icon_url="https://bnetcmsus-a.akamaihd.net/cms/gallery/D2TTHKAPW9BH1542314183036.png",
    )
    hero.title = f"{icon}  {name.upper()}"
    hero.description = (
        f"```ansi\n"
        f"\u001b[2;34m{'═'*36}\u001b[0m\n"
        f"  \u001b[1;37m{(spec + ' ' if spec else '') + classe:<28}\u001b[0m\n"
        f"  {'Race':<10}  {race}\n"
        f"  {'Faction':<10}  {ficon} {fname}\n"
        f"  {'Royaume':<10}  {realm}\n"
        + (f"  {'Guilde':<10}  <{guild}>\n" if guild else "")
        + f"\u001b[2;34m{'═'*36}\u001b[0m\n"
        f"```"
    )
    if render: hero.set_image(url=render)
    if avatar: hero.set_thumbnail(url=avatar)
    embeds.append(hero)

    # ── CARTE 2 : STATS ───────────────────────────────────────────────────────
    stats = discord.Embed(color=color)
    stats.title = f"📊  Stats — {name}"
    lv_pct   = round((int(level)/80)*100)
    ilvl_pct = round((e_ilvl/700)*100) if e_ilvl else 0
    stats.description = (
        f"```\n"
        f"╔{'═'*34}╗\n"
        f"║  NIVEAU        {str(level) + ' / 80':<18}║\n"
        f"║  {_bar(int(level),80)}  {lv_pct:>3}%║\n"
        f"╠{'═'*34}╣\n"
        f"║  ITEM LEVEL    {str(e_ilvl) + ' équipé':<18}║\n"
        f"║  {_bar(e_ilvl,700)}  {ilvl_pct:>3}%║\n"
        f"║  Ilvl moyen    {str(a_ilvl):<18}║\n"
        f"╠{'═'*34}╣\n"
        f"║  HAUTS FAITS   {f'{achiev:,}':<18}║\n"
        f"╚{'═'*34}╝\n"
        f"```"
    )
    embeds.append(stats)

    # ── CARTE 3 : IMAGE ÉQUIPEMENT ────────────────────────────────────────────
    equip_file = None
    if equip.get("equipped_items"):
        try:
            buf = await generate_equipment_image(
                char_name=name, classe=classe, realm=realm,
                equipped_ilvl=e_ilvl, items=equip["equipped_items"],
                class_color=rgb,
            )
            equip_file = discord.File(buf, filename="equipment.png")
            e_embed    = discord.Embed(color=color)
            e_embed.title = f"🎒  Équipement — {name}"
            e_embed.set_image(url="attachment://equipment.png")
            e_embed.set_footer(text="Données via l'API officielle Blizzard  •  /deconnecter-wow pour délier")
            embeds.append(e_embed)
        except Exception as e:
            log.error(f"Génération image: {e}")

    return embeds, equip_file


# ── MENU SÉLECTION ────────────────────────────────────────────────────────────
class CharacterSelect(discord.ui.Select):
    def __init__(self, characters: list, client: BattleNetClient):
        self.characters = characters
        self.client     = client
        options = [
            discord.SelectOption(
                label=f"{c.get('name')} — Niv. {c.get('level','?')}",
                description=f"{c.get('playable_class',{}).get('name','?')} · {c.get('realm',{}).get('name','?')}",
                value=str(i),
                emoji="🔵" if c.get("faction",{}).get("type")=="ALLIANCE" else "🔴",
            )
            for i, c in enumerate(characters[:25])
        ]
        super().__init__(placeholder="⚔️  Choisir un personnage…", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        c = self.characters[int(self.values[0])]
        embeds, f = await build_embeds(c, self.client)
        view = discord.ui.View(timeout=300)
        view.add_item(CharacterSelect(self.characters, self.client))
        files = [f] if f else []
        await interaction.edit_original_response(embeds=embeds[:10], attachments=files, view=view)


# ── COG ───────────────────────────────────────────────────────────────────────
class Account(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="comptewow", description="✨ Affiche ta fiche de personnage WoW")
    async def comptewow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        link = await storage.get_user_link(interaction.user.id)
        if not link:
            client = BattleNetClient()
            url    = client.get_authorize_url(storage.sign_state(interaction.user.id))
            view   = discord.ui.View()
            view.add_item(discord.ui.Button(label="🔗 Connecter mon compte Battle.net",
                                            url=url, style=discord.ButtonStyle.link))
            embed = discord.Embed(
                title="🔐  Connexion requise",
                description=(
                    "```\n"
                    "Connecte ton compte Battle.net\n"
                    "pour voir ta fiche de personnage.\n"
                    "──────────────────────────────\n"
                    "✅ Connexion officielle Blizzard\n"
                    "✅ Mot de passe jamais vu par le bot\n"
                    "✅ Visible uniquement par toi\n"
                    "──────────────────────────────\n"
                    "↳ Retape /comptewow après connexion\n"
                    "```"
                ),
                color=0x0078FF,
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

        client = BattleNetClient(region=link["region"])
        try:
            data = await client.get_account_wow_profile(link["access_token"])
        except Exception as e:
            log.error(f"Profil {interaction.user.id}: {e}")
            await storage.delete_user_link(interaction.user.id)
            await interaction.followup.send(
                embed=discord.Embed(title="❌ Session expirée",
                    description="Retape `/comptewow` pour te reconnecter.", color=0xFF0000),
                ephemeral=True)
            return

        characters = []
        for acc in (data or {}).get("wow_accounts", []):
            characters.extend(acc.get("characters", []))
        characters.sort(key=lambda c: c.get("level", 0), reverse=True)

        if not characters:
            await interaction.followup.send("Aucun personnage trouvé.", ephemeral=True)
            return

        embeds, f = await build_embeds(characters[0], client)
        view = discord.ui.View(timeout=300)
        if len(characters) > 1:
            view.add_item(CharacterSelect(characters, client))
        files = [f] if f else []
        await interaction.followup.send(embeds=embeds[:10], files=files, view=view, ephemeral=True)

    @discord.app_commands.command(name="deconnecter-wow", description="Délie ton compte Battle.net")
    async def deconnecter_wow(self, interaction: discord.Interaction):
        await storage.delete_user_link(interaction.user.id)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ Compte délié", color=0x57F287), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Account(bot))
