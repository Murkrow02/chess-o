FROM python:3.12-slim

ARG STOCKFISH_VERSION=sf_19
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && arch=$([ "$TARGETARCH" = "arm64" ] && echo arm64 || echo x86-64) \
 && curl -fsSL -o /tmp/sf.tar.gz \
    "https://github.com/official-stockfish/Stockfish/releases/download/${STOCKFISH_VERSION}/stockfish-linux-${arch}-universal.tar.gz" \
 && mkdir /tmp/sf && tar -xzf /tmp/sf.tar.gz -C /tmp/sf \
 && find /tmp/sf -type f -name 'stockfish*' -perm -u+x -exec cp {} /usr/local/bin/stockfish \; -quit \
 && chmod +x /usr/local/bin/stockfish && rm -rf /tmp/sf /tmp/sf.tar.gz \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts

ENV STOCKFISH_PATH=/usr/local/bin/stockfish \
    DATA_DIR=/data \
    KNOWLEDGE_DIR=/knowledge \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
