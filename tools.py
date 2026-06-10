from __future__ import annotations

import json
import os
from datetime import date, datetime
from functools import lru_cache
from typing import Any

if __package__:
    # Loaded as a package submodule (installed plugin / `from . import tools`).
    from .fatsecret.client import FatSecretClient
else:
    # Loaded flat (tests do `import tools` with the repo root on sys.path).
    from fatsecret.client import FatSecretClient


@lru_cache(maxsize=1)
def _client() -> FatSecretClient:
    return FatSecretClient.from_env()


def _default_meal() -> str:
    hour = datetime.now().hour
    if hour < 11:
        return "breakfast"
    if hour < 15:
        return "lunch"
    return "dinner"


# Phase 4.5: simple in-session idempotency guard
_logged_this_session: set[tuple] = set()


def _recognition_backend() -> str:
    return os.environ.get("FATSECRET_RECOGNITION_BACKEND", "fatsecret").lower()


def analyze_food_photo(args: dict, **kwargs: Any) -> str:
    """Identify food in a photo. Backend selected by FATSECRET_RECOGNITION_BACKEND."""
    backend = _recognition_backend()
    if backend == "hermes":
        return _analyze_hermes(args, **kwargs)
    return _analyze_fatsecret(args, **kwargs)


def _analyze_fatsecret(args: dict, **kwargs: Any) -> str:
    image_source = (
        args.get("image_path")
        or args.get("image_url")
        or _extract_attachment(kwargs)
    )
    if not image_source:
        return json.dumps({"error": "No image provided. Pass image_path or share a photo."})

    region = args.get("region", "US")
    language = args.get("language", "en")
    meal_hint = args.get("meal_hint") or _default_meal()

    try:
        candidates = _client().image_recognition(image_source, region=region, language=language)
    except Exception as exc:  # noqa: BLE001
        return _handle_api_error(exc, context="image recognition")

    if not candidates:
        return json.dumps({
            "status": "no_food_detected",
            "message": (
                "No food was detected in this photo. "
                "Try a clearer shot or describe the food so I can search for it."
            ),
        })

    return json.dumps({
        "status": "ok",
        "backend": "fatsecret",
        "meal_hint": meal_hint,
        "candidates": [c.to_dict() for c in candidates],
        "instruction": (
            "Present these candidates to the user. Ask them to confirm the food, "
            "serving size, and quantity before logging."
        ),
    })


def _analyze_hermes(args: dict, **kwargs: Any) -> str:
    description = args.get("description", "").strip()
    if not description:
        return json.dumps({
            "error": (
                "FATSECRET_RECOGNITION_BACKEND is set to 'hermes'. "
                "Look at the image and describe the food(s) you see, "
                "then call this tool again with the description."
            )
        })

    region = args.get("region", "US")
    language = args.get("language", "en")
    meal_hint = args.get("meal_hint") or _default_meal()

    try:
        candidates = _client().search_foods(description, region=region, language=language)
    except Exception as exc:  # noqa: BLE001
        return _handle_api_error(exc, context="food search")

    if not candidates:
        return json.dumps({
            "status": "no_results",
            "message": f"No FatSecret matches for '{description}'. Try a more specific description.",
        })

    return json.dumps({
        "status": "ok",
        "backend": "hermes",
        "meal_hint": meal_hint,
        "candidates": [c.to_dict() for c in candidates],
        "instruction": (
            "Present these candidates to the user. Ask them to confirm the food, "
            "serving size, and quantity before logging."
        ),
    })


def search_food(args: dict, **kwargs: Any) -> str:
    """Search FatSecret by name. Used for corrections and manual overrides."""
    query = args.get("query", "").strip()
    if not query:
        return json.dumps({"error": "query is required."})

    region = args.get("region", "US")
    language = args.get("language", "en")

    try:
        candidates = _client().search_foods(query, region=region, language=language)
    except Exception as exc:  # noqa: BLE001
        return _handle_api_error(exc, context="food search")

    if not candidates:
        return json.dumps({
            "status": "no_results",
            "message": f"No foods found for '{query}'. Try a different name.",
        })

    return json.dumps({
        "status": "ok",
        "query": query,
        "candidates": [c.to_dict() for c in candidates],
    })


