app_name = "pikt_inc"
app_title = "Pikt Inc"
app_publisher = "PK Whiting"
app_description = "Business Logic Implementation"
app_email = "patten.whiting@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "pikt_inc",
# 		"logo": "/assets/pikt_inc/logo.png",
# 		"title": "Pikt Inc",
# 		"route": "/pikt_inc",
# 		"has_permission": "pikt_inc.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/pikt_inc/css/pikt_inc.css"
# app_include_js = "/assets/pikt_inc/js/pikt_inc.js"

# include js, css files in header of web template
# web_include_css = "/assets/pikt_inc/css/pikt_inc.css"
# web_include_js = "/assets/pikt_inc/js/pikt_inc.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "pikt_inc/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "pikt_inc/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
home_page = "home"

# website user home page (by Role)
role_home_page = {"Customer Portal User": "portal"}

website_route_rules = [
	{"from_route": "/blog", "to_route": "blog-home"},
	{"from_route": "/blog/rss.xml", "to_route": "blog-rss.xml"},
	{"from_route": "/blog/<slug>", "to_route": "blog-post"},
]

website_redirects = [
	{"source": "/home", "target": "/", "redirect_http_status": "301"},
]

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "pikt_inc.utils.jinja_methods",
# 	"filters": "pikt_inc.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "pikt_inc.install.before_install"
# after_install = "pikt_inc.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "pikt_inc.uninstall.before_uninstall"
# after_uninstall = "pikt_inc.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "pikt_inc.utils.before_app_install"
# after_app_install = "pikt_inc.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "pikt_inc.utils.before_app_uninstall"
# after_app_uninstall = "pikt_inc.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "pikt_inc.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Opportunity": {
		"before_insert": "pikt_inc.events.opportunity.before_insert"
	},
	"Quotation": {
		"before_submit": "pikt_inc.events.quotation.before_submit",
		"after_insert": "pikt_inc.events.quotation.after_insert",
	},
	"Recurring Service Rule": {
		"after_insert": "pikt_inc.events.recurring_service_rule.after_insert",
		"on_update": "pikt_inc.events.recurring_service_rule.on_update",
	},
	"Building": {
		"after_insert": "pikt_inc.events.building.after_insert",
		"on_update": "pikt_inc.events.building.on_update",
	},
	"Site Shift Requirement": {
		"before_save": "pikt_inc.events.site_shift_requirement.before_save",
		"after_insert": "pikt_inc.events.site_shift_requirement.after_insert",
		"on_update": "pikt_inc.events.site_shift_requirement.on_update",
	},
	"Dispatch Route": {
		"before_save": "pikt_inc.events.dispatch_route.before_save",
	},
	"Shift Assignment": {
		"after_insert": "pikt_inc.events.shift_assignment.after_insert",
		"on_update": "pikt_inc.events.shift_assignment.on_update",
		"on_submit": "pikt_inc.events.shift_assignment.on_submit",
		"on_update_after_submit": "pikt_inc.events.shift_assignment.on_update_after_submit",
	},
	"Employee Checkin": {
		"after_insert": "pikt_inc.events.employee_checkin.after_insert",
	},
	"Call Out": {
		"after_insert": "pikt_inc.events.call_out.after_insert",
		"on_update": "pikt_inc.events.call_out.on_update",
	},
	"Dispatch Recommendation": {
		"after_insert": "pikt_inc.events.dispatch_recommendation.after_insert",
		"on_update": "pikt_inc.events.dispatch_recommendation.on_update",
	},
	"Employee Onboarding Request": {
		"before_insert": "pikt_inc.events.employee_onboarding_request.before_insert",
	},
	"Employee Onboarding Packet": {
		"before_save": "pikt_inc.events.employee_onboarding_packet.before_save",
	},
	"Digital Walkthrough Submission": {
		"before_save": "pikt_inc.events.digital_walkthrough_submission.before_save",
		"after_insert": "pikt_inc.events.digital_walkthrough_submission.after_insert",
		"on_update": "pikt_inc.events.digital_walkthrough_submission.on_update",
	},
	"User": {
		"before_save": "pikt_inc.events.user.before_save",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"all": [
		"pikt_inc.jobs.dispatch.dispatch_orchestrator_hour_gate",
		"pikt_inc.jobs.dispatch.dispatch_calendar_subject_sync",
		"pikt_inc.jobs.dispatch.monitor_no_show_site_shift_requirements",
		"pikt_inc.jobs.dispatch.dispatch_completion_finalizer",
		"pikt_inc.jobs.dispatch.dispatch_route_email_orchestrator",
	],
}

# Testing
# -------

# before_tests = "pikt_inc.install.before_tests"

