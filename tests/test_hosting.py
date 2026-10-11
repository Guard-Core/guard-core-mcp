import json
from typing import Any

import httpx
import jwt
import oauth_tokens
import pytest
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from guard_core_mcp.hosting import (
    METADATA_PATH,
    HostingConfig,
    TokenVerifier,
    compose_hosted_stack,
)


class RecordingApp:
    def __init__(self) -> None:
        self.reached = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.reached = True
        await JSONResponse({"ok": True})(scope, receive, send)


def make_config(**overrides: Any) -> HostingConfig:
    values: dict[str, Any] = {
        "host": "127.0.0.1",
        "port": 8020,
        "public_url": oauth_tokens.TEST_AUDIENCE,
        "oauth_issuer": oauth_tokens.TEST_ISSUER,
        "oauth_audience": oauth_tokens.TEST_AUDIENCE,
        "oauth_scope": oauth_tokens.TEST_SCOPE,
        "jwks_url": None,
        "jwks_inline": None,
    }
    values.update(overrides)
    return HostingConfig(**values)


def make_stack(jwks: str, **overrides: Any) -> tuple[Any, RecordingApp]:
    inner = RecordingApp()
    return compose_hosted_stack(
        inner, make_config(jwks_inline=jwks, **overrides)
    ), inner


def make_client(stack: Any) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=stack)
    return httpx.AsyncClient(transport=transport, base_url=oauth_tokens.TEST_AUDIENCE)


async def post_mcp(
    client: httpx.AsyncClient, token: str | None = None
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return await client.post(
        "/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1}, headers=headers
    )


async def test_metadata_is_served_without_authentication() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, _ = make_stack(oauth_tokens.build_jwks(pem))
    async with make_client(stack) as client:
        response = await client.get(METADATA_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "resource": oauth_tokens.TEST_AUDIENCE,
        "authorization_servers": [oauth_tokens.TEST_ISSUER],
        "scopes_supported": [oauth_tokens.TEST_SCOPE],
        "bearer_methods_supported": ["header"],
    }
    assert "max-age=300" in response.headers["Cache-Control"]


async def test_metadata_answers_head_requests() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, _ = make_stack(oauth_tokens.build_jwks(pem))
    async with make_client(stack) as client:
        response = await client.head(METADATA_PATH)

    assert response.status_code == 200


async def test_missing_token_is_rejected_with_a_discovery_hint() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, inner = make_stack(oauth_tokens.build_jwks(pem))
    async with make_client(stack) as client:
        response = await post_mcp(client)

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"
    expected = f'Bearer resource_metadata="{oauth_tokens.TEST_AUDIENCE}{METADATA_PATH}"'
    assert response.headers["WWW-Authenticate"] == expected
    assert inner.reached is False


async def test_non_bearer_credentials_are_rejected() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, _ = make_stack(oauth_tokens.build_jwks(pem))
    async with make_client(stack) as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": None},
        {"aud": "https://other-resource.test"},
        {"iss": "https://other-issuer.test"},
        {"scope": "other-scope"},
        {"sub": None},
    ],
)
async def test_malformed_claims_are_rejected(overrides: dict[str, Any]) -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, inner = make_stack(oauth_tokens.build_jwks(pem))
    token = oauth_tokens.sign_token(pem, **overrides)
    async with make_client(stack) as client:
        response = await post_mcp(client, token)

    assert response.status_code == 401
    assert inner.reached is False


async def test_signed_garbage_is_rejected() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, _ = make_stack(oauth_tokens.build_jwks(pem))
    async with make_client(stack) as client:
        response = await post_mcp(client, "not-a-token")

    assert response.status_code == 401


async def test_valid_token_reaches_the_server() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, inner = make_stack(oauth_tokens.build_jwks(pem))
    token = oauth_tokens.sign_token(pem)
    async with make_client(stack) as client:
        response = await post_mcp(client, token)

    assert response.status_code == 200
    assert inner.reached is True


async def test_mcprush_token_authenticates_the_proxy() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, inner = make_stack(
        oauth_tokens.build_jwks(pem), mcprush_token="mgw_unit_token"
    )
    async with make_client(stack) as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"x-mcprush-token": "mgw_unit_token"},
        )

    assert response.status_code == 200
    assert inner.reached is True


async def test_wrong_mcprush_token_is_rejected() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, inner = make_stack(
        oauth_tokens.build_jwks(pem), mcprush_token="mgw_unit_token"
    )
    async with make_client(stack) as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"x-mcprush-token": "mgw_attacker_value"},
        )

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_token"
    assert inner.reached is False


async def test_mcprush_header_fails_closed_without_configuration() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, inner = make_stack(oauth_tokens.build_jwks(pem))
    async with make_client(stack) as client:
        response = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"x-mcprush-token": "mgw_unit_token"},
        )

    assert response.status_code == 401
    assert inner.reached is False


async def test_mcprush_configuration_leaves_the_bearer_flow_untouched() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, inner = make_stack(
        oauth_tokens.build_jwks(pem), mcprush_token="mgw_unit_token"
    )
    token = oauth_tokens.sign_token(pem)
    async with make_client(stack) as client:
        anonymous = await post_mcp(client)
        reached_after_anonymous = inner.reached
        inner.reached = False
        bearer = await post_mcp(client, token)

    assert anonymous.status_code == 401
    assert reached_after_anonymous is False
    assert bearer.status_code == 200
    assert inner.reached is True


