import logging
import discord
from discord.ext import commands

import storage
from battlenet import BattleNetClient

log = logging.getLogger("wow-bot.account")

FACTION_EMOJI = {"ALLIANCE": "🔵", "HORDE": "🔴"}
MAX_EQUIP = 5  # nombre de persos dont on détaille l'équipement


class Account(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(name="comptewow", description="Affiche tous tes personnages World of Warcraft")
    async def comptewow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        link = await storage.get_user_link(interaction.user.id)

        # Pas encore lié → envoyer le bouton de connexion
        if not link:
            state = storage.sign_state(interaction.user.id)
            client = BattleNetClient()
            url = client.get_authorize_url(state)
            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="🔗 Connecter mon compte Battle.net",
                url=url,
                style=discord.ButtonStyle.link,
            ))
            await interaction.followup.send(
                "Tu n'as pas encore lié ton compte Battle.net.\n"
                "Clique ci-dessous pour te connecter (connexion officielle Blizzard, le bot ne voit jamais ton mot de passe).\n"
                "Une fois connecté, retape `/comptewow`.",
                view=view,
                ephemeral=True,
            )
            return

        # Récupérer le profil
        client = BattleNetClient(region=link["region"])
        try:
            profile = await client.get_account_wow_profile(link["access_token"])
        except Exception as e:
            log.error(f"Erreur profil {interaction.user.id}: {e}")
            await storage.delete_user_link(interaction.user.id)
            await interaction.followup.send(
                "❌ Session expirée. Retape `/comptewow` pour te reconnecter.", ephemeral=True
            )
            return

        if not profile or not profile.get("wow_accounts"):
            await interaction.followup.send("Aucun personnage trouvé sur ce compte.", ephemeral=True)
            return

        characters = []
        for account in profile["wow_accounts"]:
            characters.extend(account.get("characters", []))

        if not characters:
            await interaction.followup.send("Aucun personnage trouvé.", ephemeral=True)
            return

        characters.sort(key=lambda c: c.get("level", 0), reverse=True)

        # Embed principal : liste de tous les persos
        embed_list = discord.Embed(
            title=f"🎮 Personnages de {interaction.user.display_name}",
            description=f"**{len(characters)}** personnage(s) sur ce compte",
            color=discord.Color.blurple(),
        )
        for c in characters[:25]:
            faction = FACTION_EMOJI.get(c.get("faction", {}).get("type", ""), "⚪")
            classe = c.get("playable_class", {}).get("name", "?")
            race = c.get("playable_race", {}).get("name", "?")
            realm = c.get("realm", {}).get("name", "?")
            embed_list.add_field(
                name=f"{faction} {c.get('name', '?')} — Niv. {c.get('level', '?')}",
                value=f"*{race} {classe}*\n🏰 {realm}",
                inline=True,
            )

        embeds = [embed_list]

        # Embed équipement : les X persos les plus avancés
        equip_embed = discord.Embed(
            title="⚔️ Équipement des personnages principaux",
            color=discord.Color.dark_gold(),
        )
        for c in characters[:MAX_EQUIP]:
            realm_slug = c.get("realm", {}).get("slug", "")
            name = c.get("name", "")
            try:
                data = await client.get_character_equipment(realm_slug, name)
            except Exception:
                data = None

            if data and data.get("equipped_items"):
                items = data["equipped_items"]
                ilvls = [it.get("level", {}).get("value", 0) for it in items if it.get("level")]
                avg = round(sum(ilvls) / len(ilvls), 1) if ilvls else "?"
                slots = "\n".join(
                    f"• **{it.get('slot', {}).get('name', '?')}** — {it.get('name', '?')} (ilvl {it.get('level', {}).get('value', '?')})"
                    for it in items[:10]
                )
                equip_embed.add_field(
                    name=f"🧙 {name} — ilvl moyen ≈ {avg}",
                    value=slots or "Aucun objet",
                    inline=False,
                )
            else:
                equip_embed.add_field(name=f"🧙 {name}", value="Équipement indisponible", inline=False)

        equip_embed.set_footer(text="⚠️ L'or, les sacs et la banque ne sont pas accessibles via l'API Blizzard.")
        embeds.append(equip_embed)

        await interaction.followup.send(embeds=embeds, ephemeral=True)

    @discord.app_commands.command(name="deconnecter-wow", description="Délie ton compte Battle.net du bot")
    async def deconnecter_wow(self, interaction: discord.Interaction):
        await storage.delete_user_link(interaction.user.id)
        await interaction.response.send_message("✅ Compte Battle.net délié.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Account(bot))
