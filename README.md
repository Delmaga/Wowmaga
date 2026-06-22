# Bot Discord World of Warcraft

Deux fonctionnalités :
- `/newswow #salon` (admin) : poste automatiquement les actus, événements et promos WoW dans le salon choisi.
- `/comptewow` : chaque membre connecte **son propre** compte Battle.net et voit ses personnages (race, classe, niveau, royaume, équipement / item level estimé).
- `/deconnecter-wow` : pour délier son compte.

⚠️ Limite officielle de l'API Blizzard (pas un bug du bot) : **pas d'accès à l'or, au contenu des sacs/banque, ni aux hauts faits**. Seuls les objets **équipés** sont accessibles.

---

## 1. Discord — tu as déjà ton bot

Dans le [Discord Developer Portal](https://discord.com/developers/applications) → ton appli → onglet **Bot** :
- Active "Public Bot" si tu veux l'ajouter à d'autres serveurs plus tard.
- Pas besoin d'intent privilégié particulier (le bot n'utilise pas le contenu des messages).

Pour l'inviter sur ton serveur, génère un lien dans **OAuth2 → URL Generator** :
- Scopes : `bot` + `applications.commands`
- Permissions bot : `Send Messages`, `Embed Links`, `Use Slash Commands`

## 2. Battle.net — créer une application API

1. Va sur https://develop.battle.net/access/clients et connecte-toi avec ton compte Blizzard.
2. **Create Client**.
3. **Redirect URLs** : mets `https://TON-APP.up.railway.app/callback` (tu sauras l'URL Railway après le déploiement à l'étape 4 — tu pourras revenir modifier ce champ ensuite, ce n'est pas grave si tu le fais après coup).
4. Une fois créé, note le **Client ID** et le **Client Secret**.

## 3. Configurer les variables d'environnement

Copie `.env.example` en `.env` (en local) et remplis :
- `DISCORD_TOKEN` : ton token de bot Discord (Developer Portal → Bot → Reset Token)
- `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET` : depuis l'étape 2
- `BLIZZARD_REGION` : `eu` (Europe) ou `us`, etc.
- `BLIZZARD_REDIRECT_URI` : `https://TON-APP.up.railway.app/callback`
- `SECRET_KEY` : une longue chaîne aléatoire random (sert à sécuriser le lien de connexion)

## 4. Déployer sur Railway

1. Pousse ce dossier sur un repo GitHub.
2. Sur [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**.
3. Railway détecte le `Procfile` automatiquement (process `web`).
4. Dans **Settings → Networking**, génère un **Public Domain** (ex: `tonbot.up.railway.app`). C'est cette URL + `/callback` qui doit être dans `BLIZZARD_REDIRECT_URI` (variable Railway) **et** dans les Redirect URLs de ton appli Battle.net (étape 2.3) — les deux doivent être identiques au caractère près.
5. Dans **Variables**, ajoute toutes les variables du `.env`.
6. Railway redéploie automatiquement → regarde les **Logs** : tu dois voir `Connecté en tant que ...` et `Serveur web démarré sur le port ...`.

⚠️ Le fichier `bot_data.db` (comptes liés) et `seen_news.json` sont stockés sur le disque local du service. Sur Railway, ce disque est éphémère par défaut : un redéploiement peut tout effacer. Si tu veux que les liaisons de compte soient permanentes, ajoute un **Volume** Railway (Settings → Volumes) monté par exemple sur `/data`, et mets `DB_PATH=/data/bot_data.db` dans les variables.

## 5. Utilisation

- Un admin tape `/newswow #salon-news` une fois → terminé, le bot postera tout seul.
- Chaque membre tape `/comptewow` → reçoit un bouton "Connecter mon compte Battle.net" → se connecte avec son compte Blizzard (jamais vu par le bot) → retape `/comptewow` → voit ses personnages.

## Structure du projet

```
bot.py              -> point d'entrée (bot Discord + serveur web)
web_server.py        -> page de callback OAuth Battle.net
storage.py            -> base SQLite (salons news + comptes liés)
cogs/battlenet.py     -> client API Battle.net
cogs/news.py          -> commande /newswow + tâche planifiée
cogs/account.py        -> commandes /comptewow et /deconnecter-wow
```
