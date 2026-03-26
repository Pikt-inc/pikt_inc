from __future__ import annotations

import sys
from types import SimpleNamespace
import types
import unittest
from unittest.mock import MagicMock, patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

if "frappe" not in sys.modules:
    fake_frappe = types.SimpleNamespace(
        utils=types.SimpleNamespace(now=lambda: "2026-03-24 12:00:00"),
        db=types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            set_value=lambda *args, **kwargs: None,
            sql=lambda *args, **kwargs: [],
            commit=lambda: None,
        ),
        get_doc=lambda *args, **kwargs: None,
        throw=lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message)),
        whitelist=lambda **kwargs: (lambda fn: fn),
    )
    sys.modules["frappe"] = fake_frappe

if not hasattr(sys.modules["frappe"].db, "commit"):
    sys.modules["frappe"].db.commit = lambda: None

from pikt_inc import hooks as app_hooks
from pikt_inc.patches.post_model_sync import ensure_ssr_unique_index
from pikt_inc.services import walkthrough_review


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def append(self, fieldname, value):
        self.setdefault(fieldname, []).append(SimpleNamespace(**value))


class FakeSaveDoc(FakeDoc):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_called = False

    def save(self, ignore_permissions=False):
        self.save_called = True
        self.ignore_permissions = ignore_permissions
        return self


class TestWalkthroughReview(unittest.TestCase):
    def test_hook_wiring_adds_walkthrough_review_events(self):
        self.assertEqual(
            app_hooks.doc_events["Digital Walkthrough Submission"]["before_save"],
            "pikt_inc.events.digital_walkthrough_submission.before_save",
        )
        self.assertEqual(
            app_hooks.doc_events["Digital Walkthrough Submission"]["after_insert"],
            "pikt_inc.events.digital_walkthrough_submission.after_insert",
        )
        self.assertEqual(
            app_hooks.doc_events["Digital Walkthrough Submission"]["on_update"],
            "pikt_inc.events.digital_walkthrough_submission.on_update",
        )
        self.assertEqual(
            app_hooks.doc_events["User"]["before_save"],
            "pikt_inc.events.user.before_save",
        )

    def test_sync_submission_requires_opportunity_before_review(self):
        with self.assertRaisesRegex(Exception, "Link this walkthrough to an opportunity"):
            walkthrough_review.validate_submission_review_link(
                FakeDoc({"name": "DWS-0001", "status": "Reviewed", "opportunity": ""})
            )

    @patch.object(walkthrough_review.frappe.utils, "now", return_value="2026-03-24 12:00:00")
    @patch.object(walkthrough_review.frappe, "get_doc")
    def test_sync_submission_updates_linked_opportunity(self, mock_get_doc, _mock_now):
        opportunity = FakeSaveDoc(
            {
                "name": "CRM-OPP-0001",
                "digital_walkthrough_file": "",
                "latest_digital_walkthrough": "",
                "digital_walkthrough_received_on": "",
                "digital_walkthrough_status": "Not Requested",
            }
        )
        mock_get_doc.return_value = opportunity

        result = walkthrough_review.sync_submission_to_opportunity(
            FakeDoc(
                {
                    "name": "DWS-0001",
                    "opportunity": "CRM-OPP-0001",
                    "walkthrough_file": "/private/files/walkthrough.pdf",
                    "status": "New",
                }
            )
        )

        self.assertEqual(result["status"], "updated")
        self.assertEqual(opportunity.digital_walkthrough_file, "/private/files/walkthrough.pdf")
        self.assertEqual(opportunity.latest_digital_walkthrough, "DWS-0001")
        self.assertEqual(opportunity.digital_walkthrough_received_on, "2026-03-24 12:00:00")
        self.assertEqual(opportunity.digital_walkthrough_status, "Submitted")
        self.assertTrue(opportunity.save_called)

    @patch.object(walkthrough_review.frappe.db, "exists", return_value=False)
    def test_apply_reviewer_module_profile_adds_desk_role_and_sets_profile(self, _mock_exists):
        doc = FakeDoc(
            {
                "roles": [SimpleNamespace(role="Digital Walkthrough Reviewer")],
                "module_profile": None,
                "default_workspace": None,
                "default_app": None,
            }
        )

        result = walkthrough_review.apply_reviewer_module_profile(doc)

        self.assertEqual(result, {"status": "reviewer_profile_applied", "workspace_applied": 0})
        self.assertEqual([row.role for row in doc.roles], ["Digital Walkthrough Reviewer", "Desk User"])
        self.assertEqual(doc.module_profile, "Digital Walkthrough Reviewer Desk")
        self.assertIsNone(doc.default_workspace)
        self.assertEqual(doc.default_app, "erpnext")

    @patch.object(walkthrough_review.frappe.db, "exists", return_value=True)
    def test_apply_reviewer_module_profile_clears_reviewer_defaults_when_user_has_other_roles(self, _mock_exists):
        doc = FakeDoc(
            {
                "roles": [
                    SimpleNamespace(role="Digital Walkthrough Reviewer"),
                    SimpleNamespace(role="System Manager"),
                ],
                "module_profile": "Digital Walkthrough Reviewer Desk",
                "default_workspace": "Digital Walkthrough Review",
                "default_app": "erpnext",
            }
        )

        result = walkthrough_review.apply_reviewer_module_profile(doc)

        self.assertEqual(result, {"status": "reviewer_profile_cleared"})
        self.assertIsNone(doc.module_profile)
        self.assertIsNone(doc.default_workspace)
        self.assertIsNone(doc.default_app)

    @patch.object(ensure_ssr_unique_index.frappe.db, "commit")
    @patch.object(ensure_ssr_unique_index.frappe.db, "sql")
    @patch.object(ensure_ssr_unique_index.planning, "dispatch_data_integrity_migration")
    def test_ensure_ssr_unique_index_normalizes_blank_rules_and_adds_index(
        self,
        mock_migration,
        mock_sql,
        mock_commit,
    ):
        mock_sql.side_effect = [
            None,
            [],
            [{"cnt": 0}],
            None,
        ]

        ensure_ssr_unique_index.execute()

        mock_migration.assert_called_once_with()
        self.assertIn("SET recurring_service_rule = NULL", mock_sql.call_args_list[0].args[0])
        self.assertIn("GROUP BY recurring_service_rule, service_date, slot_index", mock_sql.call_args_list[1].args[0])
        self.assertIn("information_schema.statistics", mock_sql.call_args_list[2].args[0])
        self.assertIn("ADD UNIQUE INDEX `uniq_ssr_rule_date_slot`", mock_sql.call_args_list[3].args[0])
        mock_commit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
