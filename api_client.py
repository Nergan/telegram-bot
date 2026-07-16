import httpx
import time
import uuid
import hashlib
import base64
import asyncio
from urllib.parse import urlencode
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from config import settings

class NetlazyAPI:
    def __init__(self, user_id: str, private_key_pem: str):
        self.user_id = user_id
        self.private_key_pem = private_key_pem
        self.base_url = settings.netlazy_api_url.rstrip('/') + '/netlazy/api'

    def _sign_payload(self, canonical_payload: str) -> str:
        private_key = serialization.load_pem_private_key(self.private_key_pem.encode('utf-8'), password=None)
        signature = private_key.sign(
            canonical_payload.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=32
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')

    async def _request(self, method: str, path: str, json_data=None, params=None, extra_headers=None):
        timestamp = str(int(time.time()))
        nonce = str(uuid.uuid4())

        body_bytes = b""
        if json_data:
            import json
            body_bytes = json.dumps(json_data, separators=(',', ':')).encode('utf-8')
        
        body_hash = hashlib.sha256(body_bytes).hexdigest()
        query_str = urlencode(params) if params else ""
        canonical_path = f"/netlazy/api{path}"
        canonical_payload = f"{method.upper()}\n{canonical_path}\n{query_str}\n{timestamp}\n{nonce}\n{body_hash}"
        signature = self._sign_payload(canonical_payload)

        headers = {
            "X-User-Id": self.user_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
            "X-Fingerprint": "telegram-bot-client",
            "Content-Type": "application/json"
        }
        if extra_headers:
            headers.update(extra_headers)

        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, 
                f"{self.base_url}{path}", 
                json=json_data, 
                params=params, 
                headers=headers
            )
            resp.raise_for_status()
            return resp.json()

    async def get_profile(self):
        return await self._request("GET", "/profile/me")

    async def get_feed(self, cursor: str = None):
        params = {}
        if cursor:
            params['cursor'] = cursor
        return await self._request("GET", "/feed", params=params)

    async def get_inbox(self):
        return await self._request("GET", "/inbox")

    @staticmethod
    async def solve_pow(challenge_id: str, difficulty: int) -> str:
        prefix = "0" * difficulty
        nonce = 0
        while True:
            payload = (challenge_id + str(nonce)).encode('utf-8')
            h = hashlib.sha256(payload).hexdigest()
            if h.startswith(prefix):
                return str(nonce)
            nonce += 1
            if nonce % 20000 == 0:
                await asyncio.sleep(0)

    @classmethod
    async def fetch_challenge(cls):
        async with httpx.AsyncClient() as client:
            url = f"{settings.netlazy_api_url.rstrip('/')}/netlazy/api/security/challenge"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def register(cls, public_key_pem: str) -> dict:
        challenge = await cls.fetch_challenge()
        pow_nonce = await cls.solve_pow(challenge["challenge_id"], challenge["difficulty"])

        url = f"{settings.netlazy_api_url.rstrip('/')}/netlazy/api/auth/register"
        headers = {
            "X-Challenge-Id": challenge["challenge_id"],
            "X-Pow-Nonce": pow_nonce,
            "X-Fingerprint": "telegram-bot-client",
            "Content-Type": "application/json"
        }
        payload = {"public_key": public_key_pem}
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()