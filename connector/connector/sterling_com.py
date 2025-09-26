# connector/connector/sterling_com.py
"""
Sterling COM integration layer.

- Attempts to use a vendor wrapper ProgID if available (SterlingWrapper.Connector).
- Falls back to native Sterling COM objects (common ProgIDs tried below).
- Implements:
    - get_accounts(): enumerates account ids visible to the logged-in Sterling session.
    - place_order(order: dict): builds a COM order object and submits via SubmitOrderStruct/SubmitOrder.
- Uses win32com Dispatch and DispatchWithEvents for event handling.
- If the exact ProgIDs / field names differ in your environment, run `test_com_probe.py` (provided below)
  to list available methods/properties and adapt the small mapping table in _FIELD_MAP.
"""

import logging
import threading
import time
from typing import List, Optional

LOG = logging.getLogger("sterling_com")

try:
    import pythoncom
    import win32com.client
    from win32com.client import constants
    HAS_PYWIN32 = True
except Exception:
    HAS_PYWIN32 = False

# --------- Small configurable mapping section ----------
# If you know your exact ProgIDs, put them here.
# If you have a vendor wrapper, set WRAPPER_PROGID accordingly.
WRAPPER_PROGID = "SterlingWrapper.Connector"  # adjust if your wrapper uses a different ProgID
NATIVE_CONTROL_PROGIDS = [
    "Sterling.STIControl",
    "Sterling.STIOrderControl",
    "Sterling.StiEvents",   # used only for event dispatch
]

# Typical order field names used by many Sterling COM versions.
# If your type library uses different names, change mappings below.
_FIELD_MAP = {
    "account": ["Account", "Acct", "bstrAccount"],
    "symbol": ["Symbol", "Ticker"],
    "side": ["BuySell", "Side"],
    "qty": ["Quantity", "Qty", "lQuantity"],
    "price": ["LmtPrice", "Price", "dPrice"],
    "tif": ["TIF", "TimeInForce"],
    "destination": ["Destination", "Route"],
    "clientOrderId": ["ClientOrderId", "ClOrdID", "OrderId"],
}

# Fallback COM order object ProgID (some versions expose STIOrder)
ORDER_OBJ_PROGIDS = ["Sterling.STIOrder", "Sterling.Order", "STI.STIOrder"]

# ------------------------------------------------------

