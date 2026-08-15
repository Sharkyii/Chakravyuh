"""Temporal dataset splitting utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from src.generators import calibration as cal


@dataclass(slots=True)
class TemporalSplitConfig:
    """Configurable train/validation/test split proportions."""

    train_fraction: float = 0.60
    validation_fraction: float = 0.20
    test_fraction: float = 0.20
    start: datetime = cal.SIM_START
    end: datetime = cal.SIM_END

    def __post_init__(self) -> None:
        total = self.train_fraction + self.validation_fraction + self.test_fraction
        if abs(total - 1.0) > 1e-9:
            raise ValueError("temporal split fractions must sum to 1.0")
        if self.start >= self.end:
            raise ValueError("temporal split start must be before end")


@dataclass(slots=True)
class SplitWindow:
    name: str
    start: datetime
    end: datetime


@dataclass(slots=True)
class TemporalSplits:
    windows: dict[str, SplitWindow]
    transaction_ids: dict[str, set[str]]
    label_ids: dict[str, set[str]]


def split_windows(config: TemporalSplitConfig | None = None) -> dict[str, SplitWindow]:
    """Return deterministic temporal windows for train/validation/test."""
    cfg = config or TemporalSplitConfig()
    duration = cfg.end - cfg.start
    train_end = cfg.start + timedelta(seconds=duration.total_seconds() * cfg.train_fraction)
    validation_end = train_end + timedelta(
        seconds=duration.total_seconds() * cfg.validation_fraction
    )
    return {
        "train": SplitWindow("train", cfg.start, train_end),
        "validation": SplitWindow("validation", train_end, validation_end),
        "test": SplitWindow("test", validation_end, cfg.end),
    }


def assign_split(timestamp: datetime, windows: dict[str, SplitWindow]) -> str | None:
    """Return the split name for a timestamp, or None if outside all windows."""
    for name in ("train", "validation", "test"):
        window = windows[name]
        if window.start <= timestamp < window.end:
            return name
    return None


def temporal_split_transactions(
    transactions: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    config: TemporalSplitConfig | None = None,
) -> TemporalSplits:
    """Split transactions and labels by transaction timestamp, never randomly."""
    windows = split_windows(config)
    transaction_ids = {name: set() for name in windows}
    txn_to_split: dict[str, str] = {}
    for row in transactions:
        split_name = assign_split(row["timestamp"], windows)
        if split_name is not None:
            transaction_ids[split_name].add(row["txn_id"])
            txn_to_split[row["txn_id"]] = split_name

    label_ids = {name: set() for name in windows}
    for row in labels:
        split_name = txn_to_split.get(row["txn_id"])
        if split_name is not None:
            label_ids[split_name].add(row["txn_id"])

    return TemporalSplits(windows=windows, transaction_ids=transaction_ids, label_ids=label_ids)
