# connector/sterling_connector.py
import logging, json, asyncio
from .session_manager import SessionManager
from SterlingWrapper import Connector

LOG = logging.getLogger("sterling_connector")

class SterlingConnector:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.conn = Connector()

    async def send_market(self, order: dict) -> dict:
        return await asyncio.to_thread(self._send_market, order)

    def _send_market(self, order):
        idem = order.get("idempotencyKey")
        if idem:
            prev = self.session_manager.is_idempotent(idem)
            if prev:
                return {"status":"submitted","details":"idempotent","orderId": prev}
        try:
            res = self.conn.Sendmarket(order["account"], order["symbol"],
                                       int(order["qty"]), int(order["qty"]),
                                       order.get("route",""),
                                       order["side"], order.get("tif","D"))
            oid, status = res.split(";")
            if idem:
                self.session_manager.store_idempotent(idem, oid)
            return {"status":status, "orderId": oid}
        except Exception as e:
            LOG.exception("send_market failed")
            return {"status":"error","details":str(e)}

    async def send_limit(self, order: dict) -> dict:
        return await asyncio.to_thread(self._send_limit, order)

    def _send_limit(self, order):
        idem = order.get("idempotencyKey")
        if idem:
            prev = self.session_manager.is_idempotent(idem)
            if prev:
                return {"status":"submitted","details":"idempotent","orderId": prev}
        try:
            disp = int(order.get("display", order["qty"]))
            res = self.conn.Sendlimit(order["account"], order["symbol"], int(order["qty"]), disp,
                                      float(order["price"]), order.get("route",""),
                                      order["side"], order.get("tif","D"))
            oid, status = res.split(";")
            if idem:
                self.session_manager.store_idempotent(idem, oid)
            return {"status":status, "orderId": oid}
        except Exception as e:
            LOG.exception("send_limit failed")
            return {"status":"error","details":str(e)}

    def order_status(self, orderId: str) -> dict:
        try:
            st = self.conn.OrderStatus(orderId)
            return {"orderId": orderId, "status": st}
        except Exception as e:
            return {"status":"error","details":str(e)}

    def all_positions(self, account: str) -> list:
        try:
            raw = self.conn.AllPositions(account).split(";")
            return [p for p in raw if p.strip()]
        except Exception as e:
            LOG.exception("all_positions failed")
            return []