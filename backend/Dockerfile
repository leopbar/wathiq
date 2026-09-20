# syntax=docker/dockerfile:1.7
# ---------- base ----------
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
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

FROM base AS deps-dev
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# ---------- dev: hot reload, dev dependencies, source bind-mounted ----------
FROM deps-dev AS dev
COPY --chown=wathiq:wathiq . .
# The storage folder must exist and be owned by the app user before the named volume is
# mounted onto it — Docker copies this ownership when it initialises an empty volume.
RUN chmod +x docker-entrypoint.sh && mkdir -p /app/storage \
    && chown -R wathiq:wathiq /opt/venv /app
USER wathiq
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]

# ---------- production ----------
FROM deps-prod AS prod
COPY --chown=wathiq:wathiq . .
RUN chmod +x docker-entrypoint.sh && mkdir -p /app/storage \
    && chown -R wathiq:wathiq /opt/venv /app
USER wathiq
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
