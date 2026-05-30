from __future__ import annotations

import os
import time
from typing import Optional

import requests
from requests_oauthlib import OAuth1


class OAuth2TokenManager:
    """Client-credentials bearer token for image recognition, search, and food.get."""

    _TOKEN_URL = "https://oauth.fatsecret.com/connect/token"

    def __init__(self, client_id: str, client_secret: str, scope: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._token: Optional[str] = None
        self._expires_at: float = 0.0

    @classmethod
    def from_env(cls, scope: str = "premier image-recognition") -> "OAuth2TokenManager":
        return cls(
            client_id=os.environ["FATSECRET_CLIENT_ID"],
            client_secret=os.environ["FATSECRET_CLIENT_SECRET"],
            scope=scope,
        )

    def get_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at - 60:
            return self._token
        self._refresh()
        return self._token  # type: ignore[return-value]

    def _refresh(self) -> None:
        resp = requests.post(
            self._TOKEN_URL,
            data={"grant_type": "client_credentials", "scope": self._scope},
            auth=(self._client_id, self._client_secret),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.monotonic() + float(data.get("expires_in", 86400))

    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_token()}"}


class OAuth1Signer:
    """HMAC-SHA1 signed OAuth 1.0 auth for profile-scoped diary writes."""

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        self._auth = OAuth1(
            client_key=consumer_key,
            client_secret=consumer_secret,
            resource_owner_key=oauth_token,
            resource_owner_secret=oauth_token_secret,
            signature_method="HMAC-SHA1",
        )

    @classmethod
    def from_env(cls) -> "OAuth1Signer":
        return cls(
            consumer_key=os.environ["FATSECRET_CLIENT_ID"],
            consumer_secret=os.environ["FATSECRET_CLIENT_SECRET"],
            oauth_token=os.environ["FATSECRET_OAUTH_TOKEN"],
            oauth_token_secret=os.environ["FATSECRET_OAUTH_TOKEN_SECRET"],
        )

    @property
    def auth(self) -> OAuth1:
        return self._auth
