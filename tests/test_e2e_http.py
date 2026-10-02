import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import httpx2
import oauth_tokens
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

LAUNCH = [sys.executable, "-c", "from guard_core_mcp.http_server import main; main()"]

ALL_TOOLS = {
    "versions",
    "validate_config",
    "config_fields",
    "search_docs",
    "get_doc",
    "check_payload",
    "ecosystem",
    "adapter_setup",
    "wire_agent",
}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def wait_until_ready(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"hosted server exited early: {process.stderr}")
            try:
                response = await client.get(
                    f"{base_url}/.well-known/oauth-protected-resource"
                )
                if response.status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.1)
    raise RuntimeError("hosted server did not become ready")


@asynccontextmanager
async def running_http_server() -> AsyncIterator[tuple[str, str]]:
    port = free_port()
    pem = oauth_tokens.generate_key_pem()
    env = {
        **os.environ,
        "GUARD_CORE_MCP_HTTP_HOST": "127.0.0.1",
        "GUARD_CORE_MCP_HTTP_PORT": str(port),
        "GUARD_CORE_MCP_PUBLIC_URL": f"http://127.0.0.1:{port}",
        "GUARD_CORE_MCP_OAUTH_ISSUER": oauth_tokens.TEST_ISSUER,
        "GUARD_CORE_MCP_OAUTH_AUDIENCE": oauth_tokens.TEST_AUDIENCE,
        "GUARD_CORE_MCP_OAUTH_JWKS": oauth_tokens.build_jwks(pem),
    }
    with subprocess.Popen(
        LAUNCH, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    ) as process:
        base_url = f"http://127.0.0.1:{port}"
        try:
            await wait_until_ready(base_url, process)
            yield base_url, pem
        finally:
            process.terminate()
            process.wait(timeout=10)


@pytest.mark.e2e
async def test_metadata_and_rejection_over_real_http() -> None:
    async with running_http_server() as streams:
        base_url = streams[0]
        async with httpx.AsyncClient() as client:
            metadata = await client.get(
                f"{base_url}/.well-known/oauth-protected-resource"
            )
            rejected = await client.post(f"{base_url}/mcp", json={"jsonrpc": "2.0"})

    assert metadata.status_code == 200
    assert metadata.json()["resource"] == base_url
    assert rejected.status_code == 401
    assert "resource_metadata=" in rejected.headers["WWW-Authenticate"]


@pytest.mark.e2e
async def test_full_session_with_a_valid_token() -> None:
    async with running_http_server() as (base_url, pem):
        token = oauth_tokens.sign_token(pem)
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}
        ) as http_client:
            async with streamable_http_client(
                f"{base_url}/mcp", http_client=http_client
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listing = await session.list_tools()
                    verdict = await session.call_tool(
                        "check_payload",
                        {"path": "/probe", "query": {"q": "1' OR '1'='1"}},
                    )

    assert {tool.name for tool in listing.tools} == ALL_TOOLS
    report = json.loads(verdict.content[0].text)
    assert report["is_threat"] is True


@pytest.mark.e2e
async def test_wrong_audience_token_is_rejected_over_real_http() -> None:
    async with running_http_server() as streams:
        base_url = streams[0]
        token = oauth_tokens.sign_token(streams[1], aud="https://other-resource.test")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{base_url}/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": f"Bearer {token}"},
            )

    assert response.status_code == 401


@pytest.mark.e2e
async def test_versions_reports_the_hosted_pins_over_the_protocol() -> None:
    async with running_http_server() as (base_url, pem):
        token = oauth_tokens.sign_token(pem)
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {token}"}
        ) as http_client:
            async with streamable_http_client(
                f"{base_url}/mcp", http_client=http_client
            ) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("versions", {})

    report: dict[str, Any] = json.loads(result.content[0].text)
    assert report["installed"]["guard-core"] is not None
