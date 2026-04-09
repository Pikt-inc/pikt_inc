from __future__ import annotations

import sys
import types
import unittest
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

if "frappe" not in sys.modules:
    fake_frappe = types.SimpleNamespace(
        db=types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda *args, **kwargs: None,
            set_value=lambda *args, **kwargs: None,
        ),
        get_all=lambda *args, **kwargs: [],
        delete_doc=lambda *args, **kwargs: None,
        session=types.SimpleNamespace(user="Guest"),
        local=types.SimpleNamespace(response={}, request=types.SimpleNamespace(get_json=lambda silent=True: None)),
        request=types.SimpleNamespace(data=None),
        form_dict={},
        throw=lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message)),
        whitelist=lambda **_kwargs: (lambda fn: fn),
    )
    sys.modules["frappe"] = fake_frappe

try:
    admin_api = import_module("pikt_inc.api.admin_portal")
    admin_service = import_module("pikt_inc.services.admin_portal")
except ModuleNotFoundError:
    admin_api = import_module("pikt_inc.pikt_inc.api.admin_portal")
    admin_service = import_module("pikt_inc.pikt_inc.services.admin_portal")


def fake_get_all_factory(dataset):
    def fake_get_all(doctype, filters=None, fields=None, order_by=None, limit=None, **_kwargs):
        rows = [dict(row) for row in dataset.get(f"{doctype}_list", [])]
        filters_value = filters or {}

        def matches_operator(actual, operator, expected):
            if operator in {"=", "=="}:
                return actual == expected
            if operator == "!=":
                return actual != expected
            if operator == "in":
                return actual in {item for item in expected or []}
            raise AssertionError(f"Unsupported filter operator in test harness: {operator}")

        def matches(row):
            if isinstance(filters_value, list):
                for clause in filters_value:
                    if len(clause) != 3:
                        raise AssertionError(f"Unsupported filter clause in test harness: {clause}")
                    field, operator, expected = clause
                    if not matches_operator(row.get(field), str(operator), expected):
                        return False
                return True

            for key, value in filters_value.items():
                if isinstance(value, list) and value:
                    operator = str(value[0])
                    expected = value[1] if len(value) > 1 else None
                    if not matches_operator(row.get(key), operator, expected):
                        return False
                    continue
                if row.get(key) != value:
                    return False
            return True

        filtered = [row for row in rows if matches(row)]
        if limit is not None:
            filtered = filtered[: int(limit)]
        if fields:
            return [{field: row.get(field) for field in fields} for row in filtered]
        return filtered

    return fake_get_all


