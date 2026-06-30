FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir fastapi uvicorn celery redis flower sqlalchemy alembic psycopg2-binary pydantic pydantic-settings pymupdf httpx minio python-dotenv pyyaml

COPY services/ingestion/ .
COPY shared /app/shared

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
