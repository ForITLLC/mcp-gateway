import copy
import importlib.util
from pathlib import Path

import httpx
import pytest
from fastmcp import Client
from starlette.testclient import TestClient

from forit_mcp_gateway.auth import BearerVerifier
from forit_mcp_gateway.config import Config, Source
from forit_mcp_gateway.gateway import SourceState, create_gateway
from forit_mcp_gateway.schema import prepare_schema

module = importlib.util.spec_from_file_location("catalog", Path(__file__).parents[1] / "examples/catalog_api.py")
catalog = importlib.util.module_from_spec(module)
module.loader.exec_module(catalog)

TOKEN = "test-only-gateway-token-32-characters-long"

@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv("MCP_GATEWAY_TOKEN", TOKEN)
    return Config(sources=[Source(namespace="catalog", baseUrl="https://catalog.example",
                                  specUrl="https://catalog.example/openapi.json")])


def upstream(request):
    if request.url.path == "/openapi.json":
        return httpx.Response(200, json=catalog.SPEC, headers={"etag": '"one"'})
    return httpx.Response(200, json=catalog.ITEMS)


async def test_real_mcp_calls_exclude_writes(config):
    server = create_gateway(config, transport=httpx.MockTransport(upstream))
    async with Client(server) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == {"catalog_list_items", "catalog_get_item"}
        result = await client.call_tool("catalog_list_items", {})
        assert "Notebook" in str(result)
        with pytest.raises(Exception, match="[Nn]ot found|[Uu]nknown"):
            await client.call_tool("catalog_create_item", {})


async def test_explicit_write_allowlist(config):
    config.sources[0].readOnly = False
    config.sources[0].allowedOperations = ["create_item"]
    server = create_gateway(config, transport=httpx.MockTransport(upstream))
    async with Client(server) as client:
        assert [tool.name for tool in await client.list_tools()] == ["catalog_create_item"]


async def test_refresh_preserves_last_good_and_recovers(config):
    current = {"spec": catalog.SPEC, "status": 200, "etag": '"one"'}
    def handler(request):
        return httpx.Response(current["status"], json=current["spec"], headers={"etag": current["etag"]})
    state = SourceState(config.sources[0], transport=httpx.MockTransport(handler))
    try:
        current["status"] = 503
        await state.refresh()
        assert not state.ready and not state.slot.providers
        current["status"] = 200
        await state.refresh()
        old = state.slot.providers[0]
        current["spec"] = {"invalid": True}
        current["etag"] = '"bad"'
        await state.refresh()
        assert not state.ready and state.slot.providers[0] is old and state.etag == '"one"'
        current["spec"] = copy.deepcopy(catalog.SPEC)
        current["spec"]["paths"]["/items"]["get"]["operationId"] = "list_catalog"
        await state.refresh()
        assert state.ready and state.slot.providers[0] is not old
        assert "list_catalog" in {tool.name for tool in await state.slot.list_tools()}
        current["status"] = 304
        await state.refresh()
        assert state.ready
    finally:
        await state.client.aclose()


async def test_credentials_cannot_be_overridden_or_redirected(config, monkeypatch):
    monkeypatch.setenv("CATALOG_KEY", "test-only-upstream-key")
    source = Source(namespace="catalog", baseUrl="https://catalog.example/api",
                    specUrl="https://catalog.example/openapi.json", auth={"envVar": "CATALOG_KEY"})
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "https://other.example/steal"})
    state = SourceState(source, transport=httpx.MockTransport(handler))
    try:
        response = await state.client.get("https://catalog.example/api/items", headers={"Authorization": "attacker"})
        assert response.status_code == 302 and len(seen) == 1
        assert seen[0].headers["Authorization"] == "Bearer test-only-upstream-key"
        for url in ("https://other.example/api/items", "https://catalog.example/private", "https://catalog.example/api/%2e%2e/private"):
            with pytest.raises(ValueError):
                await state.client.get(url)
        assert len(seen) == 1
    finally:
        await state.client.aclose()


def test_schema_confinement(config):
    spec = copy.deepcopy(catalog.SPEC)
    spec["servers"] = [{"url": "https://other.example"}]
    spec["paths"]["/items"]["servers"] = spec["servers"]
    sanitized = prepare_schema(spec, config.sources[0])
    assert "servers" not in sanitized and "servers" not in sanitized["paths"]["/items"]
    spec["components"] = {"schemas": {"Bad": {"$ref": "https://other.example/schema"}}}
    with pytest.raises(ValueError, match="local component"):
        prepare_schema(spec, config.sources[0])


