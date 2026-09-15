"""Tests for pdf_inspection.py. The real Anthropic client is always mocked
here - these tests never make a network call or consume API credit.
"""

import base64
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
import httpx2

import documents
import pdf_inspection
import store

FAKE_SECRET = "sk-ant-api03-PDF-INSPECTION-TEST-FAKE-SECRET-DO-NOT-LEAK"
SAMPLE_PDF_BYTES = b"%PDF-1.4\n%fake pdf content for testing\n%%EOF"
OTHER_PDF_BYTES = b"%PDF-1.4\n%a different fake pdf, must never be sent\n%%EOF"


def make_status_error(cls, status_code: int, error_type: str, message: str):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        status_code, request=request, json={"error": {"type": error_type, "message": message}}
    )
    return cls(message, response=response, body=response.json())


def fake_citation(cited_text: str, start_page: int, end_page: int | None = None, document_title: str | None = None):
    return types.SimpleNamespace(
        type="page_location",
        cited_text=cited_text,
        document_title=document_title,
        start_page_number=start_page,
        end_page_number=end_page or start_page,
    )


def fake_text_block(text: str, citations=None):
    return types.SimpleNamespace(type="text", text=text, citations=citations)


def fake_response(
    content_blocks,
    model: str = "claude-opus-5",
    in_tok: int = 1000,
    out_tok: int = 200,
    stop_reason: str = "end_turn",
    stop_details=None,
):
    usage = types.SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok)
    return types.SimpleNamespace(
        content=content_blocks,
        model=model,
        usage=usage,
        stop_reason=stop_reason,
        stop_details=stop_details,
    )


class PdfInspectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_db_path = store.DB_PATH
        cls._original_data_dir = documents.DATA_DIR
        store.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        store.init_db()
        documents.init_documents_db()
        cls.project = store.create_project("Project Falcon", "test project for PDF inspection")

    @classmethod
    def tearDownClass(cls):
        store.DB_PATH = cls._original_db_path
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def setUp(self):
        self._env_patcher = patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": FAKE_SECRET, "ANTHROPIC_MODEL": "claude-opus-5"}
        )
        self._env_patcher.start()
        # Vary the bytes per test so repeated uploads to the shared class-level
        # project are never flagged as duplicates of each other.
        unique_pdf_bytes = SAMPLE_PDF_BYTES + f"\n% {self.id()}".encode()
        result = documents.save_uploaded_file(self.project.id, "sample.pdf", "", unique_pdf_bytes)
        assert result.status == "success" and result.document is not None
        self.document = result.document
        self.document_bytes = unique_pdf_bytes

    def tearDown(self):
        self._env_patcher.stop()

    def _mock_stream_client(self, get_final_message_return=None, stream_side_effect=None):
        mock_client = MagicMock()
        if stream_side_effect is not None:
            mock_client.messages.stream.side_effect = stream_side_effect
        else:
            mock_stream = MagicMock()
            mock_stream.get_final_message.return_value = get_final_message_return
            mock_client.messages.stream.return_value.__enter__.return_value = mock_stream
        return patch("pdf_inspection.anthropic.Anthropic", return_value=mock_client), mock_client

    def test_missing_api_key(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "missing_api_key")

    def test_sends_exact_original_pdf_bytes(self):
        response = fake_response([fake_text_block("## Document Identification\nA test document.")])
        patcher, mock_client = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertTrue(outcome.success)
        _, kwargs = mock_client.messages.stream.call_args
        doc_block = kwargs["messages"][0]["content"][0]
        self.assertEqual(doc_block["type"], "document")
        sent_bytes = base64.b64decode(doc_block["source"]["data"])
        self.assertEqual(sent_bytes, self.document_bytes)

    def test_sends_only_the_target_document(self):
        other = documents.save_uploaded_file(self.project.id, "other.pdf", "", OTHER_PDF_BYTES)
        self.assertEqual(other.status, "success")

        response = fake_response([fake_text_block("## Document Identification\nA test document.")])
        patcher, mock_client = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            pdf_inspection.inspect_document(self.document)

        _, kwargs = mock_client.messages.stream.call_args
        content = kwargs["messages"][0]["content"]
        document_blocks = [b for b in content if b.get("type") == "document"]
        self.assertEqual(len(document_blocks), 1)
        sent_bytes = base64.b64decode(document_blocks[0]["source"]["data"])
        self.assertEqual(sent_bytes, self.document_bytes)
        self.assertNotEqual(sent_bytes, OTHER_PDF_BYTES)

    def test_citations_are_preserved(self):
        citation = fake_citation("Revenue grew 12%.", start_page=4, end_page=4, document_title="sample.pdf")
        block = fake_text_block("Revenue grew 12% year over year.", citations=[citation])
        response = fake_response([block])
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        self.assertEqual(len(outcome.segments), 1)
        self.assertEqual(len(outcome.segments[0].citations), 1)
        cited = outcome.segments[0].citations[0]
        self.assertEqual(cited.start_page, 4)
        self.assertEqual(cited.end_page, 4)
        self.assertEqual(cited.cited_text, "Revenue grew 12%.")
        self.assertEqual(cited.document_title, "sample.pdf")

    def test_missing_citations_are_empty_not_invented(self):
        block = fake_text_block("## Summary\nThis is a general summary with no direct citation.")
        response = fake_response([block])
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        self.assertEqual(outcome.segments[0].citations, [])

    def test_oversized_pdf_is_rejected_before_transmission(self):
        with patch.object(pdf_inspection, "MAX_PDF_SOURCE_BYTES", 10):
            patcher, mock_client = self._mock_stream_client(get_final_message_return=None)
            with patcher:
                outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "oversized_pdf")
        mock_client.messages.stream.assert_not_called()

    def test_encrypted_pdf_error(self):
        error = make_status_error(
            anthropic.BadRequestError,
            400,
            "invalid_request_error",
            "This PDF appears to be encrypted with a password and cannot be processed.",
        )
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertTrue(outcome.transmitted)
        self.assertEqual(outcome.error_type, "encrypted_pdf")

    def test_malformed_pdf_error(self):
        error = make_status_error(
            anthropic.BadRequestError,
            400,
            "invalid_request_error",
            "The provided PDF is corrupt and could not be read.",
        )
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "malformed_pdf")

    def test_unrecognized_bad_request_falls_back_to_invalid_pdf(self):
        error = make_status_error(anthropic.BadRequestError, 400, "invalid_request_error", "Something odd happened.")
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "invalid_pdf")

    def test_max_tokens_truncation_is_a_failure_with_partial_output_preserved(self):
        block = fake_text_block("## Document Identification\nPartial anal")
        response = fake_response([block], stop_reason="max_tokens")
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "truncated_response")
        self.assertEqual(outcome.stop_reason, "max_tokens")
        self.assertIsNotNone(outcome.segments)

    def test_empty_response_is_a_failure(self):
        response = fake_response([fake_text_block("")])
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "empty_response")

    def test_missing_stored_file_is_a_failure(self):
        result = documents.save_uploaded_file(self.project.id, "vanishing.pdf", "", b"%PDF-1.4\nx\n%%EOF")
        assert result.document is not None
        documents.stored_file_path(result.document).unlink()

        outcome = pdf_inspection.inspect_document(result.document)

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "missing_file")

    def test_invalid_api_key(self):
        error = make_status_error(anthropic.AuthenticationError, 401, "authentication_error", "invalid x-api-key")
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "invalid_api_key")

    def test_model_unavailable(self):
        error = make_status_error(anthropic.NotFoundError, 404, "not_found_error", "model: bogus-model not found")
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "model_unavailable")

    def test_secret_never_appears_in_outcome(self):
        error = make_status_error(
            anthropic.AuthenticationError, 401, "authentication_error", f"invalid api key: {FAKE_SECRET}"
        )
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = pdf_inspection.inspect_document(self.document)

        self.assertNotIn(FAKE_SECRET, str(outcome.error_message))


if __name__ == "__main__":
    unittest.main()
