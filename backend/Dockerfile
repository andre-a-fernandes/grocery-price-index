FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml .
COPY main.py .

RUN uv pip install --system .

# Hugging Face Spaces sets $PORT at runtime and expects
# the container to listen on it.
ENV PORT=7860
EXPOSE 7860

CMD ["python", "main.py"]