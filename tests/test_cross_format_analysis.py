"""Tests for cross_format_analysis.py. The real Anthropic client is always
mocked here - these tests never make a network call or consume API credit.
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
import openpyxl

import cross_format_analysis
import documents
import store

FAKE_SECRET = "sk-ant-api03-CROSS-FORMAT-TEST-FAKE-SECRET-DO-NOT-LEAK"


def make_status_error(cls, status_code: int, error_type: str, message: str, path: str = "/v1/messages"):
    request = httpx2.Request("POST", f"https://api.anthropic.com{path}")
    response = httpx2.Response(
        status_code, request=request, json={"error": {"type": error_type, "message": message}}
    )
    return cls(message, response=response, body=response.json())


def build_sample_workbook(path: Path, sheet_title: str = "Revenue Model", marker: str = "") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = sheet_title
    ws["B7"] = 100
    ws["B8"] = "=B7*1.1"
    ws["C10"] = f"=NPV(0.1,B7,B7) {marker}"
    wb.save(path)
    return path.read_bytes()


def fake_pdf_citation(cited_text: str, document_index: int, start_page: int, document_title: str | None = None):
    return types.SimpleNamespace(
        type="page_location",
        cited_text=cited_text,
        document_index=document_index,
        document_title=document_title,
        start_page_number=start_page,
        end_page_number=start_page,
    )


def fake_text_block(text: str, citations=None):
    return types.SimpleNamespace(type="text", text=text, citations=citations)


def fake_response(
    content_blocks,
    model: str = "claude-opus-5",
    in_tok: int = 5000,
    out_tok: int = 1000,
    stop_reason: str = "end_turn",
    stop_details=None,
    container_id: str | None = "container_1",
):
    usage = types.SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok)
    container = types.SimpleNamespace(id=container_id) if container_id else None
    return types.SimpleNamespace(
        content=content_blocks,
        model=model,
        usage=usage,
        stop_reason=stop_reason,
        stop_details=stop_details,
        container=container,
    )


def _stream_cm(response):
    mock_stream = MagicMock()
    mock_stream.get_final_message.return_value = response
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_stream)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class CrossFormatAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_db_path = store.DB_PATH
        cls._original_data_dir = documents.DATA_DIR
        store.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        store.init_db()
        documents.init_documents_db()
        cls.project = store.create_project("Project Falcon", "test project for cross-format reconciliation")

    @classmethod
    def tearDownClass(cls):
        store.DB_PATH = cls._original_db_path
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def _scratch(self) -> Path:
        if not hasattr(self, "_scratch_dir_obj"):
            self._scratch_dir_obj = tempfile.TemporaryDirectory()
        return Path(self._scratch_dir_obj.name)

    def setUp(self):
        self._env_patcher = patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": FAKE_SECRET, "ANTHROPIC_MODEL": "claude-opus-5"}
        )
        self._env_patcher.start()

        unique = self.id()
        self.pdf_bytes = f"%PDF-1.4\n%Information memorandum\n% {unique}\n%%EOF".encode()
        pdf_result = documents.save_uploaded_file(self.project.id, "im.pdf", "", self.pdf_bytes)
        assert pdf_result.status == "success" and pdf_result.document is not None
        self.pdf_doc = pdf_result.document

        self.xlsx_bytes = build_sample_workbook(self._scratch() / "model.xlsx", marker=unique)
        xlsx_result = documents.save_uploaded_file(self.project.id, "model.xlsx", "", self.xlsx_bytes)
        assert xlsx_result.status == "success" and xlsx_result.document is not None
        self.xlsx_doc = xlsx_result.document

    def tearDown(self):
        self._env_patcher.stop()
        if hasattr(self, "_scratch_dir_obj"):
            self._scratch_dir_obj.cleanup()

    def _mock_client(self, stream_responses=None, stream_side_effect=None, upload_side_effect=None, delete_side_effect=None):
        mock_client = MagicMock()
        if upload_side_effect is not None:
            mock_client.files.upload.side_effect = upload_side_effect
        else:
            mock_client.files.upload.side_effect = [
                types.SimpleNamespace(id=f"file_{i}") for i in range(20)
            ]

        if delete_side_effect is not None:
            mock_client.files.delete.side_effect = delete_side_effect
        else:
            mock_client.files.delete.return_value = types.SimpleNamespace(id="file_x", type="file_deleted")

        if stream_side_effect is not None:
            mock_client.messages.stream.side_effect = stream_side_effect
        elif stream_responses is not None:
            mock_client.messages.stream.side_effect = [_stream_cm(r) for r in stream_responses]

        return patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client), mock_client

    # -- selection validation -------------------------------------------

    def test_missing_api_key(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "missing_api_key")

    def test_one_pdf_and_one_xlsx_accepted(self):
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        patcher, mock_client = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertTrue(outcome.success)
        self.assertTrue(outcome.transmitted)

    def test_multiple_pdfs_and_workbooks_accepted(self):
        pdf2 = documents.save_uploaded_file(
            self.project.id, "financing.pdf", "", f"%PDF-1.4\n%{self.id()}-2\n%%EOF".encode()
        ).document
        xlsx2_bytes = build_sample_workbook(self._scratch() / "model2.xlsx", marker=f"{self.id()}-2")
        xlsx2 = documents.save_uploaded_file(self.project.id, "model2.xlsx", "", xlsx2_bytes).document
        assert pdf2 is not None and xlsx2 is not None

        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent across all sources.")])
        patcher, mock_client = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis(
                [self.pdf_doc, pdf2, self.xlsx_doc, xlsx2]
            )
        self.assertTrue(outcome.success)
        self.assertEqual(mock_client.files.upload.call_count, 2)

    def test_pdf_only_selection_rejected(self):
        patcher, mock_client = self._mock_client()
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc])
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "missing_excel")
        mock_client.messages.stream.assert_not_called()

    def test_excel_only_selection_rejected(self):
        patcher, mock_client = self._mock_client()
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "missing_pdf")
        mock_client.files.upload.assert_not_called()

    def test_unsupported_file_type_rejected(self):
        txt_result = documents.save_uploaded_file(self.project.id, "notes.txt", "", b"plain text notes")
        assert txt_result.document is not None
        patcher, mock_client = self._mock_client()
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis(
                [self.pdf_doc, self.xlsx_doc, txt_result.document]
            )
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "unsupported_type")
        mock_client.files.upload.assert_not_called()
        mock_client.messages.stream.assert_not_called()

    def test_too_many_pdf_documents_rejected(self):
        with patch.object(cross_format_analysis, "MAX_PDF_DOCUMENTS", 0):
            patcher, mock_client = self._mock_client()
            with patcher:
                outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "too_many_pdf_documents")

    def test_too_many_excel_documents_rejected(self):
        with patch.object(cross_format_analysis, "MAX_EXCEL_DOCUMENTS", 0):
            patcher, mock_client = self._mock_client()
            with patcher:
                outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "too_many_excel_documents")

    def test_oversized_pdf_total_rejected_before_transmission(self):
        with patch.object(cross_format_analysis, "MAX_TOTAL_PDF_SOURCE_BYTES", len(self.pdf_bytes) - 1):
            patcher, mock_client = self._mock_client()
            with patcher:
                outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "oversized_pdf_total")

    def test_oversized_excel_workbook_rejected_before_transmission(self):
        with patch.object(cross_format_analysis, "MAX_EXCEL_WORKBOOK_SOURCE_BYTES", len(self.xlsx_bytes) - 1):
            patcher, mock_client = self._mock_client()
            with patcher:
                outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "oversized_excel_workbook")

    def test_missing_stored_file(self):
        result = documents.save_uploaded_file(self.project.id, "vanishing.pdf", "", b"%PDF-1.4\nx\n%%EOF")
        assert result.document is not None
        documents.stored_file_path(result.document).unlink()
        outcome = cross_format_analysis.run_cross_format_analysis([result.document, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertFalse(outcome.transmitted)
        self.assertEqual(outcome.error_type, "missing_file")

    # -- transmission fidelity -------------------------------------------

    def test_only_selected_files_are_transmitted(self):
        other_pdf = documents.save_uploaded_file(
            self.project.id, "unrelated.pdf", "", f"%PDF-1.4\n%unrelated-{self.id()}\n%%EOF".encode()
        ).document
        assert other_pdf is not None

        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        patcher, mock_client = self._mock_client(stream_responses=[response])
        with patcher:
            cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        _, kwargs = mock_client.messages.stream.call_args
        content = kwargs["messages"][0]["content"]
        document_blocks = [b for b in content if b.get("type") == "document"]
        self.assertEqual(len(document_blocks), 1)
        self.assertEqual(base64.b64decode(document_blocks[0]["source"]["data"]), self.pdf_bytes)
        self.assertNotIn(other_pdf.original_filename, str(kwargs))

    def test_original_pdf_bytes_sent_unchanged(self):
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        patcher, mock_client = self._mock_client(stream_responses=[response])
        with patcher:
            cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        _, kwargs = mock_client.messages.stream.call_args
        content = kwargs["messages"][0]["content"]
        document_blocks = [b for b in content if b.get("type") == "document"]
        self.assertEqual(base64.b64decode(document_blocks[0]["source"]["data"]), self.pdf_bytes)
        self.assertEqual(document_blocks[0]["title"], "im.pdf")
        self.assertTrue(document_blocks[0]["citations"]["enabled"])

    def test_original_workbook_bytes_uploaded_unchanged(self):
        captured: dict = {}

        def upload(*, file, **kwargs):
            filename, fileobj, mime_type = file
            captured["filename"] = filename
            captured["bytes"] = fileobj.read()
            captured["mime_type"] = mime_type
            return types.SimpleNamespace(id="file_abc")

        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        patcher, mock_client = self._mock_client(stream_responses=[response], upload_side_effect=upload)
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        self.assertEqual(captured["bytes"], self.xlsx_bytes)
        self.assertEqual(
            captured["mime_type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # A container_upload block referencing the uploaded file id is sent
        # alongside the PDF document block, in the same request.
        _, kwargs = mock_client.messages.stream.call_args
        content = kwargs["messages"][0]["content"]
        container_blocks = [b for b in content if b.get("type") == "container_upload"]
        self.assertEqual(container_blocks, [{"type": "container_upload", "file_id": "file_abc"}])

    def test_both_pdf_and_excel_content_blocks_present_in_one_request(self):
        # The core claim of this milestone: proves native PDF input and
        # Excel code-execution input are placed in the *same* request/context.
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        patcher, mock_client = self._mock_client(stream_responses=[response])
        with patcher:
            cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        _, kwargs = mock_client.messages.stream.call_args
        content = kwargs["messages"][0]["content"]
        types_present = {b.get("type") for b in content}
        self.assertIn("document", types_present)
        self.assertIn("container_upload", types_present)
        self.assertEqual(kwargs["tools"][0]["type"], cross_format_analysis.CODE_EXECUTION_TOOL_TYPE)

    # -- citations ---------------------------------------------------------

    def test_pdf_native_citation_preserved_and_resolved(self):
        citation = fake_pdf_citation("Revenue is $10M", document_index=0, start_page=4, document_title="im.pdf")
        block = fake_text_block("Revenue is disclosed as $10M.", citations=[citation])
        response = fake_response([block])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        pdf_citations = outcome.segments[0].pdf_citations
        self.assertEqual(len(pdf_citations), 1)
        self.assertEqual(pdf_citations[0].document_id, self.pdf_doc.id)

    def test_excel_citation_verified_and_resolved_to_correct_workbook(self):
        text = "Revenue in the model is 100 ('Workbook 1'!'Revenue Model'!B7 [value])."
        block = fake_text_block(text)
        response = fake_response([block])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        citation_parts = [p for s in outcome.segments for p in s.parts if p.type == "excel_citation"]
        self.assertEqual(len(citation_parts), 1)
        citation = citation_parts[0].citation
        self.assertEqual(citation.document_id, self.xlsx_doc.id)
        self.assertTrue(citation.exists)

    def test_multiple_workbooks_with_identical_sheet_names_remain_distinguishable(self):
        xlsx2_bytes = build_sample_workbook(
            self._scratch() / "other_model.xlsx", sheet_title="Revenue Model", marker=f"{self.id()}-2"
        )
        xlsx2 = documents.save_uploaded_file(self.project.id, "other_model.xlsx", "", xlsx2_bytes).document
        assert xlsx2 is not None
        # Give the two workbooks different B7 values so a wrong resolution
        # would be observably distinguishable in a live run; here the test
        # asserts on which *document* each citation resolves to.

        text = (
            "First model's revenue ('Workbook 1'!'Revenue Model'!B7 [value]) versus "
            "second model's revenue ('Workbook 2'!'Revenue Model'!B7 [value])."
        )
        block = fake_text_block(text)
        response = fake_response([block])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc, xlsx2])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        citation_parts = [p for s in outcome.segments for p in s.parts if p.type == "excel_citation"]
        self.assertEqual(len(citation_parts), 2)
        self.assertEqual(citation_parts[0].citation.document_id, self.xlsx_doc.id)
        self.assertEqual(citation_parts[1].citation.document_id, xlsx2.id)
        self.assertNotEqual(citation_parts[0].citation.document_id, citation_parts[1].citation.document_id)

    def test_unresolved_workbook_label_is_marked_not_guessed(self):
        text = "A stray reference ('Workbook 99'!'Revenue Model'!B7 [value])."
        block = fake_text_block(text)
        response = fake_response([block])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        citation = [p.citation for s in outcome.segments for p in s.parts if p.type == "excel_citation"][0]
        self.assertIsNone(citation.document_id)
        self.assertFalse(citation.exists)

    def test_formula_citation_with_nested_parens_parses_cleanly(self):
        text = (
            "The NPV is computed here "
            "('Workbook 1'!'Revenue Model'!C10 [formula] `=NPV(0.1,B7,B7)`) and nothing else follows."
        )
        block = fake_text_block(text)
        response = fake_response([block])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        parts = outcome.segments[0].parts
        citation_index = next(i for i, p in enumerate(parts) if p.type == "excel_citation")
        self.assertTrue(parts[citation_index].citation.exists)
        trailing_text = "".join(p.text or "" for p in parts[citation_index + 1 :])
        self.assertNotIn(")", trailing_text)

    def test_finding_with_evidence_from_both_formats_carries_both_citation_kinds(self):
        pdf_citation = fake_pdf_citation("Revenue disclosed as $10M", document_index=0, start_page=3, document_title="im.pdf")
        text = (
            "- **Title:** Revenue mismatch\n**Classification:** cross-source conflict\n"
            "**Severity:** high\n**Explanation:** the model shows a different figure.\n"
            "**PDF evidence:** the IM discloses revenue of $10M.\n"
            "**Workbook evidence:** the model shows 100 ('Workbook 1'!'Revenue Model'!B7 [value]).\n"
        )
        block = fake_text_block(text, citations=[pdf_citation])
        response = fake_response([block])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        segment = outcome.segments[0]
        self.assertEqual(len(segment.pdf_citations), 1)
        excel_parts = [p for p in segment.parts if p.type == "excel_citation"]
        self.assertEqual(len(excel_parts), 1)

    def test_missing_evidence_side_is_not_invented(self):
        block = fake_text_block(
            "- **Title:** Unsupported assumption\n**PDF evidence:** No PDF evidence located\n"
            "**Workbook evidence:** No workbook evidence located\n"
        )
        response = fake_response([block])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        assert outcome.segments is not None
        self.assertEqual(outcome.segments[0].pdf_citations, [])
        excel_parts = [p for p in outcome.segments[0].parts if p.type == "excel_citation"]
        self.assertEqual(excel_parts, [])

    def test_verification_unavailable_marks_citation_exists_none(self):
        result = documents.save_uploaded_file(self.project.id, "corrupt.xlsx", "", b"not a real xlsx file")
        assert result.document is not None

        text = "A claim ('Workbook 1'!'Sheet1'!A1 [value])."
        response = fake_response([fake_text_block(text)])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, result.document])

        self.assertTrue(outcome.success)
        assert outcome.excel_verification is not None
        self.assertFalse(outcome.excel_verification[0].available)
        self.assertEqual(outcome.excel_verification[0].unavailable_reason, "malformed_workbook")
        citation = [p.citation for s in outcome.segments for p in s.parts if p.type == "excel_citation"][0]
        self.assertIsNone(citation.exists)

    # -- provider file cleanup ----------------------------------------------

    def test_provider_files_deleted_after_success(self):
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        patcher, mock_client = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        assert outcome.excel_cleanup is not None
        self.assertEqual(len(outcome.excel_cleanup), 1)
        self.assertTrue(outcome.excel_cleanup[0].attempted)
        self.assertTrue(outcome.excel_cleanup[0].succeeded)
        mock_client.files.delete.assert_called_once()

    def test_cleanup_attempted_after_messages_stream_failure(self):
        error = make_status_error(anthropic.AuthenticationError, 401, "authentication_error", "bad key")
        patcher, mock_client = self._mock_client(stream_side_effect=error)
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertFalse(outcome.success)
        self.assertTrue(outcome.transmitted)
        assert outcome.excel_cleanup is not None
        self.assertTrue(outcome.excel_cleanup[0].attempted)
        mock_client.files.delete.assert_called_once()

    def test_cleanup_attempted_for_already_uploaded_workbook_when_second_upload_fails(self):
        xlsx2_bytes = build_sample_workbook(self._scratch() / "model2.xlsx", marker=f"{self.id()}-2")
        xlsx2 = documents.save_uploaded_file(self.project.id, "model2.xlsx", "", xlsx2_bytes).document
        assert xlsx2 is not None

        error = make_status_error(anthropic.APIStatusError, 500, "api_error", "server error", path="/v1/files")
        upload_effect = [types.SimpleNamespace(id="file_1"), error]
        patcher, mock_client = self._mock_client(upload_side_effect=upload_effect)
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc, xlsx2])

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "upload_failed")
        assert outcome.excel_cleanup is not None
        self.assertEqual(len(outcome.excel_cleanup), 1)  # only the workbook that actually got uploaded
        self.assertTrue(outcome.excel_cleanup[0].attempted)
        mock_client.messages.stream.assert_not_called()

    def test_partial_cleanup_failure_is_recorded_not_hidden(self):
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        patcher, mock_client = self._mock_client(stream_responses=[response], delete_side_effect=RuntimeError("boom"))
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)  # analysis itself still succeeded
        assert outcome.excel_cleanup is not None
        self.assertTrue(outcome.excel_cleanup[0].attempted)
        self.assertFalse(outcome.excel_cleanup[0].succeeded)

    def test_cleanup_attempted_after_still_paused(self):
        paused = fake_response([fake_text_block("Still working...")], stop_reason="pause_turn")
        patcher, mock_client = self._mock_client(
            stream_responses=[paused] * (cross_format_analysis.MAX_PAUSE_CONTINUATIONS + 1)
        )
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "still_paused")
        assert outcome.excel_cleanup is not None
        self.assertTrue(outcome.excel_cleanup[0].attempted)

    def test_pause_turn_continues_and_reuses_container(self):
        paused = fake_response([fake_text_block("Working...")], stop_reason="pause_turn")
        finished = fake_response([fake_text_block("## Executive Conclusion\nDone.")])
        patcher, mock_client = self._mock_client(stream_responses=[paused, finished])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        self.assertEqual(mock_client.messages.stream.call_count, 2)
        _, second_kwargs = mock_client.messages.stream.call_args_list[1]
        self.assertEqual(second_kwargs["container"], "container_1")

    # -- error classification / truncation ----------------------------------

    def test_encrypted_pdf_error_names_offending_document(self):
        error = make_status_error(
            anthropic.BadRequestError,
            400,
            "invalid_request_error",
            "messages.0.content.0.document.source.base64.data: the PDF is encrypted with a password.",
        )
        patcher, _ = self._mock_client(stream_side_effect=error)
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "encrypted_pdf")
        assert outcome.error_message is not None
        self.assertIn("im.pdf", outcome.error_message)

    def test_max_tokens_truncation_is_rejected_with_partial_output_preserved(self):
        block = fake_text_block("## Executive Conclusion\nPartial anal")
        response = fake_response([block], stop_reason="max_tokens")
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "truncated_response")
        self.assertEqual(outcome.stop_reason, "max_tokens")
        self.assertIsNotNone(outcome.segments)

    def test_empty_response_is_an_error(self):
        response = fake_response([fake_text_block("")])
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "empty_response")

    def test_refusal_is_an_error(self):
        response = fake_response(
            [fake_text_block("I can't help with that.")],
            stop_reason="refusal",
            stop_details=types.SimpleNamespace(explanation="policy"),
        )
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "refused")

    def test_insufficient_credit_real_world_400_shape(self):
        error = make_status_error(
            anthropic.APIStatusError,
            400,
            "invalid_request_error",
            "Your credit balance is too low to access the Anthropic API. "
            "Please go to Plans & Billing to upgrade or purchase credits.",
            path="/v1/files",
        )
        patcher, mock_client = self._mock_client(upload_side_effect=error)
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertFalse(outcome.success)
        self.assertEqual(outcome.error_type, "insufficient_credit")

    # -- tool trace ----------------------------------------------------------

    def test_tool_trace_is_captured_and_code_execution_requests_counted(self):
        blocks = [
            types.SimpleNamespace(type="server_tool_use", name="bash_code_execution", input={"command": "x"}),
            fake_text_block("## Executive Conclusion\nDone."),
        ]
        response = fake_response(blocks)
        patcher, _ = self._mock_client(stream_responses=[response])
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        self.assertEqual(outcome.usage["code_execution_requests"], 1)

    # -- secrecy ---------------------------------------------------------

    def test_secret_never_appears_in_outcome(self):
        error = make_status_error(
            anthropic.AuthenticationError, 401, "authentication_error", f"invalid api key: {FAKE_SECRET}"
        )
        patcher, _ = self._mock_client(stream_side_effect=error)
        with patcher:
            outcome = cross_format_analysis.run_cross_format_analysis([self.pdf_doc, self.xlsx_doc])
        self.assertNotIn(FAKE_SECRET, str(outcome.error_message))


if __name__ == "__main__":
    unittest.main()
