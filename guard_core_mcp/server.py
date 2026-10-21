import importlib.metadata
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from guard_core_mcp import __version__
from guard_core_mcp import config as config_module
from guard_core_mcp import detection as detection_module
from guard_core_mcp import docs as docs_module
from guard_core_mcp import ecosystem as ecosystem_module

GUARD_DISTRIBUTIONS = ("guard-core", "fastapi-guard", "guard-agent")

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

mcp = MCPServer(
    "guard-core",
    title="Guard Core",
    version=__version__,
    website_url="https://guard-core.com",
    instructions=(
        "Answers Guard security-library questions from the libraries installed in "
        "the interpreter running this server, not from generic training data. "
        "Pick a tool by question. Is my config valid: validate_config (catches "
        "unknown and deprecated keys that pydantic silently drops). Which setting "
        "controls a behaviour: config_fields. What do the docs say: search_docs, "
        "then get_doc with a returned package and path. Would this request be "
        "flagged, and by which pattern: check_payload (detection stage only). "
        "Which package guards my framework, and how do I install it: "
        "adapter_setup for one adapter, wire_agent for the telemetry agent, "
        "ecosystem for the full five-language survey. Which versions are "
        "installed versus documented: versions, which is worth calling first. "
        "All tools are read-only and idempotent: nothing is fetched from the "
        "network and nothing is modified. Errors come back as an object with an "
        "error key (and a hint where one helps) instead of being raised."
    ),
)


def installed_guard_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for distribution in GUARD_DISTRIBUTIONS:
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = None
    return versions


@mcp.tool(
    title="Guard versions",
    annotations=READ_ONLY,
)
def versions() -> dict[str, Any]:
    """Report which Guard libraries this server can introspect, and at which version.

    Call this first, before trusting any answer about a version-specific feature. It
    takes no arguments.

    Returns guard_core_mcp (this server's version), installed (the guard-core,
    fastapi-guard and guard-agent versions live in this interpreter), and
    docs_bundled_for and knowledge_bundled_for (the versions the bundled docs and the
    hand-written ecosystem notes describe).

    A null installed version means that library is absent from the interpreter running
    this server, so validate_config, config_fields and check_payload cannot answer for
    it and any answer would be a guess. An installed version that differs from
    docs_bundled_for is normal and only means the docs may lag or lead the install.
    """
    return {
        "guard_core_mcp": __version__,
        "installed": installed_guard_versions(),
        "docs_bundled_for": {
            package: entry["version"]
            for package, entry in docs_module.manifest().items()
        },
        "knowledge_bundled_for": {
            package: entry["version"]
            for package, entry in docs_module.knowledge_manifest().items()
        },
    }


def missing_library_error(exception: ModuleNotFoundError) -> dict[str, str]:
    return {
        "error": (
            f"{exception.name} is not installed in the interpreter running this server"
        ),
        "hint": (
            "Install guard-core-mcp into the environment that has your Guard libraries "
            "(uv add --dev guard-core-mcp) rather than running it in an isolated one."
        ),
    }


@mcp.tool(
    title="Validate config",
    annotations=READ_ONLY,
)
def validate_config(
    config: Annotated[
        dict[str, Any],
        Field(
            description=(
                "The config as a JSON object of field names to values, exactly as "
                "you would pass it to the model's constructor"
            ),
            examples=[{"rate_limit": 100, "enable_rate_limiting": True}],
        ),
    ],
    package: Annotated[
        str,
        Field(
            description=(
                "Which Guard library's installed model to validate against. One of "
                "fastapi-guard (SecurityConfig), guard-core (SecurityConfig) or "
                "guard-agent (AgentConfig). Any other value returns an error object"
            ),
            examples=["fastapi-guard", "guard-core", "guard-agent"],
        ),
    ] = "fastapi-guard",
) -> dict[str, Any]:
    """Check a Guard config dict against the installed library's real pydantic model.

    Use this to confirm a config is valid, or to find out why a setting seems to have
    no effect. Use config_fields instead when you do not yet know the setting's name.

    Returns valid (bool), package, version, model, errors (type errors, each with
    field, message and input), unknown_fields (each with name and did_you_mean
    suggestions), deprecated (field and message) and construction_warnings. Unknown
    keys matter: pydantic silently ignores them, so a misspelled setting does nothing
    at runtime and raises no error anywhere else. construction_warnings carries
    guard-core's own logged-not-raised misconfiguration warnings: an unknown
    constructor keyword, a trusted_proxies or whitelist /0 network, and
    enabled_detection_categories empty while penetration detection is enabled.

    Read-only: the config is validated in memory and never applied. If the library is
    not installed, or package is not recognized, returns an object with an error key
    (plus a hint when the cause is a missing install) instead of raising.
    """
    try:
        return config_module.validate_config(config, package)
    except ModuleNotFoundError as exception:
        return missing_library_error(exception)
    except ValueError as exception:
        return {"error": str(exception)}


