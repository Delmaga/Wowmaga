import logging
import discord
from discord.ext import commands

import storage
from bnet import BattleNetClient
from card_generator import generate_equipment_image
from stats_generator import generate_stats_image

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
QUALITY_ICON  = {"LEGENDARY":"🟠","EPIC":"🟣","RARE":"🔵","UNCOMMON":"🟢","COMMON":"⬜","POOR":"⬛"}
QUALITY_LABEL = {"LEGENDARY":"Légendaire","EPIC":"Épique","RARE":"Rare","UNCOMMON":"Peu commun","COMMON":"Commun"}
FACTION       = {"ALLIANCE":("Alliance 🔵"),"HORDE":("Horde 🔴")}
SLOT_ORDER    = [
    "Head","Neck","Shoulder","Back","Chest","Wrist","Hand","Waist","Legs","Feet",
    "Finger","Trinket","Main-Hand","Off-Hand",
    "Tête","Cou","Épaule","Dos","Torse","Poignet","Mains","Taille","Jambes","Pieds",
    "Doigt","Bibelot","Main droite","Main gauche",
]

def _hex(rgb): return (rgb[0]<<16)|(rgb[1]<<8)|rgb[2]
def _render(media, key="inset"):
    for a in (media or {}).get("assets",[]):
        if a.get("key")==key: return a.get("value")
    return None
def _slot_key(it):
    s = it.get("slot",{}).get("name","")
    try: return SLOT_ORDER.index(s)
    except: return 99


async def build_all(c: dict, client: BattleNetClient, discord_user):
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
    guild      = prof.get("guild",{}).get("name")
    spec       = prof.get("active_spec",{}).get("name")
    e_ilvl     = prof.get("equipped_item_level",0)
    a_ilvl     = prof.get("average_item_level",0)
    achiev     = prof.get("achievement_points",0)
    last_login = prof.get("last_login_timestamp")
    render_url = _render(media,"inset") or _render(media,"main-raw")
    avatar_url = _render(media,"avatar")

    embeds = []
    files  = []

    # ══════════════════════════════════
    # CARTE 1 : HERO (render 3D)
    # ══════════════════════════════════
    hero = discord.Embed(color=color)
    hero.set_author(
        name=f"⚔️  Fiche de {discord_user.display_name}  —  World of Warcraft",
        icon_url=discord_user.display_avatar.url,
    )
    hero.title = f"{icon}  {name.upper()}"
    hero.description = (
        f"```ansi\n"
        f"\u001b[2;34m{'═'*36}\u001b[0m\n"
        f"  \u001b[1;37m{(spec+' ' if spec else '')+classe}\u001b[0m\n"
        f"  Race      {race}\n"
        f"  Faction   {faction}\n"
        f"  Royaume   {realm}\n"
        +(f"  Guilde    <{guild}>\n" if guild else "")
        +f"\u001b[2;34m{'═'*36}\u001b[0m\n"
        f"```"
    )
    if render_url: hero.set_image(url=render_url)
    if avatar_url: hero.set_thumbnail(url=avatar_url)
    embeds.append(hero)

    # ══════════════════════════════════
    # CARTE 2 : STATS (image générée)
    # ══════════════════════════════════
    try:
        stats_buf = await generate_stats_image(
            char_name=name, classe=classe, spec=spec or "", race=race,
            realm=realm, faction=faction, guild=guild,
            level=int(level), e_ilvl=e_ilvl, a_ilvl=a_ilvl,
            achiev=achiev, last_login_ms=last_login,
            class_color=rgb, avatar_url=avatar_url,
        )
        stats_file = discord.File(stats_buf, filename="stats.png")
        files.append(stats_file)
        stats_embed = discord.Embed(color=color)
        stats_embed.title = f"📊  Statistiques — {name}"
        stats_embed.set_image(url="attachment://stats.png")
        embeds.append(stats_embed)
    except Exception as e:
        log.error(f"Stats image: {e}")

    # ══════════════════════════════════
    # CARTE 3 : OBJETS PORTÉS (texte)
    # ══════════════════════════════════
    items = equip.get("equipped_items",[])
    if items:
        gear_embed = discord.Embed(color=color)
        gear_embed.title = f"🗡️  Objets portés — {name}"

        items_sorted = sorted(items, key=_slot_key)
        left, right  = [], []
        for i, it in enumerate(items_sorted[:16]):
            slot    = it.get("slot",{}).get("name","?")
            iname   = it.get("name","?")
            ilvl    = it.get("level",{}).get("value","?")
            quality = it.get("quality",{}).get("type","COMMON")
            dot     = QUALITY_ICON.get(quality,"⬜")
            line    = f"{dot} **{iname}**\n`{slot}  •  ilvl {ilvl}`"
            (left if i%2==0 else right).append(line)

        if left:  gear_embed.add_field(name="​", value="\n\n".join(left),  inline=True)
        if right: gear_embed.add_field(name="​", value="\n\n".join(right), inline=True)

        # Résumé qualités
        qcount: dict[str,int] = {}
        for it in items:
            q = it.get("quality",{}).get("type","COMMON")
            qcount[q] = qcount.get(q,0)+1
        summary = "  ·  ".join(
            f"{QUALITY_ICON.get(q,'⬜')} {QUALITY_LABEL.get(q,q)} ×{n}"
            for q,n in qcount.items() if q in QUALITY_ICON
        )
        if summary:
            gear_embed.add_field(name="✦  Qualités", value=summary, inline=False)
        embeds.append(gear_embed)

    # ══════════════════════════════════
    # CARTE 4 : IMAGE ÉQUIPEMENT
    # ══════════════════════════════════
    if items:
        try:
            eq_buf  = await generate_equipment_image(
                char_name=name, classe=classe, realm=realm,
                equipped_ilvl=e_ilvl, items=items, class_color=rgb,
            )
            eq_file = discord.File(eq_buf, filename="equipment.png")
            files.append(eq_file)
            eq_embed = discord.Embed(color=color)
            eq_embed.title = f"🎒  Aperçu équipement — {name}"
            eq_embed.set_image(url="attachment://equipment.png")
            eq_embed.set_footer(text="Données via l'API officielle Blizzard  ·  /deconnecter-wow pour délier")
            embeds.append(eq_embed)
        except Exception as e:
            log.error(f"Equipment image: {e}")

    return embeds, files