class SterlingCOM:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self._running = False
        self._event_thread = None
        self._lock = threading.Lock()
        self._wrapper = None
        self._control = None
        self._order_progid = None

        if HAS_PYWIN32:
            self._probe_com()

    # ----------------------------
    # COM probing / discovery
    # ----------------------------
    def _probe_com(self):
        LOG.info("Probing Sterling COM interfaces...")
        # Try wrapper first
        try:
            try:
                self._wrapper = win32com.client.Dispatch(WRAPPER_PROGID)
                LOG.info("Found wrapper ProgID: %s", WRAPPER_PROGID)
            except Exception:
                LOG.debug("Wrapper ProgID %s not available", WRAPPER_PROGID)
                self._wrapper = None

            # Try native control ProgIDs
            for prog in NATIVE_CONTROL_PROGIDS:
                try:
                    ctrl = win32com.client.Dispatch(prog)
                    self._control = ctrl
                    LOG.info("Found native control ProgID: %s", prog)
                    break
                except Exception:
                    LOG.debug("ProgID %s not present", prog)
                    continue

            # Find an order object ProgID we can instantiate for building orders
            for p in ORDER_OBJ_PROGIDS:
                try:
                    obj = win32com.client.Dispatch(p)
                    # success; keep prog id
                    self._order_progid = p
                    LOG.info("Order object ProgID available: %s", p)
                    break
                except Exception:
                    continue

            if not self._control and not self._wrapper:
                LOG.warning("No Sterling COM wrapper or native control detected. COM calls will fail until registered.")
        except Exception as e:
            LOG.exception("Error during COM probe: %s", e)

    # ----------------------------
    # Start / stop (event pump)
    # ----------------------------
    def start(self):
        if not HAS_PYWIN32:
            LOG.warning("pywin32 not available. SterlingCOM.start() will be a no-op.")
            return
        with self._lock:
            if self._running:
                return
            self._running = True
            self._event_thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._event_thread.start()
            LOG.info("Sterling COM event loop thread started.")

    def stop(self):
        with self._lock:
            self._running = False
        if self._event_thread:
            self._event_thread.join(timeout=5)
            LOG.info("Sterling COM event loop thread stopped.")

    def _run_event_loop(self):
        LOG.info("COM event loop initializing...")
        pythoncom.CoInitialize()
        try:
            # Attach an event handler if possible
            try:
                win32com.client.DispatchWithEvents("Sterling.StiEvents", EventHandler(self.session_manager))
                LOG.info("Attached EventHandler to Sterling.StiEvents")
            except Exception:
                LOG.debug("Could not attach to Sterling.StiEvents; events may still come via other objects.")

            while self._running:
                pythoncom.PumpWaitingMessages()
                time.sleep(0.1)
        except Exception as e:
            LOG.exception("Error in COM event loop: %s", e)
        finally:
            pythoncom.CoUninitialize()
            LOG.info("COM event loop ending.")

    # ----------------------------
    # Account enumeration
    # ----------------------------
    def get_accounts(self) -> List[str]:
        """
        Returns list of account identifiers available to the current Sterling session.
        - Uses wrapper.GetAccounts() if available (common wrapper API).
        - Falls back to control.GetAccountList() or control.AccountList.
        - Returns cached list if none found.
        """
        if not HAS_PYWIN32:
            LOG.warning("pywin32 missing; returning cached accounts.")
            return getattr(self, "_accounts", [])

        try:
            # Wrapper path
            if self._wrapper is not None:
                try:
                    if hasattr(self._wrapper, "GetAccounts"):
                        raw = self._wrapper.GetAccounts()
                        LOG.debug("Wrapper.GetAccounts() returned: %s", raw)
                        # Raw may be a COM collection, list, or comma-separated string
                        accounts = self._coerce_to_list(raw)
                        self._set_accounts(accounts)
                        return accounts
                except Exception:
                    LOG.exception("Wrapper.GetAccounts failed; falling back.")

            # Native control path
            if self._control is not None:
                # Common method/property names
                if hasattr(self._control, "GetAccountList"):
                    raw = self._control.GetAccountList()
                elif hasattr(self._control, "AccountList"):
                    raw = self._control.AccountList
                else:
                    raw = None

                LOG.debug("Native control returned accounts raw: %s", raw)
                accounts = self._coerce_to_list(raw)
                self._set_accounts(accounts)
                return accounts

            LOG.warning("No COM method discovered to enumerate accounts; returning cached.")
            return getattr(self, "_accounts", [])

        except Exception as e:
            LOG.exception("get_accounts() error: %s", e)
            return getattr(self, "_accounts", [])

    def _coerce_to_list(self, raw) -> List[str]:
        if raw is None:
            return []
        # If it's already list-like
        try:
            # COM collections act like iterable in Python
            if isinstance(raw, (list, tuple)):
                return [str(x) for x in raw]
            # Try iterating
            items = [str(x) for x in raw]
            if items:
                return items
        except Exception:
            pass
        s = str(raw)
        # comma-separated fallback
        if "," in s:
            return [p.strip() for p in s.split(",") if p.strip()]
        # single value fallback
        return [s.strip()] if s.strip() else []

    def _set_accounts(self, accounts: List[str]):
        self._accounts = accounts
        try:
            self.session_manager.set_accounts(accounts)
        except Exception:
            LOG.debug("session_manager.set_accounts failed (maybe not implemented)")

    # ----------------------------
    # Order submission
    # ----------------------------
    def place_order(self, order: dict) -> dict:
        """
        Main entrypoint used by connector to place an order via Sterling COM.

        Input `order` fields (common):
          - account (str)            <- required
          - symbol (str)             <- required
          - side ('B'|'S' or 'BUY'|'SELL') <- required
          - qty (int)                <- required
          - price (float)            <- optional (None => market)
          - tif (str)                <- optional
          - destination (str)        <- optional
          - idempotencyKey (str)     <- optional

        Returns:
          {"status":"submitted"|"error", "details": str, "clientOrderId": str|None}
        """
        LOG.info("place_order called: %s", {k:v for k,v in order.items() if k!="raw"})
        if not HAS_PYWIN32:
            return {"status":"error","details":"pywin32 not available"}

        # Idempotency check
        idem = order.get("idempotencyKey")
        if idem:
            prev = self.session_manager.is_idempotent(idem)
            if prev:
                LOG.info("Idempotency hit for key %s -> %s", idem, prev)
                return {"status":"submitted","details":"idempotent","clientOrderId": prev}

        # Validate minimal fields
        required = ["account","symbol","side","qty"]
        for r in required:
            if r not in order:
                return {"status":"error","details": f"missing required field {r}"}

        # Normalize side
        side = str(order.get("side")).upper()
        if side in ("BUY","B"):
            side_val = "B"
        elif side in ("SELL","S"):
            side_val = "S"
        else:
            side_val = side  # send raw, COM may accept

        # Try wrapper path first (if exists)
        if self._wrapper is not None:
            try:
                if hasattr(self._wrapper, "SubmitOrder"):
                    import json
                    payload = {
                        "account": order["account"],
                        "symbol": order["symbol"],
                        "side": side_val,
                        "qty": int(order["qty"]),
                        "price": order.get("price"),
                        "tif": order.get("tif"),
                        "destination": order.get("destination"),
                        "meta": order.get("meta", {}),
                    }
                    LOG.debug("Calling wrapper.SubmitOrder with payload: %s", payload)
                    # Some wrappers accept JSON string, others accept variant/struct - try JSON first
                    res = self._wrapper.SubmitOrder(json.dumps(payload))
                    # wrapper may return JSON string or COM object; handle both
                    try:
                        if isinstance(res, str):
                            import json as _json
                            r = _json.loads(res)
                            client_id = r.get("clientOrderId") or r.get("orderId")
                            status = r.get("status","submitted")
                            details = r.get("details","")
                        else:
                            # COM object - try attributes
                            client_id = getattr(res, "ClientOrderId", None) or getattr(res, "OrderId", None)
                            status = getattr(res, "Status", "submitted")
                            details = getattr(res, "Details", "")
                        if idem and client_id:
                            self.session_manager.store_idempotent(idem, str(client_id))
                        return {"status": status or "submitted", "details": details or "", "clientOrderId": client_id}
                    except Exception:
                        LOG.exception("Wrapper returned unexpected type; returning raw string")
                        return {"status":"submitted","details": str(res), "clientOrderId": str(res)}
            except Exception:
                LOG.exception("Wrapper.SubmitOrder failed; falling back to native COM")

        # Native COM path: build STIOrder object
        if self._control is not None or self._order_progid is not None:
            try:
                # Instantiate an order object - prefer explicit ORDER_PROGID if available,
                # else try to Dispatch a generic STIOrder type.
                if self._order_progid:
                    order_obj = win32com.client.Dispatch(self._order_progid)
                else:
                    # Try common order progids
                    order_obj = None
                    for p in ORDER_OBJ_PROGIDS:
                        try:
                            order_obj = win32com.client.Dispatch(p)
                            LOG.debug("Created order object with ProgID %s", p)
                            break
                        except Exception:
                            continue
                    if order_obj is None:
                        # as a last resort, try to allocate a Variant/dictionary - but most COM impls require real object
                        return {"status":"error","details":"no STIOrder ProgID available"}

                # Map fields using _FIELD_MAP; try each candidate property name until one works
                def _set_field(obj, map_keys, value):
                    for k in map_keys:
                        try:
                            setattr(obj, k, value)
                            LOG.debug("Set field %s = %s", k, value)
                            return True
                        except Exception:
                            # try method setters like SetAccount(...)
                            try:
                                method = getattr(obj, "Set"+k, None)
                                if callable(method):
                                    method(value)
                                    LOG.debug("Called setter Set%s(%s)", k, value)
                                    return True
                            except Exception:
                                pass
                    LOG.debug("Could not set field via any candidate names: %s", map_keys)
                    return False

                _set_field(order_obj, _FIELD_MAP["account"], order["account"])
                _set_field(order_obj, _FIELD_MAP["symbol"], order["symbol"])
                _set_field(order_obj, _FIELD_MAP["side"], side_val)
                _set_field(order_obj, _FIELD_MAP["qty"], int(order["qty"]))
                if "price" in order and order["price"] is not None:
                    _set_field(order_obj, _FIELD_MAP["price"], float(order["price"]))
                if "tif" in order and order["tif"] is not None:
                    _set_field(order_obj, _FIELD_MAP["tif"], order["tif"])
                if "destination" in order and order["destination"] is not None:
                    _set_field(order_obj, _FIELD_MAP["destination"], order["destination"])

                # Submit: try common methods on control
                submit_result = None
                # If the native control exposes a SubmitOrderStruct method, call that.
                if self._control is not None and hasattr(self._control, "SubmitOrderStruct"):
                    LOG.debug("Calling control.SubmitOrderStruct(...)")
                    submit_result = self._control.SubmitOrderStruct(order_obj)
                elif self._control is not None and hasattr(self._control, "SubmitOrder"):
                    LOG.debug("Calling control.SubmitOrder(...)")
                    submit_result = self._control.SubmitOrder(order_obj)
                else:
                    # Some versions expect the order_obj itself to have a Submit method
                    if hasattr(order_obj, "Submit"):
                        LOG.debug("Calling order_obj.Submit()")
                        submit_result = order_obj.Submit()
                    else:
                        LOG.warning("No known submit method found on control or order object")
                        return {"status":"error","details":"no submit method on control/order object"}

                # Interpret submit_result (vendor-specific)
                client_id = None
                details = ""
                status = "submitted"

                try:
                    # Common shaped result: COM object with OrderId/ClientOrderId and Status attributes
                    client_id = getattr(submit_result, "ClientOrderId", None) or getattr(submit_result, "OrderId", None)
                    status = getattr(submit_result, "Status", status)
                    details = getattr(submit_result, "Details", "") or str(submit_result)
                except Exception:
                    # Fallback: submit_result may be an int code or string
                    try:
                        code = int(submit_result)
                        if code != 0:
                            status = "error"
                            details = f"submit returned code {code}"
                        else:
                            status = "submitted"
                            details = f"submit code {code}"
                    except Exception:
                        details = str(submit_result)

                if idem and client_id:
                    self.session_manager.store_idempotent(idem, str(client_id))

                return {"status": status or "submitted", "details": details or "", "clientOrderId": client_id}
            except Exception as e:
                LOG.exception("Native COM place_order failed: %s", e)
                return {"status":"error","details": str(e)}
        else:
            LOG.error("No COM wrapper or control available to place order.")
            return {"status":"error","details":"no COM implementation available"}

