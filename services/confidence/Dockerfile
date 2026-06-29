FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pydantic pydantic-settings numpy python-dotenv pyyaml

COPY . .
COPY ../../shared /app/shared

CMD ["python", "-m", "confidence.main"]
