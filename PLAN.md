# PLAN.md — Hermes plugin: photo → FatSecret food logging

A Hermes Agent plugin that receives a food photo, identifies the food, finds
nutrition via FatSecret, asks the user to confirm in chat, and logs the
confirmed food to the user's FatSecret food diary.

The plugin is personal/self-hosted = oneFatSecret profile.

This document is written to be handed to Claude Code. Work top to bottom. Do
**Phase 0** first — it resolves the two unknowns the rest of the design depends
on. Treat anything marked **VERIFY** as a fact to confirm against current docs,
not an assumption to build on.

---

## 1. Core design decisions (read before coding)

Two facts shape the whole design:

1. **FatSecret has its own Image Recognition API.** It takes a base64 image and
   returns detected foods linked to verified database entries *with nutrition
   and the `food_id` / `serving_id` needed to log them*. This collapses
   "identify the food" + "find matches + nutrition" into one purpose-built call
   and is more accurate for nutrition than guessing with a vision model and then
   text-searching. Request body is limited to ~1 MB; it takes `image_b64`,
   `include_food_data`, optional `eaten_foods`, `region`, `language`. The only
   storable values it returns are `food_id` and `serving_id`.

2. **Confirmation is tool decomposition, not a special mechanism.** Hermes is a
   conversational agent, so "ask the user, then log" is achieved by splitting the
   work into separate tools: one that *identifies and proposes* (no writes) and
   one that *logs* (the write). The log tool's schema instructs the model to call
   it only after explicit user confirmation. The agent's normal chat loop becomes
   the human-in-the-loop — no pause/resume primitive needed.

**Recognition strategy:** FatSecret Image Recognition is the primary path
(returns directly-loggable IDs + verified nutrition). Hermes' own vision model is
a *fallback* only: when recognition misses, the agent's text description of the
meal is routed into `search_food`, not into the primary path.

**State between tools:** stateless preferred — the model carries the chosen
`food_id` / `serving_id` forward from the analyze result into the log call. Keep
at most a small per-session cache keyed on `task_id` for serving disambiguation,
never as the source of truth.

---

## 2. Runtime data flow

```
food photo (inbound message)
        │
        ▼
analyze_food_photo  ──calls──►  FatSecret Image Recognition  (identify, NO write)
        │                       returns: candidates + servings + nutrition + ids
        ▼
agent presents candidates + calories in chat
        │
        ▼
USER CONFIRMS / CORRECTS   ◄── search_food (correction path) if recognition wrong
        │
        ▼
log_food_entry  ──calls──►  FatSecret food_entry.create  (write to diary)
        │
        ▼
agent confirms back: "Logged X to <meal>, N kcal"
```

---

## 3. The three tools

Hermes calls handlers as `def handler(args: dict, **kwargs) -> str` that **always
return a JSON string** and **never raise** (catch everything, return error JSON).
Accept `**kwargs` for forward compatibility.

### `analyze_food_photo`
- **Purpose:** identify food in a photo and return ranked candidates. **No writes.**
- **Input (args):** image reference (path/id/bytes — exact shape decided in Phase 0),
  optional `region`, `language`, optional `meal_hint`.
- **Behavior:** downscale image to stay under ~1 MB → base64 → FatSecret Image
  Recognition with `include_food_data=true` → normalize results.
- **Returns:** list of candidates `{ food_id, food_name, brand, servings:[{serving_id,
  description, calories, macros}], confidence }`.
- **Schema description must say:** present these to the user and ask them to confirm
  the food and serving before anything is logged.

### `search_food`
- **Purpose:** correction / manual override ("that's not pizza, it's focaccia").
- **Input (args):** `query` string, optional `region`, `language`.
- **Behavior:** call `foods.search` (and/or autocomplete) → return candidates in the
  **same shape** as `analyze_food_photo`.

### `log_food_entry`
- **Purpose:** write a confirmed entry to the user's diary. **This is the only write.**
- **Input (args):** `food_id`, `serving_id`, `quantity` (number of servings),
  `meal` (breakfast/lunch/dinner/other), `date` (default: today, timezone-aware).
