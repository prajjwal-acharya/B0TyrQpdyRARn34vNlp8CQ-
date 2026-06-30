FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Install all declared dependencies; fallback lists the full set explicitly
RUN pip install --no-cache-dir -e "." || pip install --no-cache-dir \
    fastapi uvicorn[standard] \
    celery redis flower \
    sqlalchemy alembic psycopg2-binary \
    pydantic pydantic-settings \
    pymupdf \
    opencv-python-headless \
    paddleocr \
    langdetect \
    imagehash \
    httpx python-multipart \
    minio \
    pillow numpy \
    pyyaml python-dotenv \
    prometheus-client

COPY services/ingestion/ .
COPY shared /app/shared

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
