"""Merge AI analysis with PySpark-verified nutrition data."""

from __future__ import annotations

from typing import Any

from services.spark_service import SparkFoodService


def enrich_analysis(data: dict[str, Any], spark_service: SparkFoodService) -> tuple[dict[str, Any], bool]:
    """
    Override AI nutrient estimates with verified database values when a match exists.
    Returns (enriched_data, was_enriched).
    """
    food_name = data.get("name", "")
    retrieved = spark_service.lookup_food(food_name)
    if not retrieved:
        return data, False

    nutrients = data.setdefault("nutrients", {})
    nutrients["calories"] = str(int(retrieved["calories"]))
    nutrients["protein"] = f"{retrieved['protein']}g"
    nutrients["carbs"] = f"{retrieved['carbs']}g"
    nutrients["fat"] = f"{retrieved['fat']}g"
    data["allergens"] = retrieved.get("allergens", data.get("allergens", []))
    data["cuisine"] = retrieved.get("cuisine", data.get("cuisine", ""))
    return data, True