# ══════════════════════════════════════
# MENU SÉLECTION
# ══════════════════════════════════════
class CharacterSelect(discord.ui.Select):
    def __init__(self, characters, client, discord_user):
        self.characters   = characters
        self.client       = client
        self.discord_user = discord_user
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
        embeds, files = await build_all(c, self.client, self.discord_user)
        view = discord.ui.View(timeout=300)
        view.add_item(CharacterSelect(self.characters, self.client, self.discord_user))
        await interaction.edit_original_response(embeds=embeds[:10], attachments=files, view=view)


# ══════════════════════════════════════
# COG
# ══════════════════════════════════════
class Account(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="comptewow", description="✨ Affiche ta fiche WoW (visible par tous)")
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
                title="🔐  Connexion requise",
                description=(
                    "```\n"
                    "Connecte ton compte Battle.net\n"
                    "pour afficher ta fiche.\n"
                    "──────────────────────────────\n"
                    "✅ Connexion officielle Blizzard\n"
                    "✅ Mot de passe jamais vu par le bot\n"
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
        for acc in (data or {}).get("wow_accounts",[]):
            characters.extend(acc.get("characters",[]))
        characters.sort(key=lambda c: c.get("level",0), reverse=True)

        if not characters:
            await interaction.followup.send("Aucun personnage trouvé.", ephemeral=True)
            return

        embeds, files = await build_all(characters[0], client, interaction.user)
        view = discord.ui.View(timeout=300)
        if len(characters) > 1:
            view.add_item(CharacterSelect(characters, client, interaction.user))

        await interaction.followup.send(embeds=embeds[:10], files=files, view=view)

    @discord.app_commands.command(name="deconnecter-wow", description="Délie ton compte Battle.net (privé)")
    async def deconnecter_wow(self, interaction: discord.Interaction):
        await storage.delete_user_link(interaction.user.id)
        await interaction.response.send_message(
            embed=discord.Embed(title="✅ Compte délié", color=0x57F287), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Account(bot))
