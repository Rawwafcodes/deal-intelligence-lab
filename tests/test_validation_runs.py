"""Tests for validation_runs.py: blind-run orchestration, mandate
fingerprinting, and blindness determination. The real Anthropic client is
always mocked - these tests never make a network call or consume API credit.
"""

import sys
import tempfile
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import answer_keys
import cross_format_analyses
import cross_format_analysis
import documents
import store
import validation_cases
import validation_runs

FAKE_SECRET = "sk-ant-api03-VALIDATION-RUNS-TEST-FAKE-SECRET-DO-NOT-LEAK"


def fake_text_block(text: str):
    return types.SimpleNamespace(type="text", text=text, citations=None)


def fake_response(content_blocks, stop_reason: str = "end_turn"):
    usage = types.SimpleNamespace(input_tokens=1000, output_tokens=200)
    return types.SimpleNamespace(
        content=content_blocks,
        model="claude-opus-5",
        usage=usage,
        stop_reason=stop_reason,
        stop_details=None,
        container=types.SimpleNamespace(id="container_1"),
    )


def _stream_cm(response):
    mock_stream = MagicMock()
    mock_stream.get_final_message.return_value = response
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_stream)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def mock_client_for(response):
    mock_client = MagicMock()
    mock_client.files.upload.return_value = types.SimpleNamespace(id="file_abc123")
    mock_client.files.delete.return_value = types.SimpleNamespace(id="file_abc123", type="file_deleted")
    mock_client.messages.stream.return_value = _stream_cm(response)
    return mock_client


class ValidationRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        documents.init_documents_db()
        validation_cases.init_validation_cases_db()
        answer_keys.init_answer_keys_db()
        validation_runs.init_validation_runs_db()
        cross_format_analyses.init_cross_format_analyses_db()
        cls.project = store.create_project("Project Falcon", "validation run tests")

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def setUp(self):
        self._env_patcher = patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": FAKE_SECRET, "ANTHROPIC_MODEL": "claude-opus-5"}
        )
        self._env_patcher.start()
        self.pdf_doc = documents.save_uploaded_file(
            self.project.id, "im.pdf", "", f"%PDF-1.4\n%{self.id()}\n%%EOF".encode()
        ).document
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-bytes"
        ).document

    def tearDown(self):
        self._env_patcher.stop()

    def _make_locked_case(self):
        case = validation_cases.create_validation_case(
            project_id=self.project.id,
            name=f"Case {self.id()}",
            description="",
            pdf_document_ids=[self.pdf_doc.id],
            excel_document_ids=[self.xlsx_doc.id],
        )
        answer_keys.create_initial_version(case.id)
        version = answer_keys.get_current_version(case.id)
        content = answer_keys.empty_content()
        content["issues"].append(answer_keys.new_issue(title="Revenue conflict", expected_severity="critical"))
        answer_keys.update_draft_content(case.id, version.id, content)
        answer_keys.lock_version(case.id, version.id)
        return case

    def test_mandate_fingerprint_matches_live_module_text(self):
        version, checksum = validation_runs.mandate_fingerprint()
        self.assertEqual(version, cross_format_analysis.MANDATE_VERSION)
        self.assertEqual(len(checksum), 64)
        # Deterministic: computing it again from the same (unchanged) module
        # text yields the identical checksum.
        version2, checksum2 = validation_runs.mandate_fingerprint()
        self.assertEqual(checksum, checksum2)

    def test_mandate_text_is_unchanged_by_this_milestone(self):
        # Regression guard: Milestone 8 must not alter Milestone 7's mandate.
        # This is the exact checksum recorded before Milestone 8 began.
        _, checksum = validation_runs.mandate_fingerprint()
        self.assertEqual(
            checksum, "bc3645ce1bc8f43d1ab48faf4afd063c1b3f1af04fc2efbd51e766c89d3d3346"
        )

    def test_cannot_start_a_run_without_a_locked_answer_key(self):
        case = validation_cases.create_validation_case(
            project_id=self.project.id,
            name=f"Case {self.id()}",
            description="",
            pdf_document_ids=[self.pdf_doc.id],
            excel_document_ids=[self.xlsx_doc.id],
        )
        answer_keys.create_initial_version(case.id)  # draft, never locked
        with patch("cross_format_analysis.anthropic.Anthropic") as mock_anthropic:
            with self.assertRaises(validation_runs.ValidationRunError):
                validation_runs.start_new_run(case.id, [self.pdf_doc, self.xlsx_doc])
            mock_anthropic.assert_not_called()

    def test_new_run_is_blind(self):
        case = self._make_locked_case()
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            run, outcome = validation_runs.start_new_run(case.id, [self.pdf_doc, self.xlsx_doc])
        self.assertTrue(outcome.success)
        self.assertTrue(run.is_blind)
        self.assertEqual(run.mandate_version, cross_format_analysis.MANDATE_VERSION)
        self.assertEqual(len(run.mandate_checksum), 64)

    def test_new_run_reuses_cross_format_analysis_path_and_persists_record(self):
        case = self._make_locked_case()
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            run, outcome = validation_runs.start_new_run(case.id, [self.pdf_doc, self.xlsx_doc])

        record = cross_format_analyses.get_cross_format_analysis(self.project.id, run.cross_format_analysis_id)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "success")
        self.assertEqual(record.pdf_document_ids, [self.pdf_doc.id])
        self.assertEqual(record.excel_document_ids, [self.xlsx_doc.id])

    def test_run_snapshots_answer_key_metadata_not_content(self):
        case = self._make_locked_case()
        locked_version = answer_keys.get_current_version(case.id)
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            run, outcome = validation_runs.start_new_run(case.id, [self.pdf_doc, self.xlsx_doc])

        self.assertEqual(run.answer_key_version_id, locked_version.id)
        self.assertEqual(run.answer_key_checksum, locked_version.checksum)
        self.assertEqual(run.answer_key_locked_at, locked_version.locked_at)
        # The run's own to_dict must never include answer-key content.
        self.assertNotIn("issues", str(run.to_dict()))
        self.assertNotIn("Revenue conflict", str(run.to_dict()))

    def test_attach_existing_analysis_requires_locked_key(self):
        case = validation_cases.create_validation_case(
            project_id=self.project.id,
            name=f"Case {self.id()}",
            description="",
            pdf_document_ids=[self.pdf_doc.id],
            excel_document_ids=[self.xlsx_doc.id],
        )
        answer_keys.create_initial_version(case.id)
        record = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id,
            pdf_document_ids=[self.pdf_doc.id],
            pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256],
            excel_document_ids=[self.xlsx_doc.id],
            excel_document_filenames=["model.xlsx"],
            excel_document_checksums=[self.xlsx_doc.sha256],
            status="success",
            transmitted=True,
            analysis_seconds=1.0,
            model="claude-opus-5",
            mandate_version="1",
            stop_reason="end_turn",
            input_tokens=10,
            output_tokens=10,
            code_execution_requests=1,
            error_type=None,
            error_message=None,
            segments=None,
            tool_trace=None,
            excel_cleanup=None,
            excel_verification=None,
        )
        with self.assertRaises(validation_runs.ValidationRunError):
            validation_runs.attach_existing_analysis(case.id, record)

    def test_attach_existing_analysis_locked_before_is_blind(self):
        case = self._make_locked_case()  # locked now
        record = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id,
            pdf_document_ids=[self.pdf_doc.id],
            pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256],
            excel_document_ids=[self.xlsx_doc.id],
            excel_document_filenames=["model.xlsx"],
            excel_document_checksums=[self.xlsx_doc.sha256],
            status="success",
            transmitted=True,
            analysis_seconds=1.0,
            model="claude-opus-5",
            mandate_version="1",
            stop_reason="end_turn",
            input_tokens=10,
            output_tokens=10,
            code_execution_requests=1,
            error_type=None,
            error_message=None,
            segments=None,
            tool_trace=None,
            excel_cleanup=None,
            excel_verification=None,
        )
        run = validation_runs.attach_existing_analysis(case.id, record)
        self.assertTrue(run.is_blind)  # locked strictly before this new analysis's created_at

    def test_attach_existing_analysis_locked_after_is_retrospective(self):
        # Create the analysis FIRST (simulating a plain Milestone 7 run
        # that happened before any validation case existed), then lock the
        # answer key afterward - this must never be labeled blind.
        record = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id,
            pdf_document_ids=[self.pdf_doc.id],
            pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256],
            excel_document_ids=[self.xlsx_doc.id],
            excel_document_filenames=["model.xlsx"],
            excel_document_checksums=[self.xlsx_doc.sha256],
            status="success",
            transmitted=True,
            analysis_seconds=1.0,
            model="claude-opus-5",
            mandate_version="1",
            stop_reason="end_turn",
            input_tokens=10,
            output_tokens=10,
            code_execution_requests=1,
            error_type=None,
            error_message=None,
            segments=None,
            tool_trace=None,
            excel_cleanup=None,
            excel_verification=None,
        )
        case = self._make_locked_case()  # locked_at is after record.created_at
        run = validation_runs.attach_existing_analysis(case.id, record)
        self.assertFalse(run.is_blind)

    def test_list_and_get_runs_for_case(self):
        case = self._make_locked_case()
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            run, _ = validation_runs.start_new_run(case.id, [self.pdf_doc, self.xlsx_doc])

        runs = validation_runs.list_runs_for_case(case.id)
        self.assertEqual(len(runs), 1)
        fetched = validation_runs.get_run(case.id, run.id)
        self.assertEqual(fetched.id, run.id)

    def test_secret_marker_in_answer_key_never_reaches_the_anthropic_request(self):
        secret = "SECRET-MARKER-9f8e7d6c5b4a"
        case = validation_cases.create_validation_case(
            project_id=self.project.id,
            name=f"Case {self.id()}",
            description="",
            pdf_document_ids=[self.pdf_doc.id],
            excel_document_ids=[self.xlsx_doc.id],
        )
        answer_keys.create_initial_version(case.id)
        version = answer_keys.get_current_version(case.id)
        content = answer_keys.empty_content()
        content["issues"].append(
            answer_keys.new_issue(title=f"Revenue conflict {secret}", evaluator_notes=secret)
        )
        answer_keys.update_draft_content(case.id, version.id, content)
        answer_keys.lock_version(case.id, version.id)

        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        mock_client = mock_client_for(response)
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client):
            run, outcome = validation_runs.start_new_run(case.id, [self.pdf_doc, self.xlsx_doc])

        self.assertTrue(outcome.success)
        _, stream_kwargs = mock_client.messages.stream.call_args
        self.assertNotIn(secret, str(stream_kwargs))
        # Also confirm it never appears in the files.upload call (the
        # workbook upload), or anywhere on the persisted run/outcome.
        upload_calls = str(mock_client.files.upload.call_args_list)
        self.assertNotIn(secret, upload_calls)
        self.assertNotIn(secret, str(run.to_dict()))
        self.assertNotIn(secret, str(outcome))


if __name__ == "__main__":
    unittest.main()
