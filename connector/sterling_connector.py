import clr
import os
import logging
import asyncio
from pathlib import Path

# .NET helpers
import System
from System.Reflection import Assembly

from .session_manager import SessionManager

LOG = logging.getLogger("sterling_connector")

# --- Load the vendor DLL ---
DLL_PATH = Path(__file__).resolve().parents[1] / "SterlingWrapper" / "SterlingWrapper.dll"
if not DLL_PATH.exists():
    raise FileNotFoundError(f"SterlingWrapper.dll not found at {DLL_PATH}")

asm = Assembly.LoadFile(str(DLL_PATH))

# Try to get the Connector type in multiple robust ways.
ConnectorType = None
try:
    # Preferred: pythonnet namespace import
    from SterlingWrapper import Connector as _py_connector  # type: ignore
    ConnectorType = _py_connector
    LOG.info("SterlingWrapper.Connector loaded via python import (callable).")
except Exception:
    # Fallback: search types in assembly for exact fullname
    for t in asm.GetTypes():
        if t.FullName == "SterlingWrapper.Connector":
            ConnectorType = t  # This will be a System.Type / RuntimeType
            LOG.info("SterlingWrapper.Connector resolved via Assembly.GetTypes() (System.Type).")
            break

if ConnectorType is None:
    # Final fallback: try getattr on imported module
    try:
        import SterlingWrapper as _mod  # type: ignore
        if hasattr(_mod, "Connector"):
            ConnectorType = getattr(_mod, "Connector")
            LOG.info("SterlingWrapper.Connector loaded via module getattr.")
    except Exception:
        pass

if ConnectorType is None:
    raise ImportError(
        "Could not resolve Connector type from SterlingWrapper.dll. "
        "Run inspect_dll.py to confirm available types."
    )


