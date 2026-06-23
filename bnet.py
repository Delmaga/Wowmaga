import os
import time
import aiohttp

BLIZZARD_CLIENT_ID     = os.getenv("BLIZZARD_CLIENT_ID")
BLIZZARD_CLIENT_SECRET = os.getenv("BLIZZARD_CLIENT_SECRET")
BLIZZARD_REDIRECT_URI  = os.getenv("BLIZZARD_REDIRECT_URI")
LOCALE                 = os.getenv("BLIZZARD_LOCALE", "fr_FR")

_APP_TOKEN_CACHE = {"token": None, "expires_at": 0}


def _oauth_host(region: str) -> str:
    return "https://www.battlenet.com.cn" if region == "cn" else f"https://{region}.battle.net"

def _api_host(region: str) -> str:
    return f"https://{region}.api.blizzard.com"


class BattleNetClient:
    def __init__(self, region: str = None):
        self.region = (region or os.getenv("BLIZZARD_REGION", "eu")).lower()

    async def _get_app_token(self) -> str:
        now = time.time()
        if _APP_TOKEN_CACHE["token"] and _APP_TOKEN_CACHE["expires_at"] > now + 30:
            return _APP_TOKEN_CACHE["token"]
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{_oauth_host(self.region)}/oauth/token",
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(BLIZZARD_CLIENT_ID, BLIZZARD_CLIENT_SECRET),
            ) as r:
                r.raise_for_status()
                data = await r.json()
                _APP_TOKEN_CACHE["token"]      = data["access_token"]
                _APP_TOKEN_CACHE["expires_at"] = now + data.get("expires_in", 86000)
                return _APP_TOKEN_CACHE["token"]

    async def _get(self, path: str, namespace: str, token: str) -> dict:
        params  = {"namespace": f"{namespace}-{self.region}", "locale": LOCALE}
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{_api_host(self.region)}{path}", params=params, headers=headers) as r:
                if r.status == 404:
                    return {}
                r.raise_for_status()
                return await r.json()

    async def _pub(self, path: str, namespace: str) -> dict:
        return await self._get(path, namespace, await self._get_app_token())

    # ── OAuth utilisateur ──────────────────────────────────────────────────
    def get_authorize_url(self, state: str) -> str:
        return (
            f"{_oauth_host(self.region)}/oauth/authorize"
            f"?client_id={BLIZZARD_CLIENT_ID}"
            f"&scope=wow.profile"
            f"&state={state}"
            f"&redirect_uri={BLIZZARD_REDIRECT_URI}"
            f"&response_type=code"
        )

    async def exchange_code(self, code: str) -> dict:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{_oauth_host(self.region)}/oauth/token",
                data={"grant_type": "authorization_code", "code": code, "redirect_uri": BLIZZARD_REDIRECT_URI},
                auth=aiohttp.BasicAuth(BLIZZARD_CLIENT_ID, BLIZZARD_CLIENT_SECRET),
            ) as r:
                r.raise_for_status()
                return await r.json()

    async def get_account_wow_profile(self, user_token: str) -> dict:
        return await self._get("/profile/user/wow", "profile", user_token)

    # ── Données personnage ─────────────────────────────────────────────────
    async def get_character_profile(self, realm_slug: str, name: str) -> dict:
        return await self._pub(f"/profile/wow/character/{realm_slug}/{name.lower()}", "profile")

    async def get_character_equipment(self, realm_slug: str, name: str) -> dict:
        return await self._pub(f"/profile/wow/character/{realm_slug}/{name.lower()}/equipment", "profile")

    async def get_character_media(self, realm_slug: str, name: str) -> dict:
        return await self._pub(f"/profile/wow/character/{realm_slug}/{name.lower()}/character-media", "profile")
