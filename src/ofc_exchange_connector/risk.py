from __future__ import annotations

from dataclasses import dataclass, field

from .models import ExecutionState, OrderIntent, TradeMode


class RiskRejected(RuntimeError):
    """Raised when the local risk guard rejects an order intent."""


@dataclass(frozen=True)
class RiskPolicy:
    max_notional_usdt: float = 50.0
    max_leverage: int = 4
    capital_buffer_ratio: float = 0.20
    cooldown_seconds: int = 4 * 60 * 60
    allowed_inst_ids: tuple[str, ...] = ("BTC-USDT-SWAP",)
    allowed_trade_modes: tuple[TradeMode, ...] = ("isolated",)
    min_balance_after_buffer_usdt: float = 0.0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def check(self, intent: OrderIntent, state: ExecutionState) -> tuple[str, ...]:
        notes: list[str] = list(self.notes)

        if not state.api_healthy:
            raise RiskRejected("API health check failed; order blocked.")

        if self.allowed_inst_ids and intent.inst_id not in self.allowed_inst_ids:
            raise RiskRejected(f"Instrument not allowed: {intent.inst_id}")

        if intent.td_mode not in self.allowed_trade_modes:
            raise RiskRejected(f"Trade mode not allowed: {intent.td_mode}")

        if intent.notional_usdt <= 0:
            raise RiskRejected("Notional must be greater than zero.")

        if intent.notional_usdt > self.max_notional_usdt:
            raise RiskRejected(
                f"Notional {intent.notional_usdt} exceeds max {self.max_notional_usdt} USDT."
            )

        if intent.leverage < 1:
            raise RiskRejected("Leverage must be at least 1x.")

        if intent.leverage > self.max_leverage:
            raise RiskRejected(f"Leverage {intent.leverage}x exceeds max {self.max_leverage}x.")

        required_buffer = max(
            state.available_balance_usdt * self.capital_buffer_ratio,
            self.min_balance_after_buffer_usdt,
        )
        remaining_after_order = state.available_balance_usdt - intent.notional_usdt
        if remaining_after_order < required_buffer:
            raise RiskRejected(
                "Capital buffer would be violated: "
                f"remaining={remaining_after_order:.2f}, required_buffer={required_buffer:.2f}."
            )
        notes.append(f"capital buffer preserved: {required_buffer:.2f} USDT")

        if state.last_stop_loss_at_utc is not None:
            elapsed = (state.now_utc - state.last_stop_loss_at_utc).total_seconds()
            if elapsed < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - elapsed)
                raise RiskRejected(f"Cooldown active; {remaining} seconds remaining.")
            notes.append("cooldown window cleared")

        return tuple(notes)
