from __future__ import annotations

import unittest

from ofc_exchange_connector import Credentials, ExecutionState, OKXClient, OKXConnector, OrderIntent


class OKXClientTest(unittest.TestCase):
    def test_signature_is_deterministic(self) -> None:
        client = OKXClient(
            credentials=Credentials(
                api_key="key",
                api_secret="secret",
                passphrase="pass",
            )
        )
        signature = client.sign(
            "2020-12-08T09:08:57.715Z",
            "GET",
            "/api/v5/account/balance?ccy=BTC",
            "",
        )
        self.assertEqual(signature, "wpDvCwYCprcMQsQkxWJiWy+YADoQE4ep+OEKKLimMoY=")

    def test_dry_run_does_not_require_credentials(self) -> None:
        connector = OKXConnector()
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
            ExecutionState(available_balance_usdt=200),
        )
        self.assertFalse(result.submitted)
        self.assertTrue(result.dry_run)
        self.assertEqual(result.order_body["instId"], "BTC-USDT-SWAP")


if __name__ == "__main__":
    unittest.main()
