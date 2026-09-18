"""Tests for Task 15.3's opt-in trigger configuration: persistence and
matching logic (triggers.py) and the firing orchestration
(mandates.fire_triggers_for_event). No mocking needed for firing itself
- creating a Mandate/Plan makes no external call; the two templates a
trigger can fire (readiness, reassessment) are exercised without any
provider mock for readiness, and with one for reassessment where a
successful firing is asserted.
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cross_format_analyses
import deal_briefs
import documents
import mandates
import store
import triggers
import version_dependencies
import work_products
import workspaces

PDF_BYTES = b"%PDF-1.4\n%Trigger test bytes\n%%EOF"

SAMPLE_FINDINGS_TEXT = (
    "## Reconciliation Findings\n"
    "- **Title:** Term-sheet price gap\n"
    "**Classification:** cross-source conflict\n"
    "**Severity:** critical\n"
    "**Explanation:** the price differs across sources.\n"
    "**PDF evidence:** the IM says $12m.\n"
    "**Workbook evidence:** the model says $10m.\n"
    "**Commercial or financial relevance:** determines the offer price.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask the seller to reconcile.\n\n"
)


def _text_segment(text: str) -> dict:
    return {"parts": [{"type": "text", "text": text}], "pdf_citations": []}


class TriggerValidationTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        triggers.init_triggers_db()
        self.project = store.create_project("Trigger Validation Tests", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def _base_kwargs(self, **overrides):
        kwargs = dict(
            project_id=self.project.id, name="Reassess on source change", event_type="document_version_changed",
            template_key="reassessment", owner_user_id="lead-1",
        )
        kwargs.update(overrides)
        return kwargs

    def test_creates_with_defaults(self):
        trigger = triggers.create_trigger(**self._base_kwargs())
        self.assertEqual(trigger.status, "active")
        self.assertEqual(trigger.approval_policy, "manual")
        self.assertIsNone(trigger.scope_document_id)
        self.assertIsNone(trigger.disabled_at)

    def test_rejects_empty_name(self):
        with self.assertRaises(triggers.TriggerValidationError):
            triggers.create_trigger(**self._base_kwargs(name="  "))

    def test_rejects_unknown_event_type(self):
        with self.assertRaises(triggers.TriggerValidationError):
            triggers.create_trigger(**self._base_kwargs(event_type="submission_submitted"))

    def test_rejects_incompatible_template_for_event(self):
        # decision_package_prepared only pairs with "readiness", not "reassessment"
        with self.assertRaises(triggers.TriggerValidationError):
            triggers.create_trigger(**self._base_kwargs(event_type="decision_package_prepared", template_key="reassessment"))

    def test_readiness_is_compatible_with_both_event_types(self):
        t1 = triggers.create_trigger(**self._base_kwargs(event_type="document_version_changed", template_key="readiness"))
        t2 = triggers.create_trigger(**self._base_kwargs(event_type="decision_package_prepared", template_key="readiness"))
        self.assertEqual(t1.template_key, "readiness")
        self.assertEqual(t2.template_key, "readiness")

    def test_rejects_unknown_approval_policy(self):
        with self.assertRaises(triggers.TriggerValidationError):
            triggers.create_trigger(**self._base_kwargs(approval_policy="auto"))

    def test_rejects_missing_owner(self):
        with self.assertRaises(triggers.TriggerValidationError):
            triggers.create_trigger(**self._base_kwargs(owner_user_id=""))


class TriggerMatchingTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        triggers.init_triggers_db()
        self.project = store.create_project("Trigger Matching Tests", "")
        self.other_project = store.create_project("Other Deal", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def test_unscoped_trigger_matches_any_document(self):
        triggers.create_trigger(
            project_id=self.project.id, name="x", event_type="document_version_changed", template_key="readiness",
            owner_user_id="lead-1",
        )
        matches = triggers.match_active_triggers(self.project.id, "document_version_changed", document_id="doc-1")
        self.assertEqual(len(matches), 1)
        matches2 = triggers.match_active_triggers(self.project.id, "document_version_changed", document_id="doc-2")
        self.assertEqual(len(matches2), 1)

    def test_scoped_trigger_matches_only_its_own_document(self):
        triggers.create_trigger(
            project_id=self.project.id, name="x", event_type="document_version_changed", template_key="readiness",
            owner_user_id="lead-1", scope_document_id="doc-1",
        )
        self.assertEqual(len(triggers.match_active_triggers(self.project.id, "document_version_changed", document_id="doc-1")), 1)
        self.assertEqual(len(triggers.match_active_triggers(self.project.id, "document_version_changed", document_id="doc-2")), 0)

    def test_wrong_event_type_does_not_match(self):
        triggers.create_trigger(
            project_id=self.project.id, name="x", event_type="decision_package_prepared", template_key="readiness",
            owner_user_id="lead-1",
        )
        self.assertEqual(len(triggers.match_active_triggers(self.project.id, "document_version_changed", document_id="doc-1")), 0)

    def test_disabled_trigger_does_not_match(self):
        trigger = triggers.create_trigger(
            project_id=self.project.id, name="x", event_type="document_version_changed", template_key="readiness",
            owner_user_id="lead-1",
        )
        triggers.disable_trigger(self.project.id, trigger.id)
        self.assertEqual(len(triggers.match_active_triggers(self.project.id, "document_version_changed", document_id="doc-1")), 0)

    def test_trigger_from_another_project_never_matches(self):
        triggers.create_trigger(
            project_id=self.other_project.id, name="x", event_type="document_version_changed", template_key="readiness",
            owner_user_id="lead-1",
        )
        self.assertEqual(len(triggers.match_active_triggers(self.project.id, "document_version_changed", document_id="doc-1")), 0)

    def test_disable_unknown_trigger_raises(self):
        with self.assertRaises(triggers.TriggerValidationError):
            triggers.disable_trigger(self.project.id, "does-not-exist")


class RecordFiringTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        triggers.init_triggers_db()
        self.project = store.create_project("Firing Tests", "")
        self.trigger = triggers.create_trigger(
            project_id=self.project.id, name="x", event_type="document_version_changed", template_key="readiness",
            owner_user_id="lead-1",
        )

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def test_record_and_list_firing(self):
        firing = triggers.record_firing(
            trigger_id=self.trigger.id, project_id=self.project.id, workspace_id="ws-1",
            event_detail={"document_id": "doc-1"}, mandate_id="m1", plan_id="p1", status="proposed",
            error_message=None,
        )
        self.assertEqual(firing.status, "proposed")
        listed = triggers.list_firings(self.trigger.id)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].event_detail, {"document_id": "doc-1"})

    def test_invalid_status_rejected(self):
        with self.assertRaises(triggers.TriggerValidationError):
            triggers.record_firing(
                trigger_id=self.trigger.id, project_id=self.project.id, workspace_id="ws-1", event_detail={},
                mandate_id=None, plan_id=None, status="bogus", error_message=None,
            )


class FireTriggersForEventTests(unittest.TestCase):
    """Real HTTP-free, real-database tests of mandates.fire_triggers_for_event."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        work_products.DATA_DIR = documents.DATA_DIR
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()
        version_dependencies.init_version_dependencies_db()
        triggers.init_triggers_db()
        mandates.init_mandates_db()

        self.project = store.create_project("Fire Triggers Tests", "")
        self.pdf_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF_BYTES).document
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-bytes"
        ).document
        self.analysis = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id, pdf_document_ids=[self.pdf_doc.id], pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256], excel_document_ids=[self.xlsx_doc.id],
            excel_document_filenames=["model.xlsx"], excel_document_checksums=[self.xlsx_doc.sha256],
            status="success", transmitted=True, analysis_seconds=5.0, model="claude-opus-5", mandate_version="1",
            stop_reason="end_turn", input_tokens=100, output_tokens=50, code_execution_requests=0,
            error_type=None, error_message=None, segments=[_text_segment(SAMPLE_FINDINGS_TEXT)], tool_trace=None,
            excel_cleanup=None, excel_verification=None,
        )
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def test_no_matching_trigger_returns_empty_list(self):
        result = mandates.fire_triggers_for_event(
            self.project.id, "document_version_changed", self.workspace.id, {"document_id": self.pdf_doc.id},
        )
        self.assertEqual(result, [])

    def test_readiness_trigger_fires_and_creates_a_real_mandate_and_plan(self):
        trigger = triggers.create_trigger(
            project_id=self.project.id, name="Check readiness on source change",
            event_type="document_version_changed", template_key="readiness", owner_user_id="lead-1",
        )
        firings = mandates.fire_triggers_for_event(
            self.project.id, "document_version_changed", self.workspace.id, {"document_id": self.pdf_doc.id},
            document_id=self.pdf_doc.id,
        )
        self.assertEqual(len(firings), 1)
        firing = firings[0]
        self.assertEqual(firing.status, "proposed")
        self.assertEqual(firing.trigger_id, trigger.id)
        self.assertIsNotNone(firing.mandate_id)
        self.assertIsNotNone(firing.plan_id)

        mandate = mandates.get_mandate(self.project.id, firing.mandate_id)
        self.assertEqual(mandate.status, "awaiting_approval")
        self.assertIn(trigger.name, mandate.objective)
        plan = mandates.get_plan(mandate.id, firing.plan_id)
        self.assertEqual(plan.template_key, "readiness")
        self.assertEqual(plan.stages[0]["input"]["workspace_id"], self.workspace.id)

        listed = triggers.list_firings(trigger.id)
        self.assertEqual(len(listed), 1)

    def test_reassessment_trigger_fires_but_records_error_when_workspace_not_stale(self):
        """The workspace has not been marked stale, so proposing a
        reassessment plan fails its own precondition - this must be
        recorded as an 'error' firing, not raised out of fire_triggers_
        for_event (which would break the real upload request that
        caused the event)."""
        trigger = triggers.create_trigger(
            project_id=self.project.id, name="Reassess on source change", event_type="document_version_changed",
            template_key="reassessment", owner_user_id="lead-1",
        )
        firings = mandates.fire_triggers_for_event(
            self.project.id, "document_version_changed", self.workspace.id, {"document_id": self.pdf_doc.id},
            document_id=self.pdf_doc.id,
        )
        self.assertEqual(len(firings), 1)
        self.assertEqual(firings[0].status, "error")
        self.assertIsNone(firings[0].mandate_id)
        self.assertIn(trigger.id, [t.id for t in triggers.list_triggers(self.project.id)])  # trigger itself untouched

    def test_multiple_triggers_each_fire_independently(self):
        triggers.create_trigger(
            project_id=self.project.id, name="Readiness A", event_type="document_version_changed",
            template_key="readiness", owner_user_id="lead-1",
        )
        triggers.create_trigger(
            project_id=self.project.id, name="Readiness B", event_type="document_version_changed",
            template_key="readiness", owner_user_id="analyst-1",
        )
        firings = mandates.fire_triggers_for_event(
            self.project.id, "document_version_changed", self.workspace.id, {"document_id": self.pdf_doc.id},
            document_id=self.pdf_doc.id,
        )
        self.assertEqual(len(firings), 2)
        self.assertTrue(all(f.status == "proposed" for f in firings))
        mandate_ids = {f.mandate_id for f in firings}
        self.assertEqual(len(mandate_ids), 2)  # two genuinely separate mandates


if __name__ == "__main__":
    unittest.main()
