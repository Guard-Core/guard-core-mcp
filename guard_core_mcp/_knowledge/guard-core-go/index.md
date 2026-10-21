# guard-core-go

The Go port of the guard-core security engine. Module `github.com/rennf93/guard-core-go/v4`, directive `go 1.26.0`, direct dependencies on `dlclark/regexp2`, `oschwald/maxminddb-golang`, `redis/go-redis/v9`, `golang.org/x/sys` and `golang.org/x/text`.

## Install

```sh
go get github.com/rennf93/guard-core-go/v4@v4.4.1
```

Tagged `v4.4.1` and served by the Go module proxy under the `/v4` major path (v2+ modules require the major-version suffix in the import path). Version is carried entirely by the git tag; there is no version constant in the Go source.

## Setup

The engine pattern used by every Go adapter:

1. `cfg := guardcore.DefaultSecurityConfig()`
2. `engine, err := guardcore.NewEngine(cfg)`
3. `engine.Initialize()`
4. Hand the engine to an adapter constructor such as `nethttp.New(engine)`.

Direct detection entry point: `guardcore.Detect(content, ip, context)` returning a `DetectResult`. Route-level configuration registers through `engine.Routes.Register`, and adapters pick route ids off the request context with their `WithRouteID(ctx, id)` option.

## Conformance

`conformance/guard-core-spec-4.1.0/` vendors the frozen spec 4.1.0 fixture corpus: 375 cases across 21 suites (13 detect suites, the 5 pipeline suites pipeline_ip_control, pipeline_rate_limits, pipeline_detection_response, pipeline_headers_cors and pipeline_behavior_rules, plus event_stream, redis_interop and safety_gates). `cases/index.json` pins `spec_version` 4.1.0 and records the generating reference engine (4.3.2, commit `37b6a132`); the expected values come from the reference engine and are never hand-written. The runners are `conformance_test.go`, `pipeline_test.go`, `events_test.go`, `redis_interop_test.go`, `safety_gates_test.go` and `cost_budget_test.go`, and the documented Go expected failures sit beside the corpus in `go_events_xfail.json`, `go_pipeline_xfail.json` and `go_redis_interop_xfail.json`.

## Footguns

- The README carries install and usage; the per-framework quick starts live in the adapter READMEs (nethttp-guard, gin-guard, echo-guard, fiber-guard).
- AGENTS.md and CLAUDE.md sit at the repo root, and a SKILL.md ships at `guardcore/.agents/skills/guard-core-go/SKILL.md`.
- The pre-`/v4` `v0.1.0` tag remains burned into Go module proxies forever: never depend on the unsuffixed module path.
