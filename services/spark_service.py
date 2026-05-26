"""Food data layer — PySpark."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from config import FOOD_DB_PATH, SPARK_APP_NAME

os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)


def _load_food_rows() -> list[dict[str, Any]]:
    with open(FOOD_DB_PATH, encoding="utf-8") as f:
        db = json.load(f)
    return [
        {
            "food_name": name,
            "calories": float(data["calories"]),
            "protein": float(data["protein"]),
            "carbs": float(data["carbs"]),
            "fat": float(data["fat"]),
            "allergens": data.get("allergens", []),
            "cuisine": data.get("cuisine", ""),
        }
        for name, data in db.items()
    ]


def _num(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r"\d+\.?\d*", value.replace(",", ""))
        if m:
            return float(m.group())
    return 0.0


def _history_rows(history: list[dict]) -> list[dict[str, Any]]:
    rows = []
    for item in history:
        data = item.get("data", {})
        nutrients = data.get("nutrients", {})
        hs = data.get("health_score", 0)
        try:
            health_score = float(hs) if hs not in (None, "", "N/A") else 0.0
        except (TypeError, ValueError):
            health_score = 0.0
        rows.append(
            {
                "name": data.get("name", item.get("name", "Unknown")),
                "calories": _num(nutrients.get("calories")),
                "protein": _num(nutrients.get("protein")),
                "carbs": _num(nutrients.get("carbs")),
                "fat": _num(nutrients.get("fat")),
                "health_score": health_score,
                "cuisine": data.get("cuisine", ""),
            }
        )
    return rows


class SparkFoodService:
    _instance: SparkFoodService | None = None
    engine = "pyspark"

    def __init__(self) -> None:
        from pyspark.sql import SparkSession, functions as F
        from pyspark.sql.types import (
            ArrayType,
            DoubleType,
            StringType,
            StructField,
            StructType,
        )

        self._F = F
        food_schema = StructType(
            [
                StructField("food_name", StringType(), False),
                StructField("calories", DoubleType(), False),
                StructField("protein", DoubleType(), False),
                StructField("carbs", DoubleType(), False),
                StructField("fat", DoubleType(), False),
                StructField("allergens", ArrayType(StringType()), True),
                StructField("cuisine", StringType(), True),
            ]
        )
        history_schema = StructType(
            [
                StructField("name", StringType(), True),
                StructField("calories", DoubleType(), True),
                StructField("protein", DoubleType(), True),
                StructField("carbs", DoubleType(), True),
                StructField("fat", DoubleType(), True),
                StructField("health_score", DoubleType(), True),
                StructField("cuisine", StringType(), True),
            ]
        )
        self._history_schema = history_schema

        self._spark = (
            SparkSession.builder.appName(SPARK_APP_NAME)
            .master("local[*]")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.driver.memory", "1g")
            .getOrCreate()
        )
        self._spark.sparkContext.setLogLevel("ERROR")
        rows = _load_food_rows()
        self._food_df = self._spark.createDataFrame(rows, schema=food_schema)

    @classmethod
    def get_instance(cls) -> SparkFoodService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def spark(self):
        return self._spark

    @property
    def food_df(self):
        return self._food_df

    def _row_to_dict(self, row) -> dict[str, Any]:
        return row.asDict() if row is not None else {}

    def lookup_food(self, name: str) -> dict[str, Any] | None:
        F = self._F
        if not name:
            return None
        key = name.lower().strip()
        exact = (
            self._food_df.filter(F.lower(F.col("food_name")) == key).limit(1).collect()
        )
        if exact:
            return self._row_to_dict(exact[0])
        partial = (
            self._food_df.filter(F.lower(F.col("food_name")).contains(key))
            .orderBy(F.length("food_name"))
            .limit(1)
            .collect()
        )
        return self._row_to_dict(partial[0]) if partial else None

    def search_foods(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        F = self._F
        if not query:
            return []
        key = query.lower().strip()
        rows = (
            self._food_df.filter(F.lower(F.col("food_name")).contains(key))
            .orderBy("food_name")
            .limit(limit)
            .collect()
        )
        return [self._row_to_dict(r) for r in rows]

    def get_cuisine_stats(self) -> list[dict[str, Any]]:
        F = self._F
        rows = (
            self._food_df.groupBy("cuisine")
            .agg(
                F.count("*").alias("food_count"),
                F.round(F.avg("calories"), 1).alias("avg_calories"),
                F.round(F.avg("protein"), 1).alias("avg_protein"),
                F.round(F.avg("carbs"), 1).alias("avg_carbs"),
                F.round(F.avg("fat"), 1).alias("avg_fat"),
            )
            .orderBy(F.desc("food_count"))
            .collect()
        )
        return [self._row_to_dict(r) for r in rows]

    def get_database_overview(self) -> dict[str, Any]:
        F = self._F
        row = self._food_df.agg(
            F.count("*").alias("total_foods"),
            F.round(F.avg("calories"), 1).alias("avg_calories"),
            F.round(F.max("calories"), 1).alias("max_calories"),
            F.round(F.min("calories"), 1).alias("min_calories"),
        ).collect()[0]
        return self._row_to_dict(row)

    def build_history_df(self, history: list[dict]):
        rows = _history_rows(history)
        if not rows:
            return self._spark.createDataFrame([], schema=self._history_schema)
        return self._spark.createDataFrame(rows, schema=self._history_schema)

    def get_history_stats(self, history: list[dict]) -> dict[str, Any]:
        F = self._F
        df = self.build_history_df(history)
        if df.count() == 0:
            return {}
        row = df.agg(
            F.count("*").alias("analyses"),
            F.round(F.avg("calories"), 1).alias("avg_calories"),
            F.round(F.sum("calories"), 1).alias("total_calories"),
            F.round(F.avg("health_score"), 1).alias("avg_health_score"),
            F.round(F.avg("protein"), 1).alias("avg_protein"),
        ).collect()[0]
        return self._row_to_dict(row)

    def compare_history_items(self, item1: dict, item2: dict) -> list[dict[str, Any]]:
        df = self.build_history_df([item1, item2])
        if df.count() < 2:
            return []
        names = [r["name"] for r in df.select("name").collect()]
        rows = df.collect()
        result = []
        for metric in ["calories", "protein", "carbs", "fat", "health_score"]:
            v1 = getattr(rows[0], metric, 0) or 0
            v2 = getattr(rows[1], metric, 0) or 0
            result.append(
                {
                    "nutrient": metric.replace("_", " ").title(),
                    names[0]: v1,
                    names[1]: v2,
                    "difference": round(v2 - v1, 1),
                }
            )
        return result

    def aggregate_calorie_log(self, calorie_log: list) -> dict[str, Any]:
        F = self._F
        if not calorie_log:
            return {}
        df = self._spark.createDataFrame([{"calories": float(c)} for c in calorie_log])
        row = df.agg(
            F.count("*").alias("entries"),
            F.round(F.sum("calories"), 1).alias("total"),
            F.round(F.avg("calories"), 1).alias("average"),
            F.round(F.max("calories"), 1).alias("max_entry"),
        ).collect()[0]
        return self._row_to_dict(row)

    def top_foods_by_metric(self, metric: str = "calories", limit: int = 5):
        F = self._F
        col = metric if metric in ("calories", "protein", "carbs", "fat") else "calories"
        rows = (
            self._food_df.orderBy(F.desc(col))
            .select("food_name", "cuisine", col)
            .limit(limit)
            .collect()
        )
        return [self._row_to_dict(r) for r in rows]
