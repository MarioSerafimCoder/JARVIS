import json
import socket

import httpx
import pytest

from app.services.repository import repository
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from app.tools.web_tools import web_tools
from app.web.security import UnsafeURL, WebQuerySanitizer, WebURLPolicy
from app.web.services import WebIntelligenceService, WebPageFetcher, WebSearchProvider, WebSearchService


class FakeSearchProvider(WebSearchProvider):
    def search(self, query, max_results, recency_days=None, domains=None):
        return [
            {"title": "Release oficial", "url": "https://example.com/release?tracking=1", "excerpt": "Versão atual", "published_at": "2026-08-30"},
            {"title": "Duplicado", "url": "https://example.com/release?other=2", "excerpt": "Mesmo documento"},
            {"title": "Outra fonte", "url": "https://docs.example.com/guide", "excerpt": "Guia"},
        ]


def public_resolver(host, port, type=socket.SOCK_STREAM):
    address = "93.184.216.34" if host == "example.com" else "127.0.0.1"
    return [(socket.AF_INET, type, 6, "", (address, port))]


def test_query_sanitizer_removes_private_data():
    clean, redactions = WebQuerySanitizer().sanitize("preço para mario@example.com telefone 11999998888 senha=abc123")
    assert "mario@example.com" not in clean
    assert "11999998888" not in clean
    assert "abc123" not in clean
    assert {"email", "telefone", "segredo"} <= set(redactions)


@pytest.mark.parametrize("url", ["http://localhost/admin", "http://127.0.0.1/", "file:///etc/passwd", "ftp://example.com/a"])
def test_ssrf_policy_blocks_local_and_non_http(url):
    with pytest.raises(UnsafeURL):
        WebURLPolicy(public_resolver).validate(url)


def test_fetcher_validates_every_redirect_hop():
    transport = httpx.MockTransport(lambda request: httpx.Response(302, headers={"location": "http://127.0.0.1/private"}))
    client = httpx.Client(transport=transport, follow_redirects=False)
    fetcher = WebPageFetcher(WebURLPolicy(public_resolver), client)
    with pytest.raises(UnsafeURL):
        fetcher.fetch("https://example.com/start")


def test_search_normalizes_deduplicates_and_keeps_provenance():
    result = WebSearchService(FakeSearchProvider()).search("versão atual", max_results=5)
    assert result["count"] == 2
    assert result["network_activity"] == "WEB SEARCH"
    assert all({"source_id", "title", "url", "domain", "retrieved_at", "excerpt"} <= set(source) for source in result["sources"])


def test_recency_filters_dated_results_and_reports_real_guarantee():
    class DatedProvider(WebSearchProvider):
        def search(self, query, max_results, recency_days=None, domains=None):
            return [
                {"title": "Antiga", "url": "https://example.com/old", "published_at": "2020-01-01"},
                {"title": "Atual", "url": "https://example.com/new", "published_at": "2026-08-30"},
            ]

    result = WebSearchService(DatedProvider()).search("atual", max_results=5, recency_days=2)
    assert [source["title"] for source in result["sources"]] == ["Atual"]
    assert result["recency_status"] == "guaranteed"
    assert result["recency_guarantee"] is True


def test_web_access_off_ask_on_policy():
    service = WebIntelligenceService(WebSearchService(FakeSearchProvider()))
    executor = ToolExecutor(ToolRegistry(web_tools(service)))
    repository.execute("INSERT OR REPLACE INTO app_settings VALUES (?,?,datetime('now'))", ("web_access", json.dumps({"mode": "OFF"})))
    assert executor.request("web_search", {"query": "teste"})["status"] == "blocked"
    repository.execute("UPDATE app_settings SET value_json=? WHERE key='web_access'", (json.dumps({"mode": "ASK"}),))
    proposal = executor.request("web_search", {"query": "teste"})
    assert proposal["status"] == "pending_confirmation"
    assert executor.confirm(proposal["action_id"], False)["status"] == "cancelled"
    repository.execute("UPDATE app_settings SET value_json=? WHERE key='web_access'", (json.dumps({"mode": "ON"}),))
    result = executor.request("web_search", {"query": "teste"})
    assert result["status"] == "success"
    assert result["data"]["count"] == 2


def test_network_audit_uses_sanitized_query_not_secret():
    service = WebIntelligenceService(WebSearchService(FakeSearchProvider()))
    executor = ToolExecutor(ToolRegistry(web_tools(service)))
    repository.execute("INSERT OR REPLACE INTO app_settings VALUES (?,?,datetime('now'))", ("web_access", json.dumps({"mode": "ON"})))
    executor.request("web_search", {"query": "versão para mario@example.com senha=segredo123"})
    row = repository.row("SELECT input_json FROM activity_log WHERE tool='web_search' ORDER BY timestamp DESC LIMIT 1")
    assert row is not None
    assert "mario@example.com" not in row["input_json"]
    assert "segredo123" not in row["input_json"]
