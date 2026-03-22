import frappe


def after_insert(doc, method=None):
    frappe.logger("pikt_inc").info(
        "ToDo created via pikt_inc hook: name=%s owner=%s", doc.name, doc.owner
    )
