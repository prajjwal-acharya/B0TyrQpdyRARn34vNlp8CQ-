FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    sqlalchemy alembic psycopg2-binary \
    pydantic pydantic-settings python-dotenv numpy

COPY . .
COPY ../../shared /app/shared

CMD ["python", "-m", "entity_store.main"]
