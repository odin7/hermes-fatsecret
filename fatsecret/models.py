from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Serving:
    serving_id: str
    description: str
    calories: float
    protein: float
    carbohydrate: float
    fat: float
    saturated_fat: float | None = None
    sodium: float | None = None
    fiber: float | None = None
    sugar: float | None = None
    metric_amount: float | None = None
    metric_unit: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "serving_id": self.serving_id,
            "description": self.description,
            "calories": self.calories,
            "protein_g": self.protein,
            "carbohydrate_g": self.carbohydrate,
            "fat_g": self.fat,
        }
        if self.saturated_fat is not None:
            d["saturated_fat_g"] = self.saturated_fat
        if self.sodium is not None:
            d["sodium_mg"] = self.sodium
        if self.fiber is not None:
            d["fiber_g"] = self.fiber
        if self.sugar is not None:
            d["sugar_g"] = self.sugar
        if self.metric_amount is not None:
            d["metric_amount"] = self.metric_amount
            d["metric_unit"] = self.metric_unit
        return d


@dataclass
class FoodCandidate:
    food_id: str
    food_name: str
    brand: str | None
    servings: list[Serving]
    confidence: float | None = None

    def to_dict(self) -> dict:
        return {
            "food_id": self.food_id,
            "food_name": self.food_name,
            "brand": self.brand,
            "servings": [s.to_dict() for s in self.servings],
            "confidence": self.confidence,
        }


@dataclass
class LogResult:
    status: str
    food_entry_id: str | None
    logged_food_name: str
    meal: str
    date: str
    calories: float | None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "food_entry_id": self.food_entry_id,
            "logged_food_name": self.logged_food_name,
            "meal": self.meal,
            "date": self.date,
            "calories": self.calories,
        }


def _float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _parse_serving_from_search(raw: dict) -> Serving:
    return Serving(
        serving_id=str(raw.get("serving_id", "")),
        description=str(raw.get("serving_description", "1 serving")),
        calories=_float(raw.get("calories")),
        protein=_float(raw.get("protein")),
        carbohydrate=_float(raw.get("carbohydrate")),
        fat=_float(raw.get("fat")),
        saturated_fat=_float(raw["saturated_fat"]) if raw.get("saturated_fat") else None,
        sodium=_float(raw["sodium"]) if raw.get("sodium") else None,
        fiber=_float(raw["fiber"]) if raw.get("fiber") else None,
        sugar=_float(raw["sugar"]) if raw.get("sugar") else None,
        metric_amount=_float(raw["metric_serving_amount"]) if raw.get("metric_serving_amount") else None,
        metric_unit=raw.get("metric_serving_unit"),
    )


def normalize_recognition_response(data: dict) -> list[FoodCandidate]:
    """Normalize FatSecret Image Recognition v1 response → list[FoodCandidate]."""
    food_resp = data.get("food_response")
    if not food_resp:
        return []

    items: list[dict] = [food_resp] if isinstance(food_resp, dict) else list(food_resp)

    candidates: list[FoodCandidate] = []
    for item in items:
        food_id = str(item.get("food_id", ""))
        food_name = str(item.get("food_entry_name") or item.get("food_name") or "Unknown")

        suggested = item.get("suggested_serving") or {}
        eaten_nc = (item.get("eaten") or {}).get("total_nutritional_content") or {}

        serving = Serving(
            serving_id=str(suggested.get("serving_id", "")),
            description=str(suggested.get("serving_description", "1 serving")),
            calories=_float(suggested.get("calories") or eaten_nc.get("calories")),
            protein=_float(eaten_nc.get("protein")),
            carbohydrate=_float(eaten_nc.get("carbohydrate")),
            fat=_float(eaten_nc.get("fat")),
            saturated_fat=_float(eaten_nc["saturated_fat"]) if eaten_nc.get("saturated_fat") else None,
            sodium=_float(eaten_nc["sodium"]) if eaten_nc.get("sodium") else None,
            fiber=_float(eaten_nc["fiber"]) if eaten_nc.get("fiber") else None,
            sugar=_float(eaten_nc["sugar"]) if eaten_nc.get("sugar") else None,
        )

        candidates.append(FoodCandidate(
            food_id=food_id,
            food_name=food_name,
            brand=item.get("brand_name"),
            servings=[serving] if serving.serving_id else [],
            confidence=None,
        ))

    return candidates


def normalize_search_response(data: dict) -> list[FoodCandidate]:
    """Normalize FatSecret foods.search.v5 response → list[FoodCandidate]."""
    foods_obj = data.get("foods") or {}
    food_list = foods_obj.get("food") or []
    if isinstance(food_list, dict):
        food_list = [food_list]

    candidates: list[FoodCandidate] = []
    for food in food_list:
        servings_raw = (food.get("servings") or {}).get("serving") or []
        if isinstance(servings_raw, dict):
            servings_raw = [servings_raw]

        candidates.append(FoodCandidate(
            food_id=str(food.get("food_id", "")),
            food_name=str(food.get("food_name", "Unknown")),
            brand=food.get("brand_name"),
            servings=[_parse_serving_from_search(s) for s in servings_raw],
        ))

    return candidates