class TestAdminPortalBuildingDeletion(unittest.TestCase):
    def setUp(self):
        self.deleted_docs = []
        self.set_value_calls = []
        self.dataset = {
            "Building": {
                "BUILD-1": {
                    "name": "BUILD-1",
                    "current_checklist_template": "CHK-TPL-PRIMARY",
                }
            },
            "Opportunity_list": [
                {"name": "OPP-1", "custom_building": "BUILD-1"},
            ],
            "Quotation_list": [
                {"name": "QTN-1", "custom_building": "BUILD-1"},
            ],
            "Sales Order_list": [
                {"name": "SO-1", "custom_building": "BUILD-1"},
            ],
            "Sales Invoice_list": [
                {"name": "SI-1", "custom_building": "BUILD-1"},
            ],
            "Service Agreement Addendum_list": [
                {"name": "SAA-1", "building": "BUILD-1"},
            ],
            "Checklist Session_list": [
                {"name": "CS-1", "building": "BUILD-1"},
                {"name": "CS-2", "building": "BUILD-1"},
                {"name": "CS-OTHER", "building": "OTHER"},
            ],
            "Checklist Template_list": [
                {"name": "CHK-TPL-PRIMARY", "building": "BUILD-1"},
                {"name": "CHK-TPL-LEGACY", "building": "BUILD-1"},
            ],
            "Building SOP_list": [
                {"name": "BSOP-1", "building": "BUILD-1"},
            ],
            "Site Shift Requirement_list": [
                {
                    "name": "SSR-1",
                    "building": "BUILD-1",
                    "custom_building_sop": "BSOP-1",
                    "call_out_record": "CO-1",
                },
                {
                    "name": "SSR-2",
                    "building": "BUILD-1",
                    "custom_building_sop": "",
                    "call_out_record": "CO-2",
                },
            ],
            "Dispatch Recommendation_list": [
                {"name": "REC-1", "site_shift_requirement": "SSR-1"},
                {"name": "REC-2", "site_shift_requirement": "SSR-2"},
            ],
            "Call Out_list": [
                {"name": "CO-1", "building": "BUILD-1"},
                {"name": "CO-2", "building": "BUILD-1"},
            ],
            "Recurring Service Rule_list": [
                {"name": "RSR-1", "building": "BUILD-1"},
            ],
            "Storage Location_list": [
                {"name": "SL-1", "building": "BUILD-1"},
                {"name": "SL-2", "building": "BUILD-1"},
            ],
            "File_list": [
                {"name": "FILE-1", "attached_to_doctype": "Checklist Session", "attached_to_name": "CS-1"},
                {"name": "FILE-2", "attached_to_doctype": "Checklist Session", "attached_to_name": "CS-2"},
                {"name": "FILE-OTHER", "attached_to_doctype": "Checklist Session", "attached_to_name": "CS-OTHER"},
            ],
        }

        known_names = {}
        for key, value in self.dataset.items():
            if key.endswith("_list"):
                doctype = key[: -len("_list")]
                known_names.setdefault(doctype, set()).update(row.get("name") for row in value if row.get("name"))
            elif isinstance(value, dict):
                known_names.setdefault(key, set()).update(value.keys())
        self.known_names = known_names

        admin_service.frappe.get_all = fake_get_all_factory(self.dataset)
        admin_service.frappe.db.exists = lambda doctype, name: clean_name(name) in self.known_names.get(doctype, set())
        admin_service.frappe.db.get_value = self._fake_get_value
        admin_service.frappe.db.set_value = self._record_set_value
        admin_service.frappe.delete_doc = self._record_delete_doc

    def _fake_get_value(self, doctype, name, fieldname, as_dict=False):
        if doctype == "Building" and fieldname == "current_checklist_template":
            return self.dataset["Building"].get(name, {}).get("current_checklist_template")
        return None

    def _record_set_value(self, doctype, name, fieldname, value, update_modified=False):
        self.set_value_calls.append((doctype, name, fieldname, value, update_modified))

    def _record_delete_doc(self, doctype, name, **kwargs):
        self.deleted_docs.append((doctype, name, kwargs))

    def test_delete_building_requires_admin_access(self):
        with patch.object(
            admin_service,
            "require_portal_section",
            side_effect=admin_api.CustomerPortalAccessError("This account does not have portal access to that section."),
        ):
            with self.assertRaisesRegex(Exception, "portal access to that section"):
                admin_service.delete_admin_building("BUILD-1")

    def test_delete_building_raises_not_found_for_missing_building(self):
        with patch.object(admin_service, "require_portal_section", return_value=SimpleNamespace()):
            with self.assertRaisesRegex(admin_service.CustomerPortalNotFoundError, "could not be found"):
                admin_service.delete_admin_building("BUILD-MISSING")

    def test_delete_building_unlinks_reference_docs_and_purges_owned_records(self):
        with patch.object(admin_service, "require_portal_section", return_value=SimpleNamespace()):
            result = admin_service.delete_admin_building("BUILD-1")

        self.assertEqual(result.building_id, "BUILD-1")
        self.assertEqual(result.redirect_to, "/portal/admin")

        deleted_pairs = [(doctype, name) for doctype, name, _kwargs in self.deleted_docs]
        self.assertEqual(
            deleted_pairs,
            [
                ("File", "FILE-1"),
                ("File", "FILE-2"),
                ("Checklist Session", "CS-1"),
                ("Checklist Session", "CS-2"),
                ("Checklist Template", "CHK-TPL-PRIMARY"),
                ("Checklist Template", "CHK-TPL-LEGACY"),
                ("Building SOP", "BSOP-1"),
                ("Dispatch Recommendation", "REC-1"),
                ("Dispatch Recommendation", "REC-2"),
                ("Call Out", "CO-1"),
                ("Call Out", "CO-2"),
                ("Site Shift Requirement", "SSR-1"),
                ("Site Shift Requirement", "SSR-2"),
                ("Recurring Service Rule", "RSR-1"),
                ("Storage Location", "SL-1"),
                ("Storage Location", "SL-2"),
                ("Building", "BUILD-1"),
            ],
        )
        self.assertFalse(any(doctype in {"Opportunity", "Quotation", "Sales Order", "Sales Invoice"} for doctype, _name in deleted_pairs))
        self.assertNotIn(("File", "FILE-OTHER"), deleted_pairs)

        for _doctype, _name, kwargs in self.deleted_docs:
            self.assertEqual(kwargs, {"ignore_permissions": True, "force": True})

        self.assertIn(("Building", "BUILD-1", "current_checklist_template", "", False), self.set_value_calls)
        self.assertIn(("Opportunity", "OPP-1", "custom_building", "", False), self.set_value_calls)
        self.assertIn(("Quotation", "QTN-1", "custom_building", "", False), self.set_value_calls)
        self.assertIn(("Sales Order", "SO-1", "custom_building", "", False), self.set_value_calls)
        self.assertIn(("Sales Invoice", "SI-1", "custom_building", "", False), self.set_value_calls)
        self.assertIn(("Service Agreement Addendum", "SAA-1", "building", "", False), self.set_value_calls)
        self.assertIn(("Site Shift Requirement", "SSR-1", "custom_building_sop", "", False), self.set_value_calls)
        self.assertIn(("Site Shift Requirement", "SSR-1", "call_out_record", "", False), self.set_value_calls)
        self.assertIn(("Site Shift Requirement", "SSR-2", "custom_building_sop", "", False), self.set_value_calls)
        self.assertIn(("Site Shift Requirement", "SSR-2", "call_out_record", "", False), self.set_value_calls)

    def test_api_wrapper_validates_and_returns_delete_payload(self):
        expected = admin_service.AdminBuildingDeleteResult(building_id="BUILD-1")
        with patch.object(admin_api.admin_portal_service, "delete_admin_building", return_value=expected) as delete_admin_building:
            result = admin_api.delete_admin_building(building="BUILD-1")

        self.assertEqual(result, {"building_id": "BUILD-1", "redirect_to": "/portal/admin"})
        self.assertEqual(delete_admin_building.call_args.args, ("BUILD-1",))

        with self.assertRaisesRegex(Exception, "Building is required"):
            admin_api.delete_admin_building()


