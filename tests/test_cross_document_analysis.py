"""Tests for cross_document_analysis.py. The real Anthropic client is
always mocked here - these tests never make a network call or consume API
credit.
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

import cross_document_analysis
import documents
import store

FAKE_SECRET = "sk-ant-api03-CROSS-ANALYSIS-TEST-FAKE-SECRET-DO-NOT-LEAK"


def make_status_error(cls, status_code: int, error_type: str, message: str):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        status_code, request=request, json={"error": {"type": error_type, "message": message}}
    )
    return cls(message, response=response, body=response.json())


def fake_citation(
    cited_text: str,
    document_index: int,
    start_page: int,
    end_page: int | None = None,
    document_title: str | None = None,
):
    return types.SimpleNamespace(
        type="page_location",
        cited_text=cited_text,
        document_index=document_index,
        document_title=document_title,
        start_page_number=start_page,
        end_page_number=end_page or start_page,
    )


def fake_text_block(text: str, citations=None):
    return types.SimpleNamespace(type="text", text=text, citations=citations)


def fake_response(
    content_blocks,
    model: str = "claude-opus-5",
    in_tok: int = 2000,
    out_tok: int = 500,
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


class CrossDocumentAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_db_path = store.DB_PATH
        cls._original_data_dir = documents.DATA_DIR
        store.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        store.init_db()
        documents.init_documents_db()
        cls.project = store.create_project("Project Falcon", "test project for cross-document analysis")

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

        unique = self.id()
        self.doc_a_bytes = f"%PDF-1.4\n%NDA document\n% {unique}-a\n%%EOF".encode()
        self.doc_b_bytes = f"%PDF-1.4\n%Term sheet document\n% {unique}-b\n%%EOF".encode()
        result_a = documents.save_uploaded_file(self.project.id, "nda.pdf", "", self.doc_a_bytes)
        result_b = documents.save_uploaded_file(self.project.id, "term_sheet.pdf", "", self.doc_b_bytes)
        assert result_a.status == "success" and result_a.document is not None
        assert result_b.status == "success" and result_b.document is not None
        self.doc_a = result_a.document
        self.doc_b = result_b.document

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
        return patch("cross_document_analysis.anthropic.Anthropic", return_value=mock_client), mock_client

    def test_missing_api_key(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "missing_api_key")

    def test_too_few_documents_rejected_before_transmission(self):
        patcher, mock_client = self._mock_stream_client(get_final_message_return=None)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a])

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "too_few_documents")
        mock_client.messages.stream.assert_not_called()

    def test_too_many_documents_rejected_before_transmission(self):
        with patch.object(cross_document_analysis, "MAX_DOCUMENTS", 1):
            patcher, mock_client = self._mock_stream_client(get_final_message_return=None)
            with patcher:
                outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "too_many_documents")
        mock_client.messages.stream.assert_not_called()

    def test_non_pdf_document_rejected_before_transmission(self):
        txt_result = documents.save_uploaded_file(self.project.id, "notes.txt", "", b"plain text notes")
        assert txt_result.document is not None

        patcher, mock_client = self._mock_stream_client(get_final_message_return=None)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, txt_result.document])

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "not_pdf")
        mock_client.messages.stream.assert_not_called()

    def test_combined_oversized_rejected_before_transmission(self):
        with patch.object(cross_document_analysis, "MAX_TOTAL_SOURCE_BYTES", len(self.doc_a_bytes) + 1):
            patcher, mock_client = self._mock_stream_client(get_final_message_return=None)
            with patcher:
                outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "oversized_total")
        mock_client.messages.stream.assert_not_called()

    def test_sends_exact_bytes_for_every_selected_document_in_order(self):
        response = fake_response([fake_text_block("## Combined Document Understanding\nBoth documents relate.")])
        patcher, mock_client = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertTrue(outcome.success)
        _, kwargs = mock_client.messages.stream.call_args
        content = kwargs["messages"][0]["content"]
        document_blocks = [b for b in content if b.get("type") == "document"]
        self.assertEqual(len(document_blocks), 2)
        self.assertEqual(base64.b64decode(document_blocks[0]["source"]["data"]), self.doc_a_bytes)
        self.assertEqual(base64.b64decode(document_blocks[1]["source"]["data"]), self.doc_b_bytes)
        self.assertEqual(document_blocks[0]["title"], "nda.pdf")
        self.assertEqual(document_blocks[1]["title"], "term_sheet.pdf")

    def test_request_uses_generous_max_tokens_and_client_timeout(self):
        # Regression guard: a real production run against 6 large documents
        # was cut off by a too-small max_tokens cap, and a naive fix (just
        # raising it) would risk trading that for a client read-timeout on
        # the resulting longer-running request. Both must move together.
        response = fake_response([fake_text_block("## Combined Document Understanding\nBoth relate.")])
        mock_stream = MagicMock()
        mock_stream.get_final_message.return_value = response
        mock_client = MagicMock()
        mock_client.messages.stream.return_value.__enter__.return_value = mock_stream

        with patch("cross_document_analysis.anthropic.Anthropic", return_value=mock_client) as mock_anthropic_cls:
            cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        _, client_kwargs = mock_anthropic_cls.call_args
        self.assertGreaterEqual(client_kwargs["timeout"], 1200)

        _, stream_kwargs = mock_client.messages.stream.call_args
        self.assertGreaterEqual(stream_kwargs["max_tokens"], 64000)

    def test_unselected_document_never_sent(self):
        other_bytes = f"%PDF-1.4\n%unrelated document\n% {self.id()}\n%%EOF".encode()
        other_result = documents.save_uploaded_file(self.project.id, "unrelated.pdf", "", other_bytes)
        assert other_result.status == "success"

        response = fake_response([fake_text_block("## Combined Document Understanding\nBoth documents relate.")])
        patcher, mock_client = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        _, kwargs = mock_client.messages.stream.call_args
        content = kwargs["messages"][0]["content"]
        document_blocks = [b for b in content if b.get("type") == "document"]
        self.assertEqual(len(document_blocks), 2)
        sent_bytes = [base64.b64decode(b["source"]["data"]) for b in document_blocks]
        self.assertNotIn(other_bytes, sent_bytes)

    def test_document_index_resolves_to_correct_document_id(self):
        citation_a = fake_citation("NDA term X", document_index=0, start_page=1, document_title="nda.pdf")
        citation_b = fake_citation("Term sheet term Y", document_index=1, start_page=2, document_title="term_sheet.pdf")
        block = fake_text_block(
            "The NDA states X while the term sheet states Y.", citations=[citation_a, citation_b]
        )
        response = fake_response([block])
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        citations = outcome.segments[0].citations
        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0].document_id, self.doc_a.id)
        self.assertEqual(citations[1].document_id, self.doc_b.id)

    def test_finding_missing_one_side_keeps_only_the_citation_returned(self):
        # A finding that only cites one document is passed through exactly
        # as the API returned it - the missing side is never invented.
        citation_a = fake_citation("NDA term X", document_index=0, start_page=1, document_title="nda.pdf")
        block = fake_text_block(
            "- **Title:** Possible conflict\n**Classification:** inconsistency\n"
            "**Uncertainty:** partially supported - the term sheet's corresponding clause is not cited",
            citations=[citation_a],
        )
        response = fake_response([block])
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        citations = outcome.segments[0].citations
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].document_id, self.doc_a.id)

    def test_out_of_range_document_index_does_not_crash(self):
        # Defensive: an out-of-range document_index (should not happen, but
        # must never be silently mapped to the wrong document) resolves to
        # document_id=None rather than an incorrect guess.
        citation = fake_citation("something", document_index=5, start_page=1)
        block = fake_text_block("A claim.", citations=[citation])
        response = fake_response([block])
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        self.assertIsNone(outcome.segments[0].citations[0].document_id)

    def test_missing_citations_are_empty_not_invented(self):
        block = fake_text_block("## Summary\nA general uncited remark.")
        response = fake_response([block])
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        self.assertEqual(outcome.segments[0].citations, [])

    def test_encrypted_pdf_error_names_offending_document(self):
        error = make_status_error(
            anthropic.BadRequestError,
            400,
            "invalid_request_error",
            "messages.0.content.1.document.source.base64.data: the PDF is encrypted with a password.",
        )
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertFalse(outcome.success)
        self.assertTrue(outcome.transmitted)
        self.assertEqual(outcome.error_type, "encrypted_pdf")
        assert outcome.error_message is not None
        self.assertIn("term_sheet.pdf", outcome.error_message)

    def test_malformed_pdf_error(self):
        error = make_status_error(
            anthropic.BadRequestError,
            400,
            "invalid_request_error",
            "messages.0.content.0.document.source.base64.data: The PDF specified was not valid.",
        )
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "malformed_pdf")
        assert outcome.error_message is not None
        self.assertIn("nda.pdf", outcome.error_message)

    def test_max_tokens_truncation_is_a_failure_with_partial_output_preserved(self):
        block = fake_text_block("## Combined Document Understanding\nPartial anal")
        response = fake_response([block], stop_reason="max_tokens")
        patcher, _ = self._mock_stream_client(get_final_message_return=response)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "truncated_response")
        self.assertEqual(outcome.stop_reason, "max_tokens")
        self.assertIsNotNone(outcome.segments)

    def test_partial_api_failure_missing_stored_file(self):
        result = documents.save_uploaded_file(self.project.id, "vanishing.pdf", "", b"%PDF-1.4\nx\n%%EOF")
        assert result.document is not None
        documents.stored_file_path(result.document).unlink()

        outcome = cross_document_analysis.run_cross_analysis([self.doc_a, result.document])

        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "missing_file")

    def test_secret_never_appears_in_outcome(self):
        error = make_status_error(
            anthropic.AuthenticationError, 401, "authentication_error", f"invalid api key: {FAKE_SECRET}"
        )
        patcher, _ = self._mock_stream_client(stream_side_effect=error)
        with patcher:
            outcome = cross_document_analysis.run_cross_analysis([self.doc_a, self.doc_b])

        self.assertNotIn(FAKE_SECRET, str(outcome.error_message))


if __name__ == "__main__":
    unittest.main()