def test_http_auth_and_health(config):
    with TestClient(create_gateway(config, transport=httpx.MockTransport(upstream)).http_app()) as client:
        assert client.get("/mcp").status_code == 401
        assert client.get("/mcp", headers={"Authorization": "Bearer incorrect"}).status_code == 401
        assert client.get("/health").json() == {"status": "ok", "sources": 1, "ready": 1}
        response = client.post("/mcp", headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json, text/event-stream"},
                               json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                                   "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}})
        assert response.status_code == 200


async def test_bearer_verification():
    verifier = BearerVerifier(TOKEN)
    assert await verifier.verify_token("bad") is None
    assert (await verifier.verify_token(TOKEN)).client_id == "gateway-service"


def test_fail_closed_configuration(config, monkeypatch):
    monkeypatch.delenv("MCP_GATEWAY_TOKEN")
    with pytest.raises(ValueError, match="Required environment"):
        create_gateway(config)
    for update in ({"readOnly": False}, {"specUrl": "https://other.example/openapi.json"}, {"baseUrl": "http://catalog.example"}):
        with pytest.raises(ValueError):
            Source.model_validate(config.sources[0].model_dump() | update)


def test_forit_logo_on_oauth_errors(config, monkeypatch):
    for name, value in {"ENTRA_CLIENT_ID": "00000000-0000-0000-0000-000000000001", "ENTRA_TENANT_ID": "00000000-0000-0000-0000-000000000002",
                        "ENTRA_CLIENT_SECRET": "test-only-client-secret", "MCP_OAUTH_SIGNING_KEY": TOKEN}.items():
        monkeypatch.setenv(name, value)
    config = Config.model_validate(config.model_dump() | {"auth": {
        "mode": "entra", "publicUrl": "https://gateway.example", "allowedRedirectUris": ["https://client.example/callback"]}})
    with TestClient(create_gateway(config, transport=httpx.MockTransport(upstream)).http_app()) as client:
        for path in ("/auth/callback?error=access_denied", "/authorize?client_id=unregistered&response_type=code&redirect_uri=https://client.example/callback&code_challenge=" + "a" * 43 + "&code_challenge_method=S256"):
            response = client.get(path, headers={"Accept": "text/html"})
            assert response.status_code == 400
            assert "data:image/png;base64," in response.text
            assert "blue-logo.png" not in response.text
        registration = client.post("/register", json={
            "client_name": "Demo MCP client", "redirect_uris": ["https://client.example/callback"],
            "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
            "token_endpoint_auth_method": "none"})
        assert registration.status_code == 201
        consent = client.get("/authorize", params={
            "client_id": registration.json()["client_id"], "response_type": "code",
            "redirect_uri": "https://client.example/callback", "code_challenge": "a" * 43,
            "code_challenge_method": "S256", "scope": "tools.read"})
        assert consent.status_code == 200
        assert "data:image/png;base64," in consent.text and "blue-logo.png" not in consent.text


async def test_base_path_and_header_credentials_in_real_tool_call(config, monkeypatch):
    monkeypatch.setenv("CATALOG_KEY", "test-only-key")
    spec = copy.deepcopy(catalog.SPEC)
    spec["paths"]["/items"]["get"]["parameters"] = [{
        "name": "Authorization", "in": "header", "schema": {"type": "string"}}]
    seen = []
    def handler(request):
        seen.append(request)
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=spec)
        return httpx.Response(200, json=catalog.ITEMS)
    config = Config.model_validate(config.model_dump() | {"sources": [{
        "namespace": "catalog", "baseUrl": "https://catalog.example/v1",
        "specUrl": "https://catalog.example/openapi.json", "auth": {"envVar": "CATALOG_KEY"}}]})
    async with Client(create_gateway(config, transport=httpx.MockTransport(handler))) as client:
        await client.call_tool("catalog_list_items", {"Authorization": "caller-controlled"})
        assert seen[-1].url.path == "/v1/items"
        assert seen[-1].headers["Authorization"] == "Bearer test-only-key"


def test_degraded_health(config):
    with TestClient(create_gateway(config, transport=httpx.MockTransport(
            lambda request: httpx.Response(503))).http_app()) as client:
        assert client.get("/health").status_code == 503
        assert client.get("/health").json() == {"status": "degraded", "sources": 1, "ready": 0}