def clean_name(value):
    return str(value or "").strip()


class TestAdminPortalCommercialOptions(unittest.TestCase):
    def test_get_admin_building_commercial_options_returns_service_item_and_lookup_lists(self):
        def fake_get_all(doctype, **_kwargs):
            if doctype == "Customer":
                return [
                    {"name": "CUST-1", "customer_name": "Acme HQ"},
                    {"name": "CUST-2", "customer_name": ""},
                ]
            if doctype == "Company":
                return [
                    {"name": "PK Holdings", "company_name": "PK Holdings LLC"},
                ]
            raise AssertionError(f"Unexpected doctype lookup: {doctype}")

        admin_service.frappe.get_all = fake_get_all

        with patch.object(admin_service, "require_portal_section", return_value=SimpleNamespace()):
            with patch.object(admin_service, "_configured_service_item_code", return_value="General Cleaning"):
                result = admin_service.get_admin_building_commercial_options()

        self.assertEqual(result.service_item_code, "General Cleaning")
        self.assertEqual(
            [option.model_dump(mode="python") for option in result.customers],
            [
                {"id": "CUST-1", "label": "Acme HQ"},
                {"id": "CUST-2", "label": "CUST-2"},
            ],
        )
        self.assertEqual(
            [option.model_dump(mode="python") for option in result.companies],
            [{"id": "PK Holdings", "label": "PK Holdings LLC"}],
        )


