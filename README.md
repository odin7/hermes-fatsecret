# fatsecret-food — Hermes plugin

Photo → FatSecret food logging in three tools:

| Tool | What it does |
|---|---|
| `analyze_food_photo` | Identify food via FatSecret Image Recognition. **No writes.** |
| `search_food` | Search by name (correction / manual entry). **No writes.** |
| `log_food_entry` | Write confirmed entry to diary. **Only write.** |

---

## Install

Symlink (recommended — edits to the repo are reflected immediately):

```bash
ln -s "$(pwd)" ~/.hermes/hermes-agent/plugins/fatsecret-food
```

Or copy:

```bash
pip install requests requests-oauthlib Pillow
cp -r . ~/.hermes/hermes-agent/plugins/fatsecret-food
```

---

## Required environment variables

| Variable | Description |
|---|---|
| `FATSECRET_CLIENT_ID` | Platform API client ID (= OAuth 1.0 Consumer Key) |
| `FATSECRET_CLIENT_SECRET` | Platform API client secret (= OAuth 1.0 Consumer Secret) |
| `FATSECRET_OAUTH_TOKEN` | Profile OAuth 1.0 access token (from setup below) |
| `FATSECRET_OAUTH_TOKEN_SECRET` | Profile OAuth 1.0 access token secret (from setup below) |

---

## FatSecret app setup

1. Register at [platform.fatsecret.com](https://platform.fatsecret.com/api/Default.aspx).
2. Create an app — your app page shows a **Client ID / Client Secret** pair. FatSecret uses the same credentials for both OAuth 2.0 (image recognition, search) and OAuth 1.0 (diary writes); they're also labelled "Consumer Key / Consumer Secret" in OAuth 1.0 contexts — same values.
3. Enable the **Image Recognition** add-on (Premier / Premier Free tier, 14-day trial available).
4. Run the one-time auth setup to link the plugin to your **existing fatsecret.com account**:

```bash
FATSECRET_CLIENT_ID=xxx FATSECRET_CLIENT_SECRET=yyy python3 setup_auth.py
```

This opens fatsecret.com in your browser, you log in and click Allow, then paste the PIN back into the terminal. It prints the two env vars to store:

```
export FATSECRET_OAUTH_TOKEN=...
export FATSECRET_OAUTH_TOKEN_SECRET=...
```

Add all four vars to your shell profile or Hermes `.env` — you only need to do this once.

---

## Auth architecture

Both auth flows use the same `FATSECRET_CLIENT_ID` / `FATSECRET_CLIENT_SECRET` credentials:

- **OAuth 2.0 client credentials** — used for Image Recognition, `foods.search`, `food.get`. Token auto-refreshes every ~24 h.
- **OAuth 1.0 HMAC-SHA1 signed + delegated** (all four vars) — used for `food_entry.create` (diary writes require a profile token).

---

## Endpoints used

| Operation | Endpoint |
|---|---|
| Image recognition | `POST /rest/image-recognition/v1` |
| Food search | `GET /rest/foods/search/v5` |
| Food detail | `GET /rest/food/v5` |
| Log entry | `POST /rest/food-entries/v1` |

---

## Configuration (optional)

| Variable | Default | Description |
|---|---|---|
| `FATSECRET_RECOGNITION_BACKEND` | `fatsecret` | `fatsecret` uses the Image Recognition API; `hermes` uses the model's vision + text search (no add-on required) |

Region and language are not env vars — pass them per call via the `region` / `language` tool arguments (default `US` / `en`).

---

## Running tests

```bash
cd ~/.hermes/hermes-agent/plugins/fatsecret-food
pip install requests requests-oauthlib
python -m pytest tests/ -v
```

Tests run fully offline against recorded fixtures in `tests/fixtures/`.

---

## Troubleshooting

**"No food detected" on every photo**  
→ Image recognition add-on may not be enabled on your FatSecret app — check your Premier tier status.

**HTTP 401 on diary writes**  
→ Your `FATSECRET_OAUTH_TOKEN` / `FATSECRET_OAUTH_TOKEN_SECRET` are stale or wrong. Re-run `setup_auth.py`.

**Image too large error**  
→ The plugin auto-downscales via Pillow. Install Pillow if not present: `pip install Pillow`.