async def test_preflight_requests_short_circuit_without_auth() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, inner = make_stack(oauth_tokens.build_jwks(pem))
    async with make_client(stack) as client:
        response = await client.options(
            "/mcp",
            headers={
                "Origin": "https://chatgpt.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert inner.reached is False


async def test_metadata_responses_carry_cors_headers() -> None:
    pem = oauth_tokens.generate_key_pem()
    stack, _ = make_stack(oauth_tokens.build_jwks(pem))
    async with make_client(stack) as client:
        response = await client.get(
            METADATA_PATH, headers={"Origin": "https://chatgpt.com"}
        )

    assert response.headers["access-control-allow-origin"] == "*"


@pytest.mark.parametrize("jwks_shape", ["document", "bare-key", "bare-key-list"])
async def test_inline_jwks_shapes_all_verify(jwks_shape: str) -> None:
    pem = oauth_tokens.generate_key_pem()
    document = oauth_tokens.build_jwks(pem)
    entry = json.loads(document)["keys"][0]
    if jwks_shape == "bare-key":
        inline = json.dumps(entry)
    elif jwks_shape == "bare-key-list":
        inline = json.dumps([entry])
    else:
        inline = document
    verifier = TokenVerifier(make_config(jwks_inline=inline))
    claims = verifier.verify(oauth_tokens.sign_token(pem))

    assert claims["sub"] == "user_abc123"


def test_inline_jwks_rejects_an_unknown_key_id() -> None:
    pem = oauth_tokens.generate_key_pem()
    verifier = TokenVerifier(make_config(jwks_inline=oauth_tokens.build_jwks(pem)))

    with pytest.raises(jwt.InvalidKeyError):
        verifier.verify(oauth_tokens.sign_token(pem, kid="rotated-away"))


def test_from_env_requires_the_public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GUARD_CORE_MCP_PUBLIC_URL", raising=False)

    with pytest.raises(RuntimeError, match="GUARD_CORE_MCP_PUBLIC_URL"):
        HostingConfig.from_env()


def test_from_env_requires_a_jwks_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_CORE_MCP_PUBLIC_URL", "https://mcp.guard-core.com")
    monkeypatch.setenv("GUARD_CORE_MCP_OAUTH_ISSUER", oauth_tokens.TEST_ISSUER)
    monkeypatch.delenv("GUARD_CORE_MCP_OAUTH_JWKS_URL", raising=False)
    monkeypatch.delenv("GUARD_CORE_MCP_OAUTH_JWKS", raising=False)

    with pytest.raises(RuntimeError, match="GUARD_CORE_MCP_OAUTH_JWKS"):
        HostingConfig.from_env()


def test_from_env_parses_and_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_CORE_MCP_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("GUARD_CORE_MCP_HTTP_PORT", "9443")
    monkeypatch.setenv("GUARD_CORE_MCP_PUBLIC_URL", "https://mcp.guard-core.com/")
    monkeypatch.setenv("GUARD_CORE_MCP_OAUTH_ISSUER", "https://api.guard-core.com/")
    monkeypatch.delenv("GUARD_CORE_MCP_OAUTH_AUDIENCE", raising=False)
    monkeypatch.delenv("GUARD_CORE_MCP_OAUTH_SCOPE", raising=False)
    monkeypatch.delenv("MCPRUSH_TOKEN", raising=False)
    monkeypatch.setenv(
        "GUARD_CORE_MCP_OAUTH_JWKS_URL",
        "https://api.guard-core.com/.well-known/jwks.json",
    )

    config = HostingConfig.from_env()

    assert config.host == "0.0.0.0"
    assert config.port == 9443
    assert config.public_url == "https://mcp.guard-core.com"
    assert config.oauth_issuer == "https://api.guard-core.com"
    assert config.oauth_audience == "https://mcp.guard-core.com"
    assert config.oauth_scope == "mcp"
    assert config.jwks_url == "https://api.guard-core.com/.well-known/jwks.json"
    assert config.jwks_inline is None
    assert config.mcprush_token is None


def test_from_env_reads_the_mcprush_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_CORE_MCP_PUBLIC_URL", "https://mcp.guard-core.com")
    monkeypatch.setenv("GUARD_CORE_MCP_OAUTH_ISSUER", oauth_tokens.TEST_ISSUER)
    monkeypatch.setenv(
        "GUARD_CORE_MCP_OAUTH_JWKS_URL",
        "https://api.guard-core.com/.well-known/jwks.json",
    )
    monkeypatch.setenv("MCPRUSH_TOKEN", "mgw_unit_token")
    assert HostingConfig.from_env().mcprush_token == "mgw_unit_token"

    monkeypatch.setenv("MCPRUSH_TOKEN", "")
    assert HostingConfig.from_env().mcprush_token is None


def test_from_env_prefers_the_explicit_audience(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GUARD_CORE_MCP_PUBLIC_URL", "https://mcp.guard-core.com")
    monkeypatch.setenv("GUARD_CORE_MCP_OAUTH_ISSUER", oauth_tokens.TEST_ISSUER)
    monkeypatch.setenv("GUARD_CORE_MCP_OAUTH_AUDIENCE", "https://audience.test")
    monkeypatch.setenv(
        "GUARD_CORE_MCP_OAUTH_JWKS",
        oauth_tokens.build_jwks(oauth_tokens.generate_key_pem()),
    )

    assert HostingConfig.from_env().oauth_audience == "https://audience.test"
