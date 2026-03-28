(function () {
  var CUSTOMER_ROLE = "Customer Desk User";
  var ALLOWED_ROLES = {
    "All": true,
    "Customer Desk User": true,
    "Customer Portal User": true,
    "Desk User": true,
    "Guest": true
  };

  function getRoles() {
    return Array.isArray(frappe.user_roles) ? frappe.user_roles : [];
  }

  function isCustomerDeskUser() {
    var roles = getRoles();
    return roles.indexOf(CUSTOMER_ROLE) !== -1 && roles.every(function (role) {
      return !!ALLOWED_ROLES[role];
    });
  }

  frappe.listview_settings["Building"] = {
    hide_name_column: true,
    onload: function (listview) {
      if (!isCustomerDeskUser()) {
        return;
      }
      listview.page.fields_dict = listview.page.fields_dict || {};
    }
  };
}());
