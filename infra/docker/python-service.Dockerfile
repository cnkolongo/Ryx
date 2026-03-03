FROM python:3.12-slim

# Dépendances système
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-fra \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv — gestionnaire de packages Python moderne
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Packages partagés
COPY --chown=app:app /packages /packages

# Dépendances service (layer cache)
COPY pyproject.toml .
RUN uv pip install --system -e "/packages/shared" && \
    uv pip install --system -e "/packages/evidence-guard" && \
    uv pip install --system -e "/packages/connector-sdk" && \
    uv pip install --system -e ".[dev]"

# Code source
COPY . .

# Utilisateur non-root
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${SERVICE_PORT:-8000}/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
