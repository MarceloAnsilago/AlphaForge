from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import random
from typing import Any

from domain.strategy.normalizer import build_strategy_draft
from domain.strategy.spec import StrategyDraft
from domain.miner.space import MinerSearchSpace


OPPOSITE_OPERATOR_MAP = {
    "GREATER_THAN": "LESS_THAN",
    "LESS_THAN": "GREATER_THAN",
    "GREATER_OR_EQUAL": "LESS_OR_EQUAL",
    "LESS_OR_EQUAL": "GREATER_OR_EQUAL",
    "EQUAL": "NOT_EQUAL",
    "NOT_EQUAL": "EQUAL",
    "CROSS_UP": "CROSS_DOWN",
    "CROSS_DOWN": "CROSS_UP",
    "CROSS_AND_CLOSE_ABOVE": "CROSS_AND_CLOSE_BELOW",
    "CROSS_AND_CLOSE_BELOW": "CROSS_AND_CLOSE_ABOVE",
}


def _price_source(value: str) -> dict[str, Any]:
    return {"source_type": "price", "value": value, "candle_offset": 0}


def _fixed_source(value: float) -> dict[str, Any]:
    return {"source_type": "fixed", "value": float(value), "candle_offset": 0}


def _indicator_source(indicator_name: str, indicator_output: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": "indicator",
        "value": indicator_name,
        "indicator_name": indicator_name,
        "indicator_output": indicator_output,
        "parameters": deepcopy(parameters),
        "candle_offset": 0,
    }


@dataclass(slots=True)
class RandomStrategyGenerator:
    search_space: MinerSearchSpace
    seed: int | None = None
    _random: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def generate(self, candidate_index: int) -> StrategyDraft:
        direction = self._random.choice(self.search_space.directions)
        rule_count = self._random.randint(1, max(self.search_space.max_rules_per_strategy, 1))
        entry_rules = [self._generate_rule(direction, position=index, scope="entry") for index in range(rule_count)]
        exit_rules = [self._invert_rule(rule, position=index) for index, rule in enumerate(entry_rules)]

        return build_strategy_draft(
            name=f"Miner Candidate {candidate_index}",
            direction=direction,
            settings=deepcopy(self.search_space.settings),
            market=deepcopy(self.search_space.market),
            entry_rules=entry_rules,
            exit_rules=exit_rules,
            risk_management=deepcopy(self.search_space.risk_management),
        )

    def _generate_rule(self, direction: str, position: int, scope: str) -> dict[str, Any]:
        template_family = self._random.choice(self.search_space.template_families)
        connector = "SE" if position == 0 else self._random.choice(self.search_space.connectors)
        group_id = f"{scope}_group_0"
        metadata = {"side": direction, "family": template_family, "generated_by": "miner"}

        if template_family == "price_vs_ma":
            ma_name = self._random.choice(["SMA", "EMA"])
            period = self._random.randint(*self.search_space.period_ranges["ma_period"])
            operator = self._random.choice(["GREATER_THAN", "CROSS_UP"] if direction == "BUY" else ["LESS_THAN", "CROSS_DOWN"])
            return {
                "source_a": _price_source("close"),
                "operator": operator,
                "source_b": _indicator_source(ma_name, "Valor", {"period": period}),
                "connector": connector,
                "group_id": group_id,
                "metadata": metadata,
            }

        if template_family == "ma_crossover":
            ma_name = self._random.choice(["SMA", "EMA"])
            fast_period = self._random.randint(*self.search_space.period_ranges["fast_ma_period"])
            slow_period = self._random.randint(max(fast_period + 1, self.search_space.period_ranges["slow_ma_period"][0]), self.search_space.period_ranges["slow_ma_period"][1])
            operator = "CROSS_UP" if direction == "BUY" else "CROSS_DOWN"
            return {
                "source_a": _indicator_source(ma_name, "Valor", {"period": fast_period}),
                "operator": operator,
                "source_b": _indicator_source(ma_name, "Valor", {"period": slow_period}),
                "connector": connector,
                "group_id": group_id,
                "metadata": metadata,
            }

        if template_family == "rsi_level":
            period = self._random.randint(*self.search_space.period_ranges["rsi_period"])
            oversold = round(self._random.uniform(*self.search_space.float_ranges["oversold_level"]), 2)
            overbought = round(self._random.uniform(*self.search_space.float_ranges["overbought_level"]), 2)
            level = oversold if direction == "BUY" else overbought
            operator = "LESS_THAN" if direction == "BUY" else "GREATER_THAN"
            return {
                "source_a": _indicator_source("RSI (Relative Strength Index)", "Valor", {"period": period}),
                "operator": operator,
                "source_b": _fixed_source(level),
                "connector": connector,
                "group_id": group_id,
                "metadata": {**metadata, "oversold": oversold, "overbought": overbought},
            }

        if template_family == "macd_cross":
            fast_period = self._random.randint(6, 15)
            slow_period = self._random.randint(max(fast_period + 5, 18), 35)
            signal_period = self._random.randint(4, 12)
            operator = "CROSS_UP" if direction == "BUY" else "CROSS_DOWN"
            params = {"fast_ema": fast_period, "slow_ema": slow_period, "signal": signal_period}
            return {
                "source_a": _indicator_source("MACD", "Linha MACD", params),
                "operator": operator,
                "source_b": _indicator_source("MACD", "Linha de sinal", params),
                "connector": connector,
                "group_id": group_id,
                "metadata": metadata,
            }

        period = self._random.randint(*self.search_space.period_ranges["bbands_period"])
        deviation = round(self._random.uniform(*self.search_space.float_ranges["bbands_deviation"]), 2)
        output = "Inferior" if direction == "BUY" else "Superior"
        operator = "LESS_THAN" if direction == "BUY" else "GREATER_THAN"
        return {
            "source_a": _price_source("close"),
            "operator": operator,
            "source_b": _indicator_source("Bandas de Bollinger", output, {"period": period, "deviation": deviation}),
            "connector": connector,
            "group_id": group_id,
            "metadata": metadata,
        }

    def _invert_rule(self, rule: dict[str, Any], position: int) -> dict[str, Any]:
        metadata = {**deepcopy(rule.get("metadata", {})), "generated_from": "entry_inverse"}
        return {
            "source_a": deepcopy(rule["source_a"]),
            "operator": OPPOSITE_OPERATOR_MAP.get(rule["operator"], rule["operator"]),
            "source_b": deepcopy(rule["source_b"]),
            "connector": "SE" if position == 0 else rule.get("connector", "E"),
            "group_id": rule.get("group_id", "exit_group_0").replace("entry_", "exit_"),
            "metadata": metadata,
        }
