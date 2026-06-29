FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir langchain langgraph langchain-groq pydantic pydantic-settings python-dotenv pyyaml

COPY . .
COPY ../../shared /app/shared

CMD ["python", "-m", "router.main"]
