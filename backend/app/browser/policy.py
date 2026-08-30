from __future__ import annotations

from urllib.parse import urlparse


class BrowserPolicy:
    ALLOWED_DOMAINS = {"amazon.com.br", "www.amazon.com.br", "amazon.com", "www.amazon.com"}
    SAFE_ACTIONS = {"search_products", "read_product", "read_cart", "status"}
    CONFIRM_ACTIONS = {"add_to_cart", "remove_from_cart", "change_quantity"}
    FORBIDDEN_ACTIONS = {"checkout", "place_order", "execute_js", "upload", "download", "clipboard"}

    def check_action(self, action: str) -> None:
        if action in self.FORBIDDEN_ACTIONS or action not in self.SAFE_ACTIONS | self.CONFIRM_ACTIONS:
            raise ValueError(f"Ação de navegador não permitida: {action}.")

    def check_url(self, url: str) -> str:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or host not in self.ALLOWED_DOMAINS:
            raise ValueError("Navegação bloqueada: domínio fora da lista permitida.")
        return url

