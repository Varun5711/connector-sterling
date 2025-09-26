import asyncio, json, logging, random, time
import websockets
from typing import Optional

LOG = logging.getLogger("ws_client")

class WSClient:
    def __init__(self, url: str, token: str, sterling, session_manager, tls_verify: bool=True):
        self.url = url
        self.token = token
        self.sterling = sterling
        self.session_manager = session_manager
        self.tls_verify = tls_verify
        self.ws = None
        self._stopping = False
        self._backoff = 1
        self._max_backoff = 60
        self.session_manager.register_outbound_callback(self._on_sterling_event)

    async def connect_loop(self):
        while not self._stopping:
            try:
                await self._run()
                # if run returns normally, reset backoff
                self._backoff = 1
            except Exception:
                LOG.exception("WS run error")
                await asyncio.sleep(self._next_backoff())

    def _next_backoff(self):
        b = self._backoff + random.uniform(0, min(5, self._backoff))
        self._backoff = min(self._max_backoff, b * 1.5)
        LOG.info("Reconnecting in %.1f seconds", self._backoff)
        return self._backoff

    async def _run(self):
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        LOG.info("Connecting to %s", self.url)
        ssl_ctx = None
        if not self.tls_verify:
            import ssl
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        async with websockets.connect(self.url, extra_headers=headers, ssl=ssl_ctx) as ws:
            self.ws = ws
            # register
            session_id = self.session_manager.session_id or "sterling-session"
            accounts = self.session_manager.accounts or self.sterling.get_accounts()
            self.session_manager.set_session(session_id, accounts)
            await ws.send(json.dumps({"type":"sessionRegister","sessionId":session_id,"accounts":accounts}))
            LOG.info("sessionRegister sent")
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    await self._handle(msg)
                except Exception:
                    LOG.exception("error processing inbound message")

    async def _handle(self, msg):
        mtype = msg.get("type")
        if mtype == "placeOrder":
            order = msg.get("order") or msg
            LOG.info("placeOrder received %s", order)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.sterling.place_order, order)
            ack = {"type":"orderAck", "idempotencyKey": order.get("idempotencyKey"), "status": result.get("status"), "details": result.get("details"), "clientOrderId": result.get("clientOrderId")}
            await self._send(ack)
        elif mtype == "ping":
            await self._send({"type":"pong"})
        elif mtype == "healthCheck":
            await self._send({"type":"health", "sessionId": self.session_manager.session_id, "accounts": self.session_manager.accounts})
        else:
            LOG.warning("Unknown message type %s", mtype)

    async def _send(self, obj):
        if not self.ws:
            LOG.warning("ws not connected")
            return
        try:
            await self.ws.send(json.dumps(obj))
        except Exception:
            LOG.exception("send failed")

    async def close(self):
        self._stopping = True
        if self.ws:
            await self.ws.close()

    def _on_sterling_event(self, event):
        # schedule send
        if self.ws is None:
            LOG.debug("no ws to send event")
            return
        try:
            loop = asyncio.get_event_loop()
            asyncio.run_coroutine_threadsafe(self._send(event), loop)
        except Exception:
            LOG.exception("failed schedule event")