- **Behavior:** call `food_entry.create` for the user's profile.
- **Returns:** `{ status, food_entry_id, logged_food_name, meal, date, calories }`.
- **Schema description must say:** ONLY call after the user has explicitly confirmed
  the specific food and serving from a prior `analyze_food_photo` / `search_food`
  result. Never call speculatively.

Optionally bundle a Hermes **skill** (`skills/log-food-from-photo/SKILL.md`) that
codifies the workflow: identify → present options with calories → wait for explicit
pick → log → confirm back. This keeps the confirmation discipline robust across models.

---

## 4. Plugin file layout

```
~/.hermes/plugins/fatsecret-food/
├── plugin.yaml          # manifest: provides_tools, requires_env (FatSecret creds)
├── __init__.py          # register(ctx): wire 3 tools + optional post_tool_call hook
├── schemas.py           # the 3 tool schemas the LLM reads
├── tools.py             # the 3 handlers (thin — delegate to the client below)
├── fatsecret/           # standalone client (no Hermes imports)
│   ├── auth.py          # token acquisition + refresh, profile/3-legged handling
│   ├── client.py        # image_recognition, foods.search, food.get, food_entry.create
│   └── models.py        # typed result/candidate normalization
├── skills/
│   └── log-food-from-photo/SKILL.md
├── tests/
│   └── fixtures/        # recorded FatSecret responses for offline tests
└── README.md
```

`plugin.yaml` should use `requires_env` (rich format) for the FatSecret
credentials so Hermes prompts for them at install and disables the plugin cleanly
if they're missing.

---

## 5. Phase 0 — resolve unknowns first (spikes)

Do these before writing tool signatures or auth code. Each produces a written
finding that the later phases consume.

- [ ] **0.1 — Image ingestion path.** Read the Hermes messaging/attachment code
  (Telegram/Discord/CLI gateways). Determine exactly how an inbound photo reaches
  a tool handler: is the attachment saved to a path the handler can read, passed
  via `**kwargs`/context, or retrievable through an API? The model sees the image,
  but the handler only gets LLM-supplied `args` + `**kwargs`. **Output:** the
  concrete mechanism + the decided `args` shape for `analyze_food_photo`.
- [ ] **0.2 — FatSecret app + auth shape.** Create/confirm a FatSecret Platform
  app. **VERIFY** whether a single OAuth 2.0 token (with the right scopes plus a
  profile / 3-legged flow) can cover *both* `image-recognition` *and* the
  profile-scoped diary write (`food_entry.create`), or whether two auth paths are
  required (OAuth 2.0 for recognition, OAuth 1.0 / 3-legged delegated for the
  diary). Note that image recognition is a **paid add-on** for Premier / Premier
  Free with a 14-day trial — confirm the account tier. **Output:** the auth flow
  diagram + which scopes/tier are needed.
- [ ] **0.3 — Method/version confirmation.** **VERIFY** current method names and
  versions: `food_entry.create` vs a v2 `food_entries` path; Image Recognition v1
  vs v2 endpoint; `foods.search` vs `foods.search.v3`. **Output:** the exact
  endpoints/methods to call.

---

## 6. Phase 1 — FatSecret client (standalone, no Hermes)

Build and test the entire API surface independently of the plugin contract.

- [ ] 1.1 — `auth.py`: token acquisition + refresh per Phase 0.2 finding; secure
  credential loading from env; profile handling per 0.3.
- [ ] 1.2 — `client.image_recognition(image_b64, include_food_data, region, language,
  eaten_foods=None)`; enforce the ~1 MB body limit (downscale/compress before encode).
- [ ] 1.3 — `client.search_foods(query, region, language)` and `client.get_food(food_id)`.
- [ ] 1.4 — `client.create_food_entry(food_id, serving_id, quantity, meal, date)`.
- [ ] 1.5 — `models.py`: normalize recognition + search results into one candidate shape.
- [ ] 1.6 — Unit tests against recorded fixtures (no live calls in CI). Cover: a
  good recognition, multi-item, empty/ambiguous, error 211 (nutrition-label-only),
  and a successful log.

**Exit:** the client can recognize, search, fetch, and log against fixtures and a
manual live smoke test.

---

## 7. Phase 2 — plugin scaffold + `analyze_food_photo`

