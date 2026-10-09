<p align="center">
    <a href="https://guard-core.github.io/guard-core/latest/">
        <img src="https://guard-core.github.io/guard-core/latest/assets/guard_core_legend.svg" alt="Guard Core">
    </a>
</p>

___

<p align="center">
    <strong>Model Context Protocol server for the Guard ecosystem: config validation, docs search, and corpus tooling for agents and developers.</strong>
</p>

<p align="center">
    <a href="https://badge.fury.io/py/guard-core-mcp">
        <img src="https://badge.fury.io/py/guard-core-mcp.svg?cache=none&icon=si%3Apython&icon_color=%23008cb4" alt="PyPiVersion">
    </a>
    <a href="https://guard-core.github.io/guard-core-mcp/latest/">
        <img src="https://img.shields.io/badge/docs-latest-0080ff.svg" alt="Docs">
    </a>
    <a href="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/release.yml">
        <img src="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/release.yml/badge.svg" alt="Release">
    </a>
    <a href="https://opensource.org/licenses/MIT">
        <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
    </a>
    <a href="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/ci.yml">
        <img src="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/ci.yml/badge.svg" alt="CI">
    </a>
    <a href="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/code-ql.yml">
        <img src="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/code-ql.yml/badge.svg" alt="CodeQL">
    </a>
</p>

<p align="center">
    <a href="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/pages/pages-build-deployment">
        <img src="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/pages/pages-build-deployment/badge.svg?branch=gh-pages" alt="PagesBuildDeployment">
    </a>
    <a href="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/docs.yml">
        <img src="https://github.com/Guard-Core/guard-core-mcp/actions/workflows/docs.yml/badge.svg" alt="DocsUpdate">
    </a>
    <img src="https://img.shields.io/github/last-commit/Guard-Core/guard-core-mcp?style=flat&amp;logo=git&amp;logoColor=white&amp;color=0080ff" alt="last-commit">
</p>

<p align="center">
    <img src="https://img.shields.io/badge/Python-3776AB.svg?style=flat&logo=python&logoColor=white" alt="Python"> <img src="https://img.shields.io/badge/MCP-1B1B1B.svg?style=flat" alt="MCP">
    <a href="https://pepy.tech/project/guard-core-mcp">
        <img src="https://pepy.tech/badge/guard-core-mcp" alt="Downloads">
    </a>
</p>

<p align="center">
    <a href="https://guard-core.com">Website</a> &middot;
    <a href="https://guard-core.github.io/guard-core-mcp/latest/">Docs</a> &middot;
    <a href="https://playground.guard-core.com">Playground</a> &middot;
    <a href="https://app.guard-core.com">Dashboard</a> &middot;
    <a href="https://discord.gg/ZW7ZJbjMkK">Discord</a>
</p>

---

## Why

Your agent can already read the docs. What it cannot do is tell you that the `redis_failopen` in your config is silently doing nothing because the real field is `redis_fail_open`, or that the flag you are reaching for did not exist until guard-core 3.5.0, or whether a given request would actually be blocked and by which pattern.

This server answers those from the installed package: real pydantic validation, real field metadata, and the real detection engine. It also answers the cross-language questions the libraries cannot answer: which package guards a Gin, Fastify, Laravel or Rocket app, whether it is tagged or still path-dependent, how to wire its telemetry agent, and what response codes the SaaS ingest endpoint returns.

## Install

Install it **into your project's environment**, not as an isolated tool:

```bash
uv add --dev guard-core-mcp
claude mcp add guard-core -- uv run guard-core-mcp
```

`uvx guard-core-mcp` will start, but an isolated environment contains no `guard-core` or `fastapi-guard` for it to introspect, so it can only answer from bundled documentation. Running it inside your own environment is what makes the answers match the versions you actually ship.

## Tools

| Tool | Answers |
|---|---|
| `versions` | Which Guard libraries are installed here, and at what version |
| `validate_config` | Is this config valid, including typo'd keys pydantic silently ignores |
| `config_fields` | What is this setting, what does it default to, does a setting for X exist |
| `search_docs` | Where do the docs cover this |
| `get_doc` | The full text of one documentation page |
| `check_payload` | Would this request be blocked, and by which pattern |
| `ecosystem` | The full registry matrix: 5 languages, engines, adapters, agents, conformance, SaaS contract |
| `adapter_setup` | Install plus a verified minimal integration for one adapter (e.g. `go` + `gin`) |
| `wire_agent` | How to set up the telemetry agent for a language, including the ingestion contract |

The ecosystem tools are pure data, so they work everywhere, with or without the Python libraries installed. Every quick-start snippet is copied verbatim from the sibling repo READMEs, and `release_status` tells you honestly whether a package is `published`, `tagged`, or still `untagged` (source, `main`, or path dependency only).

## ChatGPT plugin

The same tools are also served remotely at `https://mcp.guard-core.com/mcp` and packaged as a ChatGPT plugin: sign in with a guard-core account, and ChatGPT can validate configs, search the docs and run payloads through the hosted detection engine (the latest published releases, not your local versions). The packaging lives in [`plugin/`](plugin/), the hosted server in `guard_core_mcp.hosting`, and the full story (env vars, Docker image, developer-mode test loop, submission checklist) in the [ChatGPT plugin guide](https://guard-core-mcp.guard-core.com/latest/chatgpt-plugin/).

## Licence

MIT

mcp-name: io.github.Guard-Core/guard-core-mcp
