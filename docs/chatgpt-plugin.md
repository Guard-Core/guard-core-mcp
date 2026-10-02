# Guard Core as a ChatGPT plugin

The same tools that power the local MCP server are also served remotely at
`https://mcp.guard-core.com/mcp` and packaged as a ChatGPT plugin, so ChatGPT
(and Codex, and any MCP client) can validate Guard configs, search the
documentation and run payloads through the real detection engine.

## Architecture

```text
ChatGPT (MCP client)
  |
  |  1. POST https://mcp.guard-core.com/mcp          -> 401 + WWW-Authenticate
  |  2. GET  /.well-known/oauth-protected-resource   -> points at the platform API
  |  3. GET  https://api.guard-core.com/.well-known/oauth-authorization-server
  |  4. Browser sign-in + consent (guard-core account, PKCE, RS256)
  |  5. Bearer access token on every MCP request
  v
guard-core-mcp hosted (streamable-http, all nine tools, latest pinned releases)
```

The hosted server is a pure OAuth 2.1 resource server: it verifies RS256
access tokens against the platform API's JWKS and checks the `mcp` scope.
It keeps no user data; configs and payloads sent to `validate_config` and
`check_payload` are processed transiently and never persisted or logged.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `GUARD_CORE_MCP_PUBLIC_URL` | yes | Public origin of the server, advertised as the OAuth resource (`https://mcp.guard-core.com`) |
| `GUARD_CORE_MCP_OAUTH_ISSUER` | yes | Authorization server origin (`https://api.guard-core.com`) |
| `GUARD_CORE_MCP_OAUTH_JWKS_URL` | one of two | Where to fetch signing keys (`https://api.guard-core.com/.well-known/jwks.json`) |
| `GUARD_CORE_MCP_OAUTH_JWKS` | one of two | Inline JWKS JSON, for tests and air-gapped runs; wins over the URL |
| `GUARD_CORE_MCP_OAUTH_AUDIENCE` | no | Expected `aud` claim; defaults to `GUARD_CORE_MCP_PUBLIC_URL` |
| `GUARD_CORE_MCP_OAUTH_SCOPE` | no | Required scope; defaults to `mcp` |
| `GUARD_CORE_MCP_HTTP_HOST` | no | Bind host; defaults to `127.0.0.1` |
| `GUARD_CORE_MCP_HTTP_PORT` | no | Bind port; defaults to `8020` |

## Running it

```bash
uv sync --extra hosted
export GUARD_CORE_MCP_PUBLIC_URL=https://mcp.guard-core.com
export GUARD_CORE_MCP_OAUTH_ISSUER=https://api.guard-core.com
export GUARD_CORE_MCP_OAUTH_JWKS_URL=https://api.guard-core.com/.well-known/jwks.json
make run-http
```

Or use the container image, which is what the platform deploys:

```bash
docker run -p 8020:8020 \
  -e GUARD_CORE_MCP_PUBLIC_URL=https://mcp.guard-core.com \
  -e GUARD_CORE_MCP_OAUTH_ISSUER=https://api.guard-core.com \
  -e GUARD_CORE_MCP_OAUTH_JWKS_URL=https://api.guard-core.com/.well-known/jwks.json \
  ghcr.io/rennf93/guard-core-mcp:<version>
```

The image installs the `hosted` extra, so `versions` reports the exact
guard-core, fastapi-guard and guard-agent releases the container was built
with. The lockfile pins those at build time; refresh them with
`uv lock --upgrade` when a new engine release ships.

## Testing in ChatGPT developer mode

1. Settings -> Security and login -> enable Developer mode.
2. In ChatGPT Plugins, add a connector with the URL `https://mcp.guard-core.com/mcp`.
3. ChatGPT discovers the OAuth metadata and opens the guard-core sign-in; sign in, approve the consent screen.
4. From the homepage, switch the tab from Chat to Work, type `@` and pick Guard Core.
5. Ask: "Would fastapi-guard block POST /login with body user=admin' OR 1=1--?" and confirm `check_payload` reports a threat.

## Local development against a local API

Point every variable at localhost, generate a test signing key on the API
side, and pass the public half inline:

```bash
GUARD_CORE_MCP_PUBLIC_URL=http://127.0.0.1:8020 \
GUARD_CORE_MCP_OAUTH_ISSUER=http://127.0.0.1:8000 \
GUARD_CORE_MCP_OAUTH_JWKS='{"keys":[ ...public jwk... ]}' \
make run-http
```

The e2e tests in `tests/test_e2e_http.py` do exactly this with a throwaway
RSA key.

## Plugin package

`plugin/` holds the directory submission package: `plugin.json` (identity and
the `com.openai` presentation metadata), `mcp.json` (the remote server
declaration) and `skills/guard-core/SKILL.md` (tool-selection guidance that
ships to the model). The icons under `plugin/assets/` are generated
placeholders; swap in official brand assets before submitting if you have
them.

## Submission checklist

- [ ] DNS record for `mcp.guard-core.com` and the Let's Encrypt certificate
- [ ] Platform API deployed with the OAuth authorization server enabled
- [ ] Signing key generated (`scripts/generate_oauth_signing_key.py` in guard-core-app) and stored as a secret
- [ ] ChatGPT client registered on the OpenAI platform; its redirect URI and client id added to the API's `OAUTH_SERVER_CLIENTS`
- [ ] Developer-mode test loop passes end to end
- [ ] Privacy policy at guard-core.com/privacy mentions the plugin connection and transient payload processing
- [ ] Upload `plugin/` through the plugin submission portal and pass review
