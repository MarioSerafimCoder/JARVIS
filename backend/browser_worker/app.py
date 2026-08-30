from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from playwright.async_api import BrowserContext, Page, async_playwright
except ImportError:  # Worker stays diagnosable before optional setup.
    BrowserContext = Page = object  # type: ignore[assignment,misc]
    async_playwright = None


ALLOWED_HOSTS = {"amazon.com.br", "www.amazon.com.br", "amazon.com", "www.amazon.com"}
CAPABILITIES = ["search_products", "read_product", "read_cart", "add_to_cart", "remove_from_cart", "change_quantity"]
runtime = {"playwright": None, "context": None, "page": None, "site": None}


def allowed_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise HTTPException(403, "Domínio fora da lista permitida.")
    return url


def price_key(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"[^0-9]", "", value)
    return digits.lstrip("0") or "0"


async def text(page: Page, selectors: list[str], default: str | None = None) -> str | None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() and await locator.is_visible(timeout=800):
                value = " ".join((await locator.inner_text(timeout=1200)).split())
                if value:
                    return value
        except Exception:
            continue
    return default


async def active_page() -> Page:
    page = runtime.get("page")
    if page is None or page.is_closed():
        raise HTTPException(409, "Sessão do navegador não está aberta. Conecte o site primeiro.")
    return page


async def auth_state(page: Page) -> dict:
    body = (await page.locator("body").inner_text(timeout=3000)).lower()
    captcha = any(term in body for term in ("digite os caracteres", "enter the characters you see", "captcha"))
    account = (await text(page, ["#nav-link-accountList-nav-line-1"], "") or "").lower()
    authenticated = bool(account and not any(term in account for term in ("faça seu login", "sign in")))
    return {"authenticated": authenticated, "captcha_required": captcha, "status": "captcha_required" if captcha else "connected" if authenticated else "manual_login_required", "capabilities": CAPABILITIES if authenticated else ["search_products", "read_product"]}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    context = runtime.get("context")
    if context:
        await context.close()
    playwright = runtime.get("playwright")
    if playwright:
        await playwright.stop()


app = FastAPI(title="Jarvis Browser Worker", version="0.1.0", lifespan=lifespan)


class ConnectInput(BaseModel):
    site: str = Field(pattern="^amazon$")
    profile_path: str


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    max_results: int = Field(default=5, ge=1, le=8)


class ProductInput(BaseModel):
    url: str
    candidate_id: str


class AddInput(ProductInput):
    expected_price: str | None = None
    variant: str | None = None
    quantity: int = Field(default=1, ge=1, le=10)


class ItemInput(BaseModel):
    item_id: str


class QuantityInput(ItemInput):
    quantity: int = Field(ge=1, le=10)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "browser": "ready" if async_playwright else "dependency_missing", "session_open": runtime.get("page") is not None}


@app.post("/sessions/connect")
async def connect(payload: ConnectInput) -> dict:
    if async_playwright is None:
        raise HTTPException(503, "Playwright não instalado. Execute setup-browser.ps1.")
    Path(payload.profile_path).mkdir(parents=True, exist_ok=True)
    if runtime.get("context") is None:
        runtime["playwright"] = await async_playwright().start()
        try:
            runtime["context"] = await runtime["playwright"].chromium.launch_persistent_context(
                payload.profile_path,
                channel="msedge",
                headless=False,
                accept_downloads=False,
                permissions=[],
                args=["--disable-sync", "--disable-features=OptimizationHints,AutofillServerCommunication"],
            )
        except Exception as exc:
            await runtime["playwright"].stop()
            runtime.update({"playwright": None, "context": None, "page": None})
            raise HTTPException(503, f"Não foi possível abrir o Microsoft Edge controlado: {exc}") from exc
    context: BrowserContext = runtime["context"]
    pages = [item for item in context.pages if not item.is_closed()]
    page = pages[0] if pages else await context.new_page()
    runtime.update({"page": page, "site": payload.site})
    await page.goto("https://www.amazon.com.br/", wait_until="domcontentloaded", timeout=30000)
    state = await auth_state(page)
    return {**state, "site": payload.site, "manual_action": None if state["authenticated"] else "Faça login/2FA/CAPTCHA diretamente na janela aberta e depois clique em Verificar conexão."}