# ----------------------------
# COM event handler
# ----------------------------
class EventHandler:
    """
    This class is passed as the event sink to DispatchWithEvents.
    Method names should match the COM event names. The commonly named events are:
      - OnSTITradeUpdate
      - OnSTIOrderUpdate
    If your type library uses different event names, use python makepy and inspect them.
    """
    def __init__(self, session_manager):
        self.session_manager = session_manager

    def OnSTITradeUpdate(self, tradeMsg):
        try:
            trade = {
                "type": "tradeUpdate",
                "account": getattr(tradeMsg, "Account", None) or getattr(tradeMsg, "Acct", None),
                "symbol": getattr(tradeMsg, "Symbol", None) or getattr(tradeMsg, "Ticker", None),
                "side": getattr(tradeMsg, "Side", None) or getattr(tradeMsg, "BuySell", None),
                "qty": getattr(tradeMsg, "Quantity", getattr(tradeMsg, "Qty", None)),
                "price": getattr(tradeMsg, "ExecPrice", None) or getattr(tradeMsg, "Price", None),
                "execId": getattr(tradeMsg, "ExecId", None) or getattr(tradeMsg, "TradeId", None),
                "timestamp": getattr(tradeMsg, "TradeTime", None)
            }
            LOG.debug("Event OnSTITradeUpdate -> %s", trade)
            self.session_manager.handle_inbound_event(trade)
        except Exception:
            LOG.exception("Error in OnSTITradeUpdate handler")

    def OnSTIOrderUpdate(self, orderMsg):
        try:
            order = {
                "type": "orderUpdate",
                "account": getattr(orderMsg, "Account", None),
                "clientOrderId": getattr(orderMsg, "ClientOrderId", None) or getattr(orderMsg, "OrderId", None),
                "exchangeId": getattr(orderMsg, "ExchangeOrderId", None),
                "status": getattr(orderMsg, "OrderStatus", None),
                "filledQty": getattr(orderMsg, "CumExecQuantity", None),
                "avgPrice": getattr(orderMsg, "AvgPrice", None),
                "timestamp": getattr(orderMsg, "LastUpdateTime", None)
            }
            LOG.debug("Event OnSTIOrderUpdate -> %s", order)
            self.session_manager.handle_inbound_event(order)
        except Exception:
            LOG.exception("Error in OnSTIOrderUpdate handler")

