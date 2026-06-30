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

    output = {
        "decision": decision.model_dump() if decision else None,
        "dispatched_to": result.get("dispatched_to"),
        "needs_manual_review": result.get("needs_manual_review", False),
    }
    print(json.dumps(output, indent=2))
    if result.get("needs_manual_review"):
        logger.warning("Routed to manual review fallback (decision=%s)", decision)
    else:
        logger.info(
            "Classification: %s (confidence=%.2f) -> dispatched to %s",
            decision.doc_type,
            decision.confidence,
            result.get("dispatched_to"),
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m router.main <job_id>", file=sys.stderr)
        sys.exit(1)
    run(sys.argv[1])
