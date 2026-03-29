from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc import hooks as app_hooks
from pikt_inc import migrate
from pikt_inc.permissions import customer_desk as customer_desk_permissions
from pikt_inc.services import customer_desk


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

    def is_new(self):
        return bool(self.get("_is_new"))


class FakeSaveDoc(FakeDoc):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_called = False

    def save(self, ignore_permissions=False):
        self.save_called = True
        self.ignore_permissions = ignore_permissions
        return self


class TestCustomerDesk(unittest.TestCase):
    def test_hooks_register_customer_desk_permissions_and_building_events(self):
        self.assertEqual(
            app_hooks.permission_query_conditions["Building"],
            "pikt_inc.permissions.customer_desk.get_building_permission_query_conditions",
        )
        self.assertEqual(
            app_hooks.permission_query_conditions["Service Agreement"],
            "pikt_inc.permissions.customer_desk.get_service_agreement_permission_query_conditions",
        )
        self.assertEqual(
            app_hooks.permission_query_conditions["Service Agreement Addendum"],
            "pikt_inc.permissions.customer_desk.get_service_agreement_addendum_permission_query_conditions",
        )
        self.assertEqual(
            app_hooks.has_permission["Building"],
            "pikt_inc.permissions.customer_desk.has_building_permission",
        )
        self.assertEqual(
            app_hooks.doc_events["Building"]["before_insert"],
            "pikt_inc.events.building.before_insert",
        )
        self.assertEqual(
            app_hooks.doc_events["Building"]["before_save"],
            "pikt_inc.events.building.before_save",
        )

    @patch.object(customer_desk.frappe.db, "exists", return_value=True)
    def test_apply_customer_desk_module_profile_adds_desk_role_and_workspace_defaults(self, _mock_exists):
        doc = FakeDoc(
            {
                "roles": [
                    SimpleNamespace(role="Customer Desk User"),
                    SimpleNamespace(role="Customer Portal User"),
                    SimpleNamespace(role="Customer"),
                ],
                "user_type": "Website User",
                "module_profile": None,
                "default_workspace": None,
                "default_app": None,
            }
        )

        result = customer_desk.apply_customer_desk_module_profile(doc)

        self.assertEqual(result, {"status": "customer_desk_profile_applied", "workspace_applied": 1})
        self.assertEqual(
            [row.role for row in doc.roles],
            ["Customer Desk User", "Customer Portal User", "Customer", "Desk User"],
        )
        self.assertEqual(doc.user_type, "System User")
        self.assertEqual(doc.module_profile, "Customer Desk")
        self.assertEqual(doc.default_workspace, "Customer Workspace")
        self.assertEqual(doc.default_app, "erpnext")

    @patch.object(customer_desk.frappe.db, "exists", return_value=True)
    def test_apply_customer_desk_module_profile_clears_defaults_for_internal_role_mix(self, _mock_exists):
        doc = FakeDoc(
            {
                "roles": [
                    SimpleNamespace(role="Customer Desk User"),
                    SimpleNamespace(role="Sales User"),
                ],
                "user_type": "System User",
                "module_profile": "Customer Desk",
                "default_workspace": "Customer Workspace",
                "default_app": "erpnext",
            }
        )

        result = customer_desk.apply_customer_desk_module_profile(doc)

        self.assertEqual(result, {"status": "customer_desk_profile_cleared"})
        self.assertEqual(doc.user_type, "System User")
        self.assertIsNone(doc.module_profile)
        self.assertIsNone(doc.default_workspace)
        self.assertIsNone(doc.default_app)

    @patch.object(customer_desk.frappe.db, "exists", return_value=True)
    def test_apply_customer_desk_module_profile_reverts_portal_only_user_to_website_user(self, _mock_exists):
        doc = FakeDoc(
            {
                "roles": [
                    SimpleNamespace(role="Customer Portal User"),
                    SimpleNamespace(role="Customer"),
                    SimpleNamespace(role="Desk User"),
                ],
                "user_type": "System User",
                "module_profile": "Customer Desk",
                "default_workspace": "Customer Workspace",
                "default_app": "erpnext",
            }
        )

        result = customer_desk.apply_customer_desk_module_profile(doc)

        self.assertEqual(result, {"status": "customer_desk_profile_cleared"})
        self.assertEqual(doc.user_type, "Website User")
        self.assertIsNone(doc.module_profile)
        self.assertIsNone(doc.default_workspace)
        self.assertIsNone(doc.default_app)

    @patch.object(
        customer_desk.frappe,
        "get_roles",
        return_value=["All", "Customer", "Customer Desk User", "Customer Portal User", "Desk User", "Guest"],
    )
    def test_is_customer_desk_user_allows_expected_resolved_roles(self, _mock_roles):
        self.assertTrue(customer_desk.is_customer_desk_user("portal@example.com"))

    @patch.object(customer_desk, "_get_portal_contact_links")
    def test_resolve_customer_name_requires_exactly_one_customer(self, mock_links):
        mock_links.return_value = [{"customer_name": "CUST-1"}]
        self.assertEqual(customer_desk.resolve_customer_name("portal@example.com"), "CUST-1")

        mock_links.return_value = [{"customer_name": "CUST-1"}, {"customer_name": "CUST-2"}]
        self.assertEqual(customer_desk.resolve_customer_name("portal@example.com"), "")

    @patch.object(customer_desk_permissions.customer_desk, "is_customer_desk_user", return_value=True)
    @patch.object(customer_desk_permissions.customer_desk, "resolve_customer_name", return_value="CUST-1")
    def test_permission_query_conditions_scope_to_customer(self, _mock_customer, _mock_user):
        condition = customer_desk_permissions.get_building_permission_query_conditions("portal@example.com")

        self.assertEqual(condition, "`tabBuilding`.`customer` = 'CUST-1'")

    @patch.object(customer_desk_permissions.customer_desk, "is_customer_desk_user", return_value=True)
    @patch.object(customer_desk_permissions.customer_desk, "resolve_customer_name", return_value="")
    def test_permission_query_conditions_fail_closed_for_unlinked_customer(self, _mock_customer, _mock_user):
        condition = customer_desk_permissions.get_service_agreement_permission_query_conditions("portal@example.com")

        self.assertEqual(condition, "1=0")

    @patch.object(customer_desk_permissions.customer_desk, "is_customer_desk_user", return_value=True)
    @patch.object(customer_desk_permissions.customer_desk, "resolve_customer_name", return_value="CUST-1")
    def test_building_permission_allows_matching_customer_and_create(self, _mock_customer, _mock_user):
        self.assertTrue(
            customer_desk_permissions.has_building_permission(
                {"name": "BUILD-1", "customer": "CUST-1"},
                user="portal@example.com",
                permission_type="read",
            )
        )
        self.assertTrue(
            customer_desk_permissions.has_building_permission(
                {"name": "BUILD-1", "customer": "CUST-1"},
                user="portal@example.com",
                permission_type="create",
            )
        )
        self.assertFalse(
            customer_desk_permissions.has_building_permission(
                {"name": "BUILD-2", "customer": "CUST-2"},
                user="portal@example.com",
                permission_type="read",
            )
        )

    @patch.object(customer_desk_permissions.customer_desk, "is_customer_desk_user", return_value=True)
    @patch.object(customer_desk_permissions.customer_desk, "resolve_customer_name", return_value="CUST-1")
    def test_agreement_permission_denies_write_for_customer_desk_user(self, _mock_customer, _mock_user):
        self.assertFalse(
            customer_desk_permissions.has_service_agreement_permission(
                {"name": "SAG-1", "customer": "CUST-1"},
                user="portal@example.com",
                permission_type="write",
            )
        )
        self.assertTrue(
            customer_desk_permissions.has_service_agreement_permission(
                {"name": "SAG-1", "customer": "CUST-1"},
                user="portal@example.com",
                permission_type="read",
            )
        )

    @patch.object(customer_desk, "now_datetime", return_value="2026-03-28 14:00:00")
    def test_normalize_access_details_confirmation_stamps_when_first_confirmed(self, _mock_now):
        confirmed, completed_on = customer_desk.normalize_access_details_confirmation(1, existing_completed_on=None)

        self.assertEqual(confirmed, 1)
        self.assertEqual(completed_on, "2026-03-28 14:00:00")

    @patch.object(customer_desk, "make_unique_name", return_value="HQ #2")
    @patch.object(customer_desk, "_get_portal_contact_links", return_value=[{"customer_name": "CUST-1"}])
    @patch.object(customer_desk.frappe.db, "exists", side_effect=lambda doctype, name=None: name == "HQ")
    @patch.object(
        customer_desk.frappe,
        "get_roles",
        return_value=["Customer Desk User", "Customer Portal User", "Desk User"],
    )
    def test_apply_customer_desk_building_defaults_assigns_customer_and_unique_name(
        self,
        _mock_roles,
        _mock_exists,
        _mock_links,
        _mock_unique_name,
    ):
        customer_desk.frappe.session.user = "portal@example.com"
        doc = FakeDoc({"_is_new": True, "building_name": "HQ", "customer": "", "active": ""})

        result = customer_desk.apply_customer_desk_building_defaults(doc)

        self.assertEqual(result["status"], "updated")
        self.assertEqual(doc.customer, "CUST-1")
        self.assertEqual(doc.active, 1)
        self.assertEqual(doc.building_name, "HQ #2")

    @patch.object(migrate.frappe.db, "exists", return_value=True)
    @patch.object(migrate.frappe, "get_doc")
    def test_ensure_customer_desk_role_updates_existing_role(self, mock_get_doc, _mock_exists):
        role_doc = FakeSaveDoc({"desk_access": 0, "home_page": ""})
        mock_get_doc.return_value = role_doc

        migrate.ensure_customer_desk_role()

        self.assertTrue(role_doc.save_called)
        self.assertEqual(role_doc.desk_access, 1)
        self.assertEqual(role_doc.home_page, "app/customer-workspace")

    @patch.object(migrate, "ensure_customer_desk_custom_docperms")
    @patch.object(migrate, "ensure_customer_desk_title_fields")
    @patch.object(migrate, "ensure_customer_desk_workspace")
    @patch.object(migrate, "ensure_customer_desk_module_profile")
    @patch.object(migrate, "ensure_customer_desk_role")
    def test_ensure_customer_desk_records_calls_each_setup_step(
        self,
        mock_role,
        mock_profile,
        mock_workspace,
        mock_titles,
        mock_docperms,
    ):
        migrate.ensure_customer_desk_records()

        mock_role.assert_called_once_with()
        mock_profile.assert_called_once_with()
        mock_workspace.assert_called_once_with()
        mock_titles.assert_called_once_with()
        mock_docperms.assert_called_once_with()

    @patch.object(migrate, "_ensure_custom_docperms")
    @patch.object(migrate, "ensure_customer_desk_role")
    def test_ensure_building_custom_docperms_ensures_role_first(self, mock_role, mock_docperms):
        migrate.ensure_building_custom_docperms()

        mock_role.assert_called_once_with()
        mock_docperms.assert_called_once()


if __name__ == "__main__":
    unittest.main()
