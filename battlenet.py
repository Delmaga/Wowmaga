import os
import logging
import discord
from discord.ext import commands

import storage
from cogs.battlenet import BattleNetClient

log = logging.getLogger("wow-bot.account")

FACTION_EMOJI = {"ALLIANCE": "🔵", "HORDE": "🔴"}
MAX_DETAILED_EQUIPMENT = 5  # pour éviter trop d'appels API, on détaille l'équipement des X persos de plus haut niveau


class Account(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _authorize_view(self, discord_id: int) -> discord.ui.View:
        state = storage.sign_state(discord_id)
        client = BattleNetClient()
        url = client.get_authorize_url(state)
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Connecter mon compte Battle.net", url=url, style=discord.ButtonStyle.link))
        return view

    @discord.app_commands.command(name="comptewow", description="Affiche tes personnages World of Warcraft (compte Battle.net lié)")
    async def comptewow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        link = await storage.get_user_link(interaction.user.id)
        if not link:
            view = self._authorize_view(interaction.user.id)
            await interaction.followup.send(
                "Tu n'as pas encore lié ton compte Battle.net. Clique ci-dessous pour te connecter "
                "(connexion officielle Blizzard, le bot ne voit jamais ton mot de passe) :",
                view=view,
                ephemeral=True,
            )
            return

        client = BattleNetClient(region=link["region"])
        try:
            profile = await client.get_account_wow_profile(link["access_token"])
        except Exception as e:
            log.error(f"Erreur récupération profil: {e}")
            await interaction.followup.send(
                "❌ Impossible de récupérer ton profil (session peut-être expirée). Relie ton compte avec /comptewow.",
                ephemeral=True,
            )
            await storage.delete_user_link(interaction.user.id)
            return

        if not profile or not profile.get("wow_accounts"):
            await interaction.followup.send("Aucun personnage trouvé sur ce compte Battle.net.", ephemeral=True)
            return

        characters = []
        for wow_account in profile["wow_accounts"]:
            characters.extend(wow_account.get("characters", []))

        if not characters:
            await interaction.followup.send("Aucun personnage trouvé sur ce compte Battle.net.", ephemeral=True)
            return

        characters.sort(key=lambda c: c.get("level", 0), reverse=True)

        embeds = []
        main_embed = discord.Embed(
            title=f"🛡️ Personnages de {interaction.user.display_name}",
            description=f"{len(characters)} personnage(s) trouvé(s)",
            color=discord.Color.blurple(),
        )
        for c in characters[:25]:
            faction = FACTION_EMOJI.get(c.get("faction", {}).get("type", ""), "")
            classe = c.get("playable_class", {}).get("name", "?")
            race = c.get("playable_race", {}).get("name", "?")
            realm = c.get("realm", {}).get("name", "?")
            main_embed.add_field(
                name=f"{faction} {c.get('name')} — Niv. {c.get('level', '?')}",
                value=f"{race} {classe}\nRoyaume : {realm}",
                inline=True,
            )
        embeds.append(main_embed)

        # Détail équipement pour les persos les plus avancés
        detail_targets = characters[:MAX_DETAILED_EQUIPMENT]
        if detail_targets:
            detail_embed = discord.Embed(
                title="⚔️ Équipement (estimation item level)",
                color=discord.Color.dark_gold(),
            )
            for c in detail_targets:
                realm_slug = c.get("realm", {}).get("slug")
                name = c.get("name")
                try:
                    equipment = await client.get_character_equipment(realm_slug, name)
                except Exception:
                    equipment = None

                if equipment and equipment.get("equipped_items"):
                    items = equipment["equipped_items"]
                    levels = [it.get("level", {}).get("value", 0) for it in items if it.get("level")]
                    avg_ilvl = round(sum(levels) / len(levels), 1) if levels else "?"
                    detail_embed.add_field(
                        name=name,
                        value=f"{len(items)} objets équipés\nItem level moyen ≈ **{avg_ilvl}**",
                        inline=True,
                    )
                else:
                    detail_embed.add_field(name=name, value="Équipement indisponible", inline=True)
            embeds.append(detail_embed)

        note = (
            "\nℹ️ Blizzard n'expose pas via son API : l'or, le contenu des sacs/banque, "
            "ni les hauts faits. Seuls les objets **équipés** et les infos de base sont disponibles."
        )
        embeds[-1].set_footer(text=note.strip())

        await interaction.followup.send(embeds=embeds, ephemeral=True)

    @discord.app_commands.command(name="deconnecter-wow", description="Délie ton compte Battle.net de ce bot")
    async def deconnecter_wow(self, interaction: discord.Interaction):
        await storage.delete_user_link(interaction.user.id)
        await interaction.response.send_message("✅ Ton compte Battle.net a été délié.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Account(bot))