class TestAdminPortalBuildingCommercialSetup(unittest.TestCase):
    def setUp(self):
        self.set_value_calls = []
        admin_service.frappe.db.set_value = self._record_set_value

    def _record_set_value(self, doctype, name, fieldname, value=None, update_modified=False):
        self.set_value_calls.append((doctype, name, fieldname, value, update_modified))

    def test_update_admin_building_recurring_creates_project_costs_and_recurring_docs(self):
        request = admin_api.AdminBuildingUpdateRequestApi.model_validate(
            {
                "building": "BUILD-1",
                "name": "Pilot Building 1",
                "customer": "CUST-1",
                "company": "PK Holdings",
                "billing_model": "recurring",
                "contract_amount": 2500,
                "billing_interval": "month",
                "billing_interval_count": 1,
                "contract_start_date": "2026-04-01",
                "contract_end_date": "2027-03-31",
                "auto_renew": True,
            }
        )

        initial_row = {
            "name": "BUILD-1",
            "building_name": "Pilot Building 1",
            "customer": "",
            "company": "",
            "billing_model": "",
            "project": "",
            "cost_center": "",
            "subscription_plan": "",
            "subscription": "",
            "sales_order": "",
            "contract": "",
        }
        current_row = dict(initial_row)
        final_row = {
            **current_row,
            "customer": "CUST-1",
            "company": "PK Holdings",
            "billing_model": "recurring",
            "contract_amount": 2500,
            "billing_interval": "month",
            "billing_interval_count": 1,
            "contract_start_date": "2026-04-01",
            "contract_end_date": "2027-03-31",
            "auto_renew": 1,
            "project": "PROJ-BUILD-1",
            "cost_center": "CC-BUILD-1",
            "subscription_plan": "PLAN-BUILD-1",
            "subscription": "SUB-BUILD-1",
            "sales_order": "",
            "contract": "CON-BUILD-1",
        }

        with patch.object(admin_service, "require_portal_section", return_value=SimpleNamespace()):
            with patch.object(admin_service, "_building_row", side_effect=[initial_row, current_row, final_row]):
                with patch.object(admin_service, "_rename_building", return_value="BUILD-1"):
                    with patch.object(admin_service, "_ensure_customer", return_value="CUST-1") as ensure_customer:
                        with patch.object(
                            admin_service,
                            "_ensure_company",
                            return_value={
                                "name": "PK Holdings",
                                "default_currency": "USD",
                                "cost_center": "Main - PK",
                            },
                        ) as ensure_company:
                            with patch.object(
                                admin_service,
                                "_ensure_service_item",
                                return_value="General Cleaning",
                            ) as ensure_service_item:
                                with patch.object(admin_service, "_upsert_cost_center", return_value="CC-BUILD-1") as upsert_cost_center:
                                    with patch.object(admin_service, "_upsert_project", return_value="PROJ-BUILD-1") as upsert_project:
                                        with patch.object(admin_service, "_upsert_subscription_plan", return_value="PLAN-BUILD-1") as upsert_plan:
                                            with patch.object(admin_service, "_upsert_subscription", return_value="SUB-BUILD-1") as upsert_subscription:
                                                with patch.object(admin_service, "_upsert_contract", return_value="CON-BUILD-1") as upsert_contract:
                                                    result = admin_service.update_admin_building(request)

        self.assertEqual(result.building_id, "BUILD-1")
        self.assertEqual(result.project, "PROJ-BUILD-1")
        self.assertEqual(result.cost_center, "CC-BUILD-1")
        self.assertEqual(result.subscription_plan, "PLAN-BUILD-1")
        self.assertEqual(result.subscription, "SUB-BUILD-1")
        self.assertEqual(result.contract, "CON-BUILD-1")
        self.assertIsNone(result.sales_order)

        self.assertEqual(ensure_customer.call_args.args, ("CUST-1",))
        self.assertEqual(ensure_company.call_args.args, ("PK Holdings",))
        self.assertEqual(ensure_service_item.call_args.args, ("General Cleaning",))
        self.assertEqual(upsert_cost_center.call_count, 1)
        self.assertEqual(upsert_project.call_count, 1)
        self.assertEqual(upsert_plan.call_count, 1)
        self.assertEqual(upsert_subscription.call_count, 1)
        self.assertEqual(upsert_contract.call_count, 1)

        self.assertEqual(self.set_value_calls[0][0:2], ("Building", "BUILD-1"))
        self.assertEqual(
            self.set_value_calls[0][2],
            {
                "building_name": "Pilot Building 1",
                "customer": "CUST-1",
                "company": "PK Holdings",
                "address_line_1": None,
                "address_line_2": None,
                "city": None,
                "state": None,
                "postal_code": None,
                "site_notes": None,
                "unavailable_service_days": None,
                "service_frequency": None,
                "preferred_service_start_time": None,
                "preferred_service_end_time": None,
                "billing_model": "recurring",
                "contract_amount": 2500.0,
                "billing_interval": "month",
                "billing_interval_count": 1,
                "contract_start_date": "2026-04-01",
                "contract_end_date": "2027-03-31",
                "auto_renew": 1,
            },
        )
        self.assertEqual(self.set_value_calls[1][0:2], ("Building", "BUILD-1"))
        self.assertEqual(
            self.set_value_calls[1][2],
            {
                "project": "PROJ-BUILD-1",
                "cost_center": "CC-BUILD-1",
                "subscription_plan": "PLAN-BUILD-1",
                "subscription": "SUB-BUILD-1",
                "contract": "CON-BUILD-1",
                "sales_order": "",
            },
        )

    def test_update_admin_building_one_time_creates_sales_order_and_clears_recurring_links(self):
        request = admin_api.AdminBuildingUpdateRequestApi.model_validate(
            {
                "building": "BUILD-1",
                "name": "Pilot Building 1",
                "customer": "CUST-1",
                "company": "PK Holdings",
                "billing_model": "one_time",
                "contract_amount": 900,
                "contract_start_date": "2026-04-01",
            }
        )

        initial_row = {
            "name": "BUILD-1",
            "building_name": "Pilot Building 1",
            "customer": "CUST-1",
            "company": "PK Holdings",
            "billing_model": "recurring",
            "project": "PROJ-BUILD-1",
            "cost_center": "CC-BUILD-1",
            "subscription_plan": "PLAN-OLD",
            "subscription": "SUB-OLD",
            "sales_order": "",
            "contract": "CON-OLD",
        }
        current_row = dict(initial_row)
        final_row = {
            **current_row,
            "billing_model": "one_time",
            "contract_amount": 900,
            "billing_interval": "",
            "billing_interval_count": None,
            "contract_start_date": "2026-04-01",
            "contract_end_date": "",
            "auto_renew": 0,
            "project": "PROJ-BUILD-1",
            "cost_center": "CC-BUILD-1",
            "sales_order": "SO-BUILD-1",
            "subscription_plan": "",
            "subscription": "",
            "contract": "",
        }

        with patch.object(admin_service, "require_portal_section", return_value=SimpleNamespace()):
            with patch.object(admin_service, "_building_row", side_effect=[initial_row, current_row, final_row]):
                with patch.object(admin_service, "_rename_building", return_value="BUILD-1"):
                    with patch.object(admin_service, "_ensure_customer", return_value="CUST-1"):
                        with patch.object(
                            admin_service,
                            "_ensure_company",
                            return_value={
                                "name": "PK Holdings",
                                "default_currency": "USD",
                                "cost_center": "Main - PK",
                            },
                        ):
                            with patch.object(
                                admin_service,
                                "_ensure_service_item",
                                return_value="General Cleaning",
                            ):
                                with patch.object(admin_service, "_upsert_cost_center", return_value="CC-BUILD-1"):
                                    with patch.object(admin_service, "_upsert_project", return_value="PROJ-BUILD-1"):
                                        with patch.object(admin_service, "_upsert_sales_order", return_value="SO-BUILD-1") as upsert_sales_order:
                                            result = admin_service.update_admin_building(request)

        self.assertEqual(result.building_id, "BUILD-1")
        self.assertEqual(result.project, "PROJ-BUILD-1")
        self.assertEqual(result.cost_center, "CC-BUILD-1")
        self.assertEqual(result.sales_order, "SO-BUILD-1")
        self.assertIsNone(result.subscription_plan)
        self.assertIsNone(result.subscription)
        self.assertIsNone(result.contract)
        self.assertEqual(upsert_sales_order.call_count, 1)

        self.assertEqual(self.set_value_calls[0][0:2], ("Building", "BUILD-1"))
        self.assertEqual(self.set_value_calls[0][2]["billing_model"], "one_time")
        self.assertEqual(self.set_value_calls[0][2]["billing_interval_count"], "")

        self.assertEqual(self.set_value_calls[1][0:2], ("Building", "BUILD-1"))
        self.assertEqual(
            self.set_value_calls[1][2],
            {
                "project": "PROJ-BUILD-1",
                "cost_center": "CC-BUILD-1",
                "sales_order": "SO-BUILD-1",
                "subscription_plan": "",
                "subscription": "",
                "contract": "",
            },
        )

    def test_subscription_update_blocks_when_existing_doc_is_active(self):
        locked_doc = SimpleNamespace(status="Active")

        with patch.object(admin_service, "_load_doc", return_value=locked_doc):
            with self.assertRaisesRegex(Exception, "linked subscription is already active or finalized"):
                admin_service._upsert_subscription(
                    linked_name="SUB-1",
                    customer="CUST-1",
                    company_row={"name": "PK Holdings"},
                    plan_name="PLAN-1",
                    cost_center_name="CC-1",
                    contract_start_date="2026-04-01",
                    contract_end_date="2027-03-31",
                )

    def test_sales_order_update_blocks_when_existing_doc_is_submitted(self):
        locked_doc = SimpleNamespace(docstatus=1, status="Submitted")

        with patch.object(admin_service, "_load_doc", return_value=locked_doc):
            with self.assertRaisesRegex(Exception, "linked sales order is already submitted or finalized"):
                admin_service._upsert_sales_order(
                    linked_name="SO-1",
                    building_name="BUILD-1",
                    customer="CUST-1",
                    company_row={"name": "PK Holdings"},
                    project_name="PROJ-1",
                    cost_center_name="CC-1",
                    service_item_code="General Cleaning",
                    contract_amount=900,
                    contract_start_date="2026-04-01",
                    contract_end_date=None,
                )


