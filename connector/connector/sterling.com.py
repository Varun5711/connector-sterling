# connector/connector/sterling_com.py
import logging
import threading
import time

LOG = logging.getLogger("sterling_com")

try:
    import pythoncom
    import win32com.client
    HAS_PYWIN32 = True
except Exception:
    HAS_PYWIN32 = False

class SterlingCOM:
    def __init__(self, session_manager):
        self.session_manager = session_manager
        self._running = False
        self._event_thread = None
        self._lock = threading.Lock()
        self._accounts = []
        self._session_id = "sterling-session"

        # COM objects (populated lazily)
        self._wrapper = None       # vendor wrapper if available
        self._control = None       # native Sterling control if wrapper missing

        # Probe available COM interfaces on init (non-blocking)
        if HAS_PYWIN32:
            self._probe_com_implementations()

    # -------------------------
    # COM discovery / helpers
    # -------------------------
    def _probe_com_implementations(self):
        """
        Try to locate a vendor wrapper ProgID first, then fallback to standard Sterling COM ProgIDs.
        Adjust ProgIDs here if your vendor docs specify other names.
        """
        try:
            # Preferred: vendor wrapper (if provided & registered)
            try:
                LOG.debug("Trying to create SterlingWrapper COM object...")
                self._wrapper = win32com.client.Dispatch("SterlingWrapper.Connector")
                LOG.info("Using SterlingWrapper.Connector COM wrapper.")
                return
            except Exception:
                LOG.debug("SterlingWrapper.Connector not available.")

            # Fallback: native Sterling control(s) - common example names; adapt to your installer/docs
            try:
                LOG.debug("Trying to create native Sterling control 'Sterling.STIControl'...")
                self._control = win32com.client.Dispatch("Sterling.STIControl")
                LOG.info("Using Sterling.STIControl native COM interface.")
                return
            except Exception:
                LOG.debug("Sterling.STIControl not available.")

            # Another common ProgID variant
            try:
                LOG.debug("Trying 'Sterling.StiEvents' as dispatch target...")
                # Do not assign events here; this is only to check availability
                _ = win32com.client.Dispatch("Sterling.StiEvents")
                LOG.info("Sterling.StiEvents appears registered.")
            except Exception:
                LOG.debug("Sterling.StiEvents not available.")

            LOG.warning("No known Sterling COM ProgID found at probe time. COM calls will fail until proper ProgID is registered.")
        except Exception as e:
            LOG.exception("Error while probing COM implementations: %s", e)

    # -------------------------
    # Runner: starts event pump & event handler
    # -------------------------
    def start(self):
        if not HAS_PYWIN32:
            LOG.warning("pywin32 not available. COM functions disabled.")
            return
        with self._lock:
            if self._running:
                return
            self._running = True
            self._event_thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._event_thread.start()
            LOG.info("Sterling COM event thread started.")

    def stop(self):
        with self._lock:
            self._running = False
        if self._event_thread:
            self._event_thread.join(timeout=5)
            LOG.info("Sterling COM event thread stopped.")

    def _run_event_loop(self):
        LOG.info("Entering COM event loop")
        pythoncom.CoInitialize()
        try:
            # Attach to the Sterling events COM object so EventHandler methods get called.
            # DispatchWithEvents expects a ProgID or instance and a handler class.
            # If your wrapper exposes events, you may need to DispatchWithEvents to that object instead.
            try:
                events_obj = win32com.client.DispatchWithEvents("Sterling.StiEvents", EventHandler(self.session_manager))
                LOG.info("Attached EventHandler to Sterling.StiEvents")
            except Exception:
                LOG.debug("Could not attach to Sterling.StiEvents (maybe different ProgID).")

            # keep pumping messages while running so COM events are delivered
            while self._running:
                pythoncom.PumpWaitingMessages()
                time.sleep(0.1)
        except Exception as e:
            LOG.exception("COM event loop error: %s", e)
        finally:
            pythoncom.CoUninitialize()
            LOG.info("Exiting COM event loop")

    # -------------------------
    # Account enumeration
    # -------------------------
    def get_accounts(self):
        """
        Return a list of account IDs available in the current Sterling session.
        Tries wrapper first, then native COM.
        """
        if not HAS_PYWIN32:
            LOG.warning("get_accounts called but pywin32 missing")
            return self._accounts

        try:
            # 1) If wrapper exists and it exposes GetAccounts or similar, use it
            if self._wrapper is not None:
                try:
                    # Example wrapper API - adapt to your wrapper
                    LOG.debug("Querying accounts via SterlingWrapper...")
                    accounts = self._wrapper.GetAccounts()   # may return list or comma-separated string
                    if isinstance(accounts, str):
                        accounts = [a.strip() for a in accounts.split(",") if a.strip()]
                    self._accounts = list(accounts or [])
                    LOG.info("Accounts (from wrapper): %s", self._accounts)
                    self.session_manager.set_accounts(self._accounts)
                    return self._accounts
                except Exception:
                    LOG.exception("Wrapper.GetAccounts failed; falling back to native COM.")

            # 2) Native interface fallback - adjust to real methods for your Sterling version
            if self._control is not None:
                try:
                    LOG.debug("Querying accounts via Sterling.STIControl...")
                    # Example: many COM APIs expose an AccountList or GetAccounts method.
                    # Replace the method names below with the ones your STGM docs specify.
                    raw = None
                    if hasattr(self._control, "GetAccountList"):
                        raw = self._control.GetAccountList()
                    elif hasattr(self._control, "AccountList"):
                        raw = self._control.AccountList
                    # raw might be a COM collection - convert carefully
                    accounts = []
                    if raw is None:
                        LOG.warning("Native control returned no accounts (raw is None).")
                    else:
                        try:
                            for a in raw:
                                accounts.append(str(a))
                        except Exception:
                            # raw may be a comma-separated string
                            accounts = [s.strip() for s in str(raw).split(",") if s.strip()]
                    self._accounts = accounts
                    LOG.info("Accounts (from native control): %s", self._accounts)
                    self.session_manager.set_accounts(self._accounts)
                    return self._accounts
                except Exception:
                    LOG.exception("Error reading accounts from native control.")

            # 3) Last-resort: return cached accounts (may be empty)
            LOG.warning("No working COM method to enumerate accounts; returning cached accounts.")
            return self._accounts

        except Exception as e:
            LOG.exception("Unhandled error in get_accounts: %s", e)
            return self._accounts

    # -------------------------
    # Place order implementation
    # -------------------------
    def place_order(self, order):
        """
        Places an order through Sterling.

        `order` is a dict with keys:
          - account (string)
          - symbol (string)
          - side ('B' or 'S')
          - qty (int)
          - price (float) [optional for market]
          - tif (string) [optional]
          - destination (string) [optional]
          - idempotencyKey (string) [optional]

        Returns dict {status: 'submitted'|'error', details: str, clientOrderId: str|None}
        """
        LOG.info("Placing order via COM: %s", order)
        if not HAS_PYWIN32:
            return {"status": "error", "details": "pywin32 not available on this host"}

        # Simple idempotency check (delegate persistent storage to session_manager)
        idempotency_key = order.get("idempotencyKey")
        if idempotency_key:
            prev = self.session_manager.is_idempotent(idempotency_key)
            if prev:
                LOG.info("Idempotency: returning cached result for key %s", idempotency_key)
                # prev is stored as a string; you can store JSON if needed
                return {"status": "submitted", "details": "idempotent-return", "clientOrderId": prev}

        try:
            # Try wrapper first: assume wrapper has a SubmitOrder(orderDict) method
            if self._wrapper is not None:
                try:
                    LOG.debug("Using wrapper.SubmitOrder if available")
                    # wrapper.SubmitOrder may expect a COM-friendly structure or simple dict-like string
                    # many COM wrappers accept JSON strings or variant dictionaries; adapt to your wrapper.
                    if hasattr(self._wrapper, "SubmitOrder"):
                        # Some wrappers accept a JSON string; others accept argument list. Try JSON first.
                        import json
                        payload = json.dumps(order)
                        result = self._wrapper.SubmitOrder(payload)
                        # Interpret result: may be JSON or a simple success code
                        try:
                            # If wrapper returns JSON string
                            r = json.loads(result) if isinstance(result, str) else result
                            client_order_id = r.get("clientOrderId") or r.get("orderId") or None
                            status = r.get("status") or "submitted"
                            details = r.get("details") or ""
                        except Exception:
                            # if wrapper returns simple bool or code
                            client_order_id = str(result)
                            status = "submitted"
                            details = "(wrapper returned raw result)"
                        # persist idempotency
                        if idempotency_key and client_order_id:
                            self.session_manager.store_idempotent(idempotency_key, client_order_id)
                        return {"status": status, "details": details, "clientOrderId": client_order_id}
                    else:
                        LOG.debug("Wrapper exists but has no SubmitOrder method; falling back.")
                except Exception:
                    LOG.exception("Wrapper.SubmitOrder failed; falling back to native COM.")

            # Native COM path: construct an order object and call SubmitOrderStruct (common pattern)
            if self._control is not None:
                try:
                    LOG.debug("Using native control to place order")
                    # NOTE: The exact API names / struct creation depend on Sterling versions.
                    # Common pattern (pseudo):
                    # orderObj = win32com.client.Dispatch("Sterling.STIOrder")
                    # orderObj.Account = order["account"]
                    # orderObj.Symbol = order["symbol"]
                    # orderObj.Side = order["side"]
                    # orderObj.Quantity = int(order["qty"])
                    # if price -> orderObj.LmtPrice = float(order["price"])
                    # set tif/destination etc.
                    # result = self._control.SubmitOrderStruct(orderObj)
                    # Interpret result.
                    order_obj = win32com.client.Dispatch("Sterling.STIOrder")  # may differ
                    # Set fields - adapt these to the actual field names in your COM type library
                    if "account" in order:
                        try: order_obj.Account = order["account"]
                        except Exception: order_obj.SetAccount(order["account"])
                    if "symbol" in order:
                        order_obj.Symbol = order["symbol"]
                    if "side" in order:
                        order_obj.BuySell = order["side"]  # field name may be BuySell / Side
                    if "qty" in order:
                        order_obj.Quantity = int(order["qty"])
                    if "price" in order and order["price"] is not None:
                        order_obj.LmtPrice = float(order["price"])
                    if "tif" in order:
                        order_obj.TIF = order["tif"]
                    if "destination" in order:
                        order_obj.Destination = order["destination"]

                    # Submit via control (method name may be SubmitOrderStruct / SubmitOrder)
                    if hasattr(self._control, "SubmitOrderStruct"):
                        res = self._control.SubmitOrderStruct(order_obj)
                    elif hasattr(self._control, "SubmitOrder"):
                        res = self._control.SubmitOrder(order_obj)
                    else:
                        # as a last resort, try calling a generic Order entry point
                        LOG.warning("No known submit method on native control; attempting SubmitOrderStruct anyway.")
                        res = self._control.SubmitOrderStruct(order_obj)

                    # Interpret result (vendor-specific)
                    # Many APIs return an object with Status/OrderId, or an integer code.
                    client_order_id = None
                    status = "submitted"
                    details = ""

                    # Example: if res is a dict or COM object exposing attributes:
                    try:
                        # if res has attributes like OrderId or ClientOrderId
                        client_order_id = getattr(res, "OrderId", None) or getattr(res, "ClientOrderId", None)
                        status = getattr(res, "Status", "submitted")
                        details = getattr(res, "Details", "")
                    except Exception:
                        # if res is an int code
                        try:
                            code = int(res)
                            if code != 0:
                                status = "error"
                                details = f"submit returned code {code}"
                        except Exception:
                            # fallback: stringify result
                            details = str(res)

                    if idempotency_key and client_order_id:
                        self.session_manager.store_idempotent(idempotency_key, client_order_id)

                    return {"status": status or "submitted", "details": details or "", "clientOrderId": client_order_id}

                except Exception as e:
                    LOG.exception("Native COM submit failed: %s", e)
                    return {"status": "error", "details": str(e)}

            # If neither wrapper nor control available:
            LOG.error("No COM implementation available to place order.")
            return {"status": "error", "details": "No COM implementation available"}

        except Exception as e:
            LOG.exception("Unhandled exception in place_order: %s", e)
            return {"status": "error", "details": str(e)}


class EventHandler:
    """
    COM event handler class used with DispatchWithEvents.
    It receives events from Sterling (names depend on the COM library)
    and forwards translated messages to session_manager.handle_inbound_event.
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
                "execId": getattr(tradeMsg, "ExecId", None),
                "timestamp": getattr(tradeMsg, "TradeTime", None)
            }
            self.session_manager.handle_inbound_event(trade)
        except Exception:
            LOG.exception("Error in OnSTITradeUpdate")

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
            self.session_manager.handle_inbound_event(order)
        except Exception:
            LOG.exception("Error in OnSTIOrderUpdate")