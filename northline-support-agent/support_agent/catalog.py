"""Bundled store data for the fictional Northline Supply shop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Catalog:
    policy: dict
    faqs: list[dict]
    orders: dict[str, dict]

    @classmethod
    def load(cls, data_dir: Path | None = None) -> Catalog:
        root = data_dir or DATA_DIR
        policy = json.loads((root / "policy.json").read_text(encoding="utf-8"))
        faqs = json.loads((root / "faqs.json").read_text(encoding="utf-8"))
        orders = json.loads((root / "orders.json").read_text(encoding="utf-8"))
        return cls(
            policy=policy,
            faqs=faqs,
            orders={order["id"].upper(): order for order in orders},
        )

    @property
    def store_name(self) -> str:
        return str(self.policy["store_name"])

    @property
    def as_of(self) -> date:
        return date.fromisoformat(self.policy["as_of"])

    @property
    def return_window_days(self) -> int:
        return int(self.policy["return_window_days"])

    def order(self, order_id: str | None) -> dict | None:
        if not order_id:
            return None
        return self.orders.get(order_id.upper())
