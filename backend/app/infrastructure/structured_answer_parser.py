import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.application.errors import AnswerGenerationError
from app.domain.entities import SourceReference, StructuredRagResponse

logger = logging.getLogger(__name__)


class SourceReferenceSchema(BaseModel):
    document: str = Field(description="Document filename or identifier.")
    page: int | None = Field(default=None, description="1-based page number if available, else null.")


class StructuredAnswerSchema(BaseModel):
    answer: str = Field(description="Direct, grounded answer to the question.")
    summary: str = Field(description="A brief summary of the answer.")
    key_points: list[str] = Field(default_factory=list, description="Key points from the answer.")
    sources: list[SourceReferenceSchema] = Field(default_factory=list, description="Source documents and pages cited.")
    confidence: Literal["High", "Medium", "Low"] = Field(default="Low", description="Confidence level: High, Medium, or Low.")
    follow_up_questions: list[str] = Field(default_factory=list, description="Relevant follow-up questions.")


_SourceModel = SourceReferenceSchema
_StructuredAnswerModel = StructuredAnswerSchema


def _derive_summary(answer: str, max_chars: int = 160) -> str:
    clean = " ".join(answer.split())
    if not clean:
        return "No summary available."
    for sep in [". ", "? ", "! "]:
        idx = clean.find(sep)
        if idx != -1 and idx < max_chars:
            return clean[: idx + 1]
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rsplit(" ", 1)[0] + "..."


def _normalize_confidence(val: object) -> str:
    if isinstance(val, str):
        clean = val.strip().capitalize()
        if clean in ("High", "Medium", "Low"):
            return clean
    return "Low"


def _normalize_sources(raw_sources: object) -> list[SourceReference]:
    if not isinstance(raw_sources, list):
        return []
    results: list[SourceReference] = []
    for item in raw_sources:
        if isinstance(item, str):
            doc_str = item.strip()
            if doc_str:
                results.append(SourceReference(document=doc_str, page=None))
        elif isinstance(item, dict):
            doc_val = item.get("document") or item.get("filename") or item.get("name") or item.get("source")
            if doc_val and str(doc_val).strip():
                doc_str = str(doc_val).strip()
                page_val = item.get("page")
                page_int: int | None = None
                if isinstance(page_val, int):
                    page_int = page_val
                elif isinstance(page_val, str):
                    page_clean = page_val.strip()
                    if page_clean.isdigit():
                        try:
                            page_int = int(page_clean)
                        except ValueError:
                            page_int = None
                results.append(SourceReference(document=doc_str, page=page_int))
    return results


def _normalize_string_list(raw_list: object) -> list[str]:
    if not isinstance(raw_list, list):
        return []
    return [str(x).strip() for x in raw_list if x is not None and str(x).strip()]


def parse_structured_answer(raw_text: str) -> StructuredRagResponse:
    if not raw_text or not raw_text.strip():
        raise AnswerGenerationError(
            "The model returned an invalid response format. Please try again."
        )

    clean_text = raw_text.strip()
    payload: dict[str, object] | None = None

    try:
        json_str = _extract_json_object(clean_text)
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = None

    if payload is None:
        logger.warning(
            "Model response was not valid JSON; falling back to raw-text answer representation."
        )
        return StructuredRagResponse(
            answer=clean_text,
            summary=_derive_summary(clean_text),
            key_points=[],
            sources=[],
            confidence="Low",
            follow_up_questions=[],
        )

    raw_ans = payload.get("answer")
    answer = str(raw_ans).strip() if raw_ans and str(raw_ans).strip() else clean_text

    raw_summary = payload.get("summary")
    summary = str(raw_summary).strip() if raw_summary and str(raw_summary).strip() else _derive_summary(answer)

    key_points = _normalize_string_list(payload.get("key_points"))
    sources = _normalize_sources(payload.get("sources"))
    confidence = _normalize_confidence(payload.get("confidence"))
    follow_up_questions = _normalize_string_list(payload.get("follow_up_questions"))

    return StructuredRagResponse(
        answer=answer,
        summary=summary,
        key_points=key_points,
        sources=sources,
        confidence=confidence,
        follow_up_questions=follow_up_questions,
    )


def _extract_json_object(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response.")
    return text[start : end + 1]
