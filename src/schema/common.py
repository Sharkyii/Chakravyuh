"""Shared types and constants used across all table schemas."""

from __future__ import annotations

from decimal import Decimal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# INR amounts as fixed-point decimal128(12, 2): up to ~10 billion rupees, paise precision.
Money = Decimal
AMOUNT_PRECISION = 12
AMOUNT_SCALE = 2
