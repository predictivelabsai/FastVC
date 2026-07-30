FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_DIR=/opt/fastembed-cache \
    PORT=5059

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the default fastembed model so first request isn't slow.
RUN mkdir -p "$FASTEMBED_CACHE_DIR" && \
    python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='$FASTEMBED_CACHE_DIR')"

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 5059

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl --fail http://127.0.0.1:5059/healthz || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "main.py"]
