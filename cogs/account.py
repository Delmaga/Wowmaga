import io
import logging
import discord
from discord.ext import commands

import storage
from battlenet import BattleNetClient
from card_generator import generate_equipment_image

log = logging.getLogger("wow-bot.account")

CLASS_COLORS_RGB = {
    "Guerrier": (198,155, 58), "Warrior": (198,155, 58),
    "Paladin":  (244,140,186),
    "Chasseur": (170,211,114), "Hunter": (170,211,114),
    "Voleur":   (255,244,104), "Rogue":  (255,244,104),
    "Prêtre":   (220,220,220), "Priest": (220,220,220),
    "Chevalier de la mort": (196, 30, 58), "Death Knight": (196, 30, 58),
    "Chaman":   (  0,112,221), "Shaman": (  0,112,221),
    "Mage":     ( 63,199,235),
    "Démoniste":(135,136,238), "Warlock":(135,136,238),
    "Moine":    (  0,255,152), "Monk":   (  0,255,152),
    "Druide":   (255,124, 10), "Druid":  (255,124, 10),
    "Chasseur de démons": (163,48,201), "Demon Hunter": (163,48,201),
    "Évocateur":(51,147,127),  "Evoker": (51,147,127),
}

CLASS_COLORS_HEX = {k: (v[0]<<16)|(v[1]<<8)|v[2] for k, v in CLASS_COLORS_RGB.items()}

CLASS_ICON = {
    "Guerrier":"⚔️","Warrior":"⚔️","Paladin":"🛡️",
    "Chasseur":"🏹","Hunter":"🏹","Voleur":"🗡️","Rogue":"🗡️",
    "Prêtre":"✨","Priest":"✨","Chevalier de la mort":"💀","Death Knight":"💀",
    "Chaman":"⚡","Shaman":"⚡","Mage":"🔥","Démoniste":"🟣","Warlock":"🟣",
    "Moine":"👊","Monk":"👊","Druide":"🌿","Druid":"🌿",
    "Chasseur de démons":"🔮","Demon Hunter":"🔮","Évocateur":"🐉","Evoker":"🐉",
}

FACTION_DATA = {
    "ALLIANCE": ("Alliance", "🔵"),
    "HORDE":    ("Horde",    "🔴"),
}

def _render_url(media: dict, key: str = "inset") -> str | None:
    for asset in (media or {}).get("assets", []):
        if asset.get("key") == key:
            return asset.get("value")
    return None

def _bar(val: int, maxi: int, length: int = 18) -> str:
    filled = max(0, min(round((val / maxi) * length), length))
    return "▰" * filled + "▱" * (length - filled)


async def build_hero_embed(c: dict, client: BattleNetClient) -> tuple[list[discord.Embed], discord.File | None]:
    name       = c.get("name", "?")
    level      = c.get("level", 0)
    classe     = c.get("playable_class", {}).get("name", "?")
    race       = c.get("playable_race",  {}).get("name", "?")
    realm      = c.get("realm", {}).get("name", "?")
    realm_slug = c.get("realm", {}).get("slug", "")
    faction_t  = c.get("faction", {}).get("type", "")

    faction_name, faction_icon = FACTION_DATA.get(faction_t, ("Neutre", "⚪"))
    color_hex   = CLASS_COLORS_HEX.get(classe, 0x5865F2)
    color_rgb   = CLASS_COLORS_RGB.get(classe, (88, 101, 242))
    class_icon  = CLASS_ICON.get(classe, "🎮")

    try:    profile   = await client.get_character_profile(realm_slug, name)
    except: profile   = {}
    try:    equipment = await client.get_character_equipment(realm_slug, name)
    except: equipment = {}
    try:    media     = await client.get_character_media(realm_slug, name)
    except: media     = {}

    profile   = profile   or {}
    equipment = equipment or {}

    guild         = profile.get("guild", {}).get("name")
    spec          = profile.get("active_spec", {}).get("name")
    equipped_ilvl = profile.get("equipped_item_level", 0)
    avg_ilvl      = profile.get("average_item_level",  0)
    achiev        = profile.get("achievement_points",   0)

    render_url = _render_url(media, "inset") or _render_url(media, "main-raw")
    avatar_url = _render_url(media, "avatar")

    embeds = []

    # ══════════════════════════════════════════════════════
    #  CARTE 1 : HERO — render 3D plein format
    # ══════════════════════════════════════════════════════
    hero = discord.Embed(color=color_hex)
    hero.set_author(
        name="⚔️  World of Warcraft  —  Fiche de Personnage",
        icon_url="https://bnetcmsus-a.akamaihd.net/cms/gallery/D2TTHKAPW9BH1542314183036.png",
    )
    hero.title = f"{class_icon}  {name.upper()}"
    hero.description = (
        f"```ansi\n"
        f"\u001b[2;34m{'═'*38}\u001b[0m\n"
        f"  \u001b[1;37m{spec or classe:<20}\u001b[0m {faction_icon} {faction_name}\n"
        f"  {'Race':<10}  {race}\n"
        f"  {'Classe':<10}  {classe}\n"
        f"  {'Royaume':<10}  {realm}\n"
        + (f"  {'Guilde':<10}  <{guild}>\n" if guild else "")
        + f"\u001b[2;34m{'═'*38}\u001b[0m\n"
        f"```"
    )
    if render_url:
        hero.set_image(url=render_url)
    if avatar_url:
        hero.set_thumbnail(url=avatar_url)
    embeds.append(hero)

    # ══════════════════════════════════════════════════════
    #  CARTE 2 : STATS
    # ══════════════════════════════════════════════════════
    stats = discord.Embed(color=color_hex)
    stats.title = f"📊  Stats de {name}"

    lv_pct   = round((int(level) / 80) * 100)
    ilvl_pct = round((equipped_ilvl / 700) * 100) if equipped_ilvl else 0

    block = (
        f"```\n"
        f"╔{'═'*36}╗\n"
        f"║  NIVEAU          {level:<4} / 80{' '*12}║\n"
        f"║  {_bar(int(level),80)}  {lv_pct:>3}%  ║\n"
        f"╠{'═'*36}╣\n"
        f"║  ITEM LEVEL      {equipped_ilvl:<4} équipé{' '*9}║\n"
        f"║  {_bar(equipped_ilvl,700)}  {ilvl_pct:>3}%  ║\n"
        f"║  Ilvl moyen      {avg_ilvl:<4}{' '*17}║\n"
        f"╠{'═'*36}╣\n"
        f"║  HAUTS FAITS     {f'{achiev:,}':<18}║\n"
        f"╚{'═'*36}╝\n"
        f"```"
    )
    stats.description = block
    embeds.append(stats)

    # ══════════════════════════════════════════════════════
    #  CARTE 3 : IMAGE D'ÉQUIPEMENT GÉNÉRÉE
    # ══════════════════════════════════════════════════════
    equip_file = None
    if equipment.get("equipped_items"):
        items = equipment["equipped_items"]
        try:
            buf = await generate_equipment_image(
                char_name=name,
                classe=classe,
                realm=realm,
                equipped_ilvl=equipped_ilvl,
                items=items,
                class_color=color_rgb,
            )
            equip_file = discord.File(buf, filename="equipment.png")
            equip_embed = discord.Embed(color=color_hex)
            equip_embed.title = f"🎒  Équipement de {name}"
            equip_embed.set_image(url="attachment://equipment.png")
            equip_embed.set_footer(
                text="Icônes & données via l'API officielle Blizzard  •  /deconnecter-wow pour délier ton compte"
            )
            embeds.append(equip_embed)
        except Exception as e:
            log.error(f"Erreur génération image: {e}")

    return embeds, equip_file


