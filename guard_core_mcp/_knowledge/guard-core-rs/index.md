# guard-core-rs

The Rust port of the guard-core detection engine. Cargo workspace (`crates/*`), edition 2024, MSRV 1.92, `unsafe_code = "forbid"`.

## State

Tagged `v4.2.0` with both publishable crates on crates.io. Workspace members:

- `guard-core-rs` 4.2.0: the facade crate, re-exporting `detect`, `compiler`, `preprocessor` and `semantic` from the engine.
- `guard-core-engine` 4.2.0: the engine crate, the integration point the framework adapters depend on.
- `guard-core-python` 4.2.0: PyO3 cdylib binding, kept `publish = false`.
- `guard-core-benchmark` and `guard-core-conformance`: internal.

The README documents the two published crates and links the adapter repos.

## Setup

The adapters (tower-guard-rs, axum-guard-rs, actix-guard-rs, rocket-guard-rs) depend on the engine crate directly:

```toml
guard-core-engine = "4.2.0"
```

Engine view: `detect(content, context, config)` with `DetectConfig::max_full_scan_bytes` (262,144 bytes, the ecosystem default). The engine never scans the HTTP method, and its header view skips `sec-*` plus a fixed set of standard hop headers.

## Conformance

`conformance/` holds the spec 4.1.0 corpus vendored byte-identical from the reference (the 12 detect suites, 184 cases, plus the 5 pipeline suites), a `pattern_ledger.toml`, and an `xfail_baseline.toml` that is empty: the detect suites run 184/184 green under the fail-closed drift gate, and the pipeline suites run with the reference-vocabulary event-bus capture as the only documented skip. Binary cases with full-entropy random noise are deliberately excluded from the corpus; their decode-stage parity gaps are covered by the `guard-core-engine` binary_noise_gate honesty tests instead.

## Honest gaps

- Behavior-rule storage is in-memory only: the behavior engine's sliding windows and ban dispatch live in process-local stores; the reference's Redis-backed layout for behavior rules has no distributed mode in this port.
- Route IP-list order diverges from the reference: this port evaluates the route `ip_blacklist` first and then lets a route `ip_whitelist` take over the verdict, while the reference evaluates the route whitelist first (a whitelisted IP that is also blacklisted passes there, is denied here).

## Footguns

- The facade crate re-exports the detect path, but the adapters still integrate through `guard-core-engine` directly; follow their lead unless you only need the facade surface.
- `guard-core-python` stays `publish = false`: do not look for it on crates.io.
- No `.agents` skill and no docs/ directory; AGENTS.md (mirrored byte-identically in CLAUDE.md) is the real documentation.
