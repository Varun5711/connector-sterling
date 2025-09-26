import clr, os, logging, json, asyncio
from .session_manager import SessionManager

LOG = logging.getLogger("sterling_connector")

# Add SterlingWrapper.dll reference
DLL_PATH = os.path.join(os.path.dirname(__file__), "..", "SterlingWrapper", "SterlingWrapper.dll")
DLL_PATH = os.path.abspath(DLL_PATH)
clr.AddReference(DLL_PATH)

from SterlingWrapper import Connector as SterlingWrapperConnector

class SterlingConnector:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.conn = SterlingWrapperConnector()
        LOG.info("SterlingWrapper Connector loaded")

    def get_accounts(self):
        try:
            accts = self.conn.GetAccounts() if hasattr(self.conn, "GetAccounts") else []
            accounts = [a.strip() for a in accts.split(",")] if isinstance(accts, str) else []
            self.session_manager.set_session("sterling-session", accounts)
            return accounts
        except Exception as e:
            LOG.error("get_accounts failed: %s", e)
            return []

    async def send_market(self, order: dict):
        return await asyncio.to_thread(self._send_market, order)

    def _send_market(self, order: dict):
        idem = order.get("idempotencyKey")
        if idem:
            prev = self.session_manager.is_idempotent(idem)
            if prev:
                return {"status": "submitted", "details": "idempotent", "orderId": prev}
        try:
            res = self.conn.Sendmarket(order["account"], order["symbol"],
                                       int(order["qty"]), int(order["qty"]),
                                       order.get("route",""), order["side"],
                                       order.get("tif","D"))
            oid, status = res.split(";")
            if idem: self.session_manager.store_idempotent(idem, oid)
            return {"status": status, "orderId": oid}
        except Exception as e:
            LOG.exception("send_market failed")
            return {"status":"error","details":str(e)}

    async def send_limit(self, order: dict):
        return await asyncio.to_thread(self._send_limit, order)

    def _send_limit(self, order: dict):
        try:
            disp = int(order.get("display", order["qty"]))
            res = self.conn.Sendlimit(order["account"], order["symbol"], int(order["qty"]), disp,
                                      float(order["price"]), order.get("route",""),
                                      order["side"], order.get("tif","D"))
            oid, status = res.split(";")
            return {"status": status, "orderId": oid}
        except Exception as e:
            LOG.exception("send_limit failed")
            return {"status":"error","details":str(e)}

    def order_status(self, oid: str):
        try:
            return {"orderId": oid, "status": self.conn.OrderStatus(oid)}
        except Exception as e:
            return {"status":"error","details":str(e)}

    def all_positions(self, account: str):
        try:
            raw = self.conn.AllPositions(account).split(";")
            return [p for p in raw if p.strip()]
        except Exception as e:
            LOG.exception("all_positions failed")
            return []