# guard-core-rs

The Rust port of the guard-core detection engine. Cargo workspace (`crates/*`), edition 2024, MSRV 1.92, `unsafe_code = "forbid"`.

## State

Tagged `v4.1.0` with both publishable crates on crates.io. Workspace members:

- `guard-core-rs` 4.1.0: the facade crate, re-exporting `detect`, `compiler`, `preprocessor` and `semantic` from the engine.
- `guard-core-engine` 4.1.0: the engine crate, the integration point the framework adapters depend on.
- `guard-core-python` 4.1.0: PyO3 cdylib binding, kept `publish = false`.
- `guard-core-benchmark` and `guard-core-conformance`: internal.

The README documents the two published crates and links the adapter repos.

## Setup

The adapters (tower-guard-rs, axum-guard-rs, actix-guard-rs, rocket-guard-rs) depend on the engine crate directly:

```toml
guard-core-engine = "4.1.0"
```

Engine view: `detect(content, context, config)` with `DetectConfig::max_full_scan_bytes` (262,144 bytes, the ecosystem default). The engine never scans the HTTP method, and its header view skips `sec-*` plus a fixed set of standard hop headers.

## Conformance

`conformance/` holds the spec 4.0.3 corpus (184 cases across 12 suites, pinned at reference commit `810d86cc`), a `pattern_ledger.toml`, and an `xfail_baseline.toml` that is effectively empty: running the full 4.x detect pipeline (pattern table across the scan views, semantic analysis, scoring), the engine passes the corpus (184/184 green under the fail-closed drift gate). Binary cases with full-entropy random noise are deliberately excluded from the corpus; their decode-stage parity gaps are covered by the `guard-core-engine` binary_noise_gate honesty tests instead.

## Footguns

- The facade crate re-exports the detect path, but the adapters still integrate through `guard-core-engine` directly; follow their lead unless you only need the facade surface.
- `guard-core-python` stays `publish = false`: do not look for it on crates.io.
- No `.agents` skill and no docs/ directory; AGENTS.md (mirrored byte-identically in CLAUDE.md) is the real documentation.
