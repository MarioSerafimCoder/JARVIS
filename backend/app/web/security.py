from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    pass


class WebURLPolicy:
    """Deny-by-default URL validation, including every redirect hop."""

    def __init__(self, resolver: Callable[..., list] | None = None) -> None:
        self.resolver = resolver or socket.getaddrinfo

    def validate(self, url: str) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            raise UnsafeURL("Somente URLs HTTP ou HTTPS públicas são permitidas.")
        if not parsed.hostname or parsed.username or parsed.password:
            raise UnsafeURL("URL sem host público válido.")
        host = parsed.hostname.rstrip(".").lower()
        if host in {"localhost", "metadata.google.internal"} or host.endswith((".local", ".internal", ".lan")):
            raise UnsafeURL("Host local ou de metadados bloqueado.")
        try:
            addresses = {item[4][0].split("%", 1)[0] for item in self.resolver(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except OSError as exc:
            raise UnsafeURL("Não foi possível resolver o host público.") from exc
        if not addresses:
            raise UnsafeURL("Host sem endereço resolvido.")
        for raw in addresses:
            address = ipaddress.ip_address(raw)
            if not address.is_global:
                raise UnsafeURL(f"Endereço não público bloqueado: {address}.")
        return parsed.geturl()


class WebQuerySanitizer:
    _email = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
    _phone = re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[-.\s]?\d{4}(?!\d)")
    _document = re.compile(r"(?<!\d)\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}(?!\d)")
    _secret = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|(?:password|senha|token|secret)\s*[:=]\s*\S+)", re.I)
    _path = re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/)[^\s]+", re.I)

    def sanitize(self, query: str) -> tuple[str, list[str]]:
        clean = " ".join(query.split())[:500]
        redactions: list[str] = []
        for label, pattern in (("email", self._email), ("telefone", self._phone), ("documento", self._document), ("segredo", self._secret), ("caminho_local", self._path)):
            if pattern.search(clean):
                clean = pattern.sub(f"[{label}_removido]", clean)
                redactions.append(label)
        if not clean.strip():
            raise ValueError("A consulta ficou vazia após remover dados privados.")
        return clean, redactions

