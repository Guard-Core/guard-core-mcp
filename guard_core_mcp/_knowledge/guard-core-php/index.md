# guard-core-php

The PHP port of the guard-core security engine. Composer name `rennf93/guard-core-php`, requires PHP `^8.2` plus `ext-pcre`, `ext-mbstring` and `ext-json`. Namespace root `RenzoFranceschini\GuardCore\`.

## Install

```sh
composer require rennf93/guard-core-php
```

Tagged `v4.4.0` and on Packagist, so a plain `composer require` resolves it; no VCS repository block or dev stability is needed.

composer.json carries no `version` field (the tag carries it).

## Setup

- `RenzoFranceschini\GuardCore\Config\SecurityConfig` is the config object (named arguments: `enableRedis`, `blacklist`, `rateLimit`, `rateLimitWindow`, `enableRateLimiting`, ...).
- `RenzoFranceschini\GuardCore\Engine\GuardEngine` is the engine; `execute(GuardRequest $request): ?GuardResponse` is the main entry point.
- `Request\SimpleGuardRequest` builds a request without a framework; `Request\GuardResponseFactory` produces responses. Adapters (psr15-guard, laravel-guard, symfony-guard, slim-guard) translate their framework's request/response into these types.

## Conformance

`make test` runs `bin/conformance.php` (detect, also `composer conformance`), `bin/conformance_pipeline.php`, `bin/conformance_events.php`, `bin/conformance_safety.php` and `bin/conformance_redis.php` (needs Redis) over the vendored spec 4.1.0 corpus in `conformance/guard-core-spec-4.1.0/` (375 cases across 21 suites). `bin/conformance_cost.php` ships too, but no Makefile target, composer script or workflow runs it.

## Footguns

- AGENTS.md exists, but there is no CLAUDE.md and no SKILL.md; the README and docs/ carry the usage.
- README "Detection limits": on stock php.ini, PCRE2 can exhaust its stack on long single-line subjects for the line-walk and segment-loop pattern families. Once a view subject's first line reaches `SusPatterns::GATED_PATTERN_MAX_SUBJECT_BYTES` (15360 bytes), those families are skipped for the rest of the scan, so detection completes but loses their coverage on single lines of 15 KB or more.
- The repo name is `guard-core-php` but the vendor name is `rennf93/`; the adapters resolve `rennf93/guard-core-php` `^4.4.0` from Packagist with no path repository.
