from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from ofc_exchange_connector import ExecutionState, OrderIntent, RiskPolicy, RiskRejected


def sample_intent(**overrides):
    payload = {
        "inst_id": "BTC-USDT-SWAP",
        "side": "buy",
        "td_mode": "isolated",
        "order_type": "market",
        "size": "1",
        "notional_usdt": 25.0,
        "leverage": 2,
    }
    payload.update(overrides)
    return OrderIntent(**payload)


class RiskPolicyTest(unittest.TestCase):
    def test_accepts_safe_intent(self) -> None:
        policy = RiskPolicy(max_notional_usdt=50, max_leverage=4, capital_buffer_ratio=0.2)
        notes = policy.check(sample_intent(), ExecutionState(available_balance_usdt=200))
        self.assertTrue(any("capital buffer preserved" in note for note in notes))

    def test_rejects_large_notional(self) -> None:
        policy = RiskPolicy(max_notional_usdt=50)
        with self.assertRaises(RiskRejected):
            policy.check(sample_intent(notional_usdt=75), ExecutionState(available_balance_usdt=200))

    def test_rejects_high_leverage(self) -> None:
        policy = RiskPolicy(max_leverage=4)
        with self.assertRaises(RiskRejected):
            policy.check(sample_intent(leverage=10), ExecutionState(available_balance_usdt=200))

    def test_rejects_buffer_violation(self) -> None:
        policy = RiskPolicy(max_notional_usdt=100, capital_buffer_ratio=0.2)
        with self.assertRaises(RiskRejected):
            policy.check(sample_intent(notional_usdt=90), ExecutionState(available_balance_usdt=100))

    def test_rejects_cooldown(self) -> None:
        now = datetime.now(timezone.utc)
        policy = RiskPolicy(cooldown_seconds=4 * 60 * 60)
        with self.assertRaises(RiskRejected):
            policy.check(
                sample_intent(),
                ExecutionState(
                    available_balance_usdt=200,
                    now_utc=now,
                    last_stop_loss_at_utc=now - timedelta(minutes=30),
                ),
            )


if __name__ == "__main__":
    unittest.main()
