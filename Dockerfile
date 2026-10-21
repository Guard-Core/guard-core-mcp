ARG PYTHON_VERSION=3.10
FROM python:${PYTHON_VERSION}-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/

RUN useradd --create-home --uid 10001 app \
    && mkdir /app \
    && chown app:app /app

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=10 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER 10001

COPY --chown=app:app pyproject.toml uv.lock* README.md /app/

RUN uv sync --extra dev --frozen

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=app:app guard_core_mcp/ /app/guard_core_mcp/
COPY --chown=app:app tests/ /app/tests/
COPY --chown=app:app scripts/ /app/scripts/

RUN uv pip install --python .venv/bin/python --no-deps -e /app

# The server speaks MCP over stdio and opens no port, so the check confirms the server module loads with its tools registered.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD ["python", "-c", "from guard_core_mcp.server import mcp"]
