from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


Side = Literal["buy", "sell"]
TradeMode = Literal["isolated", "cross", "cash"]
OrderType = Literal["market", "limit"]
PositionSide = Literal["long", "short", "net"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Credentials:
    api_key: str
    api_secret: str
    passphrase: str

    def is_complete(self) -> bool:
        return bool(self.api_key and self.api_secret and self.passphrase)


@dataclass(frozen=True)
class OrderIntent:
    inst_id: str
    side: Side
    td_mode: TradeMode
    order_type: OrderType
    size: str
    notional_usdt: float
    leverage: int = 1
    pos_side: PositionSide | None = None
    reduce_only: bool = False
    client_order_id: str | None = None

    def to_okx_body(self) -> dict[str, str]:
        body: dict[str, str] = {
            "instId": self.inst_id,
            "tdMode": self.td_mode,
            "side": self.side,
            "ordType": self.order_type,
            "sz": self.size,
        }
        if self.pos_side and self.pos_side != "net":
            body["posSide"] = self.pos_side
        if self.reduce_only:
            body["reduceOnly"] = "true"
        if self.client_order_id:
            body["clOrdId"] = self.client_order_id
        return body


@dataclass(frozen=True)
class ExecutionState:
    available_balance_usdt: float
    api_healthy: bool = True
    last_stop_loss_at_utc: datetime | None = None
    now_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ExecutionResult:
    submitted: bool
    dry_run: bool
    simulated: bool
    intent: OrderIntent
    order_body: dict[str, str]
    risk_notes: tuple[str, ...]
    exchange_response: dict[str, Any] | None = None
    created_at_utc: str = field(default_factory=utc_now_iso)

    def public_dict(self) -> dict[str, Any]:
        return {
            "submitted": self.submitted,
            "dry_run": self.dry_run,
            "simulated": self.simulated,
            "order_body": dict(self.order_body),
            "risk_notes": list(self.risk_notes),
            "exchange_response": self.exchange_response,
            "created_at_utc": self.created_at_utc,
        }
