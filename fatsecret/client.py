from __future__ import annotations

import base64
import io
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.request import urlopen

import requests

from .auth import OAuth1Signer, OAuth2TokenManager
from .models import (
    FoodCandidate,
    LogResult,
    Serving,
    _float,
    normalize_recognition_response,
    normalize_search_response,
)

_RECOGNITION_URL = "https://platform.fatsecret.com/rest/image-recognition/v1"
_SEARCH_URL = "https://platform.fatsecret.com/rest/foods/search/v5"
_FOOD_GET_URL = "https://platform.fatsecret.com/rest/food/v5"
_FOOD_ENTRY_URL = "https://platform.fatsecret.com/rest/food-entries/v1"

# base64 limit per FatSecret docs: 999,982 chars ≈ 750 KB raw bytes
_MAX_IMAGE_BYTES = 750_000

_EPOCH = date(1970, 1, 1)


def _days_since_epoch(d: date) -> int:
    return (d - _EPOCH).days


def _load_and_encode_image(source: str) -> str:
    """Read image from file path or URL, downscale if needed, return base64."""
    if source.startswith("http://") or source.startswith("https://"):
        with urlopen(source, timeout=15) as resp:  # noqa: S310
            data = resp.read()
    else:
        data = Path(source).read_bytes()

    if len(data) > _MAX_IMAGE_BYTES:
        data = _downscale(data)

    return base64.b64encode(data).decode("ascii")


def _downscale(data: bytes) -> bytes:
    """Iteratively shrink an image with Pillow until it fits under _MAX_IMAGE_BYTES."""
    try:
        from PIL import Image
    except ImportError:
        # Return as-is and let the API reject if too large; Pillow is optional
        return data

    img = Image.open(io.BytesIO(data))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    quality = 85
    while True:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        compressed = buf.getvalue()
        if len(compressed) <= _MAX_IMAGE_BYTES:
            return compressed
        if quality > 40:
            quality -= 15
        elif img.width > 320:
            new_w = img.width * 3 // 4
            new_h = img.height * 3 // 4
            img = img.resize((new_w, new_h), Image.LANCZOS)
        else:
            return compressed  # give up shrinking, send best effort


class FatSecretClient:
    def __init__(self, oauth2: OAuth2TokenManager, oauth1: OAuth1Signer) -> None:
        self._oauth2 = oauth2
        self._oauth1 = oauth1
        self._session = requests.Session()

    @classmethod
    def from_env(cls) -> "FatSecretClient":
        return cls(
            oauth2=OAuth2TokenManager.from_env(),
            oauth1=OAuth1Signer.from_env(),
        )

    # ------------------------------------------------------------------
    # Phase 1.2
    # ------------------------------------------------------------------

    def image_recognition(
        self,
        image_source: str,
        *,
        region: str = "US",
        language: str = "en",
        eaten_foods: Optional[list[str]] = None,
    ) -> list[FoodCandidate]:
        image_b64 = _load_and_encode_image(image_source)
        payload: dict = {
            "image_b64": image_b64,
            "include_food_data": True,
            "region": region,
            "language": language,
        }
        if eaten_foods:
            payload["eaten_foods"] = eaten_foods

        resp = self._session.post(
            _RECOGNITION_URL,
            json=payload,
            headers=self._oauth2.auth_header(),
            timeout=30,
        )
        resp.raise_for_status()
        return normalize_recognition_response(resp.json())

    # ------------------------------------------------------------------
    # Phase 1.3
    # ------------------------------------------------------------------

    def search_foods(
        self,
        query: str,
        *,
        region: str = "US",
        language: str = "en",
        max_results: int = 10,
    ) -> list[FoodCandidate]:
        resp = self._session.get(
            _SEARCH_URL,
            params={
                "search_expression": query,
                "region": region,
                "language": language,
                "max_results": max_results,
                "format": "json",
            },
            headers=self._oauth2.auth_header(),
            timeout=15,
        )
        resp.raise_for_status()
        return normalize_search_response(resp.json())

    def get_food(self, food_id: str, region: str = "US") -> Optional[FoodCandidate]:
        resp = self._session.get(
            _FOOD_GET_URL,
            params={"food_id": food_id, "region": region, "format": "json"},
            headers=self._oauth2.auth_header(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        food = data.get("food")
        if not food:
            return None

        servings_raw = (food.get("servings") or {}).get("serving") or []
        if isinstance(servings_raw, dict):
            servings_raw = [servings_raw]

        servings = [
            Serving(
                serving_id=str(s.get("serving_id", "")),
                description=str(s.get("serving_description", "")),
                calories=_float(s.get("calories")),
                protein=_float(s.get("protein")),
                carbohydrate=_float(s.get("carbohydrate")),
                fat=_float(s.get("fat")),
                saturated_fat=_float(s["saturated_fat"]) if s.get("saturated_fat") else None,
                sodium=_float(s["sodium"]) if s.get("sodium") else None,
                fiber=_float(s["fiber"]) if s.get("fiber") else None,
                sugar=_float(s["sugar"]) if s.get("sugar") else None,
                metric_amount=_float(s["metric_serving_amount"]) if s.get("metric_serving_amount") else None,
                metric_unit=s.get("metric_serving_unit"),
            )
            for s in servings_raw
        ]
        return FoodCandidate(
            food_id=str(food.get("food_id", "")),
            food_name=str(food.get("food_name", "Unknown")),
            brand=food.get("brand_name"),
            servings=servings,
        )

    # ------------------------------------------------------------------
    # Phase 1.4
    # ------------------------------------------------------------------

    def create_food_entry(
        self,
        food_id: str,
        serving_id: str,
        number_of_units: float,
        meal: str,
        food_entry_name: str,
        entry_date: Optional[date] = None,
    ) -> LogResult:
        if entry_date is None:
            entry_date = datetime.now(tz=timezone.utc).date()

        resp = self._session.post(
            _FOOD_ENTRY_URL,
            data={
                "food_id": food_id,
                "serving_id": serving_id,
                "number_of_units": str(number_of_units),
                "meal": meal,
                "food_entry_name": food_entry_name,
                "date": str(_days_since_epoch(entry_date)),
                "format": "json",
            },
            auth=self._oauth1.auth,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        entry = data.get("food_entry") or data
        nc = entry.get("total_nutritional_content") or {}
        calories = _float(nc["calories"]) if nc.get("calories") else None

        return LogResult(
            status="logged",
            food_entry_id=str(entry.get("food_entry_id", "")),
            logged_food_name=food_entry_name,
            meal=meal,
            date=entry_date.isoformat(),
            calories=calories,
        )
