#!/usr/bin/env python3
"""
One-time setup: link this plugin to your existing fatsecret.com account.

Usage:
    FATSECRET_CLIENT_ID=xxx FATSECRET_CLIENT_SECRET=yyy python3 setup_auth.py

Prints the two env vars to add to your shell profile / Hermes config.
"""
import os
import webbrowser

from requests_oauthlib import OAuth1Session

REQUEST_TOKEN_URL = "https://authentication.fatsecret.com/oauth/request_token"
AUTHORIZE_URL = "https://authentication.fatsecret.com/oauth/authorize"
ACCESS_TOKEN_URL = "https://authentication.fatsecret.com/oauth/access_token"


def main() -> None:
    client_id = os.environ.get("FATSECRET_CLIENT_ID") or input("FATSECRET_CLIENT_ID: ").strip()
    client_secret = os.environ.get("FATSECRET_CLIENT_SECRET") or input("FATSECRET_CLIENT_SECRET: ").strip()

    # Step 1 — get a request token (oob = PIN flow, no web server needed)
    oauth = OAuth1Session(client_id, client_secret=client_secret, callback_uri="oob")
    resp = oauth.fetch_request_token(REQUEST_TOKEN_URL)
    request_token = resp["oauth_token"]
    request_token_secret = resp["oauth_token_secret"]

    # Step 2 — send the user to fatsecret.com to log in and authorize
    auth_url = f"{AUTHORIZE_URL}?oauth_token={request_token}"
    print(f"\nOpening FatSecret authorization page in your browser...")
    print(f"If it doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    # Step 3 — user pastes the PIN shown by FatSecret after authorizing
    verifier = input("Paste the PIN shown by FatSecret: ").strip()

    # Step 4 — exchange for a permanent access token
    oauth = OAuth1Session(
        client_id,
        client_secret=client_secret,
        resource_owner_key=request_token,
        resource_owner_secret=request_token_secret,
        verifier=verifier,
    )
    tokens = oauth.fetch_access_token(ACCESS_TOKEN_URL)

    print("\nSuccess! Add these to your shell profile or Hermes .env:\n")
    print(f"export FATSECRET_OAUTH_TOKEN={tokens['oauth_token']}")
    print(f"export FATSECRET_OAUTH_TOKEN_SECRET={tokens['oauth_token_secret']}")


if __name__ == "__main__":
    main()
