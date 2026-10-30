import asyncio
import json
import time
from unittest.mock import MagicMock

import jwt
import oauth_tokens
import pytest
from jwt import PyJWKClient
from jwt.jwk_set_cache import JWKSetCache
from starlette.types import Message, Scope

from guard_core_mcp import hosting
from guard_core_mcp.hosting import (
    UNKNOWN_KID_TTL_SECONDS,
    BearerAuthMiddleware,
    HostingConfig,
    TokenVerifier,
)

JWKS_URL = "https://issuer.test/jwks.json"
OTHER_KEYS = json.loads(oauth_tokens.build_jwks(oauth_tokens.generate_key_pem()))
FETCH_SECONDS = 0.2


def jwks_config() -> HostingConfig:
    return HostingConfig(
        host="127.0.0.1",
        port=8020,
        public_url=oauth_tokens.TEST_AUDIENCE,
        oauth_issuer=oauth_tokens.TEST_ISSUER,
        oauth_audience=oauth_tokens.TEST_AUDIENCE,
        oauth_scope=oauth_tokens.TEST_SCOPE,
        jwks_url=JWKS_URL,
        jwks_inline=None,
    )


def count_jwks_fetches(
    monkeypatch: pytest.MonkeyPatch, document: dict[str, object], delay: float = 0.0
) -> list[float]:
    fetches: list[float] = []

    def fetch(self: PyJWKClient) -> dict[str, object]:
        fetches.append(time.monotonic())
        time.sleep(delay)
        return document

    monkeypatch.setattr(PyJWKClient, "fetch_data", fetch)
    return fetches


def one_miss_fetches(monkeypatch: pytest.MonkeyPatch) -> int:
    """JWKS fetches PyJWKClient itself makes for one unknown-kid token."""
    fetches = count_jwks_fetches(monkeypatch, OTHER_KEYS)
    with pytest.raises(jwt.PyJWTError):
        TokenVerifier(jwks_config()).verify(bad_kid_token("probe"))
    return len(fetches)


async def call_with_token(middleware: BearerAuthMiddleware, token: str) -> int:
    statuses: list[int] = []

    async def receive() -> Message:
        return {"type": "http.request", "body": b""}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
    }
    await middleware(scope, receive, send)
    return statuses[0]


def bad_kid_token(kid: str) -> str:
    return jwt.encode({"x": 1}, "k" * 32, algorithm="HS256", headers={"kid": kid})


async def test_a_burst_of_distinct_unknown_kids_fetches_once_and_keeps_the_loop_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = one_miss_fetches(monkeypatch)
    fetches = count_jwks_fetches(monkeypatch, OTHER_KEYS, FETCH_SECONDS)
    middleware = BearerAuthMiddleware(
        MagicMock(), TokenVerifier(jwks_config()), "https://m.test/meta"
    )
    ticks: list[float] = []

    async def heartbeat() -> None:
        while True:
            ticks.append(time.monotonic())
            await asyncio.sleep(0.01)

    beat = asyncio.create_task(heartbeat())
    statuses = await asyncio.gather(
        *(call_with_token(middleware, bad_kid_token(f"kid-{n}")) for n in range(10))
    )
    beat.cancel()

    assert set(statuses) == {401}
    assert len(fetches) == expected
    assert (
        max(b - a for a, b in zip(ticks, ticks[1:], strict=False)) < FETCH_SECONDS / 2
    )


async def test_an_unknown_kid_is_refetched_only_after_the_miss_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pem = oauth_tokens.generate_key_pem()
    document = dict(OTHER_KEYS)
    fetches = count_jwks_fetches(monkeypatch, document)
    clock = [1000.0]
    monkeypatch.setattr(hosting.time, "monotonic", lambda: clock[0])
    verifier = TokenVerifier(jwks_config())
    assert verifier._jwks_client is not None
    verifier._jwks_client.cooldown_duration = 0
    token = oauth_tokens.sign_token(pem, kid="rotated")

    with pytest.raises(jwt.PyJWTError):
        verifier.verify(token)
    one_miss = len(fetches)
    for _ in range(3):
        with pytest.raises(jwt.PyJWTError):
            verifier.verify(token)
    assert len(fetches) == one_miss

    clock[0] += UNKNOWN_KID_TTL_SECONDS + 1
    rotated = json.loads(oauth_tokens.build_jwks(pem))["keys"][0]
    document["keys"] = [{**rotated, "kid": "rotated"}]

    assert verifier.verify(token)["sub"] == "user_abc123"


async def test_a_jwks_connection_failure_is_not_remembered_as_an_unknown_kid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def fail(self: PyJWKClient) -> dict[str, object]:
        calls.append(1)
        raise jwt.PyJWKClientConnectionError("issuer down")

    monkeypatch.setattr(PyJWKClient, "fetch_data", fail)
    verifier = TokenVerifier(jwks_config())

    for _ in range(2):
        with pytest.raises(jwt.PyJWKClientConnectionError):
            verifier.verify(bad_kid_token("k1"))

    assert len(calls) == 2


async def test_an_empty_jwks_document_is_remembered_like_an_unknown_kid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetches = count_jwks_fetches(monkeypatch, {"keys": []})
    verifier = TokenVerifier(jwks_config())

    for number in range(3):
        with pytest.raises(jwt.PyJWTError):
            verifier.verify(bad_kid_token(f"kid-{number}"))

    assert len(fetches) == 1


async def test_a_known_kid_verifies_on_the_loop_without_a_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pem = oauth_tokens.generate_key_pem()
    count_jwks_fetches(monkeypatch, json.loads(oauth_tokens.build_jwks(pem)))
    verifier = TokenVerifier(jwks_config())
    token = oauth_tokens.sign_token(pem)
    assert (await verifier.verify_without_blocking(token))["sub"] == "user_abc123"

    def no_thread(*args: object) -> None:
        raise AssertionError("a cached key must not cost a thread hop")

    monkeypatch.setattr(hosting.asyncio, "to_thread", no_thread)

    assert (await verifier.verify_without_blocking(token))["sub"] == "user_abc123"


async def test_an_expired_jwk_set_is_refetched_inside_the_miss_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pem = oauth_tokens.generate_key_pem()
    document = json.loads(oauth_tokens.build_jwks(pem))
    fetches = count_jwks_fetches(monkeypatch, document)
    verifier = TokenVerifier(jwks_config())
    assert verifier._jwks_client is not None
    verifier.verify(oauth_tokens.sign_token(pem))
    with pytest.raises(jwt.PyJWTError):
        verifier.verify(bad_kid_token("unknown"))
    document["keys"] = [{**document["keys"][0], "kid": "rotated"}]
    verifier._jwks_client.jwk_set_cache = JWKSetCache(300)
    before = len(fetches)

    claims = verifier.verify(oauth_tokens.sign_token(pem, kid="rotated"))

    assert claims["sub"] == "user_abc123"
    assert len(fetches) == before + 1
