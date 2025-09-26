import asyncio
import logging
import signal
import sys
from pathlib import Path
import yaml

from connector.sterling_com import SterlingCOM
from connector.ws_client import WSClient
from connector.rest_api import create_app
from connector.session_manager import SessionManager

LOG = logging.getLogger("sterling_connector")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent.parent / "config" / "config.yaml"

def load_config():
    if not CONFIG_PATH.exists():
        LOG.warning("config.yaml not found at %s, using defaults", CONFIG_PATH)
        return {}
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

async def main():
    cfg = load_config()
    enigma_ws_url = cfg.get("connector", {}).get("enigma_ws_url")
    ws_auth_token = cfg.get("connector", {}).get("auth_token")

    session_manager = SessionManager()
    sterling = SterlingCOM(session_manager=session_manager)

    ws_client = WSClient(
        enigma_ws_url=enigma_ws_url,
        auth_token=ws_auth_token,
        sterling=sterling,
        session_manager=session_manager
    )

    app = create_app(session_manager=session_manager, sterling=sterling)
    import uvicorn
    server_config = uvicorn.Config(app, host="0.0.0.0", port=5000, log_level="info")
    server = uvicorn.Server(server_config)

    LOG.info("Starting connector components...")
    loop = asyncio.get_event_loop()

    tasks = []
    tasks.append(loop.create_task(ws_client.connect_loop()))
    tasks.append(loop.create_task(server.serve()))

    sterling.start()

    stop_event = asyncio.Event()

    def _handle_stop(*args):
        LOG.info("Stopping on signal")
        stop_event.set()

    try:
        loop.add_signal_handler(signal.SIGINT, _handle_stop)
        loop.add_signal_handler(signal.SIGTERM, _handle_stop)
    except NotImplementedError:
        pass

    await stop_event.wait()
    LOG.info("Shutdown requested, stopping services...")
    await ws_client.close()
    sterling.stop()
    await asyncio.gather(*tasks, return_exceptions=True)
    LOG.info("Connector shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        LOG.exception("Fatal error in connector main: %s", e)
        sys.exit(1)