fixtures = [
	{
		"dt": "Notification",
		"filters": [
			[
				"name",
				"in",
				[
					"Commercial Cleaning Instant Estimate",
					"Employee Onboarding Invite",
					"Employee Onboarding Reminder",
					"Employee Onboarding Submitted",
					"Error Log",
					"Integration Request",
					"Lead Quotation Review Invite",
					"New Commercial Cleaning Lead",
					"New Contact Form Lead",
					"New Digital Walkthrough Submission",
					"New Unlinked Digital Walkthrough Submission",
					"Pre-Service Visit Reminder",
					"Reviewer Opportunity Walkthrough Submitted",
				],
			]
		],
	},
	{
		"dt": "Builder Page",
		"filters": [
			[
				"route",
				"in",
				[
					"home",
					"about",
					"billing-setup-complete",
					"commercial-cleaning-services",
					"contact",
					"digital-walkthrough",
					"digital-walkthrough-received",
					"faq",
					"industries",
					"industries/industrial-flex",
					"industries/medical-offices",
					"industries/office-buildings",
					"industries/retail-stores",
					"portal",
					"portal/agreements",
					"portal/billing",
					"portal/locations",
					"quote",
					"quote-accepted",
					"review-quote",
					"residential-cleaning-services",
					"reviews",
					"service-area",
					"service-area/kyle-tx",
					"service-area/san-marcos-tx",
					"services",
					"services/commercial-cleaning",
					"services/day-porter-services",
					"services/floor-care",
					"services/medical-office-cleaning",
					"services/office-cleaning",
					"thank-you",
				],
			]
		],
	},
	{
		"dt": "Builder Component",
		"filters": [
			[
				"component_name",
				"in",
				[
					"LP About / Story Section",
					"LP City Links Grid",
					"LP Contact Form",
					"LP Contact Info Card",
					"LP CTA Band",
					"LP FAQ Accordion",
					"LP Feature List Section",
					"LP Site Navbar",
					"LP Site Footer",
					"LP Industry Detail Section",
					"LP Industry Links Grid",
					"LP Process Section",
					"LP Quote Form",
					"LP Quote Result Section",
					"LP Service Area Section",
					"LP Service Detail Section",
					"LP Service Links Grid",
					"LP Hero Centered",
					"LP Testimonial Section",
					"LP Trust Section",
					"LP Walkthrough Received",
					"Portal Shell Header",
					"Portal Summary Stat Card",
					"Portal Record List Card",
					"Portal Invoice Row Card",
					"Portal Agreement Preview Card",
					"Portal Location Edit Card",
					"Portal Empty State Block",
				],
			]
		],
	},
	{
		"dt": "Block Template",
		"filters": [
			[
				"name",
				"in",
				[
					"LP Hero Centered",
					"LP Section Header",
					"LP Primary Button",
					"LP Secondary Button",
					"LP Trust Pill",
					"LP CTA Button Row",
					"LP Simple Info Card",
					"LP Process Step Card",
					"LP Checklist Item",
					"LP Testimonial Card",
					"LP Metric Pill",
				],
			]
		],
	},
	{
		"dt": "Workspace",
		"filters": [["name", "in", ["Marketing Blog"]]],
	},
]

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "pikt_inc.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"create_instant_quote_opportunity": "pikt_inc.api.public_intake.create_instant_quote_opportunity",
	"validate_public_funnel_opportunity": "pikt_inc.api.public_intake.validate_public_funnel_opportunity",
	"save_opportunity_walkthrough_upload": "pikt_inc.api.public_intake.save_opportunity_walkthrough_upload",
	"validate_public_quote": "pikt_inc.api.public_quote.validate_public_quote",
	"accept_public_quote": "pikt_inc.api.public_quote.accept_public_quote",
	"load_public_quote_portal_state": "pikt_inc.api.public_quote.load_public_quote_portal_state",
	"complete_public_service_agreement_signature": "pikt_inc.api.public_quote.complete_public_service_agreement_signature",
	"complete_public_quote_billing_setup_v2": "pikt_inc.api.public_quote.complete_public_quote_billing_setup_v2",
	"complete_public_quote_access_setup_v2": "pikt_inc.api.public_quote.complete_public_quote_access_setup_v2",
	"dispatch_reconcile_routes": "pikt_inc.api.dispatch.dispatch_reconcile_routes",
	"dispatch_reconcile_rule": "pikt_inc.api.dispatch.dispatch_reconcile_rule",
	"dispatch_sync_paused_buildings": "pikt_inc.api.dispatch.dispatch_sync_paused_buildings",
	"dispatch_data_integrity_migration": "pikt_inc.api.dispatch.dispatch_data_integrity_migration",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "pikt_inc.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["pikt_inc.utils.before_request"]
# after_request = ["pikt_inc.utils.after_request"]

# Job Events
# ----------
# before_job = ["pikt_inc.utils.before_job"]
# after_job = ["pikt_inc.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"pikt_inc.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