- [ ] 2.1 — `plugin.yaml` manifest with `provides_tools` and `requires_env`.
- [ ] 2.2 — `schemas.py`: schema for `analyze_food_photo` (clear, specific
  description; image-input param matching the Phase 0.1 mechanism).
- [ ] 2.3 — `tools.py`: `analyze_food_photo` handler → reads image (per 0.1) →
  calls the Phase 1 client → returns candidate JSON. Catch-all error handling.
- [ ] 2.4 — `__init__.py`: `register(ctx)` wiring the tool via `ctx.register_tool(...)`.
- [ ] 2.5 — Manual test: send a photo in a Hermes session, confirm candidates come
  back with names + calories. **No logging yet.**

**Exit:** photo in → candidates in chat.

---

## 8. Phase 3 — `log_food_entry` + `search_food` + confirmation UX

- [ ] 3.1 — `search_food` schema + handler (same candidate shape as analyze).
- [ ] 3.2 — `log_food_entry` schema + handler; schema description enforces
  "confirm first." Handler calls `create_food_entry`.
- [ ] 3.3 — `skills/log-food-from-photo/SKILL.md`: the identify → present → confirm
  → log → confirm-back workflow; register it via `ctx.register_skill(...)`.
- [ ] 3.4 — Tune schema descriptions and test that the model reliably waits for an
  explicit user pick before logging, and uses `search_food` when the user corrects it.

**Exit:** full identify → confirm → log loop works end to end.

---

## 9. Phase 4 — robustness

- [ ] 4.1 — Multi-item meals: one photo, several foods; confirm/log each (or as a
  group) without losing track of which `food_id` maps to which item.
- [ ] 4.2 — Serving size + quantity selection: surface serving options, let the
  user pick serving and number of servings.
- [ ] 4.3 — Error handling: error 211 (nutrition-label-only image), empty/ambiguous
  recognition, oversized image (auto-downscale under ~1 MB), auth/token-refresh
  failures, network timeouts. Every failure returns a clear, user-facing message.
- [ ] 4.4 — Meal-type + date inference: default meal from time of day, date =
  today in the user's timezone; allow override in the confirm step.
- [ ] 4.5 — Idempotency: a retried `log_food_entry` (same food/serving/meal/date
  within a short window) must not create a duplicate diary entry.
- [ ] 4.6 — Localization: respect `region` / `language` (relevant for bilingual
  use); make defaults configurable.

---

## 10. Phase 5 — packaging + observability

- [ ] 5.1 — `README.md`: install steps, required env vars, FatSecret app setup,
  scope/tier notes, troubleshooting.
- [ ] 5.2 — `post_tool_call` hook logging latency + usage (slots into an existing
  metrics/observability stack if present).
- [ ] 5.3 — Config: defaults for region/language/meal inference.
- [ ] 5.4 — Test pass (unit + a scripted manual e2e checklist).
- [ ] 5.5 — Optional: distribute via pip entry point
  (`[project.entry-points."hermes_agent.plugins"]`).

---

## 11. Key decisions to lock before coding

- **Recognition primary = FatSecret Image Recognition;** vision model only as a
  fallback feeding `search_food`.
- **Stateless tool chaining;** model carries `food_id`/`serving_id` forward.
- **One auth path or two** (Phase 0.2) — affects `auth.py` complexity.

---

## 12. Open questions / things to VERIFY against current docs

- Whether one OAuth 2.0 token can cover both `image-recognition` and the
  profile-scoped diary write, or two auth flows are required. (Phase 0.2)
- Exact current method names/versions: `food_entry.create` vs v2 `food_entries`;
  IR v1 vs v2; `foods.search` vs `.v3`. (Phase 0.4)
- The precise Hermes mechanism for a tool handler to access an inbound image. (Phase 0.1)
- FatSecret account tier / image-recognition add-on availability and cost.

---

## 13. References

- Hermes — Build a Plugin: https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin
- Hermes — Plugins overview: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- Hermes — Event hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- FatSecret — Platform API: https://platform.fatsecret.com/platform-api
- FatSecret — Image Recognition: https://platform.fatsecret.com/docs/v1/image.recognition
- FatSecret — OAuth 2.0: https://platform.fatsecret.com/docs/guides/authentication/oauth2
- FatSecret — Authentication guide (profiles / delegated): https://platform.fatsecret.com/docs/guides/authentication
