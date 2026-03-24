from __future__ import annotations

import frappe

from pikt_inc.services.dispatch import planning


INDEX_NAME = "uniq_ssr_rule_date_slot"


def _index_exists():
    rows = frappe.db.sql(
        """
        SELECT COUNT(*) AS cnt
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = 'tabSite Shift Requirement'
          AND index_name = %s
        """,
        (INDEX_NAME,),
        as_dict=True,
    )
    return bool(rows and rows[0].get("cnt"))


def _duplicate_rule_keys():
    return frappe.db.sql(
        """
        SELECT recurring_service_rule, service_date, slot_index, COUNT(*) AS cnt
        FROM `tabSite Shift Requirement`
        WHERE IFNULL(recurring_service_rule, '') <> ''
        GROUP BY recurring_service_rule, service_date, slot_index
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, recurring_service_rule ASC, service_date ASC, slot_index ASC
        LIMIT 5
        """,
        as_dict=True,
    )


def execute():
    planning.dispatch_data_integrity_migration()

    frappe.db.sql(
        """
        UPDATE `tabSite Shift Requirement`
        SET recurring_service_rule = NULL
        WHERE IFNULL(recurring_service_rule, '') = ''
        """
    )

    duplicates = _duplicate_rule_keys()
    if duplicates:
        sample = ", ".join(
            f"{row.get('recurring_service_rule')}:{row.get('service_date')}#{row.get('slot_index')} ({row.get('cnt')})"
            for row in duplicates
        )
        raise Exception(
            "Cannot create uniq_ssr_rule_date_slot because duplicate rule-backed Site Shift Requirements remain: "
            + sample
        )

    if _index_exists():
        return

    frappe.db.sql(
        """
        ALTER TABLE `tabSite Shift Requirement`
        ADD UNIQUE INDEX `uniq_ssr_rule_date_slot`
        (`recurring_service_rule`, `service_date`, `slot_index`)
        """
    )
