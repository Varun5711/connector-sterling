import asyncio, websockets, json, logging
LOG = logging.getLogger("ws_client")

class WSClient:
    def __init__(self, url, token, sterling, session_mgr, tls_verify=True):
        self.url = url
        self.token = token
        self.sterling = sterling
        self.session_mgr = session_mgr
        self.ws = None
        self._stopping = False

        self.session_mgr.register_outbound_callback(self._on_sterling_event)

    async def connect_loop(self):
        while not self._stopping:
            try:
                await self._run()
            except Exception:
                LOG.exception("WS error")
                await asyncio.sleep(5)

    async def _run(self):
        headers = {}
        if self.token: headers["Authorization"] = f"Bearer {self.token}"
        async with websockets.connect(self.url, extra_headers=headers) as ws:
            self.ws = ws
            accounts = self.sterling.get_accounts()
            self.session_mgr.set_session("sterling-session", accounts)
            await ws.send(json.dumps({"type":"sessionRegister","accounts":accounts}))

            async for raw in ws:
                msg = json.loads(raw)
                await self._handle(msg)

    async def _handle(self, msg):
        if msg.get("type")=="placeOrder":
            order = msg["order"]
            res = await self.sterling.send_market(order) if order.get("type")=="market" else await self.sterling.send_limit(order)
            await self._send({"type":"orderAck","result":res})

    async def _send(self, obj):
        if self.ws: await self.ws.send(json.dumps(obj))

    async def close(self):
        self._stopping = True
        if self.ws: await self.ws.close()

    def _on_sterling_event(self, ev):
        asyncio.get_event_loop().create_task(self._send(ev))