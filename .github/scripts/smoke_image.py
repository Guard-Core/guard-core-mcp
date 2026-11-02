"""Image smoke test (LEDGER 6.542).

Run inside the built image:
docker run --rm -i --entrypoint python <image> - < smoke_image.py

It starts the image's own guard-core-mcp-http with a throw-away RSA key as the
issuer's JWKS. Over streamable-http with a signed bearer token, and over the
stdio console script, it initializes and lists the tools. It needs only what
the image already carries.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

PORT = "8021"
BASE = "http://127.0.0.1:" + PORT
ISSUER = "https://auth.example.test"
PUBLIC_URL = "https://mcp.example.test"
EXPECTED_TOOLS = {
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


def signed_token_and_jwks() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    entry = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    entry.update(kid="smoke", alg="RS256", use="sig")
    claims = {
        "iss": ISSUER,
        "aud": PUBLIC_URL,
        "sub": "smoke",
        "scope": "mcp",
        "exp": int(time.time()) + 300,
    }
    token = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "smoke"})
    return token, json.dumps({"keys": [entry]})


async def tools_over_http(token: str) -> set[str]:
    headers = {"Authorization": "Bearer " + token}
    async with create_mcp_http_client(headers=headers) as client:
        async with streamable_http_client(BASE + "/mcp", http_client=client) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                info = await session.initialize()
                print("http initialize:", info.server_info.name, info.protocol_version)
                return {tool.name for tool in (await session.list_tools()).tools}


async def tools_over_stdio() -> set[str]:
    params = StdioServerParameters(command="guard-core-mcp", args=[])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print("stdio initialize:", info.server_info.name, info.protocol_version)
            return {tool.name for tool in (await session.list_tools()).tools}


def wait_for_server_card() -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(
                BASE + "/.well-known/mcp/server-card.json", timeout=2
            )
            return
        except OSError:
            time.sleep(0.5)
    raise SystemExit("the hosted server never served its server card")


def main() -> None:
    token, jwks = signed_token_and_jwks()
    env = {
        **os.environ,
        "GUARD_CORE_MCP_HTTP_HOST": "127.0.0.1",
        "GUARD_CORE_MCP_HTTP_PORT": PORT,
        "GUARD_CORE_MCP_PUBLIC_URL": PUBLIC_URL,
        "GUARD_CORE_MCP_OAUTH_ISSUER": ISSUER,
        "GUARD_CORE_MCP_OAUTH_JWKS": jwks,
    }
    with tempfile.TemporaryFile("w+") as log:
        server = subprocess.Popen(
            ["guard-core-mcp-http"], env=env, stdout=log, stderr=log
        )
        try:
            wait_for_server_card()
            try:
                urllib.request.urlopen(
                    urllib.request.Request(BASE + "/mcp", method="POST", data=b"{}"),
                    timeout=5,
                )
            except urllib.error.HTTPError as denied:
                assert denied.code == 401, denied.code
            else:
                raise SystemExit("an unauthenticated POST /mcp was not refused")
            over_http = asyncio.run(tools_over_http(token))
        finally:
            server.terminate()
            server.wait(timeout=15)
        log.seek(0)
        sys.stdout.write(log.read()[-2000:])
    over_stdio = asyncio.run(tools_over_stdio())
    assert over_http == EXPECTED_TOOLS, over_http
    assert over_stdio == EXPECTED_TOOLS, over_stdio
    print("smoke ok:", len(EXPECTED_TOOLS), "tools over streamable-http and stdio")


main()
