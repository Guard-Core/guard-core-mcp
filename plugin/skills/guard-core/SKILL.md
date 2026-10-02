---
name: guard-core
description: Use the Guard Core tools whenever the user asks about the Guard security ecosystem (fastapi-guard, guard-core, guard-agent, or any Guard adapter in Go, TypeScript, PHP or Rust): validating configs, looking up settings, searching documentation, checking whether a request would be blocked, or choosing and wiring adapters.
---

Pick the tool by the question being asked:

- "Is my config valid" or "why is this setting doing nothing" gives the user's config object to validate_config. It catches unknown keys that pydantic silently ignores, type errors, deprecated fields, and construction-time warnings.
- "What does setting X do", "does a setting for Y exist", "what is the default for Z" go to config_fields.
- "Where is this documented" goes to search_docs; call get_doc with the returned package and path for the full page.
- "Would this request be blocked" goes to check_payload with the method, path, query, headers and body the user supplies. Report is_threat, the matching pattern, and threat_categories. Always state that check_payload runs the detection stage only: IP rules, rate limiting and user-agent checks can still block or allow a request that detection alone scored differently.
- Which package guards a Gin, Fastify, Laravel or Rocket app, and any cross-language survey, goes to ecosystem; follow up with adapter_setup for a chosen language and framework, or wire_agent for telemetry setup.
- Before quoting version-specific behavior, call versions and compare installed against docs_bundled_for. The hosted server runs the latest published releases, not the user's local versions, so say so whenever the user asks about their own installed version.
