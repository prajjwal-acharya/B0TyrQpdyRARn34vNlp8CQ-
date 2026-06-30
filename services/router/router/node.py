"""LangGraph node for document-type classification.

Decision rule
─────────────
1. Build a text context from the first-page bbox entries + document metadata.
2. Call Groq/Llama3 (cheap, fast) with structured output.
3. If Groq confidence ≥ GROQ_CONFIDENCE_THRESHOLD → return result immediately.
4. Otherwise fetch the first-page image from MinIO and call Gemini Flash
   (multimodal, accurate) — ``fallback_used=True`` in the returned decision.
"""
from __future__ import annotations

import base64
import logging
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from minio import Minio
from pydantic import BaseModel, Field

from shared.contracts import P1OutputPayload

from .schemas import DocType, RouterDecision, RouterState

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ config
GROQ_CONFIDENCE_THRESHOLD: float = float(os.getenv("GROQ_CONFIDENCE_THRESHOLD", "0.85"))
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

_SUPPORTED = ", ".join(e.value for e in DocType)

_SYSTEM_PROMPT = f"""You are a document classification expert for financial and identity documents.

Supported document types: {_SUPPORTED}

Document definitions:
- passport: Government-issued identity/travel document with personal details and photo page
- itr: Income Tax Return form filed with the tax authority (e.g. ITR-1, ITR-2)
- bank_statement: Bank account transaction history (monthly/quarterly statement)
- form_16: Employer-issued tax deduction certificate (Part A + Part B)
- salary_slip: Monthly pay slip listing earnings, deductions, and net pay
- gst: GST registration certificate or GST return document
- property_deed: Legal document for property ownership or transfer (sale deed, lease)

Classify the document from the text/metadata provided. Return a JSON with:
  doc_type  — one of [{_SUPPORTED}]
  confidence — float 0.0–1.0 reflecting your certainty
  reasoning  — one concise sentence explaining the classification
"""


# --------------------------------------------------- internal LLM schema
class _LLMDecision(BaseModel):
    doc_type: DocType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


# --------------------------------------------------- helpers
def _get_minio() -> Minio:
    return Minio(
        os.getenv("MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        secure=False,
    )


def _build_text_context(payload: P1OutputPayload) -> str:
    """Assemble a text summary of the document for the LLM prompt."""
    lines: list[str] = [
        f"Filename: {payload.metadata.filename}",
        f"Language: {payload.detected_lang}",
        f"Page count: {payload.metadata.page_count}",
    ]

    first_page = payload.bbox_data.get("0", [])
    if first_page:
        page_text = " ".join(e.text for e in first_page if e.text.strip())
        if page_text:
            lines.append(f"First-page OCR text: {page_text[:2000]}")

    native = (payload.native_text_layer or {}).get("0", "")
    if native:
        lines.append(f"First-page native text: {native[:2000]}")

    return "\n".join(lines)


def _fetch_first_page_image(payload: P1OutputPayload) -> bytes | None:
    """Download the first-page image from MinIO. Returns None on any failure."""
    if not payload.page_images:
        return None
    minio_key = payload.page_images[0].minio_key  # "processed/{job_id}/page_0.png"
    parts = minio_key.split("/", 1)
    if len(parts) != 2:
        logger.warning("Unexpected MinIO key format: %s", minio_key)
        return None
    bucket, obj_key = parts
    try:
        response = _get_minio().get_object(bucket, obj_key)
        return response.read()
    except Exception:
        logger.exception("Failed to fetch page image from MinIO (key=%s)", minio_key)
        return None


def _groq_classify(text_context: str) -> _LLMDecision:
    chain = ChatGroq(model=GROQ_MODEL, temperature=0).with_structured_output(_LLMDecision)
    return chain.invoke(  # type: ignore[return-value]
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"Classify this document:\n\n{text_context}"),
        ]
    )


def _gemini_classify(text_context: str, image_bytes: bytes | None) -> _LLMDecision:
    content: list[dict] = [
        {"type": "text", "text": f"Classify this document:\n\n{text_context}"}
    ]
    if image_bytes:
        b64 = base64.b64encode(image_bytes).decode()
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
        )

    chain = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0).with_structured_output(
        _LLMDecision
    )
    return chain.invoke(  # type: ignore[return-value]
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]
    )


# --------------------------------------------------- LangGraph node
def classify_document(state: RouterState) -> dict[str, RouterDecision]:
    """LangGraph node: classify a document from its P1 output payload.

    Fast path (Groq) is taken when confidence ≥ GROQ_CONFIDENCE_THRESHOLD.
    Otherwise Gemini Flash (multimodal, with the first-page image) is used.
    """
    payload = state["p1_payload"]
    text_context = _build_text_context(payload)

    groq_result = _groq_classify(text_context)

    if groq_result.confidence >= GROQ_CONFIDENCE_THRESHOLD:
        logger.info(
            "Groq fast-path: %s (confidence=%.2f)",
            groq_result.doc_type,
            groq_result.confidence,
        )
        return {
            "decision": RouterDecision(
                doc_type=groq_result.doc_type,
                confidence=groq_result.confidence,
                reasoning=groq_result.reasoning,
                fallback_used=False,
            )
        }

    logger.info(
        "Groq confidence %.2f < threshold %.2f — escalating to Gemini Flash",
        groq_result.confidence,
        GROQ_CONFIDENCE_THRESHOLD,
    )
    image_bytes = _fetch_first_page_image(payload)
    gemini_result = _gemini_classify(text_context, image_bytes)

    return {
        "decision": RouterDecision(
            doc_type=gemini_result.doc_type,
            confidence=gemini_result.confidence,
            reasoning=gemini_result.reasoning,
            fallback_used=True,
        )
    }