# ══════════════════════════════════════════════════════════
#  MENU DÉROULANT
# ══════════════════════════════════════════════════════════
class CharacterSelect(discord.ui.Select):
    def __init__(self, characters: list, client: BattleNetClient):
        self.characters = characters
        self.client     = client
        options = [
            discord.SelectOption(
                label=f"{c.get('name')}  —  Niv. {c.get('level','?')}",
                description=f"{c.get('playable_class',{}).get('name','?')}  ·  {c.get('realm',{}).get('name','?')}",
                value=str(i),
                emoji="🔵" if c.get("faction",{}).get("type")=="ALLIANCE" else "🔴",
            )
            for i, c in enumerate(characters[:25])
        ]
        super().__init__(
            placeholder="⚔️  Choisir un personnage…",
            min_values=1, max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        c = self.characters[int(self.values[0])]
        embeds, equip_file = await build_hero_embed(c, self.client)
        view = discord.ui.View(timeout=300)
        view.add_item(CharacterSelect(self.characters, self.client))
        files = [equip_file] if equip_file else []
        await interaction.edit_original_response(embeds=embeds[:10], attachments=files, view=view)


# ══════════════════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════════════════
class Account(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="comptewow",
        description="✨ Affiche ta fiche de personnage World of Warcraft"
    )
    async def comptewow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        link = await storage.get_user_link(interaction.user.id)
        if not link:
            state  = storage.sign_state(interaction.user.id)
            client = BattleNetClient()
            url    = client.get_authorize_url(state)
            view   = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="🔗  Connecter mon compte Battle.net",
                url=url, style=discord.ButtonStyle.link,
            ))
            embed = discord.Embed(
                title="🔐  Connexion Battle.net requise",
                description=(
                    "```\n"
                    "Connecte ton compte Battle.net pour\n"
                    "afficher ta fiche de personnage.\n"
                    "────────────────────────────────\n"
                    "✅  Connexion officielle Blizzard\n"
                    "✅  Le bot ne voit jamais ton mdp\n"
                    "✅  Données visibles uniquement par toi\n"
                    "────────────────────────────────\n"
                    "↳  Après connexion, retape /comptewow\n"
                    "```"
                ),
                color=0x0078FF,
            )
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

        client = BattleNetClient(region=link["region"])
        try:
            profile_data = await client.get_account_wow_profile(link["access_token"])
        except Exception as e:
            log.error(f"Erreur profil: {e}")
            await storage.delete_user_link(interaction.user.id)
            await interaction.followup.send(
                embed=discord.Embed(title="❌ Session expirée",
                description="Retape `/comptewow` pour te reconnecter.", color=0xFF0000),
                ephemeral=True,
            )
            return

        if not profile_data or not profile_data.get("wow_accounts"):
            await interaction.followup.send("Aucun personnage trouvé.", ephemeral=True)
            return

        characters = []
        for acc in profile_data["wow_accounts"]:
            characters.extend(acc.get("characters", []))
        characters.sort(key=lambda c: c.get("level", 0), reverse=True)

        embeds, equip_file = await build_hero_embed(characters[0], client)

        view = discord.ui.View(timeout=300)
        if len(characters) > 1:
            view.add_item(CharacterSelect(characters, client))

        files = [equip_file] if equip_file else []
        await interaction.followup.send(embeds=embeds[:10], files=files, view=view, ephemeral=True)

    @discord.app_commands.command(
        name="deconnecter-wow",
        description="Délie ton compte Battle.net du bot"
    )
    async def deconnecter_wow(self, interaction: discord.Interaction):
        await storage.delete_user_link(interaction.user.id)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ Compte délié",
            description="Compte Battle.net déconnecté.", color=0x57F287),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Account(bot))