@mcp.tool(
    title="Config fields lookup",
    annotations=READ_ONLY,
)
def config_fields(
    query: Annotated[
        str,
        Field(
            description=(
                "Either an exact config field name or plain words describing the "
                "behaviour. Matching is case-insensitive and word order does not "
                "matter"
            ),
            examples=["rate_limit", "ban suspicious ips", "redis"],
        ),
    ],
    package: Annotated[
        str,
        Field(
            description=(
                "Which Guard library's installed model to search. One of "
                "fastapi-guard, guard-core or guard-agent. Any other value returns "
                "an error object"
            ),
            examples=["fastapi-guard", "guard-core", "guard-agent"],
        ),
    ] = "fastapi-guard",
) -> dict[str, Any]:
    """Find a Guard config setting by name or by what it does, with type and default.

    Use this to learn what a setting means, or whether a setting for some behaviour
    exists at all. Use validate_config instead to check a whole config you already
    wrote, and search_docs for prose explanations rather than field metadata.

    Returns package, version, query, exact and matches. An exact field name fills
    exact with that field's name, type, default, required flag and description
    (otherwise exact is null). Every query also fills matches with each other field
    whose name or description contains every word of the query; if nothing matches
    at all, matches falls back to the closest field names by spelling.

    Read-only, in-memory lookup. If the library is not installed, or package is not
    recognized, returns an object with an error key instead of raising.
    """
    try:
        return config_module.config_fields(query, package)
    except ModuleNotFoundError as exception:
        return missing_library_error(exception)
    except ValueError as exception:
        return {"error": str(exception)}


@mcp.tool(
    title="Search docs",
    annotations=READ_ONLY,
)
def search_docs(
    query: Annotated[
        str,
        Field(
            description=(
                "Words to look for in the bundled documentation. Pages are ranked by "
                "how often the words occur, so use specific terms"
            ),
            examples=["rate limiting", "trusted proxies", "agent retry"],
        ),
    ],
    package: Annotated[
        str | None,
        Field(
            description=(
                "Restrict the search to one library, for example fastapi-guard, "
                "guard-core or guard-agent. Omit to search every bundled library. "
                "An unrecognized name silently matches nothing"
            ),
            examples=["fastapi-guard", "guard-core", "guard-agent"],
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            description="Maximum number of results to return, highest score first",
            examples=[5, 10],
        ),
    ] = 5,
) -> dict[str, Any]:
    """Search the bundled Guard documentation and return ranked, citable pages.

    Use this to answer how or why questions from documentation, and to find the page
    to read in full with get_doc. Use config_fields instead for a setting's type and
    default, and adapter_setup or wire_agent for install and wiring steps.

    Returns query and results. Each result has package, path, heading, snippet, url
    (the live documentation page to cite) and score. Pass a result's package and path
    straight to get_doc to read the whole page.

    Read-only and offline: it searches the docs shipped inside this package. Unlike
    validate_config, an unrecognized package is not an error, it silently matches
    nothing, so an empty results list means either a real gap in the docs or a
    mistyped package name; retry with package omitted before concluding the former.
    """
    return docs_module.search_docs(query, package, limit)


