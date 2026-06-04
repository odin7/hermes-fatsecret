#!/usr/bin/env python3
"""
Minimal OAuth 1.0 test for food_entry.create.
Reuses the HMAC-SHA1 signing helpers from setup_auth.py (no requests_oauthlib).
Sends a dummy food_id=1 — expect error 4/10/etc., NOT error 8 if signing is OK.

Usage (credentials must be in env):
    python3 debug_oauth.py
"""
import os
import time
import uuid

import requests

from setup_auth import _pct, _sign

URL = "https://platform.fatsecret.com/rest/server.api"


def main() -> None:
    consumer_key = os.environ["FATSECRET_CLIENT_ID"]
    consumer_secret = os.environ["FATSECRET_CLIENT_SECRET"]
    oauth_token = os.environ["FATSECRET_OAUTH_TOKEN"]
    token_secret = os.environ["FATSECRET_OAUTH_TOKEN_SECRET"]

    body_params = {
        "method":           "food_entry.create",
        "food_id":          "1",           # dummy — triggers data error, not auth error
        "serving_id":       "1",
        "number_of_units":  "1",
        "meal":             "breakfast",
        "food_entry_name":  "Test",
        "date":             "20604",       # 2026-05-31
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
    oauth_params["oauth_signature"] = _sign("POST", URL, all_params, consumer_secret, token_secret)

    auth_header = "OAuth " + ", ".join(
        f'{k}="{_pct(v)}"' for k, v in sorted(oauth_params.items())
    )

    print("Authorization:", auth_header[:120], "...")
    print("Body:", body_params)
    print()

    resp = requests.post(URL, data=body_params, headers={"Authorization": auth_header})
    print("HTTP status:", resp.status_code)
    print("Response:", resp.text)


if __name__ == "__main__":
    main()