class TestAdminPortalCostCenterResolution(unittest.TestCase):
    def test_resolve_company_group_cost_center_returns_parent_group_when_company_default_is_leaf(self):
        with patch.object(
            admin_service,
            "_cost_center_row",
            side_effect=[
                {
                    "name": "Main - PK",
                    "company": "PK Holdings",
                    "parent_cost_center": "PK Holdings - PK",
                    "is_group": 0,
                },
                {
                    "name": "PK Holdings - PK",
                    "company": "PK Holdings",
                    "parent_cost_center": "",
                    "is_group": 1,
                },
            ],
        ):
            with patch.object(admin_service, "_company_group_cost_centers", return_value=[]):
                resolved = admin_service._resolve_company_group_cost_center(
                    {"name": "PK Holdings", "cost_center": "Main - PK"}
                )

        self.assertEqual(resolved, "PK Holdings - PK")

    def test_resolve_company_group_cost_center_falls_back_to_root_group(self):
        with patch.object(admin_service, "_cost_center_row", return_value=None):
            with patch.object(
                admin_service,
                "_company_group_cost_centers",
                return_value=[
                    {"name": "PK Holdings - PK", "parent_cost_center": ""},
                    {"name": "North Region - PK", "parent_cost_center": "PK Holdings - PK"},
                ],
            ):
                resolved = admin_service._resolve_company_group_cost_center(
                    {"name": "PK Holdings", "cost_center": "Missing - PK"}
                )

        self.assertEqual(resolved, "PK Holdings - PK")


