# BIDSHub — OCI image for Streamlit + SQLite. Build and run via ./hub-docker (see README).
#
#   docker build -t bidshub:3.1.5 --build-arg BIDSHUB_VERSION=3.1.5 .
#   # or: ./hub-docker install   (uses docker-compose.yml)
#
# The app listens on 0.0.0.0:8501 inside the container. Mount ./data to persist SQLite.
# Not a hardened multi-tenant server image. Process runs as non-root (uid 1000).

FROM python:3.12-slim-bookworm

ARG BIDSHUB_VERSION=3.1.5
LABEL org.opencontainers.image.title="BIDSHub" \
      org.opencontainers.image.version="${BIDSHUB_VERSION}" \
      org.opencontainers.image.description="Multi-platform BIDS dataset management and exploration (Streamlit)" \
      org.opencontainers.image.licenses="MIT"

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/app \
    BIDSHUB_NONINTERACTIVE=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN groupadd -g 1000 bidshub && useradd -m -u 1000 -g bidshub bidshub

WORKDIR /app

# build-essential + zlib for numcodecs wheels that compile from source on arm64/slim
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    zlib1g-dev \
    && pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y build-essential zlib1g-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Runtime dirs + non-root ownership (bind-mount ./data from host: see README for permissions)
RUN mkdir -p data logs .streamlit /app/.cache \
    && chown -R bidshub:bidshub /app \
    && chmod +x hub 2>/dev/null || true \
    && chmod +x bin/hub-docker 2>/dev/null || true

USER bidshub

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8501/_stcore/health > /dev/null || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
