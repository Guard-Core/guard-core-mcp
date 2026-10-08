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
    instructions=(
        "Security answers for the Guard ecosystem from the libraries actually "
        "installed in your interpreter, not from generic training data. "
        "validate_config catches unknown and deprecated SecurityConfig keys before "
        "pydantic silently drops them; config_fields finds the setting that controls "
        "a behaviour; search_docs and get_doc return citable pages from the bundled "
        "documentation; check_payload runs a request through guard-core's real "
        "detection engine to explain or confirm a verdict; ecosystem, adapter_setup "
        "and wire_agent cover the five-language adapter matrix and telemetry agent; "
        "versions reports what is installed versus what the bundled docs describe. "
        "All tools are read-only: nothing is fetched from the network and nothing is "
        "modified."
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
    """Report which Guard libraries this server can introspect, and at what version.

    Also reports this server's own guard-core-mcp version. A null installed version
    means that library is absent from the interpreter running this server, so any
    answer about it would be a guess rather than introspection. Compare installed
    against docs_bundled_for before trusting a documentation answer about a
    version-specific feature.
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
        dict[str, Any], Field(description="SecurityConfig fields to validate")
    ],
    package: Annotated[
        str,
        Field(
            description=(
                "Which Guard library to validate against: fastapi-guard, guard-core "
                "or guard-agent"
            )
        ),
    ] = "fastapi-guard",
) -> dict[str, Any]:
    """Validate a Guard config against the installed library's model.

    Reports type errors, deprecated fields, and unknown keys. Unknown keys matter:
    pydantic silently ignores them, so a misspelled setting does nothing at runtime
    and raises no error anywhere else.

    Also surfaces guard-core's own construction-time misconfiguration warnings
    (logged rather than raised) under construction_warnings: an unknown constructor
    keyword, a trusted_proxies /0 network, a whitelist /0 network, and
    enabled_detection_categories empty while penetration detection is enabled all
    land here as plain messages.
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
                "A config field name, or words describing what the setting should do"
            )
        ),
    ],
    package: Annotated[
        str,
        Field(
            description=(
                "Which Guard library to search: fastapi-guard, guard-core or "
                "guard-agent"
            )
        ),
    ] = "fastapi-guard",
) -> dict[str, Any]:
    """Look up Guard config settings by name or by what they do.

    An exact field name populates the exact result with that field's type, default,
    required-ness and description. Every query, exact or not, also populates matches
    with every other field whose name or description contains every word of the query
    (case-insensitively, word order does not matter), which is the fastest way to
    answer whether a setting for some behaviour exists at all.
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
        str, Field(description="Words to search the bundled documentation for")
    ],
    package: Annotated[
        str | None,
        Field(
            description=(
                "Restrict the search to one library: fastapi-guard, guard-core or "
                "guard-agent. Omit to search all three"
            )
        ),
    ] = None,
    limit: Annotated[int, Field(description="Maximum number of results to return")] = 5,
) -> dict[str, Any]:
    """Search the bundled Guard documentation and return citable pages.

    Covers fastapi-guard, guard-core and guard-agent. Omit package to search all
    three. Each result carries the live documentation URL for that page. Unlike
    validate_config and config_fields, an unrecognized package is not an error here,
    it silently matches nothing, so an empty results list can mean either a real gap
    in the docs or a mistyped package name; if empty, try again with package omitted.
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
                "The library the page belongs to, taken from a search_docs result"
            )
        ),
    ],
    path: Annotated[
        str,
        Field(description="The page path, taken from a search_docs result"),
    ],
) -> dict[str, Any]:
    """Return the full text of one bundled documentation page.

    Use the package and path from a search_docs result.
    """
    return docs_module.get_doc(package, path)