class TestAdminPortalSubscriptionPlanUpsert(unittest.TestCase):
    def test_upsert_subscription_plan_sets_fixed_rate_on_insert(self):
        created = SimpleNamespace(name="PLAN-1")

        with patch.object(admin_service, "_load_doc", return_value=None):
            with patch.object(admin_service, "_insert_doc", return_value=created) as insert_doc:
                result = admin_service._upsert_subscription_plan(
                    linked_name=None,
                    building_display_name="Pilot Building 1",
                    company_row={"default_currency": "USD"},
                    cost_center_name="CC-1",
                    service_item_code="General Cleaning",
                    contract_amount=2500,
                    billing_interval="month",
                    billing_interval_count=1,
                )

        self.assertEqual(result, "PLAN-1")
        payload = insert_doc.call_args.args[0]
        self.assertEqual(payload["doctype"], "Subscription Plan")
        self.assertEqual(payload["item"], "General Cleaning")
        self.assertEqual(payload["price_determination"], "Fixed Rate")
        self.assertEqual(payload["cost"], 2500)
        self.assertEqual(payload["billing_interval"], "Month")
        self.assertEqual(payload["billing_interval_count"], 1)

    def test_upsert_subscription_plan_sets_fixed_rate_on_update(self):
        linked = SimpleNamespace(
            name="PLAN-1",
            plan_name="",
            currency="USD",
            item="Old Item",
            price_determination="Based On Price List",
            price_list="Standard Selling",
            cost=1200,
            billing_interval="Week",
            billing_interval_count=2,
            cost_center="OLD-CC",
        )

        with patch.object(admin_service, "_load_doc", return_value=linked):
            with patch.object(admin_service, "_save_doc") as save_doc:
                result = admin_service._upsert_subscription_plan(
                    linked_name="PLAN-1",
                    building_display_name="Pilot Building 1",
                    company_row={"default_currency": "USD"},
                    cost_center_name="CC-1",
                    service_item_code="General Cleaning",
                    contract_amount=2500,
                    billing_interval="month",
                    billing_interval_count=1,
                )

        self.assertEqual(result, "PLAN-1")
        self.assertEqual(linked.plan_name, "Pilot Building 1 General Cleaning")
        self.assertEqual(linked.item, "General Cleaning")
        self.assertEqual(linked.price_determination, "Fixed Rate")
        self.assertEqual(linked.price_list, "")
        self.assertEqual(linked.cost, 2500)
        self.assertEqual(linked.billing_interval, "Month")
        self.assertEqual(linked.billing_interval_count, 1)
        self.assertEqual(linked.cost_center, "CC-1")
        save_doc.assert_called_once_with(linked)


