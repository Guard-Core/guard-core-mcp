from typing import Any

import oauth_tokens
import pytest

from guard_core_mcp import http_server


def test_main_serves_the_hosted_app_on_the_configured_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GUARD_CORE_MCP_HTTP_HOST", "127.0.0.1")
    monkeypatch.setenv("GUARD_CORE_MCP_HTTP_PORT", "8123")
    monkeypatch.setenv("GUARD_CORE_MCP_PUBLIC_URL", oauth_tokens.TEST_AUDIENCE)
    monkeypatch.setenv("GUARD_CORE_MCP_OAUTH_ISSUER", oauth_tokens.TEST_ISSUER)
    monkeypatch.setenv("GUARD_CORE_MCP_OAUTH_AUDIENCE", oauth_tokens.TEST_AUDIENCE)
    monkeypatch.setenv(
        "GUARD_CORE_MCP_OAUTH_JWKS",
        oauth_tokens.build_jwks(oauth_tokens.generate_key_pem()),
    )
    calls: list[tuple[Any, dict[str, Any]]] = []
    monkeypatch.setattr(
        http_server.uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs))
    )

    http_server.main()

    assert len(calls) == 1
    app, kwargs = calls[0]
    assert callable(app)
    assert kwargs == {"host": "127.0.0.1", "port": 8123, "log_level": "info"}