@app.get("/sessions/{site}/status")
async def session_status(site: str) -> dict:
    if site != "amazon":
        raise HTTPException(404, "Site não suportado.")
    if runtime.get("page") is None:
        return {"site": site, "status": "disconnected", "authenticated": False, "capabilities": []}
    page = await active_page()
    return {"site": site, **await auth_state(page)}


@app.post("/sessions/{site}/disconnect")
async def disconnect(site: str) -> dict:
    context = runtime.get("context")
    if context:
        await context.close()
    playwright = runtime.get("playwright")
    if playwright:
        await playwright.stop()
    runtime.update({"playwright": None, "context": None, "page": None, "site": None})
    return {"site": site, "status": "disconnected", "authenticated": False}


@app.post("/amazon/search")
async def search_products(payload: SearchInput) -> dict:
    page = await active_page()
    await page.goto(f"https://www.amazon.com.br/s?k={quote_plus(payload.query)}", wait_until="domcontentloaded", timeout=30000)
    if (await auth_state(page))["captcha_required"]:
        return {"status": "captcha_required", "items": []}
    cards = page.locator('[data-component-type="s-search-result"]')
    items = []
    for index in range(min(await cards.count(), payload.max_results * 2)):
        card = cards.nth(index)
        try:
            title = " ".join((await card.locator("h2 span").first.inner_text(timeout=1200)).split())
            href = await card.locator("h2 a").first.get_attribute("href")
            if not title or not href:
                continue
            url = href if href.startswith("http") else "https://www.amazon.com.br" + href.split("?", 1)[0]
            allowed_url(url)
            item = {
                "title": title,
                "price": await text(card, [".a-price .a-offscreen"]),
                "rating": await text(card, [".a-icon-alt"]),
                "review_count": await text(card, ["[aria-label$='avaliações']", "[aria-label$='ratings']"]),
                "delivery": await text(card, ["[data-cy='delivery-recipe']"]),
                "prime": bool(await card.locator("i.a-icon-prime").count()),
                "availability": "available",
                "seller": None,
                "variant": None,
                "url": url,
            }
            items.append(item)
            if len(items) >= payload.max_results:
                break
        except Exception:
            continue
    return {"status": "success", "items": items, "verified": True}


@app.post("/amazon/product")
async def read_product(payload: ProductInput) -> dict:
    page = await active_page()
    await page.goto(allowed_url(payload.url), wait_until="domcontentloaded", timeout=30000)
    state = await auth_state(page)
    return {"status": state["status"] if state["captcha_required"] else "success", "candidate_id": payload.candidate_id, "title": await text(page, ["#productTitle", "h1"]), "price": await text(page, ["#corePrice_feature_div .a-offscreen", ".a-price .a-offscreen"]), "seller": await text(page, ["#sellerProfileTriggerId", "#merchant-info"]), "availability": await text(page, ["#availability"]), "url": page.url, "verified": not state["captcha_required"]}


async def cart_snapshot(page: Page) -> dict:
    await page.goto("https://www.amazon.com.br/gp/cart/view.html", wait_until="domcontentloaded", timeout=30000)
    state = await auth_state(page)
    if state["captcha_required"]:
        return {"status": "captcha_required", "items": [], "verified": False}
    rows = page.locator(".sc-list-item[data-asin]")
    items = []
    for index in range(await rows.count()):
        row = rows.nth(index)
        asin = await row.get_attribute("data-asin") or f"row-{index}"
        items.append({"item_id": asin, "title": await text(row, [".sc-product-title", ".a-truncate-full"]), "price": await text(row, [".sc-product-price", ".a-price .a-offscreen"]), "quantity": await row.locator("select.sc-update-quantity-select").input_value() if await row.locator("select.sc-update-quantity-select").count() else "1"})
    return {"status": "success", "items": items, "verified": True}


