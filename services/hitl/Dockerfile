FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir httpx langgraph langchain pydantic pydantic-settings python-dotenv

COPY . .
COPY ../../shared /app/shared

CMD ["python", "-m", "hitl.main"]
