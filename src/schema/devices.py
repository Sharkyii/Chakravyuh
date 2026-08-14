"""Devices table — not in docs/data-schema-v1.md's seven-table list, added
by explicit decision (see conversation) because transactions.device_id is
"fk -> devices" and the master brief requires a device population generator
(primary device stability, household sharing, upgrades/loss, fingerprint
fields) as its own entity alongside parties and merchants.

Device replacement (upgrade/loss) is modelled as a new device row with
`replaced_device_id` pointing at the old one, rather than mutating history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pyarrow as pa

from src.schema.enums import DeviceType


@dataclass(slots=True)
class Device:
    device_id: str
    primary_party_id: str  # fk -> parties; the device's main/registered user
    device_type: DeviceType
    os_name: str
    os_version: str
    device_model: str
    fingerprint_hash: str  # stable hash of hardware/software attributes
    is_emulator: bool
    is_shared_household_device: bool
    first_seen_at: datetime
    last_seen_at: datetime
    retired_at: Optional[datetime]
    replaced_device_id: Optional[str]  # fk -> devices; prior device in the chain


def arrow_schema() -> pa.Schema:
    ts_ms_ist = pa.timestamp("ms", tz="Asia/Kolkata")
    return pa.schema(
        [
            pa.field("device_id", pa.string(), nullable=False),
            pa.field("primary_party_id", pa.string(), nullable=False),
            pa.field("device_type", pa.string(), nullable=False),
            pa.field("os_name", pa.string(), nullable=False),
            pa.field("os_version", pa.string(), nullable=False),
            pa.field("device_model", pa.string(), nullable=False),
            pa.field("fingerprint_hash", pa.string(), nullable=False),
            pa.field("is_emulator", pa.bool_(), nullable=False),
            pa.field("is_shared_household_device", pa.bool_(), nullable=False),
            pa.field("first_seen_at", ts_ms_ist, nullable=False),
            pa.field("last_seen_at", ts_ms_ist, nullable=False),
            pa.field("retired_at", ts_ms_ist, nullable=True),
            pa.field("replaced_device_id", pa.string(), nullable=True),
        ]
    )
