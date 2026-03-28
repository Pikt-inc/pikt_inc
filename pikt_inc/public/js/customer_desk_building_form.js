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
    "active",
    "supervisor_user",
    "access_details_completed_on",
    "custom_service_agreement",
    "custom_service_agreement_addendum"
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

  function hideFields(frm) {
    HIDDEN_FIELDS.forEach(function (fieldname) {
      if (frm.fields_dict[fieldname]) {
        frm.set_df_property(fieldname, "hidden", 1);
      }
    });
    if (!frm.is_new() && frm.fields_dict.building_name) {
      frm.set_df_property("building_name", "read_only", 1);
    }
  }

  frappe.ui.form.on("Building", {
    setup: function (frm) {
      if (!isCustomerDeskUser()) {
        return;
      }
      hideFields(frm);
    },
    refresh: function (frm) {
      if (!isCustomerDeskUser()) {
        return;
      }
      hideFields(frm);
    }
  });
}());
