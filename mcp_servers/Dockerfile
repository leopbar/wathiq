# syntax=docker/dockerfile:1.7
# One image, four servers. Each Compose service runs a different module from it, so the tool
# sets stay separate processes without four near-identical builds.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN groupadd --gid 1001 wathiq && useradd --uid 1001 --gid 1001 --create-home wathiq

# ---------- dependency layers (cached on pyproject/uv.lock only) ----------
FROM base AS deps-prod
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base AS deps-dev
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# ---------- runtime: what the four services run ----------
FROM deps-prod AS runtime
COPY --chown=wathiq:wathiq . .
RUN chown -R wathiq:wathiq /opt/venv /app
USER wathiq
# Each service overrides MCP_PORT and the module it runs.
ENV MCP_PORT=9100
EXPOSE 9100
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['MCP_PORT']}/healthz\", timeout=4).status == 200 else 1)"
CMD ["python", "-m", "wathiq_mcp.company_registry"]

# ---------- dev: the same code plus the test tools ----------
FROM deps-dev AS dev
COPY --chown=wathiq:wathiq . .
RUN chown -R wathiq:wathiq /opt/venv /app
USER wathiq
ENV MCP_PORT=9100
CMD ["pytest", "-q"]
