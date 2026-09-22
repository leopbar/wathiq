"""Synthetic data for the simulated servers.

Everything in this file is invented. The company registry, the sanctions list and the core
banking customers are stand-ins: no real registry, no real sanctions source, no real bank.
The UI and the docs say so wherever these results are shown.

The company names match the ones the demo database seeds, so a demo case can actually be
looked up. That is deliberate: a registry that never finds anything teaches nothing.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

_PUNCTUATION = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE = re.compile(r"\s+")


def normalise(value: str) -> str:
    """Company names come with LLC, L.L.C., FZ-LLC. Punctuation is dropped, not split."""
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub("", value.lower())).strip()


def similarity(left: str, right: str) -> float:
    """How alike two names are, 0 to 1.

    Two measures, and the stronger one wins:

    * **token overlap** catches word-order and suffix differences — "Al Noor Logistics LLC"
      against "Al Noor Logistics FZ-LLC";
    * **character similarity** catches spelling differences inside a word — "Youssef Karam"
      against "Youssef Karem", where token overlap sees two different words and scores far
      too low.

    Transliterated Arabic names need both: the same person is written half a dozen ways.
    """
    left_norm, right_norm = normalise(left), normalise(right)
    if not left_norm or not right_norm:
        return 0.0

    a, b = set(left_norm.split()), set(right_norm.split())
    token_score = len(a & b) / len(a | b)
    character_score = SequenceMatcher(None, left_norm, right_norm).ratio()
    return round(max(token_score, character_score), 3)


# --- company registry (simulated) ---------------------------------------------
# `aliases` are the spellings a document might legitimately use; `registered_name` is the one
# the registry considers correct. That difference is exactly what the investigator resolves.
COMPANIES: list[dict[str, Any]] = [
    {
        "license_number": "CN-1042288",
        "registered_name": "Falcon Ridge Trading LLC",
        "aliases": ["Falcon Ridge Trading L.L.C.", "Falcon Ridge Trading"],
        "legal_form": "Limited Liability Company",
        "status": "active",
        "activity": "General trading",
        "authority": "Department of Economic Development (simulated)",
        "established": "2016-03-11",
    },
    {
        "license_number": "CN-2255019",
        "registered_name": "Al Noor Logistics FZ-LLC",
        "aliases": ["Al Noor Logistics", "Al Noor Logistics FZ LLC", "Alnoor Logistics"],
        "legal_form": "Free Zone LLC",
        "status": "active",
        "activity": "Freight forwarding",
        "authority": "Free Zone Authority (simulated)",
        "established": "2018-09-02",
    },
    {
        "license_number": "CN-3390477",
        "registered_name": "Dunes Technology Solutions",
        "aliases": ["Dunes Tech Solutions", "Dunes Technology"],
        "legal_form": "Sole Establishment",
        "status": "active",
        "activity": "IT consultancy",
        "authority": "Department of Economic Development (simulated)",
        "established": "2020-01-20",
    },
    {
        "license_number": "CN-4417832",
        "registered_name": "Pearl Harbour Marine Services",
        "aliases": ["Pearl Harbour Marine"],
        "legal_form": "Limited Liability Company",
        "status": "active",
        "activity": "Marine services",
        "authority": "Free Zone Authority (simulated)",
        "established": "2015-06-30",
    },
    {
        "license_number": "CN-5529114",
        "registered_name": "Sahara Green Contracting",
        "aliases": ["Sahara Green Contracting LLC"],
        "legal_form": "Limited Liability Company",
        "status": "suspended",
        "activity": "Building contracting",
        "authority": "Department of Economic Development (simulated)",
        "established": "2013-11-14",
    },
    {
        "license_number": "CN-6604521",
        "registered_name": "Oasis Medical Supplies",
        "aliases": ["Oasis Medical Supplies LLC", "Oasis Medical"],
        "legal_form": "Limited Liability Company",
        "status": "active",
        "activity": "Medical equipment trading",
        "authority": "Department of Economic Development (simulated)",
        "established": "2019-04-08",
    },
    {
        "license_number": "CN-7718003",
        "registered_name": "Emerald Bay Hospitality",
        "aliases": ["Emerald Bay Hospitality LLC"],
        "legal_form": "Limited Liability Company",
        "status": "active",
        "activity": "Hotel management",
        "authority": "Media Zone Authority (simulated)",
        "established": "2017-02-25",
    },
    {
        "license_number": "CN-8823640",
        "registered_name": "Silver Dune Investments",
        "aliases": ["Silver Dune Investment", "Silver Dunes Investments"],
        "legal_form": "Investment holding",
        "status": "active",
        "activity": "Investment holding",
        "authority": "Free Zone Authority (simulated)",
        "established": "2014-08-19",
    },
    {
        "license_number": "CN-9931286",
        "registered_name": "Crescent Field Energy",
        "aliases": ["Crescent Field Energy LLC"],
        "legal_form": "Limited Liability Company",
        "status": "active",
        "activity": "Energy services",
        "authority": "Department of Economic Development (simulated)",
        "established": "2012-05-05",
    },
    {
        "license_number": "CN-1015577",
        "registered_name": "Blue Horizon Shipping",
        "aliases": ["Blue Horizon Shipping Agency"],
        "legal_form": "Branch",
        "status": "active",
        "activity": "Shipping agency",
        "authority": "Free Zone Authority (simulated)",
        "established": "2011-10-01",
    },
    {
        "license_number": "CN-1126894",
        "registered_name": "Golden Sands Foodstuff",
        "aliases": ["Golden Sands Foodstuff Trading", "Golden Sand Foodstuff"],
        "legal_form": "Limited Liability Company",
        "status": "active",
        "activity": "Foodstuff trading",
        "authority": "Department of Economic Development (simulated)",
        "established": "2018-12-12",
    },
    {
        "license_number": "CN-1237410",
        "registered_name": "Northern Gate Engineering",
        "aliases": ["Northern Gate Engineering Consultancy"],
        "legal_form": "Limited Liability Company",
        "status": "active",
        "activity": "Engineering consultancy",
        "authority": "Department of Economic Development (simulated)",
        "established": "2016-07-07",
    },
    {
        "license_number": "CN-1348126",
        "registered_name": "Atlas Fleet Rentals",
        "aliases": ["Atlas Fleet Rental"],
        "legal_form": "Limited Liability Company",
        "status": "expired",
        "activity": "Vehicle rental",
        "authority": "Department of Economic Development (simulated)",
        "established": "2010-02-02",
    },
    {
        "license_number": "CN-1459033",
        "registered_name": "Coral Reef Interiors",
        "aliases": ["Coral Reef Interior Design"],
        "legal_form": "Sole Establishment",
        "status": "active",
        "activity": "Interior design",
        "authority": "Media Zone Authority (simulated)",
        "established": "2021-03-17",
    },
    {
        "license_number": "CN-1560948",
        "registered_name": "Zenith Cloud Services",
        "aliases": ["Zenith Cloud Service", "Zenith Cloud"],
        "legal_form": "Free Zone LLC",
        "status": "active",
        "activity": "Cloud services",
        "authority": "Free Zone Authority (simulated)",
        "established": "2022-06-21",
    },
]


# --- sanctions list (simulated sample) ----------------------------------------
# Invented names only. Two of them are deliberately close to the demo people, so a realistic
# "possible match — a human must decide" can actually happen in a demo.
SANCTIONS: list[dict[str, Any]] = [
    {
        "id": "SIM-SAN-0001",
        "name": "Yousef Karem",
        "aliases": ["Yusuf Karem", "Youssef Karem"],
        "country": "Unknown",
        "list": "Simulated sample list",
        "reason": "Invented entry for demonstration",
    },
    {
        "id": "SIM-SAN-0002",
        "name": "Elena Petrovna",
        "aliases": ["Elena Petrovaa"],
        "country": "Unknown",
        "list": "Simulated sample list",
        "reason": "Invented entry for demonstration",
    },
    {
        "id": "SIM-SAN-0003",
        "name": "Northwind Shell Holdings",
        "aliases": ["Northwind Shell"],
        "country": "Unknown",
        "list": "Simulated sample list",
        "reason": "Invented entry for demonstration",
    },
    {
        "id": "SIM-SAN-0004",
        "name": "Marcus Verdanti",
        "aliases": [],
        "country": "Unknown",
        "list": "Simulated sample list",
        "reason": "Invented entry for demonstration",
    },
    {
        "id": "SIM-SAN-0005",
        "name": "Atlas Fleet Rental Group",
        "aliases": ["Atlas Fleet Group"],
        "country": "Unknown",
        "list": "Simulated sample list",
        "reason": "Invented entry for demonstration",
    },
]


# --- core banking customers (simulated) ---------------------------------------
CUSTOMERS: list[dict[str, Any]] = [
    {
        "customer_id": "SIM-CUS-100001",
        "name": "Falcon Ridge Trading LLC",
        "segment": "Corporate",
        "kyc_status": "refresh_due",
        "last_refreshed": "2023-08-14",
        "risk_rating": "medium",
    },
    {
        "customer_id": "SIM-CUS-100002",
        "name": "Al Noor Logistics FZ-LLC",
        "segment": "Corporate",
        "kyc_status": "refresh_due",
        "last_refreshed": "2023-11-02",
        "risk_rating": "low",
    },
    {
        "customer_id": "SIM-CUS-100003",
        "name": "Dunes Technology Solutions",
        "segment": "SME",
        "kyc_status": "current",
        "last_refreshed": "2025-02-19",
        "risk_rating": "low",
    },
    {
        "customer_id": "SIM-CUS-100004",
        "name": "Sahara Green Contracting",
        "segment": "Corporate",
        "kyc_status": "blocked",
        "last_refreshed": "2022-05-30",
        "risk_rating": "high",
    },
    # Individuals, for use case 2: a salary certificate is written to a person's file. The
    # names match people the demo database seeds, so a salary case can find its customer.
    {
        "customer_id": "SIM-CUS-200001",
        "name": "Mariam Al Hashimi",
        "segment": "Retail",
        "kyc_status": "current",
        "last_refreshed": "2025-06-03",
        "risk_rating": "low",
    },
    {
        "customer_id": "SIM-CUS-200002",
        "name": "Priya Nair",
        "segment": "Retail",
        "kyc_status": "current",
        "last_refreshed": "2025-01-21",
        "risk_rating": "low",
    },
    {
        "customer_id": "SIM-CUS-200003",
        "name": "Daniel Osei",
        "segment": "Retail",
        "kyc_status": "current",
        "last_refreshed": "2024-11-09",
        "risk_rating": "medium",
    },
    {
        "customer_id": "SIM-CUS-200004",
        "name": "Hamad Al Suwaidi",
        "segment": "Retail",
        "kyc_status": "current",
        "last_refreshed": "2025-03-30",
        "risk_rating": "low",
    },
]