class SterlingConnector:
    """
    Wrapper around vendor SterlingWrapper.Connector. Handles safe instantiation
    whether the Connector was exposed as a Python-callable class or only as a System.Type.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.conn = None
        # Instantiate the underlying connector object properly depending on type
        try:
            # Case A: ConnectorType is a normal python-callable (pythonnet-exposed type/class)
            if callable(ConnectorType):
                # Example: from SterlingWrapper import Connector -> Connector is callable
                self.conn = ConnectorType()
                LOG.info("Instantiated SterlingWrapper.Connector via direct call.")
            else:
                # Case B: ConnectorType is a System.Type (RuntimeType). Use Activator to create instance.
                # System.Activator.CreateInstance expects a System.Type
                self.conn = System.Activator.CreateInstance(ConnectorType)
                LOG.info("Instantiated SterlingWrapper.Connector via System.Activator.CreateInstance.")
        except Exception as e:
            LOG.exception("Failed to instantiate SterlingWrapper Connector: %s", e)
            raise

    # ----------------------------
    # Account / positions
    # ----------------------------
    def get_accounts(self):
        try:
            accts = self.conn.GetAccounts()
            if isinstance(accts, str):
                accounts = [a.strip() for a in accts.split(",") if a.strip()]
            else:
                try:
                    accounts = list(accts)
                except Exception:
                    accounts = [str(accts)]
            self.session_manager.set_session("sterling-session", accounts)
            return accounts
        except Exception as e:
            LOG.exception("get_accounts error: %s", e)
            return []

    def all_positions(self, account: str):
        try:
            raw = self.conn.AllPositions(account)
            if raw is None:
                return []
            parts = str(raw).split(";")
            return [p for p in parts if p.strip()]
        except Exception as e:
            LOG.exception("all_positions failed: %s", e)
            return []

    # ----------------------------
    # Order placement (async wrappers)
    # ----------------------------
    async def send_market(self, order: dict):
        return await asyncio.to_thread(self._send_market, order)

    def _send_market(self, order: dict):
        idem = order.get("idempotencyKey")
        if idem:
            prev = self.session_manager.is_idempotent(idem)
            if prev:
                return {"status": "submitted", "details": "idempotent", "orderId": prev}

        try:
            res = self.conn.Sendmarket(
                order["account"],
                order["symbol"],
                int(order["qty"]),
                int(order.get("visible_qty", order["qty"])),
                order.get("route", ""),
                order["side"],
                order.get("tif", "D"),
            )
            oid, status = str(res).split(";")
            if idem:
                self.session_manager.store_idempotent(idem, oid)
            return {"status": status, "orderId": oid}
        except Exception as e:
            LOG.exception("Sendmarket failed: %s", e)
            return {"status": "error", "details": str(e)}

    async def send_limit(self, order: dict):
        return await asyncio.to_thread(self._send_limit, order)

    def _send_limit(self, order: dict):
        idem = order.get("idempotencyKey")
        if idem:
            prev = self.session_manager.is_idempotent(idem)
            if prev:
                return {"status": "submitted", "details": "idempotent", "orderId": prev}
        try:
            disp = int(order.get("display", 0))
            res = self.conn.Sendlimit(
                order["account"],
                order["symbol"],
                int(order["qty"]),
                disp,
                float(order["price"]),
                order.get("route", ""),
                order["side"],
                order.get("tif", "D"),
            )
            oid, status = str(res).split(";")
            if idem:
                self.session_manager.store_idempotent(idem, oid)
            return {"status": status, "orderId": oid}
        except Exception as e:
            LOG.exception("Sendlimit failed: %s", e)
            return {"status": "error", "details": str(e)}

    async def send_stop_limit(self, order: dict):
        return await asyncio.to_thread(self._send_stop_limit, order)

    def _send_stop_limit(self, order: dict):
        try:
            disp = int(order.get("display", 0))
            res = self.conn.Sendstoplimit(
                order["account"],
                order["symbol"],
                int(order["qty"]),
                disp,
                order.get("route", ""),
                float(order["stop_price"]),
                float(order["limit_price"]),
                order["side"],
                order.get("tif", "D"),
            )
            oid, status = str(res).split(";")
            return {"status": status, "orderId": oid}
        except Exception as e:
            LOG.exception("Sendstoplimit failed: %s", e)
            return {"status": "error", "details": str(e)}

    # ----------------------------
    # Cancels / status / utility
    # ----------------------------
    def replace_limit_order(self, ordId, qty, price):
        try:
            res = self.conn.ReplaceOrder(ordId, qty, price)
            new_id, status = str(res).split(";")
            return {"status": status, "orderId": new_id}
        except Exception as e:
            LOG.exception("ReplaceOrder failed: %s", e)
            return {"status": "error", "details": str(e)}

    def cancel_order(self, account: str, ordID: str):
        try:
            self.conn.CancelOrder(account, ordID)
            return {"status": "cancelRequested", "orderId": ordID}
        except Exception as e:
            LOG.exception("CancelOrder failed: %s", e)
            return {"status": "error", "details": str(e)}

    def cancel_all_symbol_orders(self, account: str, symbol: str):
        if not symbol:
            return {"status": "error", "details": "symbol empty"}
        try:
            self.conn.CancellAllSymbol(symbol, account)
            return {"status": "cancelAllSymbolRequested", "symbol": symbol}
        except Exception as e:
            LOG.exception("CancellAllSymbol failed: %s", e)
            return {"status": "error", "details": str(e)}

    def cancel_all(self, account: str):
        try:
            self.conn.CancellAll(account)
            return {"status": "cancelAllRequested", "account": account}
        except Exception as e:
            LOG.exception("CancellAll failed: %s", e)
            return {"status": "error", "details": str(e)}

    def order_status(self, ordID: str):
        try:
            return {"orderId": ordID, "status": self.conn.OrderStatus(ordID)}
        except Exception as e:
            LOG.exception("OrderStatus failed: %s", e)
            return {"status": "error", "details": str(e)}

    def orders_count(self):
        try:
            return int(self.conn.GetOrders())
        except Exception as e:
            LOG.exception("GetOrders failed: %s", e)
            return -1