# ----------------------------
# Utility/test helper
# ----------------------------
def makepy_generate():
    """
    Use this to generate early-binding wrappers for the registered type libraries.
    Run in an interactive powershell/command prompt with your venv active:
        python -c "import win32com.client.makepy as mp; mp.GenerateFromTypeLibSpec()"
    Or specify the lib GUID/filename to speed up discovery.
    """
    import win32com.client.makepy as makepy
    LOG.info("Generating MakePy wrappers for all registered type libs (may take a while)...")
    try:
        makepy.GenerateFromTypeLibSpec()  # interactive selection may be required
    except Exception:
        LOG.exception("MakePy generation failed - run interactively to select the type library")

# ----------------------------
# Quick probe script can be run to inspect available members
# ----------------------------
if __name__ == "__main__" and True:
    # example quick test - set to True and run directly on Windows to inspect
    if not HAS_PYWIN32:
        print("pywin32 not installed")
    else:
        sm = type("SM", (), {"set_accounts": lambda self, a: print("set_accounts:", a), "handle_inbound_event": lambda self,m: print("evt",m)})()
        sc = SterlingCOM(sm)
        print("wrapper:", sc._wrapper)
        print("control:", sc._control)
        print("order_prog:", sc._order_progid)
        print("accounts:", sc.get_accounts())