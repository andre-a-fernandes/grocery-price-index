FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency resolution and package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the backend's dependency manifest (pyproject.toml) and the workspace uv.lock.
# Build context is the repository root, so we reference backend/ paths.
COPY backend/pyproject.toml ./pyproject.toml
COPY uv.lock ./

# Install dependencies into a project virtual environment.
# --no-install-project skips editable-installing the backend package itself
# --no-group dev skips the dev dependency group (pytest, ruff, httpx),
# --frozen ensures we use the exact versions from the lock file.
RUN uv sync --frozen --no-group dev --no-install-project --no-progress

# Copy the application code.
COPY backend/ ./

# Hugging Face Spaces sets $PORT at runtime and expects
# the container to listen on it.
ENV PORT=7860
EXPOSE 7860

# Add virtualenv to PATH so we don't need `uv run` at runtime
ENV PATH="/app/.venv/bin:$PATH"

# Liveness probe: hit the health endpoint (GET /) defined in main.py.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python healthcheck.py

# Run via the project's virtualenv. --no-sync skips the lockfile re-check
# (dependencies were pinned during the build).
CMD ["python", "main.py"]
