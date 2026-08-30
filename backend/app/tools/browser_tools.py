from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.browser.services import BrowserAgent
from app.tools.base import RiskLevel, Tool
from app.tools.implementations import FunctionTool
from app.tools.web_tools import access_mode


class SiteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    site: str = Field(default="amazon", pattern="^amazon$")


class ProductSearchInput(SiteInput):
    query: str = Field(min_length=1, max_length=200)
    max_results: int = Field(default=5, ge=1, le=8)


class CandidateInput(SiteInput):
    candidate_id: str = Field(min_length=1)


class AddCartInput(CandidateInput):
    expected_price: str | None = None
    variant: str | None = None
    quantity: int = Field(default=1, ge=1, le=10)


class CartItemInput(SiteInput):
    item_id: str = Field(min_length=1)


class QuantityInput(CartItemInput):
    quantity: int = Field(ge=1, le=10)


def browser_safe_risk(_: dict) -> RiskLevel:
    return RiskLevel.SAFE if access_mode("browser_access", "OFF") == "ON" else RiskLevel.DANGEROUS


def browser_confirm_risk(_: dict) -> RiskLevel:
    return RiskLevel.CONFIRM if access_mode("browser_access", "OFF") == "ON" else RiskLevel.DANGEROUS


def browser_tools(agent: BrowserAgent) -> list[Tool]:
    blocked = "Browser Agent está desligado. Conecte um site em Conexões e ative o acesso nas Configurações."
    return [
        FunctionTool("browser_search_products", "Pesquisa produtos na loja conectada usando navegação semântica controlada.", ProductSearchInput.model_json_schema(), RiskLevel.SAFE, lambda p: agent.execute("search_products", p), ProductSearchInput, risk_resolver=browser_safe_risk, blocked_message=blocked),
        FunctionTool("browser_read_product", "Lê detalhes atuais de um candidato de produto já identificado.", CandidateInput.model_json_schema(), RiskLevel.SAFE, lambda p: agent.execute("read_product", p), CandidateInput, risk_resolver=browser_safe_risk, blocked_message=blocked),
        FunctionTool("browser_read_cart", "Lê e verifica o carrinho da loja conectada; nunca finaliza compra.", SiteInput.model_json_schema(), RiskLevel.SAFE, lambda p: agent.execute("read_cart", p), SiteInput, risk_resolver=browser_safe_risk, blocked_message=blocked),
        FunctionTool("browser_add_to_cart", "Adiciona um candidato ao carrinho somente após confirmação. Revalida preço, variante e quantidade; checkout não existe.", AddCartInput.model_json_schema(), RiskLevel.CONFIRM, lambda p: agent.execute("add_to_cart", p), AddCartInput, risk_resolver=browser_confirm_risk, blocked_message=blocked),
        FunctionTool("browser_remove_from_cart", "Remove item do carrinho somente após confirmação.", CartItemInput.model_json_schema(), RiskLevel.CONFIRM, lambda p: agent.execute("remove_from_cart", p), CartItemInput, risk_resolver=browser_confirm_risk, blocked_message=blocked),
        FunctionTool("browser_change_cart_quantity", "Altera quantidade no carrinho somente após confirmação e verificação.", QuantityInput.model_json_schema(), RiskLevel.CONFIRM, lambda p: agent.execute("change_quantity", p), QuantityInput, risk_resolver=browser_confirm_risk, blocked_message=blocked),
    ]

