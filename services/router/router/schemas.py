"""Pydantic v2 schemas for the document-type router (Phase 2)."""
from __future__ import annotations

from enum import Enum
from typing import TypedDict

from pydantic import BaseModel, Field

from shared.contracts import P1OutputPayload


class DocType(str, Enum):
    PASSPORT = "passport"
    ITR = "itr"
    BANK_STATEMENT = "bank_statement"
    FORM_16 = "form_16"
    SALARY_SLIP = "salary_slip"
    GST = "gst"
    PROPERTY_DEED = "property_deed"


class RouterDecision(BaseModel):
    """Classification result returned by the routing node.

    ``fallback_used`` is True when the Groq fast-path was not confident enough
    and Gemini Flash multimodal was invoked instead.
    """

    doc_type: DocType
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    fallback_used: bool = False


class RouterState(TypedDict):
    """LangGraph state flowing through the Phase 2 routing graph."""

    p1_payload: P1OutputPayload
    decision: RouterDecision | None


__all__ = ["DocType", "RouterDecision", "RouterState"]
