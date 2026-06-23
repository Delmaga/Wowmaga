import os
import logging
from aiohttp import web

import storage
from bnet import BattleNetClient

log  = logging.getLogger("wow-bot.web")
PORT = int(os.getenv("PORT", "8080"))

OK_HTML = """<html><head><meta charset="utf-8"><title>Lié !</title>
<style>body{font-family:sans-serif;background:#1e1f22;color:#fff;display:flex;
height:100vh;align-items:center;justify-content:center;text-align:center}
div{background:#2b2d31;padding:40px;border-radius:12px}h1{color:#f1c40f}</style></head>
<body><div><h1>✅ Compte Battle.net lié !</h1>
<p>Retourne sur Discord et tape <b>/comptewow</b>.</p></div></body></html>"""

ERR_HTML = """<html><head><meta charset="utf-8"><title>Erreur</title>
<style>body{font-family:sans-serif;background:#1e1f22;color:#fff;display:flex;
height:100vh;align-items:center;justify-content:center;text-align:center}
div{background:#2b2d31;padding:40px;border-radius:12px}h1{color:#e74c3c}</style></head>
<body><div><h1>❌ Erreur</h1><p>{msg}</p></div></body></html>"""


async def handle_callback(req: web.Request):
    code  = req.query.get("code")
    state = req.query.get("state")
    if not code or not state:
        return web.Response(text=ERR_HTML.format(msg="Paramètres manquants."),
                            content_type="text/html", status=400)

    discord_id = storage.verify_state(state)
    if discord_id is None:
        return web.Response(text=ERR_HTML.format(msg="Lien invalide ou expiré."),
                            content_type="text/html", status=400)

    region = os.getenv("BLIZZARD_REGION", "eu")
    client = BattleNetClient(region=region)
    try:
        token_data = await client.exchange_code(code)
    except Exception as e:
        log.error(f"Échange OAuth échoué: {e}")
        return web.Response(text=ERR_HTML.format(msg="Connexion Battle.net échouée."),
                            content_type="text/html", status=400)

    await storage.save_user_link(
        discord_id=discord_id,
        region=region,
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        expires_in=token_data.get("expires_in", 86000),
    )
    return web.Response(text=OK_HTML, content_type="text/html")


async def health(req: web.Request):
    return web.Response(text="OK")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/callback", handle_callback)
    app.router.add_get("/",         health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info(f"Serveur web démarré sur le port {PORT}")
    return runner
