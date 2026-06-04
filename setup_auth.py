#!/usr/bin/env python3
"""
One-time setup: link this plugin to your existing fatsecret.com account.

FatSecret issues TWO separate credential pairs:
  - OAuth 2.0  → Client ID + Client Secret  (image recognition, food search)
  - OAuth 1.0  → Consumer Key + Consumer Secret  (diary writes — needed here)

Find your Consumer Key and Consumer Secret at platform.fatsecret.com → your app.

Usage:
    FATSECRET_CONSUMER_KEY=xxx FATSECRET_CONSUMER_SECRET=yyy python3 setup_auth.py

Prints the two env vars to add to your shell profile / Hermes config.

Set OAUTH_DEBUG=1 to print signature details for troubleshooting.
"""
import base64
import hashlib
import hmac
import os
import time
import uuid
import urllib.parse
import webbrowser

import requests

REQUEST_TOKEN_URL = "https://authentication.fatsecret.com/oauth/request_token"
AUTHORIZE_URL = "https://authentication.fatsecret.com/oauth/authorize"
ACCESS_TOKEN_URL = "https://authentication.fatsecret.com/oauth/access_token"

DEBUG = os.environ.get("OAUTH_DEBUG") == "1"


def _pct(s: str) -> str:
    return urllib.parse.quote(str(s), safe="")


def _sign(method: str, url: str, params: dict, consumer_secret: str, token_secret: str = "") -> str:
    param_str = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in sorted(params.items()))
    base = "&".join([method.upper(), _pct(url), _pct(param_str)])
    key = f"{_pct(consumer_secret)}&{_pct(token_secret)}"
    if DEBUG:
        print(f"\n[DEBUG] method={method}  url={url}")
        print(f"[DEBUG] params={sorted(params.items())}")
        print(f"[DEBUG] base_string={base}")
        print(f"[DEBUG] signing_key={key}")
    digest = hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def _base_params(consumer_key: str, **extra) -> dict:
    return {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
        **extra,
    }


def _token_request(method: str, url: str, params: dict,
                   consumer_secret: str, token_secret: str = "") -> dict:
    params["oauth_signature"] = _sign(method, url, params, consumer_secret, token_secret)

    if method.upper() == "POST":
        # Send OAuth params in the request body (application/x-www-form-urlencoded)
        r = requests.post(url, data=params)
    else:
        # Send OAuth params in the query string
        qs = "&".join(f"{_pct(k)}={_pct(v)}" for k, v in params.items())
        r = requests.get(f"{url}?{qs}")

    if DEBUG:
        print(f"[DEBUG] response {r.status_code}: {r.text[:300]}")

    if not r.ok:
        raise SystemExit(f"Token request failed {r.status_code}: {r.text}")

    parsed = dict(urllib.parse.parse_qsl(r.text))
    if not parsed:
        raise SystemExit(f"Unexpected response (expected key=value pairs): {r.text!r}")
    return parsed


def main() -> None:
    # OAuth 1.0 Consumer Key/Secret — distinct from OAuth 2.0 Client ID/Secret
    client_id = (
        os.environ.get("FATSECRET_CONSUMER_KEY")
        or os.environ.get("FATSECRET_CLIENT_ID")
        or input("FATSECRET_CONSUMER_KEY: ").strip()
    )
    client_secret = (
        os.environ.get("FATSECRET_CONSUMER_SECRET")
        or os.environ.get("FATSECRET_CLIENT_SECRET")
        or input("FATSECRET_CONSUMER_SECRET: ").strip()
    )

    # Step 1 — request token
    # FatSecret docs: POST to authentication.fatsecret.com/oauth/request_token
    params = _base_params(client_id, oauth_callback="oob")
    resp = _token_request("POST", REQUEST_TOKEN_URL, params, client_secret)
    request_token = resp["oauth_token"]
    request_token_secret = resp["oauth_token_secret"]

    # Step 2 — authorize
    auth_url = f"{AUTHORIZE_URL}?oauth_token={request_token}"
    print("\nOpening FatSecret authorization page in your browser...")
    print(f"If it doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    # Step 3 — PIN
    verifier = input("Paste the PIN shown by FatSecret: ").strip()

    # Step 4 — access token
    # FatSecret docs: GET to authentication.fatsecret.com/oauth/access_token
    params = _base_params(client_id, oauth_token=request_token, oauth_verifier=verifier)
    tokens = _token_request("GET", ACCESS_TOKEN_URL, params, client_secret, request_token_secret)

    print("\nSuccess! Add these to your shell profile or Hermes .env:\n")
    print(f"export FATSECRET_OAUTH_TOKEN={tokens['oauth_token']}")
    print(f"export FATSECRET_OAUTH_TOKEN_SECRET={tokens['oauth_token_secret']}")


if __name__ == "__main__":
    main()
