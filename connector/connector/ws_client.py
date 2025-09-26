import asyncio
import json
import logging
import websockets
from typing import Optional

LOG = logging.getLogger("ws_client")

class WSClient:
    def __init__(self, enigma_ws_url: str, auth_token: Optional[str], sterling, session_manager):
        self.enigma_ws_url = enigma_ws_url
        self.auth_token = auth_token
        self.sterling = sterling
        self.session_manager = session_manager
        self._ws = None
        self.session_manager.register_outbound_callback(self._on_sterling_event)
        self._reconnect_delay = 5

    async def connect_loop(self):
        while True:
            try:
                await self._connect_and_run()
            except Exception:
                LOG.exception("WS client error, retrying in %s seconds", self._reconnect_delay)
                await asyncio.sleep(self._reconnect_delay)

    async def _connect_and_run(self):
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        LOG.info("Connecting to Enigma WS: %s", self.enigma_ws_url)
        async with websockets.connect(self.enigma_ws_url, extra_headers=headers) as ws:
            self._ws = ws
            session_id = self.session_manager.session_id or "sterling-session"
            accounts = self.session_manager.get_accounts()
            await ws.send(json.dumps({"type":"sessionRegister","sessionId":session_id,"accounts":accounts}))
            LOG.info("Registered session=%s accounts=%s", session_id, accounts)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    await self._handle_message(msg)
                except Exception:
                    LOG.exception("Error handling message from Enigma")

    async def _handle_message(self, msg):
        mtype = msg.get("type")
        if mtype == "placeOrder":
            order = msg.get("order") or msg
            LOG.info("Received placeOrder: %s", order)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.sterling.place_order, order)
            ack = {"type":"orderAck","idempotencyKey": order.get("idempotencyKey"), "status": result.get("status"), "details": result.get("details")}
            await self._send(ack)
        elif mtype == "ping":
            await self._send({"type":"pong"})
        else:
            LOG.warning("Unknown message type: %s", mtype)

    async def _send(self, obj):
        if self._ws is None:
            LOG.warning("WS not connected, drop send: %s", obj)
            return
        try:
            await self._ws.send(json.dumps(obj))
        except Exception:
            LOG.exception("Failed to send")

    async def close(self):
        if self._ws:
            await self._ws.close()

    def _on_sterling_event(self, event):
        try:
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(self._send(event), loop)
        except Exception:
            LOG.exception("Failed to forward event")