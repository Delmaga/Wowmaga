import os
import time
import aiohttp

BLIZZARD_CLIENT_ID = os.getenv("BLIZZARD_CLIENT_ID")
BLIZZARD_CLIENT_SECRET = os.getenv("BLIZZARD_CLIENT_SECRET")
BLIZZARD_REDIRECT_URI = os.getenv("BLIZZARD_REDIRECT_URI")
LOCALE = os.getenv("BLIZZARD_LOCALE", "fr_FR")

_APP_TOKEN_CACHE = {"token": None, "expires_at": 0}


def _oauth_host(region: str) -> str:
    return "https://www.battlenet.com.cn" if region == "cn" else f"https://{region}.battle.net"


def _api_host(region: str) -> str:
    return f"https://{region}.api.blizzard.com"


class BattleNetClient:
    def __init__(self, region: str = None):
        self.region = (region or os.getenv("BLIZZARD_REGION", "eu")).lower()

    async def _get_app_token(self):
        now = time.time()
        if _APP_TOKEN_CACHE["token"] and _APP_TOKEN_CACHE["expires_at"] > now + 30:
            return _APP_TOKEN_CACHE["token"]
        url = f"{_oauth_host(self.region)}/oauth/token"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data={"grant_type": "client_credentials"},
                auth=aiohttp.BasicAuth(BLIZZARD_CLIENT_ID, BLIZZARD_CLIENT_SECRET),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                _APP_TOKEN_CACHE["token"] = data["access_token"]
                _APP_TOKEN_CACHE["expires_at"] = now + data.get("expires_in", 86000)
                return _APP_TOKEN_CACHE["token"]

    async def _raw_get(self, path: str, namespace: str, token: str):
        params = {"namespace": f"{namespace}-{self.region}", "locale": LOCALE}
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{_api_host(self.region)}{path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.json()

    async def _get_public(self, path: str, namespace: str):
        token = await self._get_app_token()
        return await self._raw_get(path, namespace, token)

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
        url = f"{_oauth_host(self.region)}/oauth/token"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data={"grant_type": "authorization_code", "code": code, "redirect_uri": BLIZZARD_REDIRECT_URI},
                auth=aiohttp.BasicAuth(BLIZZARD_CLIENT_ID, BLIZZARD_CLIENT_SECRET),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_account_wow_profile(self, user_token: str):
        """Tous les personnages du compte connecté."""
        return await self._raw_get("/profile/user/wow", "profile", user_token)

    async def get_character_equipment(self, realm_slug: str, name: str):
        path = f"/profile/wow/character/{realm_slug.lower()}/{name.lower()}/equipment"
        return await self._get_public(path, "profile")
