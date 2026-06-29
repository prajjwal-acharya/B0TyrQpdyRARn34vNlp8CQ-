FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir httpx pydantic pydantic-settings python-dotenv pyyaml

COPY . .
COPY ../../shared /app/shared

CMD ["python", "-m", "validation.main"]
