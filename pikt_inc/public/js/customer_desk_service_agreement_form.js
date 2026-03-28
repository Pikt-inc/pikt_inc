(function () {
  var CUSTOMER_ROLE = "Customer Desk User";
  var ALLOWED_ROLES = {
    "All": true,
    "Customer Desk User": true,
    "Customer Portal User": true,
    "Desk User": true,
    "Guest": true
  };
  var HIDDEN_FIELDS = [
    "customer",
    "template",
    "template_version",
    "signer_ip",
    "signer_user_agent"
  ];
  var READ_ONLY_FIELDS = [
    "agreement_name",
    "status",
    "rendered_html_snapshot",
    "signed_by_name",
    "signed_by_title",
    "signed_by_email",
    "signed_on"
  ];

  function getRoles() {
    return Array.isArray(frappe.user_roles) ? frappe.user_roles : [];
  }

  function isCustomerDeskUser() {
    var roles = getRoles();
    return roles.indexOf(CUSTOMER_ROLE) !== -1 && roles.every(function (role) {
      return !!ALLOWED_ROLES[role];
    });
  }

  function applyReadOnlyView(frm) {
    HIDDEN_FIELDS.forEach(function (fieldname) {
      if (frm.fields_dict[fieldname]) {
        frm.set_df_property(fieldname, "hidden", 1);
      }
    });
    READ_ONLY_FIELDS.forEach(function (fieldname) {
      if (frm.fields_dict[fieldname]) {
        frm.set_df_property(fieldname, "read_only", 1);
      }
    });
    frm.disable_save();
    if (frm.page && frm.page.clear_primary_action) {
      frm.page.clear_primary_action();
    }
  }

  frappe.ui.form.on("Service Agreement", {
    setup: function (frm) {
      if (!isCustomerDeskUser()) {
        return;
      }
      applyReadOnlyView(frm);
    },
    refresh: function (frm) {
      if (!isCustomerDeskUser()) {
        return;
      }
      applyReadOnlyView(frm);
    }
  });
}());