class TestAdminPortalContractUpsert(unittest.TestCase):
    def test_upsert_contract_sets_default_terms_on_insert(self):
        created = SimpleNamespace(name="CON-1")

        with patch.object(admin_service, "_load_doc", return_value=None):
            with patch.object(admin_service, "_insert_doc", return_value=created) as insert_doc:
                result = admin_service._upsert_contract(
                    linked_name=None,
                    customer="CUST-1",
                    project_name="PROJ-1",
                    contract_start_date="2026-04-01",
                    contract_end_date="2027-03-31",
                )

        self.assertEqual(result, "CON-1")
        payload = insert_doc.call_args.args[0]
        self.assertEqual(payload["doctype"], "Contract")
        self.assertEqual(payload["party_type"], "Customer")
        self.assertEqual(payload["party_name"], "CUST-1")
        self.assertEqual(payload["document_type"], "Project")
        self.assertEqual(payload["document_name"], "PROJ-1")
        self.assertEqual(payload["contract_terms"], admin_service.DEFAULT_COMMERCIAL_CONTRACT_TERMS)

    def test_upsert_contract_preserves_existing_terms_on_update(self):
        linked = SimpleNamespace(
            name="CON-1",
            party_type="Customer",
            party_name="CUST-OLD",
            start_date="2025-01-01",
            end_date="2025-12-31",
            contract_terms="Custom negotiated terms",
            document_type="Project",
            document_name="PROJ-OLD",
            status="",
        )

        with patch.object(admin_service, "_load_doc", return_value=linked):
            with patch.object(admin_service, "_save_doc") as save_doc:
                result = admin_service._upsert_contract(
                    linked_name="CON-1",
                    customer="CUST-1",
                    project_name="PROJ-1",
                    contract_start_date="2026-04-01",
                    contract_end_date="2027-03-31",
                )

        self.assertEqual(result, "CON-1")
        self.assertEqual(linked.party_name, "CUST-1")
        self.assertEqual(linked.contract_terms, "Custom negotiated terms")
        self.assertEqual(linked.document_name, "PROJ-1")
        save_doc.assert_called_once_with(linked)


