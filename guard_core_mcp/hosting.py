import hmac
import json
import os
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWK, PyJWKClient
from mcp.server.transport_security import TransportSecuritySettings
from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from guard_core_mcp.server import mcp

METADATA_PATH = "/.well-known/oauth-protected-resource"


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"environment variable {name} is required for hosted mode")
    return value


@dataclass(frozen=True)
class HostingConfig:
    host: str
    port: int
    public_url: str
    oauth_issuer: str
    oauth_audience: str
    oauth_scope: str
    jwks_url: str | None
    jwks_inline: str | None
    mcprush_token: str | None = None

    @classmethod
    def from_env(cls) -> "HostingConfig":
        public_url = _env("GUARD_CORE_MCP_PUBLIC_URL").rstrip("/")
        jwks_url = os.environ.get("GUARD_CORE_MCP_OAUTH_JWKS_URL") or None
        jwks_inline = os.environ.get("GUARD_CORE_MCP_OAUTH_JWKS") or None
        if jwks_url is None and jwks_inline is None:
            raise RuntimeError(
                "set GUARD_CORE_MCP_OAUTH_JWKS_URL or GUARD_CORE_MCP_OAUTH_JWKS "
                "for hosted mode"
            )
        audience = os.environ.get("GUARD_CORE_MCP_OAUTH_AUDIENCE") or public_url
        return cls(
            host=os.environ.get("GUARD_CORE_MCP_HTTP_HOST", "127.0.0.1"),
            port=int(os.environ.get("GUARD_CORE_MCP_HTTP_PORT", "8020")),
            public_url=public_url,
            oauth_issuer=_env("GUARD_CORE_MCP_OAUTH_ISSUER").rstrip("/"),
            oauth_audience=audience.rstrip("/"),
            oauth_scope=os.environ.get("GUARD_CORE_MCP_OAUTH_SCOPE", "mcp"),
            jwks_url=jwks_url,
            jwks_inline=jwks_inline,
            mcprush_token=os.environ.get("MCPRUSH_TOKEN") or None,
        )

    def metadata_url(self) -> str:
        return f"{self.public_url}{METADATA_PATH}"

    def metadata_document(self) -> dict[str, Any]:
        return {
            "resource": self.public_url,
            "authorization_servers": [self.oauth_issuer],
            "scopes_supported": [self.oauth_scope],
            "bearer_methods_supported": ["header"],
        }


class TokenVerifier:
    def __init__(self, config: HostingConfig) -> None:
        self._issuer = config.oauth_issuer
        self._audience = config.oauth_audience
        self._required_scope = config.oauth_scope
        self._inline_keys = self._parse_inline_keys(config.jwks_inline)
        self._jwks_client = (
            PyJWKClient(config.jwks_url, cache_keys=True) if config.jwks_url else None
        )

    @staticmethod
    def _parse_inline_keys(jwks_inline: str | None) -> dict[str, PyJWK]:
        if not jwks_inline:
            return {}
        document = json.loads(jwks_inline)
        if isinstance(document, list):
            entries = document
        elif "keys" in document:
            entries = document["keys"]
        else:
            entries = [document]
        return {entry["kid"]: PyJWK.from_dict(entry) for entry in entries}

    def _signing_key(self, token: str) -> Any:
        if self._jwks_client is not None:
            return self._jwks_client.get_signing_key_from_jwt(token).key
        kid = jwt.get_unverified_header(token).get("kid")
        if kid is None or kid not in self._inline_keys:
            raise jwt.InvalidKeyError("unknown signing key id")
        return self._inline_keys[kid].key

    def verify(self, token: str) -> dict[str, Any]:
        claims = jwt.decode(
            token,
            key=self._signing_key(token),
            algorithms=["RS256"],
            issuer=self._issuer,
            audience=self._audience,
            options={"require": ["exp", "iss", "aud", "sub", "scope"]},
        )
        if self._required_scope not in str(claims["scope"]).split():
            raise jwt.InvalidTokenError("token lacks the required scope")
        return claims


class BearerAuthMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        verifier: TokenVerifier,
        metadata_url: str,
        mcprush_token: str | None = None,
    ) -> None:
        self.app = app
        self._verifier = verifier
        self._metadata_url = metadata_url
        self._mcprush_token = mcprush_token.encode() if mcprush_token else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == METADATA_PATH:
            await self.app(scope, receive, send)
            return
        mcprush = Headers(scope=scope).get("x-mcprush-token")
        if mcprush is not None:
            # The mcprush proxy authenticates with this header instead of an
            # OAuth bearer; a present-but-unmatched header must fail closed
            # rather than fall through to the bearer flow.
            if self._mcprush_token is None or not hmac.compare_digest(
                mcprush.encode(), self._mcprush_token
            ):
                await self._reject(scope, receive, send, "invalid mcprush token")
                return
            await self.app(scope, receive, send)
            return
        token = self._bearer_token(Headers(scope=scope).get("Authorization"))
        if token is None:
            await self._reject(scope, receive, send, "missing bearer token")
            return
        try:
            self._verifier.verify(token)
        except jwt.PyJWTError as exception:
            await self._reject(scope, receive, send, str(exception) or "invalid token")
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _bearer_token(authorization: str | None) -> str | None:
        if authorization is None or not authorization.lower().startswith("bearer "):
            return None
        return authorization[7:].strip()

    async def _reject(
        self, scope: Scope, receive: Receive, send: Send, detail: str
    ) -> None:
        response = JSONResponse(
            {"error": "invalid_token", "error_description": detail},
            status_code=401,
            headers={
                "WWW-Authenticate": f'Bearer resource_metadata="{self._metadata_url}"'
            },
        )
        await response(scope, receive, send)


class ProtectedResourceMetadata:
    def __init__(self, app: ASGIApp, config: HostingConfig) -> None:
        self.app = app
        self._document = config.metadata_document()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        serves_metadata = (
            scope["type"] == "http"
            and scope["method"] in ("GET", "HEAD")
            and scope["path"] == METADATA_PATH
        )
        if serves_metadata:
            response = JSONResponse(
                self._document, headers={"Cache-Control": "public, max-age=300"}
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def compose_hosted_stack(mcp_app: ASGIApp, config: HostingConfig) -> ASGIApp:
    auth = BearerAuthMiddleware(
        ProtectedResourceMetadata(mcp_app, config),
        TokenVerifier(config),
        config.metadata_url(),
        mcprush_token=config.mcprush_token,
    )
    return CORSMiddleware(
        auth,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Mcp-Session-Id",
            "Mcp-Protocol-Version",
            "Last-Event-Id",
            "X-Mcprush-Token",
        ],
        expose_headers=["Mcp-Session-Id"],
        max_age=86400,
    )


def create_hosted_app(config: HostingConfig) -> ASGIApp:
    return compose_hosted_stack(
        mcp.streamable_http_app(
            stateless_http=True,
            host=config.host,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=False
            ),
        ),
        config,
    )
