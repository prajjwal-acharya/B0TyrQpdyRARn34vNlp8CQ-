"""
Seed ChromaDB with initial few-shot extraction examples.

This script populates the vector store with a small set of manually curated
extraction examples so that RAG retrieval works on day one (before real
documents have been processed and added via Phase 9 learning).

Usage:
    python scripts/seed-chromadb.py

Prerequisites:
    - ChromaDB service must be running (make up)
    - CHROMA_HOST and CHROMA_PORT must be set in .env
    - GEMINI_API_KEY must be set in .env (for embedding generation)
"""

from __future__ import annotations

import os

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))

# Placeholder seed examples — replace with real curated extractions before production use
SEED_EXAMPLES: list[dict] = [
    {
        "doc_type": "passport",
        "input_text": "PLACEHOLDER: passport OCR text sample",
        "extraction": {
            "surname": "SHARMA",
            "given_names": "RAHUL KUMAR",
            "passport_number": "A1234567",
            "nationality": "IND",
            "date_of_birth": "15/08/1990",
            "date_of_expiry": "09/03/2028",
        },
        "metadata": {"source": "seed", "version": "1.0"},
    },
    {
        "doc_type": "itr",
        "input_text": "PLACEHOLDER: ITR OCR text sample",
        "extraction": {
            "pan_number": "ABCDE1234F",
            "assessment_year": "2023-24",
            "gross_total_income": 1200000,
            "itr_form_type": "ITR-1",
        },
        "metadata": {"source": "seed", "version": "1.0"},
    },
]


def main() -> None:
    try:
        import chromadb  # type: ignore[import]
    except ImportError:
        print("chromadb not installed. Run: pip install chromadb")
        return

    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

    collection = client.get_or_create_collection(
        name="extraction_examples",
        metadata={"description": "Few-shot extraction examples for RAG"},
    )

    for i, example in enumerate(SEED_EXAMPLES):
        doc_id = f"seed_{example['doc_type']}_{i}"
        collection.upsert(
            ids=[doc_id],
            documents=[example["input_text"]],
            metadatas=[
                {
                    "doc_type": example["doc_type"],
                    "extraction_json": str(example["extraction"]),
                    **example["metadata"],
                }
            ],
        )
        print(f"Seeded: {doc_id}")

    print(f"\nSeeded {len(SEED_EXAMPLES)} examples into ChromaDB collection 'extraction_examples'.")
    print("Collection stats:", collection.count())


if __name__ == "__main__":
    main()
