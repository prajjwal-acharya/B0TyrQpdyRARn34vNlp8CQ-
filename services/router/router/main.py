"""Standalone entrypoint — run the router graph for a given job_id.

Usage (inside the container):
    python -m router.main <job_id>

The ingestion API URL is read from INGESTION_API_URL (default: http://ingestion-api:8000).
"""
from __future__ import annotations

import json
import logging
import os
import sys

import httpx

from shared.contracts import P1OutputPayload

from .graph import router_graph

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def run(job_id: str) -> None:
    ingestion_url = os.getenv("INGESTION_API_URL", "http://ingestion-api:8000")
    logger.info("Fetching P1 payload for job %s from %s", job_id, ingestion_url)

    resp = httpx.get(f"{ingestion_url}/jobs/{job_id}", timeout=30)
    resp.raise_for_status()

    payload = P1OutputPayload.model_validate(resp.json())
    result = router_graph.invoke({"p1_payload": payload, "decision": None})
    decision = result["decision"]

    print(json.dumps(decision.model_dump(), indent=2))
    logger.info("Classification: %s (confidence=%.2f)", decision.doc_type, decision.confidence)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m router.main <job_id>", file=sys.stderr)
        sys.exit(1)
    run(sys.argv[1])