@mcp.tool(
    title="Get doc page",
    annotations=READ_ONLY,
)
def get_doc(
    package: Annotated[
        str,
        Field(
            description=(
                "The library the page belongs to, copied from a search_docs result "
                "or from the keys versions reports under docs_bundled_for and "
                "knowledge_bundled_for"
            ),
            examples=["fastapi-guard", "guard-core-go"],
        ),
    ],
    path: Annotated[
        str,
        Field(
            description=(
                "The page path relative to the library's bundled docs, copied from a "
                "search_docs result. Paths outside the bundled docs are rejected"
            ),
            examples=["installation.md", "tutorial/ip-management/rate-limiter.md"],
        ),
    ],
) -> dict[str, Any]:
    """Return the full text of one bundled Guard documentation page.

    Use this after search_docs when a snippet is not enough; it does not search. The
    package and path come from a search_docs result.

    Returns package, path, url (the live page to cite) and content (the full markdown).
    An unknown package or a path that does not exist returns {"error": "unknown doc
    path"}; the two cases are not distinguished. Read-only and offline, and it cannot
    read files outside the bundled documentation.
    """
    return docs_module.get_doc(package, path)


@mcp.tool(
    title="Check payload",
    annotations=READ_ONLY,
)
async def check_payload(
    path: Annotated[
        str,
        Field(
            description="Request path of the request to test",
            examples=["/login", "/api/v1/items"],
        ),
    ] = "/",
    method: Annotated[
        str,
        Field(
            description="HTTP method of the request to test",
            examples=["GET", "POST"],
        ),
    ] = "GET",
    query: Annotated[
        dict[str, str] | None,
        Field(
            description=(
                "Query-string parameters as a JSON object of names to string values"
            ),
            examples=[{"q": "1' OR '1'='1"}],
        ),
    ] = None,
    headers: Annotated[
        dict[str, str] | None,
        Field(
            description=(
                "Request headers as a JSON object of names to values. Names are "
                "matched case-insensitively"
            ),
            examples=[{"User-Agent": "sqlmap/1.7"}],
        ),
    ] = None,
    body: Annotated[
        str | dict[str, Any] | list[Any] | None,
        Field(
            description=(
                "Request body as a raw string, or a JSON object or array, which is "
                "serialized for you. Omit for a bodyless request"
            ),
            examples=['{"name": "<script>alert(1)</script>"}'],
        ),
    ] = None,
    config: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "SecurityConfig fields to override guard-core's defaults, as a JSON "
                "object, to see how a setting changes the verdict. enable_redis is "
                "always forced off"
            ),
            examples=[{"enabled_detection_categories": ["sqli", "xss"]}],
        ),
    ] = None,
) -> dict[str, Any]:
    """Run one synthetic request through guard-core's real penetration-detection engine.

    Use this to confirm that an attack payload is caught, or to explain why a benign
    request was flagged. Use validate_config instead to check a config, not a request.

    Returns is_threat (bool), trigger_info (the matched parameter and pattern, empty
    when clean), threat_categories (for example sqli or xss), threat_scores (a score
    per category) and elapsed_ms. Verdicts come from the same detection path a live
    adapter runs. Read-only and sandboxed: the request is never sent anywhere and
    enable_redis is forced off so Redis is never touched. If guard-core is not
    installed, returns an object with an error key and a hint instead of raising.

    This is the detection stage alone, not the whole middleware pipeline. A real
    request also passes IP rules, rate limiting, user-agent and cloud-provider checks,
    any of which can block it before detection runs, and a whitelisted IP skips
    detection entirely. A clean verdict here does not promise the request reaches the
    route, and a threat verdict does not promise a running app would block it.

    The scan is bounded, so a payload past a cap is judged on the scanned prefix only:
    detection_max_scan_values caps values inspected (default 512),
    detection_max_scan_chars caps total characters scanned (default 65536), and
    detection_max_json_depth (default 32) caps how deep a JSON body is walked before
    the rest is scanned as one serialized value. These caps and the enhanced
    detection path apply from guard-core 3.15.0; versions reports what is installed.
    """
    try:
        return await detection_module.check_payload(
            path, method, query, headers, body, config
        )
    except ModuleNotFoundError as exception:
        return missing_library_error(exception)


