import logging

from app.application.errors import AnswerGenerationError
from app.domain.entities import Chunk, ConversationMessage, StructuredRagResponse
from app.domain.repositories import AnswerGenerator
from app.infrastructure.structured_answer_parser import parse_structured_answer

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
You are a retrieval-augmented question answering assistant.
Answer only from the provided document chunks.
If the chunks do not contain enough information, say that the provided documents do not contain the answer.
Do not use outside knowledge.
Return only valid JSON with this exact shape:
{
  "answer": "...",
  "summary": "...",
  "key_points": ["...", "..."],
  "sources": [{"document": "Operating Systems.pdf", "page": 12}],
  "confidence": "High",
  "follow_up_questions": ["...", "..."]
}
Use confidence as one of: High, Medium, Low.
Only include sources that appear in the retrieved document chunks. If page is unavailable, use null.
Do not wrap the JSON in markdown fences.
""".strip()


class GeminiAnswerGenerator(AnswerGenerator):
    def __init__(
        self,
        api_key: str | None,
        model: str,
        temperature: float,
        max_output_tokens: int,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens

    def generate(
        self,
        question: str,
        chunks: list[Chunk],
        history: list[ConversationMessage] | None = None,
    ) -> StructuredRagResponse:
        if not chunks:
            return StructuredRagResponse(
                answer=(
                    "The provided documents do not contain enough information to answer "
                    "that question."
                ),
                summary="No relevant document context was retrieved.",
                key_points=[],
                sources=[],
                confidence="Low",
                follow_up_questions=[
                    "Can you upload a document that covers this topic?",
                    "Can you ask a more specific question about the uploaded files?",
                ],
            )
        if not self._api_key:
            raise AnswerGenerationError(
                "GEMINI_API_KEY is not configured. Add it to backend/.env and restart the API."
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._api_key)
            response = client.models.generate_content(
                model=self._model,
                contents=_build_user_prompt(question, chunks, history or []),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=self._temperature,
                    max_output_tokens=self._max_output_tokens,
                    response_mime_type="application/json",
                ),
            )
        except Exception as exc:
            logger.error(
                "Gemini content generation failed with %s: %s",
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            raise AnswerGenerationError(
                "Gemini could not generate an answer for this request."
            ) from exc

        text = getattr(response, "text", None)
        if not text:
            raise AnswerGenerationError("Gemini returned an empty response.")
        return parse_structured_answer(text)


def _build_user_prompt(
    question: str,
    chunks: list[Chunk],
    history: list[ConversationMessage],
) -> str:
    context_blocks = "\n\n".join(
        (
            f"[source]\n"
            f"document: {chunk.filename}\n"
            f"chunk_id: {chunk.id}\n"
            f"page: {chunk.metadata.get('page') or chunk.metadata.get('page_number') or 'null'}\n"
            f"score: {chunk.score}\n"
            f"text:\n"
            f"{chunk.text}"
        )
        for chunk in chunks
    )
    history_text = "\n".join(
        f"{message.role}: {message.content}" for message in history[-8:]
    ) or "No prior messages in this chat session."
    return f"""
Conversation memory:
{history_text}

Question:
{question}

Retrieved document chunks:
{context_blocks}

Use the conversation memory only to resolve follow-up references and maintain continuity. Answer with concise reasoning grounded only in the retrieved chunks. If the answer is not in the chunks, say the information is unavailable in the provided documents.
""".strip()
