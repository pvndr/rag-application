import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.application.errors import AnswerGenerationError
from app.domain.entities import SourceReference, StructuredRagResponse


class _SourceModel(BaseModel):
    document: str = Field(..., min_length=1)
    page: int | None = None


class _StructuredAnswerModel(BaseModel):
    answer: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    key_points: list[str] = Field(default_factory=list)
    sources: list[_SourceModel] = Field(default_factory=list)
    confidence: Literal["High", "Medium", "Low"] = "Low"
    follow_up_questions: list[str] = Field(default_factory=list)


def parse_structured_answer(raw_text: str) -> StructuredRagResponse:
    try:
        payload = json.loads(_extract_json_object(raw_text))
        model = _StructuredAnswerModel.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise AnswerGenerationError(
            "The model returned an invalid response format. Please try again."
        ) from exc

    return StructuredRagResponse(
        answer=model.answer,
        summary=model.summary,
        key_points=model.key_points,
        sources=[
            SourceReference(document=source.document, page=source.page)
            for source in model.sources
        ],
        confidence=model.confidence,
        follow_up_questions=model.follow_up_questions,
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
