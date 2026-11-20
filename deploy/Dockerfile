FROM python:3.11-slim

LABEL description="WW local Gemini workspace API"

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-dashboard.txt requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-dashboard.txt

COPY . .

RUN groupadd --system ww \
    && useradd --system --gid ww --home-dir /home/ww --create-home ww \
    && mkdir -p /workspace \
    && chown -R ww:ww /app /workspace /home/ww

ENV PYTHONUNBUFFERED=1
ENV WW_WORKSPACE=/workspace
ENV WW_COOKIE_FILE=/run/secrets/cookies.txt
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/', timeout=4)" || exit 1

USER ww

CMD ["python", "-m", "uvicorn", "src.dashboard.app:app", "--host", "0.0.0.0", "--port", "8080"]
