import json
import uuid
from typing import Any, Dict, List, Optional

import ccxt
from common.db import fetch_df, execute
from common import LoggerFactory
from ..main.tenant_context import get_current_tenant


logger = LoggerFactory.get_logger("live_trading_service")


class LiveTradingService:
    """
    Real-time trading service backed by ccxt, scoped per tenant.
    """

    SUPPORTED_EXCHANGES = {
        "binance",
        "bybit",
        "okx",
        "coinbase",
        "kraken",
        "bitfinex",
        "kucoin",
        "bitget",
    }

    def __init__(self, tenant_id: Optional[str] = None):
        self.tenant_id = tenant_id or get_current_tenant()

    # ------------------------------------------------------------------
    # Account management helpers
    # ------------------------------------------------------------------
    def list_accounts(self) -> List[Dict[str, Any]]:
        df = fetch_df(
            """
            SELECT id, exchange, label, is_active, created_at, updated_at
            FROM tenant_exchange_accounts
            WHERE tenant_id = :tenant_id
            ORDER BY created_at ASC
            """,
            tenant_id=self.tenant_id,
        )
        accounts = df.to_dict(orient="records") if not df.empty else []
        for item in accounts:
            item["has_credentials"] = True
            item["api_key_preview"] = item.get("api_key_preview") or "已配置"
        return accounts

    def get_account(self, account_id: str, include_secret: bool = False) -> Dict[str, Any]:
        df = fetch_df(
            """
            SELECT id, tenant_id, exchange, label, api_key, api_secret, api_passphrase,
                   extra, is_active, created_at, updated_at
            FROM tenant_exchange_accounts
            WHERE id = :id AND tenant_id = :tenant_id
            """,
            id=account_id,
            tenant_id=self.tenant_id,
        )
    if df.empty:
        raise ValueError("Account not found")

    record = df.iloc[0].to_dict()
    extra = record.get("extra")
        if isinstance(extra, str):
            try:
                record["extra"] = json.loads(extra)
            except json.JSONDecodeError:
                record["extra"] = {}

    if not include_secret:
        record["api_key_preview"] = self._mask_secret(record.get("api_key"))
        record["has_passphrase"] = bool(record.get("api_passphrase"))
        record.pop("api_key", None)
        record.pop("api_secret", None)
        record.pop("api_passphrase", None)

        return record

    def create_account(
        self,
        exchange: str,
        api_key: str,
        api_secret: str,
        label: Optional[str] = None,
        api_passphrase: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        self._validate_exchange(exchange)
        account_id = str(uuid.uuid4())
        execute(
            """
            INSERT INTO tenant_exchange_accounts
            (id, tenant_id, exchange, label, api_key, api_secret, api_passphrase, extra, is_active, created_at, updated_at)
            VALUES
            (:id, :tenant_id, :exchange, :label, :api_key, :api_secret, :api_passphrase, :extra::jsonb, :is_active, NOW(), NOW())
            """,
            id=account_id,
            tenant_id=self.tenant_id,
            exchange=exchange,
            label=label,
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
            extra=json.dumps(extra or {}),
            is_active=is_active,
        )
        logger.info("Created trading account %s for tenant %s", account_id, self.tenant_id)
        return self.get_account(account_id)

    def update_account(
        self,
        account_id: str,
        exchange: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        label: Optional[str] = None,
        api_passphrase: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        df = fetch_df(
            "SELECT id FROM tenant_exchange_accounts WHERE id = :id AND tenant_id = :tenant_id",
            id=account_id,
            tenant_id=self.tenant_id,
        )
        if df.empty:
            raise ValueError("Account not found")

        fields = []
        params: Dict[str, Any] = {"id": account_id, "tenant_id": self.tenant_id}

        if exchange:
            self._validate_exchange(exchange)
            fields.append("exchange = :exchange")
            params["exchange"] = exchange
        if label is not None:
            fields.append("label = :label")
            params["label"] = label
        if api_key is not None:
            fields.append("api_key = :api_key")
            params["api_key"] = api_key
        if api_secret is not None:
            fields.append("api_secret = :api_secret")
            params["api_secret"] = api_secret
        if api_passphrase is not None:
            fields.append("api_passphrase = :api_passphrase")
            params["api_passphrase"] = api_passphrase
        if extra is not None:
            fields.append("extra = :extra::jsonb")
            params["extra"] = json.dumps(extra)
        if is_active is not None:
            fields.append("is_active = :is_active")
            params["is_active"] = is_active

        if not fields:
            return self.get_account(account_id)

        fields.append("updated_at = NOW()")
        sql = f"""
        UPDATE tenant_exchange_accounts
        SET {', '.join(fields)}
        WHERE id = :id AND tenant_id = :tenant_id
        """
        execute(sql, **params)
        logger.info("Updated trading account %s for tenant %s", account_id, self.tenant_id)
        return self.get_account(account_id)

    def delete_account(self, account_id: str) -> None:
        affected = execute(
            "DELETE FROM tenant_exchange_accounts WHERE id = :id AND tenant_id = :tenant_id",
            id=account_id,
            tenant_id=self.tenant_id,
        )
        if affected == 0:
            raise ValueError("Account not found")
        logger.info("Deleted trading account %s for tenant %s", account_id, self.tenant_id)

    # ------------------------------------------------------------------
    # Trading operations
    # ------------------------------------------------------------------
    def test_connection(self, account_id: str) -> Dict[str, Any]:
        account = self.get_account(account_id, include_secret=True)
        client = self._build_exchange_client(account)
        try:
            client.check_required_credentials()
            # Use a lightweight call - time sync may not require auth but ensures connectivity.
            server_time = client.milliseconds()
            return {"success": True, "server_time": server_time}
        except Exception as exc:
            logger.error("Connection test failed for account %s: %s", account_id, exc)
            raise

    def fetch_balances(self, account_id: str) -> Dict[str, Any]:
        account = self.get_account(account_id, include_secret=True)
        client = self._build_exchange_client(account)
        balances = client.fetch_balance()
        return balances

    def fetch_open_orders(self, account_id: str, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        account = self.get_account(account_id, include_secret=True)
        client = self._build_exchange_client(account)
        orders = client.fetch_open_orders(symbol)
        return orders

    def place_order(
        self,
        account_id: str,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        account = self.get_account(account_id, include_secret=True)
        client = self._build_exchange_client(account)
        ccxt_params = params or {}

        if order_type.lower() == "market":
            order = client.create_order(symbol, order_type, side, amount, None, ccxt_params)
        else:
            if price is None:
                raise ValueError("Price is required for limit orders")
            order = client.create_order(symbol, order_type, side, amount, price, ccxt_params)
        return order

    def cancel_order(
        self,
        account_id: str,
        order_id: str,
        symbol: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        account = self.get_account(account_id, include_secret=True)
        client = self._build_exchange_client(account)
        result = client.cancel_order(order_id, symbol, params or {})
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _validate_exchange(self, exchange: str) -> None:
        if exchange not in self.SUPPORTED_EXCHANGES:
            raise ValueError(f"Unsupported exchange '{exchange}'. Supported: {sorted(self.SUPPORTED_EXCHANGES)}")

    def _build_exchange_client(self, account: Dict[str, Any]):
        exchange_id = account["exchange"]
        if exchange_id not in ccxt.exchanges:
            raise ValueError(f"ccxt does not support exchange '{exchange_id}'")

        exchange_class = getattr(ccxt, exchange_id)
        extra = account.get("extra") or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except json.JSONDecodeError:
                extra = {}

        config = {
            "apiKey": account.get("api_key"),
            "secret": account.get("api_secret"),
            "enableRateLimit": True,
        }
        if account.get("api_passphrase"):
            # ccxt uses 'password' for passphrase (e.g., OKX, Coinbase Pro)
            config["password"] = account["api_passphrase"]

        if isinstance(extra, dict):
            config.update(extra)

        client = exchange_class(config)
        return client

    @staticmethod
    def _mask_secret(secret: Optional[str]) -> Optional[str]:
        if not secret:
            return None
        if len(secret) <= 4:
            return "*" * len(secret)
        return f"{secret[:2]}***{secret[-2:]}"
