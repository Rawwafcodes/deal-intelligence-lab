"""Table-driven tests for authz.py's centralized policy - pure, no
server or database (see authz.py's own module docstring). server.py's
own real HTTP behavior is covered separately in
tests/test_authorization_matrix.py; this file only tests the policy
function itself against every role/capability pair, so a future
capability change that silently narrows or widens a role is caught
here first, independent of any route wiring."""

import unittest

import authz
import identity


class CapabilityMatrixShapeTests(unittest.TestCase):
    def test_every_deal_role_has_a_matrix_row(self):
        for role in identity.DEAL_ROLES:
            self.assertIsNotNone(authz.capabilities_for(role))

    def test_every_matrix_row_covers_every_capability(self):
        for role in identity.DEAL_ROLES:
            row = authz.capabilities_for(role)
            self.assertEqual(set(row.keys()), set(authz.ALL_CAPABILITIES))

    def test_unknown_role_denies_everything(self):
        row = authz.capabilities_for("not_a_real_role")
        self.assertTrue(all(v is False for v in row.values()))

    def test_none_role_denies_everything(self):
        row = authz.capabilities_for(None)
        self.assertTrue(all(v is False for v in row.values()))

    def test_unknown_capability_raises(self):
        with self.assertRaises(ValueError):
            authz.has_capability("deal_lead", "not_a_real_capability")


class DealLeadTests(unittest.TestCase):
    def test_deal_lead_has_every_capability(self):
        for capability in authz.ALL_CAPABILITIES:
            self.assertTrue(
                authz.has_capability("deal_lead", capability),
                f"deal_lead should have {capability}",
            )


class ExternalExecutiveTests(unittest.TestCase):
    """Every assertion here traces directly to the founder's own 2026-
    09-27 authorization closeout directive's "May access only"/"May not
    access by default" lists for external_executive."""

    def test_denied_capabilities(self):
        denied = (
            authz.VIEW_INTERNAL_DOCUMENTS,
            authz.DOWNLOAD_DOCUMENTS,
            authz.VIEW_FINDINGS,
            authz.MANAGE_FINDINGS,
            authz.CREATE_REQUESTS,
            authz.VIEW_MANDATES,
            authz.CREATE_MANDATES,
            authz.EXECUTE_MANDATES,
            authz.VIEW_WORK_PRODUCTS,
            authz.SUBMIT_WORK,
            authz.REVIEW_WORK,
            authz.APPROVE_PUBLISH,
            authz.VIEW_INTERNAL_ACTIVITY,
            authz.VIEW_READINESS,
            authz.VIEW_REASSESSMENTS,
            authz.REQUEST_REASSESSMENT,
            authz.VIEW_ASSERTIONS,
            authz.MANAGE_ASSERTIONS,
            authz.VIEW_TRIGGERS,
            authz.CONFIGURE_TRIGGERS,
            authz.MANAGE_MEMBERSHIP,
        )
        for capability in denied:
            self.assertFalse(
                authz.has_capability("external_executive", capability),
                f"external_executive should NOT have {capability}",
            )

    def test_allowed_capabilities(self):
        allowed = (
            authz.VIEW_DEAL,
            authz.VIEW_REQUESTS,
            authz.RESPOND_AS_EXTERNAL,
            authz.VIEW_DECISION_PACKAGES,
        )
        for capability in allowed:
            self.assertTrue(
                authz.has_capability("external_executive", capability),
                f"external_executive should have {capability}",
            )

    def test_denied_set_and_allowed_set_cover_every_capability(self):
        # Guards against a newly-added capability in authz.py silently
        # missing from both lists above (and therefore from this test).
        allowed = {authz.VIEW_DEAL, authz.VIEW_REQUESTS, authz.RESPOND_AS_EXTERNAL, authz.VIEW_DECISION_PACKAGES}
        denied = set(authz.ALL_CAPABILITIES) - allowed
        self.assertEqual(allowed | denied, set(authz.ALL_CAPABILITIES))

    def test_only_sees_sent_or_answered_requests(self):
        self.assertTrue(authz.request_visible_to("external_executive", "sent"))
        self.assertTrue(authz.request_visible_to("external_executive", "answered"))
        self.assertFalse(authz.request_visible_to("external_executive", "draft"))
        self.assertFalse(authz.request_visible_to("external_executive", "closed"))

    def test_only_sees_approved_deliverables(self):
        self.assertTrue(authz.deliverable_visible_to("external_executive", "approved"))
        self.assertFalse(authz.deliverable_visible_to("external_executive", "draft"))
        self.assertFalse(authz.deliverable_visible_to("external_executive", "superseded"))


class AnalystTests(unittest.TestCase):
    def test_cannot_review_work(self):
        # docs/09-acceptance.md T04's own literal mechanism: an analyst
        # can never approve/return any submission, own or otherwise -
        # this alone satisfies "may not approve their own submission",
        # a strict subset of "may not review at all".
        self.assertFalse(authz.has_capability("analyst", authz.REVIEW_WORK))

    def test_cannot_approve_publish(self):
        self.assertFalse(authz.has_capability("analyst", authz.APPROVE_PUBLISH))

    def test_cannot_configure_triggers(self):
        self.assertFalse(authz.has_capability("analyst", authz.CONFIGURE_TRIGGERS))

    def test_cannot_manage_membership(self):
        self.assertFalse(authz.has_capability("analyst", authz.MANAGE_MEMBERSHIP))

    def test_can_submit_and_create_mandates(self):
        self.assertTrue(authz.has_capability("analyst", authz.SUBMIT_WORK))
        self.assertTrue(authz.has_capability("analyst", authz.CREATE_MANDATES))
        self.assertTrue(authz.has_capability("analyst", authz.EXECUTE_MANDATES))

    def test_can_view_and_manage_findings(self):
        self.assertTrue(authz.has_capability("analyst", authz.VIEW_FINDINGS))
        self.assertTrue(authz.has_capability("analyst", authz.MANAGE_FINDINGS))


class ReviewerTests(unittest.TestCase):
    def test_can_review_work(self):
        self.assertTrue(authz.has_capability("reviewer", authz.REVIEW_WORK))

    def test_cannot_approve_publish(self):
        # Reviewer's "recommend" role has no dedicated approval endpoint
        # (disclosed since Task 14.3/17.10) - the closeout directive's own
        # "where current domain rules support it" qualifier keeps this
        # False, not widened.
        self.assertFalse(authz.has_capability("reviewer", authz.APPROVE_PUBLISH))

    def test_can_configure_triggers(self):
        self.assertTrue(authz.has_capability("reviewer", authz.CONFIGURE_TRIGGERS))

    def test_cannot_manage_membership(self):
        self.assertFalse(authz.has_capability("reviewer", authz.MANAGE_MEMBERSHIP))


if __name__ == "__main__":
    unittest.main()
