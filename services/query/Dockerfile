FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi uvicorn sqlalchemy psycopg2-binary \
    pydantic pydantic-settings python-dotenv httpx

COPY . .
COPY ../../shared /app/shared

EXPOSE 8000

CMD ["uvicorn", "query.main:app", "--host", "0.0.0.0", "--port", "8000"]
