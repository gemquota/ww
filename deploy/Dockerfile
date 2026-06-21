FROM python:3.13-slim AS builder

LABEL description="WW Bridge — Gemini Multi-Agent Coding Harness"
LABEL maintainer="WW Team"

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        pydantic-settings \
        pyyaml \
        uvicorn \
        fastapi \
        mkdocs \
        mkdocs-material

# Copy application
COPY . .

# Create runtime directories
RUN mkdir -p .ww/sessions .tel/logs

# --- Stage 2: Runtime ---
FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r ww && useradd -r -g ww -d /app -s /sbin/nologin ww

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

# Create runtime directories with correct permissions
RUN mkdir -p .ww/sessions .tel/logs && chown -R ww:ww /app

# Default config
ENV WW_CONFIG=/app/config.yaml
ENV WW_WORKSPACE=/app
ENV PYTHONUNBUFFERED=1

# Read-only root filesystem compatibility
VOLUME ["/app/.ww", "/app/.tel"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request, sys; urllib.request.urlopen('http://localhost:8080/api/v1/health', timeout=5)" 2>/dev/null || exit 1

USER ww

ENTRYPOINT ["python3", "gemini_bridge.py"]
CMD []
