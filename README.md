# fatsecret-food — Hermes plugin

Photo → FatSecret food logging in three tools:

| Tool | What it does |
|---|---|
| `analyze_food_photo` | Identify food via FatSecret Image Recognition. **No writes.** |
| `search_food` | Search by name (correction / manual entry). **No writes.** |
| `log_food_entry` | Write confirmed entry to diary. **Only write.** |

---

## Install

```bash
pip install requests requests-oauthlib Pillow
cp -r . ~/.hermes/plugins/fatsecret-food
```

Or with the pip entry-point (if packaged):
```bash
pip install fatsecret-food-hermes
```

---

## Required environment variables

| Variable | Description |
|---|---|
| `FATSECRET_CLIENT_ID` | Platform API client ID |
| `FATSECRET_CLIENT_SECRET` | Platform API client secret |
| `FATSECRET_OAUTH_TOKEN` | Profile OAuth 1.0 token |
| `FATSECRET_OAUTH_TOKEN_SECRET` | Profile OAuth 1.0 token secret |

---

## FatSecret app setup

1. Register at [platform.fatsecret.com](https://platform.fatsecret.com/api/Default.aspx).
2. Create an app — note the **Client ID** and **Client Secret**.
3. Enable the **Image Recognition** add-on (Premier / Premier Free tier, 14-day trial available).
4. Run the one-time profile setup to obtain `FATSECRET_OAUTH_TOKEN` / `FATSECRET_OAUTH_TOKEN_SECRET`:

```python
# run once
import requests
from requests_oauthlib import OAuth1

auth = OAuth1(
    client_key="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    # no resource_owner_key/secret for profile.create
)
resp = requests.get(
    "https://platform.fatsecret.com/rest/server.api",
    params={"method": "profile.create", "format": "json"},
    auth=auth,
)
profile = resp.json()["profile"]
print("FATSECRET_OAUTH_TOKEN =", profile["auth_token"])
print("FATSECRET_OAUTH_TOKEN_SECRET =", profile["auth_secret"])
```

Set those two values in your shell or Hermes config and you're done.

---

## Auth architecture

Two auth flows run in parallel:

- **OAuth 2.0 client credentials** (`FATSECRET_CLIENT_ID` + `FATSECRET_CLIENT_SECRET`)  
  Used for: Image Recognition, `foods.search`, `food.get`  
  Token auto-refreshes every ~24 h.

- **OAuth 1.0 HMAC-SHA1 signed + delegated** (all four vars)  
  Used for: `food_entry.create` (diary writes require a profile token)

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

Override defaults via environment variables:

| Variable | Default | Description |
|---|---|---|
| `FATSECRET_REGION` | `US` | Default region for search / recognition |
| `FATSECRET_LANGUAGE` | `en` | Default language for results |

---

## Running tests

```bash
cd ~/.hermes/plugins/fatsecret-food
pip install requests requests-oauthlib
python -m pytest tests/ -v
```

Tests run fully offline against recorded fixtures in `tests/fixtures/`.

---

## Troubleshooting

**"No food detected" on every photo**  
→ Image recognition add-on may not be enabled on your FatSecret app — check your Premier tier status.

**HTTP 401 on diary writes**  
→ Your `FATSECRET_OAUTH_TOKEN` / `FATSECRET_OAUTH_TOKEN_SECRET` are stale or wrong. Re-run the profile setup script above.

**Image too large error**  
→ The plugin auto-downscales via Pillow. Install Pillow if not present: `pip install Pillow`.
