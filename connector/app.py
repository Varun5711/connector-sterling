import asyncio
import logging
import uvicorn

from fastapi import FastAPI
from connector.config_loader import load_config
from connector.session_manager import SessionManager
from connector.ws_client import WSClient
from connector.sterling_connector import SterlingConnector

LOG = logging.getLogger("app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI()

def main():
    # ---- Load config ----
    cfg = load_config()
    token = cfg["connector"].get("auth_token")
    url = cfg["connector"]["enigma_ws_url"]

    # TLS options
    verify = cfg.get("tls", {}).get("verify", True)
    cafile = cfg.get("tls", {}).get("cafile")

    LOG.info("Loaded config: ws_url=%s verify=%s cafile=%s", url, verify, cafile)

    # ---- Initialize managers ----
    session_mgr = SessionManager()
    sterling = SterlingConnector(session_mgr)
    ws_client = WSClient(url, token, session_mgr, verify=verify, cafile=cafile)

    # ---- Start async tasks ----
    loop = asyncio.get_event_loop()
    loop.create_task(ws_client.connect_loop())

    # ---- Run API ----
    uvicorn.run(app, host="0.0.0.0", port=5000, loop="asyncio")

# ---- API Endpoints ----
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/accounts")
async def accounts():
    # In real life, query SterlingConnector for accounts
    return {"accounts": ["TEST123", "LIVE456"]}

if __name__ == "__main__":
    main()
