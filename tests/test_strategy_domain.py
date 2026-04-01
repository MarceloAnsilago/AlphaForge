from __future__ import annotations

import unittest

from domain.strategy.normalizer import build_strategy_draft, normalize_strategy
from domain.strategy.spec import STRATEGY_DRAFT_VERSION, STRATEGY_SPEC_VERSION
from domain.strategy.validator import StrategyValidationError


class StrategyDomainTests(unittest.TestCase):
    def test_builder_payload_is_strategy_draft(self) -> None:
        draft = build_strategy_draft(
            name="Teste",
            direction="BUY",
            settings={"initial_volume": 1.0},
            market={"symbol": "EURUSD"},
            entry_rules=[],
            exit_rules=[],
            risk_management={"stop": {"type": "NONE", "value": 0.0}, "take": {"type": "NONE", "value": 0.0}},
        ).to_dict()

        self.assertEqual(draft["version"], STRATEGY_DRAFT_VERSION)
        self.assertEqual(draft["name"], "Teste")

    def test_normalizer_converts_draft_to_strategy_spec(self) -> None:
        draft = {
            "version": STRATEGY_DRAFT_VERSION,
            "name": "Teste",
            "direction": "buy",
            "settings": {"initial_volume": 1.0},
            "market": {"symbol": "EURUSD"},
            "entry_rules": [
                {
                    "source_a": {"source_type": "price", "value": "close"},
                    "operator": "greater_than",
                    "source_b": {"source_type": "fixed", "value": 1.0},
                    "metadata": {"side": "buy"},
                }
            ],
            "exit_rules": [],
            "risk_management": {"stop": {"type": "NONE", "value": 0.0}, "take": {"type": "NONE", "value": 0.0}},
        }

        spec = normalize_strategy(draft)

        self.assertEqual(spec.version, STRATEGY_SPEC_VERSION)
        self.assertEqual(spec.direction, "BUY")
        self.assertEqual(spec.entry_rules[0].operator, "GREATER_THAN")
        self.assertEqual(spec.entry_rules[0].metadata["side"], "BUY")

    def test_validator_rejects_invalid_operator(self) -> None:
        draft = {
            "name": "Teste",
            "direction": "BUY",
            "settings": {"initial_volume": 1.0},
            "market": {"symbol": "EURUSD"},
            "entry_rules": [
                {
                    "source_a": {"source_type": "price", "value": "close"},
                    "operator": "INVALID",
                    "source_b": {"source_type": "fixed", "value": 1.0},
                }
            ],
            "exit_rules": [],
            "risk_management": {"stop": {"type": "NONE", "value": 0.0}, "take": {"type": "NONE", "value": 0.0}},
        }

        with self.assertRaises(StrategyValidationError):
            normalize_strategy(draft)


if __name__ == "__main__":
    unittest.main()
