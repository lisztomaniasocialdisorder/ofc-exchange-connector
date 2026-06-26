from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ofc_exchange_connector import ExecutionState, OKXConnector, OrderIntent, RiskPolicy


def main() -> None:
    connector = OKXConnector(
        risk_policy=RiskPolicy(
            max_notional_usdt=50,
            max_leverage=4,
            capital_buffer_ratio=0.20,
            cooldown_seconds=4 * 60 * 60,
            allowed_inst_ids=("BTC-USDT-SWAP",),
        )
    )

    result = connector.submit_order(
        OrderIntent(
            inst_id="BTC-USDT-SWAP",
            side="buy",
            td_mode="isolated",
            order_type="market",
            size="1",
            notional_usdt=25,
            leverage=2,
        ),
        ExecutionState(
            available_balance_usdt=200,
            api_healthy=True,
        ),
    )

    print(result.public_dict())


if __name__ == "__main__":
    main()
