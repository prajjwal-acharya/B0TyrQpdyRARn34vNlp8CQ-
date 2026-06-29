FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    langchain langgraph langchain-google-genai langsmith \
    chromadb pymupdf opencv-python-headless paddleocr \
    langdetect imagehash pillow numpy pydantic pydantic-settings \
    python-dotenv pyyaml

COPY . .
COPY ../../shared /app/shared

CMD ["python", "-m", "extraction.main"]