class TestAdminPortalBuildingUpdateApi(unittest.TestCase):
    def test_update_admin_building_api_wrapper_validates_and_returns_payload(self):
        expected = admin_service.AdminBuildingUpdateResult(
            building_id="BUILD-1",
            project="PROJ-BUILD-1",
            cost_center="CC-BUILD-1",
            subscription_plan="PLAN-BUILD-1",
            subscription="SUB-BUILD-1",
            contract="CON-BUILD-1",
        )
        with patch.object(
            admin_api.admin_portal_service,
            "update_admin_building",
            return_value=expected,
        ) as update_admin_building:
            result = admin_api.update_admin_building(
                building="BUILD-1",
                name="Pilot Building 1",
                customer="CUST-1",
                company="PK Holdings",
                billing_model="recurring",
                contract_amount=2500,
                billing_interval="month",
                billing_interval_count=1,
                contract_start_date="2026-04-01",
                contract_end_date="2027-03-31",
                auto_renew=1,
            )

        self.assertEqual(
            result,
            {
                "building_id": "BUILD-1",
                "project": "PROJ-BUILD-1",
                "cost_center": "CC-BUILD-1",
                "subscription_plan": "PLAN-BUILD-1",
                "subscription": "SUB-BUILD-1",
                "sales_order": None,
                "contract": "CON-BUILD-1",
            },
        )
        request = update_admin_building.call_args.args[0]
        self.assertEqual(request.building_id, "BUILD-1")
        self.assertEqual(request.name, "Pilot Building 1")
        self.assertEqual(request.customer, "CUST-1")
        self.assertEqual(request.company, "PK Holdings")
        self.assertEqual(request.billing_model, "recurring")
        self.assertEqual(request.contract_amount, 2500.0)
        self.assertEqual(str(request.contract_start_date), "2026-04-01")
        self.assertEqual(str(request.contract_end_date), "2027-03-31")
        self.assertTrue(request.auto_renew)

    def test_update_admin_building_api_wrapper_rejects_incomplete_commercial_setup(self):
        with self.assertRaisesRegex(Exception, "Customer is required when commercial setup is configured"):
            admin_api.update_admin_building(
                building="BUILD-1",
                name="Pilot Building 1",
                billing_model="recurring",
                contract_amount=2500,
                billing_interval="month",
                billing_interval_count=1,
                contract_start_date="2026-04-01",
            )


if __name__ == "__main__":
    unittest.main()
