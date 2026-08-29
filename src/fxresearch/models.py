from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pandas import Timestamp


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class SignalCandidate:
    symbol: str
    side: Side
    signal_time: Timestamp
    entry_time: Timestamp
    entry_price: float
    stop_price: float
    target_price: float
    stop_distance: float
    spread_pips: float
    amdx_day: str


@dataclass
class Trade:
    symbol: str
    side: Side
    entry_time: Timestamp
    exit_time: Timestamp
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    r_multiple: float
    exit_reason: str
    amdx_day: str