@app.get("/amazon/cart")
async def read_cart() -> dict:
    return await cart_snapshot(await active_page())


@app.post("/amazon/cart/add")
async def add_to_cart(payload: AddInput) -> dict:
    page = await active_page()
    await page.goto(allowed_url(payload.url), wait_until="domcontentloaded", timeout=30000)
    state = await auth_state(page)
    if state["captcha_required"]:
        return {"status": "captcha_required", "verified": False}
    title_now = await text(page, ["#productTitle", "h1"])
    price_now = await text(page, ["#corePrice_feature_div .a-offscreen", ".a-price .a-offscreen"])
    if payload.expected_price and price_key(price_now) != price_key(payload.expected_price):
        return {"status": "PRICE_CHANGED", "expected_price": payload.expected_price, "current_price": price_now, "candidate_id": payload.candidate_id, "verified": False}
    if payload.variant:
        variant = page.get_by_text(payload.variant, exact=True).first
        if not await variant.count():
            return {"status": "VARIANT_UNAVAILABLE", "variant": payload.variant, "verified": False}
        await variant.click(timeout=3000)
    button = page.locator("#add-to-cart-button").first
    if not await button.count():
        return {"status": "UNAVAILABLE", "verified": False}
    await button.click(timeout=5000)
    await page.wait_for_timeout(1200)
    cart = await cart_snapshot(page)
    matching = [item for item in cart.get("items", []) if title_now and item.get("title") and title_now.lower()[:60] in item["title"].lower()]
    if not matching:
        return {"status": "UNKNOWN", "reason": "Não foi possível verificar o produto no carrinho.", "verified": False, "cart": cart}
    item = matching[0]
    if payload.quantity != 1:
        changed = await change_quantity(QuantityInput(item_id=item["item_id"], quantity=payload.quantity))
        if not changed.get("verified"):
            return changed
    return {"status": "success", "candidate_id": payload.candidate_id, "title": title_now, "price": price_now, "variant": payload.variant, "quantity": payload.quantity, "cart_item_id": item["item_id"], "verified": True}


@app.post("/amazon/cart/remove")
async def remove_from_cart(payload: ItemInput) -> dict:
    page = await active_page()
    await page.goto("https://www.amazon.com.br/gp/cart/view.html", wait_until="domcontentloaded", timeout=30000)
    row = page.locator(f'.sc-list-item[data-asin="{payload.item_id}"]').first
    if not await row.count():
        return {"status": "UNKNOWN", "verified": False}
    delete = row.get_by_role("button", name=re.compile("excluir|delete", re.I)).first
    if not await delete.count():
        delete = row.locator("input[value='Excluir'], input[value='Delete']").first
    await delete.click(timeout=4000)
    await page.wait_for_timeout(800)
    verified = not await page.locator(f'.sc-list-item[data-asin="{payload.item_id}"]').count()
    return {"status": "success" if verified else "UNKNOWN", "item_id": payload.item_id, "verified": verified}


@app.post("/amazon/cart/quantity")
async def change_quantity(payload: QuantityInput) -> dict:
    page = await active_page()
    if "/cart" not in page.url:
        await page.goto("https://www.amazon.com.br/gp/cart/view.html", wait_until="domcontentloaded", timeout=30000)
    row = page.locator(f'.sc-list-item[data-asin="{payload.item_id}"]').first
    select = row.locator("select.sc-update-quantity-select").first
    if not await select.count():
        return {"status": "UNKNOWN", "verified": False}
    await select.select_option(str(payload.quantity))
    await page.wait_for_timeout(900)
    actual = await select.input_value()
    return {"status": "success" if actual == str(payload.quantity) else "UNKNOWN", "item_id": payload.item_id, "quantity": int(actual), "verified": actual == str(payload.quantity)}

