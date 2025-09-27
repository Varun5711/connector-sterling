import asyncio
import logging
import websockets
import ssl
import certifi

LOG = logging.getLogger("ws_client")

class WSClient:
    def __init__(self, url: str, token: str, session_manager, verify: bool = True, cafile: str | None = None):
        self.url = url
        self.token = token
        self.session_manager = session_manager
        self.verify = verify
        self.cafile = cafile

    def _make_ssl_context(self):
        """Build SSL context based on settings."""
        if self.url.startswith("ws://"):
            return None  # no TLS for plain ws://
        if not self.verify:
            LOG.warning("⚠️ TLS verification disabled (unsafe, use only for dev/testing!)")
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        if self.cafile:
            return ssl.create_default_context(cafile=self.cafile)
        return ssl.create_default_context(cafile=certifi.where())

    async def connect_loop(self):
        """Keep reconnecting WebSocket client."""
        while True:
            try:
                await self._run()
            except Exception as e:
                LOG.error("WS error: %s", e, exc_info=True)
                await asyncio.sleep(5)

    async def _run(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        ssl_ctx = self._make_ssl_context()

        LOG.info("Connecting WS → %s", self.url)
        async with websockets.connect(self.url, extra_headers=headers, ssl=ssl_ctx) as ws:
            LOG.info("Connected to WS server")
            async for msg in ws:
                try:
                    self.session_manager.handle_inbound_event(msg)
                except Exception:
                    LOG.exception("Error handling inbound WS message")