@mcp.tool(
    title="Check payload",
    annotations=READ_ONLY,
)
async def check_payload(
    path: Annotated[
        str, Field(description="Request path, e.g. /login or /api/v1/items")
    ] = "/",
    method: Annotated[str, Field(description="HTTP method of the request")] = "GET",
    query: Annotated[
        dict[str, str] | None, Field(description="Query parameters of the request")
    ] = None,
    headers: Annotated[
        dict[str, str] | None, Field(description="Request headers")
    ] = None,
    body: Annotated[
        str | dict[str, Any] | list[Any] | None,
        Field(
            description=(
                "Request body as a raw string or a JSON object or array, which is "
                "serialized for you"
            )
        ),
    ] = None,
    config: Annotated[
        dict[str, Any] | None,
        Field(
            description=(
                "SecurityConfig fields to override the detection defaults with; "
                "enable_redis is always forced off in this sandbox"
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Run a request through guard-core's real detection engine.

    Reports whether the penetration-detection stage flags this request and which
    pattern matched, which is the reliable way to explain a false positive or confirm
    that an attack payload is actually caught. config accepts SecurityConfig fields to
    test how a setting changes the verdict, except enable_redis, which this tool always
    forces to False so the sandbox never touches Redis.

    This is the detection stage alone, not the whole middleware pipeline. A real request
    also passes IP rules, rate limiting, user-agent and cloud-provider checks, any of
    which can block it before detection runs, and a whitelisted IP skips detection
    entirely. So a clean verdict here does not promise the request reaches the route,
    and a threat verdict does not promise the running app would have blocked it.

    guard-core 3.15.0 bounds this scan three ways: detection_max_scan_values caps the
    request values inspected (default 512, names and values counted), and
    detection_max_scan_chars separately caps the total characters handed to the
    pattern engine across those values (default 65536); a value that would start
    after either budget is spent is skipped, so a payload beyond either cap only gets
    a verdict on the scanned prefix. detection_max_json_depth (default 32) caps how
    deep a JSON body is walked structurally; a dict or list reached at that depth is
    serialized back to text and scanned as one value instead of being descended into
    further.

    Since guard-core 3.15.0, detect_penetration_attempt also configures guard-core's
    detection singleton from the config it is given, the first time it runs or
    whenever the config object changes, instead of requiring the caller to configure
    it separately first. check_payload never configured that singleton itself, so
    before 3.15.0 it always ran guard-core's slower legacy pattern path rather than
    the enhanced path a real adapter runs, and could report a different verdict than
    a live request would. From 3.15.0 on, check_payload's verdicts come from that
    same enhanced path.
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
    """Return the full Guard ecosystem registry.

    Every language, engine, adapter and agent, with install commands and
    conformance status.

    The matrix covers five languages (python, go, typescript, php, rust). Each
    language entry carries its engine package (name, install command, version,
    release status, conformance status), every framework adapter with a verified
    quick-start snippet and the Python adapter it maps to, and the telemetry
    agent with its delivery semantics. The conformance block describes the frozen
    spec-4.0.2 corpus every engine is tested against, and the saas block documents
    the guard-core-app ingestion contract all agents share.

    release_status values: published (live on a package registry), tagged (git
    tag exists, registry presence may still lag), untagged (install from source,
    main, or a path dependency). Read release_status and notes together: several
    Go, PHP and Rust packages carry tags or version constants that registry
    publishing has not caught up with.

    Use wire_agent or adapter_setup when you already know the language and
    framework; use this tool to survey the ecosystem or resolve a package name.
    """
    return ecosystem_module.ecosystem()


@mcp.tool(
    title="Adapter setup",
    annotations=READ_ONLY,
)
def adapter_setup(
    language: Annotated[
        str,
        Field(description="One of python, go, typescript, php, rust"),
    ],
    framework: Annotated[
        str,
        Field(
            description=(
                "The adapter slug (gin, fastify, laravel, axum, fastapi) or the "
                "adapter package name"
            )
        ),
    ],
) -> dict[str, Any]:
    """Return the install and a verified minimal integration for one Guard adapter.

    language is one of python, go, typescript, php, rust; framework is that
    language's adapter slug (for example go + gin, typescript + fastify, php +
    laravel, rust + axum, python + fastapi) or the adapter package name. The
    answer carries the adapter's install command, release status, its role in
    the framework, the Python adapter it mirrors, a quick-start snippet taken
    verbatim from the adapter's README, and the engine install and conformance
    status it depends on.

    Every snippet comes from the sibling repo's README at the time this server
    was built; untagged packages move fast, so re-check the repo when the answer
    says release_status is untagged.
    """
    return ecosystem_module.adapter_setup(language, framework)


@mcp.tool(
    title="Wire agent",
    annotations=READ_ONLY,
)
def wire_agent(
    language: Annotated[
        str,
        Field(description="One of python, go, typescript, php, rust"),
    ],
    framework: Annotated[
        str | None,
        Field(
            description=(
                "Optional adapter slug of that language to add integration notes for"
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Return how to set up the Guard telemetry agent for one language.

    language is one of python, go, typescript, php, rust. The answer carries the
    agent package and install command, its release status, a quick-start
    snippet, a summary of its buffer, flush, overflow and retry semantics, how
    it integrates with that language's adapters, and the full guard-core-app
    ingestion contract (endpoints, headers, HMAC signing, size limits and
    response semantics) the agent ships against.

    framework (optional) selects an adapter of that language and adds a note
    about how the agent hooks into it. For python this points at the bundled
    guard-agent doc page for the adapter; for the other languages the agent is
    standalone and the note says so.
    """
    return ecosystem_module.wire_agent(language, framework)


def main() -> None:
    mcp.run()
