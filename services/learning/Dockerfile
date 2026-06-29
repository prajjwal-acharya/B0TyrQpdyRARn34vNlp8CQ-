FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    celery redis langchain chromadb \
    pydantic pydantic-settings python-dotenv pyyaml sqlalchemy psycopg2-binary

COPY . .
COPY ../../shared /app/shared

CMD ["celery", "-A", "learning.tasks", "beat", "--loglevel=info"]
