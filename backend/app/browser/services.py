from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx

from app.browser.policy import BrowserPolicy
from app.core.config import Settings
from app.core.database import utc_now
from app.services.repository import repository


class BrowserWorkerClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self.base_url, self.client = base_url.rstrip("/"), client

    def call(self, method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 45) -> dict[str, Any]:
        owns = self.client is None
        client = self.client or httpx.Client(timeout=timeout, trust_env=False)
        try:
            response = client.request(method, self.base_url + path, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError("Browser Worker indisponível. Execute start-browser.ps1.") from exc
        finally:
            if owns:
                client.close()

    def health(self) -> dict[str, Any]:
        try:
            return self.call("GET", "/health", timeout=3)
        except RuntimeError:
            return {"status": "offline", "browser": "unavailable"}


class BrowserProfileManager:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    def descriptor(self) -> dict[str, Any]:
        return {"kind": "dedicated_persistent_profile", "path": str(self.path), "personal_browser_reused": False}


class BrowserSessionManager:
    def __init__(self, worker: BrowserWorkerClient, profile: BrowserProfileManager) -> None:
        self.worker, self.profile = worker, profile

    def connect(self, site: str) -> dict[str, Any]:
        if site != "amazon":
            raise ValueError("Site ainda não suportado.")
        result = self.worker.call("POST", "/sessions/connect", {"site": site, "profile_path": str(self.profile.path)})
        now = utc_now()
        repository.execute(
            "INSERT OR REPLACE INTO browser_sites VALUES (?,?,?,?,?,?,?)",
            (site, result.get("status", "manual_login_required"), str(self.profile.path), int(bool(result.get("authenticated"))), json.dumps(result.get("capabilities", [])), now, result.get("error")),
        )
        repository.execute("INSERT INTO browser_sessions_metadata VALUES (?,?,?,?,?,?,?)", (str(uuid.uuid4()), site, result.get("status", "open"), int(bool(result.get("authenticated"))), now, None, result.get("error")))
        return {**result, "profile": self.profile.descriptor()}

    def status(self, site: str = "amazon") -> dict[str, Any]:
        worker = self.worker.health()
        stored = repository.row("SELECT * FROM browser_sites WHERE site=?", (site,))
        if worker.get("status") != "ok":
            return {"site": site, "status": "worker_offline", "authenticated": False, "worker": worker, "profile": self.profile.descriptor(), "capabilities": []}
        result = self.worker.call("GET", f"/sessions/{site}/status")
        if stored:
            repository.execute("UPDATE browser_sites SET status=?,authenticated=?,last_checked_at=?,last_error=? WHERE site=?", (result.get("status", "unknown"), int(bool(result.get("authenticated"))), utc_now(), result.get("error"), site))
        return {**result, "worker": worker, "profile": self.profile.descriptor()}

    def disconnect(self, site: str = "amazon") -> dict[str, Any]:
        result = self.worker.call("POST", f"/sessions/{site}/disconnect")
        repository.execute("UPDATE browser_sites SET status='disconnected',authenticated=0,last_checked_at=? WHERE site=?", (utc_now(), site))
        return result


class SiteAdapter(ABC):
    @abstractmethod
    def search_products(self, query: str, max_results: int = 5) -> list[dict[str, Any]]: ...
    @abstractmethod
    def read_product(self, candidate_id: str) -> dict[str, Any]: ...
    @abstractmethod
    def read_cart(self) -> dict[str, Any]: ...
    @abstractmethod
    def add_to_cart(self, candidate_id: str, expected_price: str | None, variant: str | None, quantity: int) -> dict[str, Any]: ...


class AmazonSiteAdapter(SiteAdapter):
    def __init__(self, worker: BrowserWorkerClient, policy: BrowserPolicy) -> None:
        self.worker, self.policy = worker, policy

    def _store(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        output = []
        for item in candidates:
            self.policy.check_url(item["url"])
            candidate_id = item.get("id") or str(uuid.uuid4())
            candidate = {"id": candidate_id, "site": "amazon", "title": item.get("title", ""), "price": item.get("price"), "seller": item.get("seller"), "rating": item.get("rating"), "review_count": item.get("review_count"), "delivery": item.get("delivery"), "prime": bool(item.get("prime")), "availability": item.get("availability"), "url": item["url"], "variant": item.get("variant")}
            repository.execute("INSERT OR REPLACE INTO product_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (candidate_id, "amazon", candidate["title"], candidate["price"], candidate["seller"], candidate["rating"], candidate["review_count"], candidate["delivery"], int(candidate["prime"]), candidate["availability"], candidate["url"], candidate["variant"], utc_now(), json.dumps(item, ensure_ascii=False)))
            output.append(candidate)
        return output

    def _candidate(self, candidate_id: str) -> dict[str, Any]:
        item = repository.row("SELECT * FROM product_candidates WHERE id=? AND site='amazon'", (candidate_id,))
        if not item:
            raise ValueError("Candidato de produto não encontrado ou expirado.")
        self.policy.check_url(item["url"])
        return item

    def search_products(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        self.policy.check_action("search_products")
        result = self.worker.call("POST", "/amazon/search", {"query": query[:200], "max_results": max(1, min(max_results, 8))})
        return self._store(result.get("items", []))

    def read_product(self, candidate_id: str) -> dict[str, Any]:
        self.policy.check_action("read_product")
        candidate = self._candidate(candidate_id)
        return self.worker.call("POST", "/amazon/product", {"url": candidate["url"], "candidate_id": candidate_id})

    def read_cart(self) -> dict[str, Any]:
        self.policy.check_action("read_cart")
        return self.worker.call("GET", "/amazon/cart")

    def add_to_cart(self, candidate_id: str, expected_price: str | None, variant: str | None, quantity: int) -> dict[str, Any]:
        self.policy.check_action("add_to_cart")
        candidate = self._candidate(candidate_id)
        expected = expected_price or candidate.get("price")
        return self.worker.call("POST", "/amazon/cart/add", {"candidate_id": candidate_id, "url": candidate["url"], "expected_price": expected, "variant": variant or candidate.get("variant"), "quantity": max(1, min(quantity, 10))})

    def remove_from_cart(self, item_id: str) -> dict[str, Any]:
        self.policy.check_action("remove_from_cart")
        return self.worker.call("POST", "/amazon/cart/remove", {"item_id": item_id})

    def change_quantity(self, item_id: str, quantity: int) -> dict[str, Any]:
        self.policy.check_action("change_quantity")
        return self.worker.call("POST", "/amazon/cart/quantity", {"item_id": item_id, "quantity": max(1, min(quantity, 10))})


class SiteAdapterRegistry:
    def __init__(self) -> None:
        self._items: dict[str, SiteAdapter] = {}

    def register(self, name: str, adapter: SiteAdapter) -> None:
        self._items[name] = adapter

    def get(self, name: str) -> SiteAdapter:
        if name not in self._items:
            raise ValueError("Site sem adaptador registrado.")
        return self._items[name]


class BrowserAgent:
    def __init__(self, settings: Settings) -> None:
        self.policy = BrowserPolicy()
        self.worker = BrowserWorkerClient(settings.browser_worker_url)
        self.profile = BrowserProfileManager(settings.browser_profile_path)
        self.sessions = BrowserSessionManager(self.worker, self.profile)
        self.adapters = SiteAdapterRegistry()
        self.adapters.register("amazon", AmazonSiteAdapter(self.worker, self.policy))

    def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.policy.check_action(action)
        adapter = self.adapters.get(payload.get("site", "amazon"))
        if action == "search_products":
            data = {"items": adapter.search_products(payload["query"], payload.get("max_results", 5))}
        elif action == "read_product":
            data = adapter.read_product(payload["candidate_id"])
        elif action == "read_cart":
            data = adapter.read_cart()
        elif action == "add_to_cart":
            data = adapter.add_to_cart(payload["candidate_id"], payload.get("expected_price"), payload.get("variant"), payload.get("quantity", 1))
        elif action == "remove_from_cart":
            data = adapter.remove_from_cart(payload["item_id"])  # type: ignore[attr-defined]
        elif action == "change_quantity":
            data = adapter.change_quantity(payload["item_id"], payload["quantity"])  # type: ignore[attr-defined]
        else:
            raise ValueError("Ação semântica não implementada.")
        return {**data, "network_activity": "BROWSER ACTION", "site": payload.get("site", "amazon"), "verified": data.get("verified", action in {"search_products", "read_product", "read_cart"})}

