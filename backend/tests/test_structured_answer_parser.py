import json
import unittest

from app.application.errors import AnswerGenerationError
from app.domain.entities import SourceReference, StructuredRagResponse
from app.infrastructure.structured_answer_parser import parse_structured_answer


class StructuredAnswerParserTests(unittest.TestCase):
    def test_valid_structured_json(self) -> None:
        raw = json.dumps(
            {
                "answer": "Operating systems manage computer hardware.",
                "summary": "OS hardware management overview.",
                "key_points": ["Resource allocation", "Process scheduling"],
                "sources": [{"document": "os.pdf", "page": 12}],
                "confidence": "High",
                "follow_up_questions": ["What is process scheduling?"],
            }
        )
        res = parse_structured_answer(raw)
        self.assertEqual(res.answer, "Operating systems manage computer hardware.")
        self.assertEqual(res.summary, "OS hardware management overview.")
        self.assertEqual(res.key_points, ["Resource allocation", "Process scheduling"])
        self.assertEqual(res.sources, [SourceReference(document="os.pdf", page=12)])
        self.assertEqual(res.confidence, "High")
        self.assertEqual(res.follow_up_questions, ["What is process scheduling?"])

    def test_lowercase_confidence_normalization(self) -> None:
        for input_conf, expected in [("high", "High"), ("medium", "Medium"), ("low", "Low"), ("HIGH", "High")]:
            raw = json.dumps(
                {
                    "answer": "Grounded answer.",
                    "summary": "Summary.",
                    "confidence": input_conf,
                }
            )
            res = parse_structured_answer(raw)
            self.assertEqual(res.confidence, expected)

    def test_source_as_object(self) -> None:
        raw = json.dumps(
            {
                "answer": "Grounded answer.",
                "summary": "Summary.",
                "sources": [{"document": "architecture.pdf", "page": 42}],
            }
        )
        res = parse_structured_answer(raw)
        self.assertEqual(len(res.sources), 1)
        self.assertEqual(res.sources[0].document, "architecture.pdf")
        self.assertEqual(res.sources[0].page, 42)

    def test_source_as_string_filename(self) -> None:
        raw = json.dumps(
            {
                "answer": "Grounded answer.",
                "summary": "Summary.",
                "sources": ["guide.pdf", "manual.txt"],
            }
        )
        res = parse_structured_answer(raw)
        self.assertEqual(len(res.sources), 2)
        self.assertEqual(res.sources[0], SourceReference(document="guide.pdf", page=None))
        self.assertEqual(res.sources[1], SourceReference(document="manual.txt", page=None))

    def test_numeric_page_string(self) -> None:
        raw = json.dumps(
            {
                "answer": "Grounded answer.",
                "summary": "Summary.",
                "sources": [
                    {"document": "doc1.pdf", "page": "12"},
                    {"document": "doc2.pdf", "page": "null"},
                    {"document": "doc3.pdf", "page": None},
                ],
            }
        )
        res = parse_structured_answer(raw)
        self.assertEqual(res.sources[0], SourceReference(document="doc1.pdf", page=12))
        self.assertEqual(res.sources[1], SourceReference(document="doc2.pdf", page=None))
        self.assertEqual(res.sources[2], SourceReference(document="doc3.pdf", page=None))

    def test_missing_summary(self) -> None:
        raw = json.dumps(
            {
                "answer": "The virtual file system provides an abstraction layer. It hides details.",
            }
        )
        res = parse_structured_answer(raw)
        self.assertEqual(res.answer, "The virtual file system provides an abstraction layer. It hides details.")
        self.assertTrue(len(res.summary) > 0)
        self.assertIn("virtual file system", res.summary)

    def test_missing_optional_lists(self) -> None:
        raw = json.dumps(
            {
                "answer": "Simple answer.",
                "summary": "Simple summary.",
            }
        )
        res = parse_structured_answer(raw)
        self.assertEqual(res.key_points, [])
        self.assertEqual(res.sources, [])
        self.assertEqual(res.follow_up_questions, [])
        self.assertEqual(res.confidence, "Low")

    def test_malformed_json_with_non_empty_plain_text_fallback(self) -> None:
        raw = "An operating system coordinates hardware resources and manages system execution."
        res = parse_structured_answer(raw)
        self.assertIsInstance(res, StructuredRagResponse)
        self.assertEqual(res.answer, raw)
        self.assertTrue(len(res.summary) > 0)
        self.assertEqual(res.sources, [])
        self.assertEqual(res.key_points, [])
        self.assertEqual(res.follow_up_questions, [])
        self.assertEqual(res.confidence, "Low")

    def test_completely_empty_response(self) -> None:
        for empty_val in ["", "   ", "\n\t  \n"]:
            with self.assertRaises(AnswerGenerationError):
                parse_structured_answer(empty_val)


if __name__ == "__main__":
    unittest.main()
