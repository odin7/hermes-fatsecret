#!/usr/bin/env python3
"""
Minimal OAuth 1.0 test for food_entry.create.
Uses the same HMAC-SHA1 signing as setup_auth.py (no requests_oauthlib).
Sends a dummy food_id=1 — expect error 4/10/etc., NOT error 8 if signing is OK.

Usage (credentials must be in env):
    python3 debug_oauth.py
"""
import base64
import hashlib
import hmac
import os
import time
import uuid
import urllib.parse

import requests


def _pct(s: str) -> str:
    return urllib.parse.quote(str(s), safe="")


def _sign(method: str, url: str, params: dict, consumer_secret: str, token_secret: str) -> str:
    param_str = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in sorted(params.items()))
    base = "&".join([method.upper(), _pct(url), _pct(param_str)])
    key = f"{_pct(consumer_secret)}&{_pct(token_secret)}"
    digest = hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


consumer_key    = os.environ["FATSECRET_CLIENT_ID"]
consumer_secret = os.environ["FATSECRET_CLIENT_SECRET"]
oauth_token     = os.environ["FATSECRET_OAUTH_TOKEN"]
token_secret    = os.environ["FATSECRET_OAUTH_TOKEN_SECRET"]

URL = "https://platform.fatsecret.com/rest/server.api"

body_params = {
    "method":           "food_entry.create",
    "food_id":          "1",           # dummy — triggers data error, not auth error
    "serving_id":       "1",
    "number_of_units":  "1",
    "meal":             "breakfast",
    "food_entry_name":  "Test",
    "date":             "20604",       # 2026-05-30
    "format":           "json",
}

oauth_params = {
    "oauth_consumer_key":     consumer_key,
    "oauth_nonce":            uuid.uuid4().hex,
    "oauth_signature_method": "HMAC-SHA1",
    "oauth_timestamp":        str(int(time.time())),
    "oauth_token":            oauth_token,
    "oauth_version":          "1.0",
}

all_params = {**body_params, **oauth_params}
sig = _sign("POST", URL, all_params, consumer_secret, token_secret)
oauth_params["oauth_signature"] = sig

auth_header = "OAuth " + ", ".join(
    f'{k}="{_pct(v)}"' for k, v in sorted(oauth_params.items())
)

print("Authorization:", auth_header[:120], "...")
print("Body:", body_params)
print()

resp = requests.post(URL, data=body_params, headers={"Authorization": auth_header})
print("HTTP status:", resp.status_code)
print("Response:", resp.text)
