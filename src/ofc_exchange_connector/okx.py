from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Credentials, ExecutionResult, ExecutionState, OrderIntent
from .risk import RiskPolicy


def iso_utc_now_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def load_okx_credentials_from_env() -> Credentials | None:
    api_key = os.getenv("OKX_API_KEY", "")
    api_secret = os.getenv("OKX_API_SECRET", "")
    passphrase = os.getenv("OKX_API_PASSPHRASE", "")
    if not (api_key and api_secret and passphrase):
        return None
    return Credentials(api_key=api_key, api_secret=api_secret, passphrase=passphrase)


@dataclass
class OKXClient:
    credentials: Credentials | None = None
    base_url: str = "https://www.okx.com"
    simulated: bool = True
    timeout_seconds: int = 20
    max_retries: int = 3

    def sign(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        if self.credentials is None or not self.credentials.is_complete():
            raise RuntimeError("OKX credentials are required for signing.")
        prehash = f"{timestamp}{method.upper()}{request_path}{body}"
        digest = hmac.new(
            self.credentials.api_secret.encode("utf-8"),
            prehash.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _headers(self, timestamp: str, signature: str) -> dict[str, str]:
        if self.credentials is None:
            raise RuntimeError("OKX credentials are required for authenticated headers.")
        headers = {
            "OK-ACCESS-KEY": self.credentials.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.credentials.passphrase,
            "Content-Type": "application/json",
        }
        if self.simulated:
            headers["x-simulated-trading"] = "1"
        return headers

    def request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        params = params or {}
        body = body or {}
        query = f"?{urlencode(params)}" if params and method == "GET" else ""
        request_path = f"{path}{query}"
        url = f"{self.base_url}{request_path}"
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if method == "POST" else ""

        headers: dict[str, str] = {}
        if auth:
            timestamp = iso_utc_now_ms()
            signature = self.sign(timestamp, method, request_path, body_str)
            headers = self._headers(timestamp, signature)

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                payload = body_str.encode("utf-8") if method == "POST" else None
                req = Request(url=url, data=payload, method=method, headers=headers)
                with urlopen(req, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                retryable = exc.code == 429 or "50011" in raw
                last_error = RuntimeError(f"OKX HTTP {exc.code} {request_path}: {raw}")
                if retryable and attempt < self.max_retries - 1:
                    time.sleep(min(8.0, 0.5 * (2**attempt)))
                    continue
                raise last_error from exc
            except (TimeoutError, URLError) as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    time.sleep(min(8.0, 0.5 * (2**attempt)))
                    continue
                raise RuntimeError(f"OKX request failed: {request_path}") from exc

        raise RuntimeError(f"OKX request failed: {request_path}") from last_error

    def public_time(self) -> dict[str, Any]:
        return self.request("GET", "/api/v5/public/time", auth=False)

    def get_balance(self, currency: str = "USDT") -> dict[str, Any]:
        return self.request("GET", "/api/v5/account/balance", params={"ccy": currency}, auth=True)

    def get_positions(self, inst_type: str = "SWAP", inst_id: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"instType": inst_type}
        if inst_id:
            params["instId"] = inst_id
        return self.request("GET", "/api/v5/account/positions", params=params, auth=True)

    def set_leverage(self, inst_id: str, leverage: int, td_mode: str, pos_side: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "instId": inst_id,
            "lever": str(int(leverage)),
            "mgnMode": td_mode,
        }
        if pos_side and pos_side != "net":
            body["posSide"] = pos_side
        return self.request("POST", "/api/v5/account/set-leverage", body=body, auth=True)

    def place_order(self, intent: OrderIntent) -> dict[str, Any]:
        return self.request("POST", "/api/v5/trade/order", body=intent.to_okx_body(), auth=True)


@dataclass
class OKXConnector:
    client: OKXClient | None = None
    risk_policy: RiskPolicy = RiskPolicy()
    dry_run: bool = True
    enable_live_orders: bool = False

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = OKXClient(credentials=load_okx_credentials_from_env())

    def submit_order(self, intent: OrderIntent, state: ExecutionState) -> ExecutionResult:
        risk_notes = self.risk_policy.check(intent, state)
        body = intent.to_okx_body()

        if self.dry_run or not self.enable_live_orders:
            return ExecutionResult(
                submitted=False,
                dry_run=True,
                simulated=bool(self.client and self.client.simulated),
                intent=intent,
                order_body=body,
                risk_notes=risk_notes,
                exchange_response={"dry_run": True, "reason": "live execution disabled"},
            )

        if self.client is None:
            raise RuntimeError("OKX client is required for live execution.")
        if self.client.credentials is None or not self.client.credentials.is_complete():
            raise RuntimeError("Complete OKX credentials are required for live execution.")

        if intent.leverage > 1:
            self.client.set_leverage(intent.inst_id, intent.leverage, intent.td_mode, intent.pos_side)

        response = self.client.place_order(intent)
        return ExecutionResult(
            submitted=True,
            dry_run=False,
            simulated=self.client.simulated,
            intent=intent,
            order_body=body,
            risk_notes=risk_notes,
            exchange_response=response,
        )
