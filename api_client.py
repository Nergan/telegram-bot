import httpx
from .config import settings

class NetlazyAPI:
    def __init__(self, telegram_id: int):
        self.telegram_id = telegram_id
        self.base_url = settings.netlazy_api_url.rstrip('/') + '/netlazy/api'
        
    @property
    def headers(self):
        return {
            "X-Bot-Token": settings.netlazy_bot_token,
            "X-Telegram-Id": str(self.telegram_id),
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs):
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, f"{self.base_url}{path}", headers=self.headers, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Propagate specific errors to handlers
                raise e

    async def get_profile(self):
        return await self._request("GET", "/profile/me")

    async def get_feed(self, cursor: str = None):
        params = {}
        if cursor:
            params['cursor'] = cursor
        return await self._request("GET", "/feed", params=params)
        
    async def get_inbox(self):
        return await self._request("GET", "/inbox")

    # Static methods for operations not tied to an existing TG user session
    @staticmethod
    async def bot_register(public_key: str, telegram_id: int):
        async with httpx.AsyncClient() as client:
            url = f"{settings.netlazy_api_url.rstrip('/')}/netlazy/api/auth/bot/register"
            headers = {"X-Bot-Token": settings.netlazy_bot_token, "Content-Type": "application/json"}
            payload = {"public_key": public_key, "telegram_id": telegram_id}
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def bot_link(user_id: str, telegram_id: int):
        async with httpx.AsyncClient() as client:
            url = f"{settings.netlazy_api_url.rstrip('/')}/netlazy/api/auth/bot/link"
            headers = {"X-Bot-Token": settings.netlazy_bot_token, "Content-Type": "application/json"}
            payload = {"user_id": user_id, "telegram_id": telegram_id}
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    
    @staticmethod
    async def bot_unlink(telegram_id: int):
        async with httpx.AsyncClient() as client:
            url = f"{settings.netlazy_api_url.rstrip('/')}/netlazy/api/auth/bot/unlink"
            headers = {"X-Bot-Token": settings.netlazy_bot_token, "Content-Type": "application/json"}
            payload = {"telegram_id": telegram_id}
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()