@mcp.tool(
    title="Ecosystem registry",
    annotations=READ_ONLY,
)
def ecosystem() -> dict[str, Any]:
    """Survey the whole Guard ecosystem: every language, engine, adapter and agent.

    Use this to resolve a package name or compare languages. It takes no arguments.
    When you already know the language and framework, use adapter_setup for one
    adapter or wire_agent for the telemetry agent instead, which return less.

    Returns the full registry for five languages (python, go, typescript, php, rust).
    Each language entry holds its engine (name, install command, version,
    release_status, conformance status), every framework adapter with a verified
    quick-start snippet and the Python adapter it maps to, and its telemetry agent
    with delivery semantics. A conformance block describes the frozen spec-4.1.0
    corpus every engine is tested against, and a saas block documents the
    guard-core-app ingestion contract all agents share.

    release_status is published (live on a package registry), tagged (a git tag
    exists, registry presence may lag) or untagged (install from source, main or a
    path dependency). Read it together with notes: several Go, PHP and Rust packages
    carry tags or version constants that registry publishing has not caught up with.
    Read-only static data that works with or without the Guard libraries installed.
    """
    return ecosystem_module.ecosystem()


@mcp.tool(
    title="Adapter setup",
    annotations=READ_ONLY,
)
def adapter_setup(
    language: Annotated[
        str,
        Field(
            description=(
                "The language of the adapter. One of python, go, typescript, php "
                "or rust. Any other value returns an error object"
            ),
            examples=["python", "go", "typescript", "php", "rust"],
        ),
    ],
    framework: Annotated[
        str,
        Field(
            description=(
                "The adapter slug for that language, or the adapter package name. "
                "An unknown slug returns an error object listing the valid ones"
            ),
            examples=["fastapi", "gin", "fastify", "laravel", "axum"],
        ),
    ],
) -> dict[str, Any]:
    """Get the install command and a verified minimal integration for one Guard adapter.

    Use this when you know the language and web framework and want working setup code.
    Use ecosystem instead to survey every adapter, and wire_agent to set up telemetry.

    Returns language, engine (package, install command, release_status and conformance
    status of the engine the adapter depends on) and adapter (install command,
    release_status, its role in the framework, the Python adapter it mirrors, and a
    quick-start snippet taken verbatim from the adapter's README). Snippets reflect
    the README at the time this server was built; when release_status is untagged,
    re-check the repository. An unknown language or framework returns an object with
    an error key instead of raising. Read-only static data, works without the Guard
    libraries installed.
    """
    return ecosystem_module.adapter_setup(language, framework)


@mcp.tool(
    title="Wire agent",
    annotations=READ_ONLY,
)
def wire_agent(
    language: Annotated[
        str,
        Field(
            description=(
                "The language whose telemetry agent to set up. One of python, go, "
                "typescript, php or rust. Any other value returns an error object"
            ),
            examples=["python", "go", "typescript", "php", "rust"],
        ),
    ],
    framework: Annotated[
        str | None,
        Field(
            description=(
                "Optional adapter slug of that language, to add a note on how the "
                "agent hooks into that adapter. Omit for the agent alone"
            ),
            examples=["fastapi", "gin", "laravel"],
        ),
    ] = None,
) -> dict[str, Any]:
    """Get how to set up the Guard telemetry agent for one language.

    Use this to ship security events and metrics to the guard-core-app backend. Use
    adapter_setup instead for the request-blocking middleware itself.

    Returns language, agent (package, install command, release_status, quick-start
    snippet, and a summary of its buffer, flush, overflow and retry semantics),
    ingestion (the guard-core-app contract the agent ships against: endpoints,
    headers, HMAC signing, size limits and response semantics) and framework_note.
    For python the note points at the bundled guard-agent doc page for the adapter;
    for other languages the agent is standalone and the note says so. An unknown
    language or framework returns an object with an error key instead of raising.
    Read-only static data, works without the Guard libraries installed.
    """
    return ecosystem_module.wire_agent(language, framework)


def main() -> None:
    mcp.run()