def log_food_entry(args: dict, **kwargs: Any) -> str:
    """Write a confirmed food entry to the diary. ONLY call after user confirmation."""
    food_id = str(args.get("food_id", "")).strip()
    serving_id = str(args.get("serving_id", "")).strip()
    food_entry_name = str(args.get("food_entry_name", "")).strip()

    if not food_id or not serving_id or not food_entry_name:
        return json.dumps({"error": "food_id, serving_id, and food_entry_name are required."})

    try:
        quantity = float(args.get("quantity", 1))
    except (TypeError, ValueError):
        return json.dumps({"error": "quantity must be a number."})

    meal = str(args.get("meal", "") or _default_meal()).lower()
    if meal not in {"breakfast", "lunch", "dinner", "other"}:
        meal = _default_meal()

    entry_date: date | None = None
    if args.get("date"):
        try:
            entry_date = date.fromisoformat(str(args["date"]))
        except ValueError:
            return json.dumps({"error": f"Invalid date format: {args['date']}. Use YYYY-MM-DD."})

    if entry_date is None:
        entry_date = datetime.now().date()

    # Phase 4.5: idempotency guard — skip duplicate within same session
    dedup_key = (food_id, serving_id, meal, entry_date.isoformat())
    if dedup_key in _logged_this_session:
        return json.dumps({
            "status": "duplicate_skipped",
            "message": (
                f"'{food_entry_name}' for {meal} on {entry_date} was already logged "
                "in this session. No duplicate entry created."
            ),
        })

    try:
        result = _client().create_food_entry(
            food_id=food_id,
            serving_id=serving_id,
            number_of_units=quantity,
            meal=meal,
            food_entry_name=food_entry_name,
            entry_date=entry_date,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_api_error(exc, context="logging food entry")

    _logged_this_session.add(dedup_key)
    return json.dumps(result.to_dict())


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _extract_attachment(kwargs: dict) -> str | None:
    """Try to find an image path from Hermes gateway kwargs."""
    # Hermes may pass attachment paths under various keys
    for key in ("attachment_paths", "attachments", "media_paths"):
        val = kwargs.get(key)
        if val:
            if isinstance(val, (list, tuple)) and val:
                return str(val[0])
            if isinstance(val, str):
                return val
    # Some gateways inject a 'message' dict with media metadata
    msg = kwargs.get("message") or {}
    if isinstance(msg, dict):
        for key in ("photo_path", "file_path", "image_path"):
            if msg.get(key):
                return str(msg[key])
    return None


def _handle_api_error(exc: Exception, context: str) -> str:
    import requests as req_lib

    if isinstance(exc, req_lib.HTTPError):
        status = exc.response.status_code if exc.response is not None else "?"
        try:
            body = exc.response.json() if exc.response is not None else {}
        except Exception:
            body = {}
        api_code = (body.get("error") or {}).get("code", "")
        api_msg = (body.get("error") or {}).get("message", str(exc))

        if str(api_code) == "211":
            return json.dumps({
                "status": "no_food_detected",
                "message": (
                    "FatSecret couldn't identify food in this image (error 211). "
                    "Try a closer shot or describe the food so I can search for it."
                ),
            })

        return json.dumps({"error": f"{context} failed (HTTP {status}): {api_msg}"})

    if isinstance(exc, req_lib.Timeout):
        return json.dumps({"error": f"{context} timed out. Please try again."})

    if isinstance(exc, req_lib.ConnectionError):
        return json.dumps({"error": f"{context} failed: network error. Check your connection."})

    return json.dumps({"error": f"{context} failed: {exc}"})
