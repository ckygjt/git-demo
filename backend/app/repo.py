"""数据访问层：P0 直接读取 data/seed 下的 JSON/YAML；后续可换 SQLite 而不影响上层。"""
import json
from datetime import datetime
from functools import lru_cache

import yaml

from .config import IMAGES, SEED


def _load_json(name: str) -> list[dict]:
    with open(SEED / name, encoding="utf-8") as f:
        return json.load(f)


def parse_time(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


class Repo:
    def __init__(self) -> None:
        self.tickets = {t["ticket_id"]: t for t in _load_json("tickets.json")}
        self.orders = {o["order_id"]: o for o in _load_json("orders.json")}
        self.logistics = {x["order_id"]: x for x in _load_json("logistics.json")}
        self.chats = {c["ticket_id"]: c for c in _load_json("chats.json")}
        self.accounts = {a["account_id"]: a for a in _load_json("accounts.json")}
        with open(SEED / "products.yaml", encoding="utf-8") as f:
            self.products = {p["sku_id"]: p for p in yaml.safe_load(f)}
        self.results: dict[str, dict] = {}

    def ticket(self, tid: str) -> dict | None:
        return self.tickets.get(tid)

    def pending(self) -> list[dict]:
        return [t for t in self.tickets.values() if t.get("status") == "pending"]

    def order(self, oid: str) -> dict | None:
        return self.orders.get(oid)

    def product(self, sku: str) -> dict | None:
        return self.products.get(sku)

    def image_path(self, name: str):
        return IMAGES / name

    def other_tickets(self, tid: str) -> list[dict]:
        return [t for t in self.tickets.values() if t["ticket_id"] != tid]

    def credible_history(self) -> list[dict]:
        """已确认可信的工单（历史结论 + 本次运行中判为可信的）。"""
        out = []
        for t in self.tickets.values():
            v = self.results.get(t["ticket_id"], {}).get("verdict") or t.get("history_verdict")
            if v == "credible":
                out.append(t)
        return out

    def save_result(self, tid: str, result: dict) -> None:
        self.results[tid] = result


@lru_cache
def repo() -> Repo:
    return Repo()
