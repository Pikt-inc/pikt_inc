from __future__ import annotations

import json
from pathlib import Path
import unittest

from pikt_inc import hooks as app_hooks


CUSTOM_NOTIFICATION_NAMES = (
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
)

NOTIFICATION_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "notification.json"


class TestNotificationFixtures(unittest.TestCase):
    def test_hooks_export_custom_notifications(self):
        notification_fixture = next(fixture for fixture in app_hooks.fixtures if fixture["dt"] == "Notification")

        self.assertEqual(
            notification_fixture["filters"],
            [["name", "in", list(CUSTOM_NOTIFICATION_NAMES)]],
        )

    def test_notification_fixture_contains_custom_notifications(self):
        notification_fixture = json.loads(NOTIFICATION_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(len(notification_fixture), len(CUSTOM_NOTIFICATION_NAMES))
        self.assertEqual({doc["name"] for doc in notification_fixture}, set(CUSTOM_NOTIFICATION_NAMES))
        self.assertTrue(all(doc["doctype"] == "Notification" for doc in notification_fixture))
