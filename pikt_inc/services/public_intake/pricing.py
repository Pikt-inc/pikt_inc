from __future__ import annotations

import frappe

from .constants import DEFAULT_COMPANY, DEFAULT_CURRENCY
from .shared import clean


def normalize_bathroom_traffic_level(value):
    raw = clean(value)
    lowered = raw.lower()
    mapping = {
        "": "None",
        "0": "None",
        "none": "None",
        "1-2": "Light",
        "light": "Light",
        "3-5": "Medium",
        "medium": "Medium",
        "6-10": "Heavy",
        "11+": "Heavy",
        "heavy": "Heavy",
    }
    return mapping.get(raw, mapping.get(lowered, ""))


def apply_instant_quote_pricing(doc):
    building_type = clean(doc.get("building_type") or "Other")
    service_frequency = clean(doc.get("service_frequency") or "Monthly").replace("\u2014", "-").replace(
        "\u2013", "-"
    )
    service_interest = clean(doc.get("service_interest") or "Recurring standard cleaning").replace(
        "\u2014", "-"
    ).replace("\u2013", "-")
    bathroom_count_range = normalize_bathroom_traffic_level(doc.get("bathroom_count_range")) or "None"

    sq_ft_raw = clean(doc.get("building_size") or "0").replace(",", "")
    try:
        sq_ft = float(sq_ft_raw)
    except Exception:
        sq_ft = 0.0

    pricing_low = {
        "Office": 0.18,
        "Warehouse": 0.10,
        "Retail": 0.16,
        "Medical": 0.22,
        "Industrial": 0.18,
        "Educational": 0.15,
        "Other": 0.17,
    }
    pricing_high = {
        "Office": 0.285,
        "Warehouse": 0.16,
        "Retail": 0.24,
        "Medical": 0.36,
        "Industrial": 0.30,
        "Educational": 0.24,
        "Other": 0.28,
    }
    frequency_factors = {
        "5x/week": 1.00,
        "3x/week": 1.08,
        "2x/week": 1.18,
        "Weekly": 1.35,
        "Biweekly": 1.60,
        "Monthly": 1.95,
    }
    service_factors = {
        "Recurring standard cleaning": 1.00,
        "Recurring cleaning + restocking": 1.08,
        "Recurring cleaning + disinfection": 1.12,
        "Not sure - need recommendation": 1.05,
        "Special request / custom scope": 1.20,
    }
    bathroom_low_adders = {
        "None": 0.00,
        "Light": 125.00,
        "Medium": 425.00,
        "Heavy": 1050.00,
    }
    bathroom_high_adders = {
        "None": 0.00,
        "Light": 225.00,
        "Medium": 725.00,
        "Heavy": 1700.00,
    }

    if bathroom_count_range not in bathroom_low_adders:
        bathroom_count_range = "None"

    if sq_ft <= 0:
        size_factor = 1.00
    elif sq_ft < 2000:
        size_factor = 1.15
    else:
        size_factor = 1.00

    low_rate = pricing_low.get(building_type, 0.17)
    high_rate = pricing_high.get(building_type, 0.28)
    frequency_factor = frequency_factors.get(service_frequency, 1.95)
    service_factor = service_factors.get(service_interest, 1.00)

    low_monthly = sq_ft * low_rate * frequency_factor * service_factor * size_factor
    high_monthly = sq_ft * high_rate * frequency_factor * service_factor * size_factor
    low_monthly += bathroom_low_adders.get(bathroom_count_range, 0.0)
    high_monthly += bathroom_high_adders.get(bathroom_count_range, 0.0)

    minimum_monthly = 600.00
    if low_monthly < minimum_monthly:
        low_monthly = minimum_monthly
    if high_monthly < minimum_monthly:
        high_monthly = minimum_monthly

    low_monthly = round(low_monthly, 2)
    high_monthly = round(high_monthly, 2)
    mid_estimate = round((low_monthly + high_monthly) / 2, 2)
    green_firm_quote = low_monthly + ((high_monthly - low_monthly) * 0.70)

    if green_firm_quote < 2000:
        green_firm_quote = round(green_firm_quote / 25.0) * 25.0
    elif green_firm_quote < 5000:
        green_firm_quote = round(green_firm_quote / 50.0) * 50.0
    else:
        green_firm_quote = round(green_firm_quote / 100.0) * 100.0

    green_firm_quote = round(green_firm_quote, 2)

    risk_score = 0
    risk_score += {
        "Office": 0,
        "Warehouse": 3,
        "Retail": 1,
        "Medical": 2,
        "Industrial": 3,
        "Educational": 1,
        "Other": 1,
    }.get(building_type, 1)
    risk_score += {
        "5x/week": 0,
        "3x/week": 0,
        "2x/week": 1,
        "Weekly": 2,
        "Biweekly": 3,
        "Monthly": 4,
    }.get(service_frequency, 2)
    risk_score += {
        "Recurring standard cleaning": 0,
        "Recurring cleaning + restocking": 1,
        "Recurring cleaning + disinfection": 1,
        "Not sure - need recommendation": 2,
        "Special request / custom scope": 4,
    }.get(service_interest, 1)

    if sq_ft <= 0:
        risk_score += 4

    if service_interest == "Special request / custom scope":
        risk_level = "Red"
    elif risk_score <= 2:
        risk_level = "Green"
    elif risk_score <= 6:
        risk_level = "Yellow"
    else:
        risk_level = "Red"

    doc.bathroom_count_range = bathroom_count_range
    doc.custom_estimate_low = low_monthly
    doc.custom_estimate_high = high_monthly
    doc.opportunity_amount = green_firm_quote if risk_level == "Green" else mid_estimate
    doc.risk_level = risk_level

    if not doc.get("status"):
        doc.status = "Open"
    if not doc.get("company"):
        doc.company = DEFAULT_COMPANY
    if not doc.get("currency"):
        doc.currency = DEFAULT_CURRENCY
    if not doc.get("naming_series"):
        doc.naming_series = "CRM-OPP-.YYYY.-"

    if not (doc.custom_estimate_low and doc.custom_estimate_high):
        frappe.log_error(
            (
                "Instant quote range missing after calculation. building_type={0}, "
                "service_frequency={1}, service_interest={2}, building_size={3}, "
                "bathroom_traffic_level={4}"
            ).format(
                building_type,
                service_frequency,
                service_interest,
                sq_ft_raw,
                bathroom_count_range,
            ),
            "Instant Quote Range Missing",
        )

    return {
        "low": low_monthly,
        "high": high_monthly,
        "final_price": doc.opportunity_amount,
        "risk": risk_level,
        "currency": doc.get("currency") or DEFAULT_CURRENCY,
    }
