from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PairRule:
    spread_max_pips: float
    max_stop_pips: float
    pip_size: float


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    timezone: str
    day_start: str
    asian_start: str
    asian_end: str
    trading_end: str
    closeback_max_fraction: float
    midpoint_reclaim_invalidates: bool
    setup_expiry_minutes: int
    atr_period: int
    atr_multiplier: float
    target_r: float
    max_trades_per_day: int
    daily_realised_loss_stop_r: float
    one_trade_per_pair_per_day: bool
    pair_rules: dict[str, PairRule]


def load_config(path: str | Path) -> StrategyConfig:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    pair_rules = {
        symbol: PairRule(**params)
        for symbol, params in raw["pair_rules"].items()
    }
    return StrategyConfig(
        name=raw["strategy"]["name"],
        timezone=raw["strategy"]["timezone"],
        day_start=raw["sessions"]["day_start"],
        asian_start=raw["sessions"]["asian_start"],
        asian_end=raw["sessions"]["asian_end"],
        trading_end=raw["sessions"]["trading_end"],
        closeback_max_fraction=raw["signal"]["closeback_max_fraction"],
        midpoint_reclaim_invalidates=raw["signal"]["midpoint_reclaim_invalidates"],
        setup_expiry_minutes=raw["signal"]["setup_expiry_minutes"],
        atr_period=raw["risk"]["atr_period"],
        atr_multiplier=raw["risk"]["atr_multiplier"],
        target_r=raw["risk"]["target_r"],
        max_trades_per_day=raw["risk"]["max_trades_per_day"],
        daily_realised_loss_stop_r=raw["risk"]["daily_realised_loss_stop_r"],
        one_trade_per_pair_per_day=raw["risk"]["one_trade_per_pair_per_day"],
        pair_rules=pair_rules,
    )
