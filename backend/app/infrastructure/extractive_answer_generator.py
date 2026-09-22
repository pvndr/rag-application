from app.domain.entities import Chunk, ConversationMessage, SourceReference, StructuredRagResponse
from app.domain.repositories import AnswerGenerator


class ExtractiveAnswerGenerator(AnswerGenerator):
    def generate(
        self,
        question: str,
        chunks: list[Chunk],
        history: list[ConversationMessage] | None = None,
    ) -> StructuredRagResponse:
        if not chunks:
            return StructuredRagResponse(
                answer=(
                    "I could not find relevant context in the uploaded documents. "
                    "Upload more material or try a more specific question."
                ),
                summary="No relevant context was found in the indexed documents.",
                key_points=[],
                sources=[],
                confidence="Low",
                follow_up_questions=[
                    "Can you upload a document that covers this topic?",
                    "Can you ask a more specific question?",
                ],
            )

        context = "\n\n".join(
            f"From {chunk.filename}: {chunk.text.strip()}" for chunk in chunks[:3]
        )
        return StructuredRagResponse(
            answer=(
                f"Based on the retrieved document context, here is the most relevant "
                f"information for: \"{question}\"\n\n{context}"
            ),
            summary="The answer was generated from the top retrieved document chunks.",
            key_points=[chunk.text.strip()[:220] for chunk in chunks[:3]],
            sources=[
                SourceReference(
                    document=chunk.filename,
                    page=_page_from_metadata(chunk.metadata),
                )
                for chunk in chunks[:3]
            ],
            confidence="Medium",
            follow_up_questions=[
                "Would you like a deeper explanation from the same sources?",
                "Should I compare this with another uploaded document?",
            ],
        )


def _page_from_metadata(metadata: dict[str, str | int | float]) -> int | None:
    page = metadata.get("page") or metadata.get("page_number")
    return int(page) if isinstance(page, int | float) else None
