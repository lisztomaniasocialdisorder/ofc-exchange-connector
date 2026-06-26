# OFC Exchange Connector

Public review scope for the exchange API connector used by OFC Toolkit.

This repository is intentionally small. It only contains the boundary that reviewers should inspect for API-key handling, request signing, order submission, dry-run behavior, and basic risk checks. It does not contain the OFC AI model, strategy weights, private datasets, license server, customer dashboard, or payment code.

## Why This Exists

Trading software asks users to trust code that can talk to an exchange account. OFC does not want that trust to be based on slogans.

This connector is published so reviewers can verify:

- API credentials are read from the local environment and are not hard-coded.
- The connector does not include withdrawal endpoints.
- Orders are blocked by default unless live execution is explicitly enabled.
- Dry-run mode returns the exact payload that would be sent without sending it.
- The risk guard can enforce notional limits, leverage limits, capital buffer, cooldown, allowed instruments, and connection health checks.
- Logs and returned objects avoid printing API secrets.

## Scope

Included:

- OKX REST request signing.
- OKX authenticated request headers.
- OKX simulated trading header support.
- Public endpoint access.
- Account balance / position read helpers.
- Set leverage and place order helpers.
- A safe order executor with dry-run first behavior.
- A small risk guard that can reject unsafe order intents.
- Example scripts and unit tests.

Not included:

- AI model code.
- Signal generation logic.
- Strategy parameters.
- Training notebooks.
- Backtest result files.
- Customer license server.
- Payment or admin systems.
- Any real API key, passphrase, secret, token, database, or customer data.

## Safety Defaults

The connector is safe-by-default:

- `dry_run=True` by default.
- `enable_live_orders=False` by default.
- `simulated=True` by default for OKX.
- Missing credentials are allowed in dry-run examples.
- Live order submission requires both `dry_run=False` and `enable_live_orders=True`.
- Withdrawals are not implemented.

This code is still early-stage. It is published for review and testing, not as a promise of profitability or production readiness.

## Quick Start

Use Python 3.11 or newer.

```powershell
git clone https://github.com/lisztomaniasocialdisorder/ofc-exchange-connector.git
cd ofc-exchange-connector
python -m pip install -e .
python -m unittest
python examples/okx_dry_run.py
```

The dry-run example does not need an API key.

## Environment Variables

Live or simulated exchange requests that require authentication read credentials from your local environment:

```powershell
$env:OKX_API_KEY="your-key"
$env:OKX_API_SECRET="your-secret"
$env:OKX_API_PASSPHRASE="your-passphrase"
```

Recommended OKX API permissions:

- Read enabled.
- Trade enabled only after Testnet / Demo testing.
- Withdrawal disabled.
- IP whitelist enabled if your exchange account supports it.

Never commit `.env` files or real credentials.

## Dry-Run Example

```python
from ofc_exchange_connector import (
    ExecutionState,
    OKXConnector,
    OrderIntent,
    RiskPolicy,
)

connector = OKXConnector(
    risk_policy=RiskPolicy(
        max_notional_usdt=50,
        max_leverage=4,
        capital_buffer_ratio=0.20,
        cooldown_seconds=4 * 60 * 60,
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

print(result)
```

Because the connector defaults to dry-run mode, this returns the signed-order candidate payload without submitting it.

## Live Execution Checklist

Before live execution:

1. Read the code.
2. Run the unit tests.
3. Use an exchange Demo / Testnet environment first.
4. Create a dedicated API key with withdrawal disabled.
5. Set strict API permissions and IP whitelist.
6. Start with a very small notional amount.
7. Keep `max_notional_usdt`, `max_leverage`, `capital_buffer_ratio`, and `cooldown_seconds` conservative.

To make live order submission possible in your own local script, both conditions must be true:

```python
OKXConnector(dry_run=False, enable_live_orders=True)
```

If either one is missing, the connector will not place a live order.

## Risk Guard

The included `RiskPolicy` can reject an order when:

- API health is marked unhealthy.
- The instrument is not in the allowed list.
- The trade mode is not allowed.
- Requested notional is above `max_notional_usdt`.
- Requested leverage is above `max_leverage`.
- The account balance would violate the configured capital buffer.
- The cooldown window is still active.

These checks are not a guarantee against losses. They are a local safety layer that should be reviewed, tested, and customized before use.

## Security Notes For Reviewers

Things worth checking:

- `src/ofc_exchange_connector/okx.py` builds OKX signatures locally with HMAC-SHA256.
- `src/ofc_exchange_connector/okx.py` only sends authenticated headers to OKX endpoints requested by the caller.
- `src/ofc_exchange_connector/risk.py` rejects unsafe order intents before the executor can call `place_order`.
- `src/ofc_exchange_connector/models.py` keeps returned execution results free of credential fields.
- No file writes are used for API secrets.
- No network telemetry or external callback is implemented.

If you find an issue, please open a GitHub issue with:

- The affected file and line.
- The unsafe behavior.
- A minimal reproduction if possible.
- Whether it affects dry-run, simulated trading, or live trading.

## Status

Early public review version.

This repository does not claim third-party audit approval, public live-performance verification, or corporate legal backing. It exists so the API connector boundary can be inspected directly.
