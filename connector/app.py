import asyncio, signal
from connector.config_loader import load_config, get_secret
from connector.logger import configure_logging
from connector.session_manager import SessionManager
from connector.sterling_connector import SterlingConnector
from connector.ws_client import WSClient
from connector.rest_api import create_app
import uvicorn

logger = configure_logging("INFO")

def main():
    cfg = load_config()
    ws_url = cfg["connector"]["enigma_ws_url"]
    token = get_secret("ENIGMA_WS_TOKEN") or cfg["connector"].get("auth_token")

    session_mgr = SessionManager()
    sterling = SterlingConnector(session_mgr)
    ws_client = WSClient(ws_url, token, sterling, session_mgr)

    app = create_app(session_mgr, sterling)

    loop = asyncio.get_event_loop()
    tasks = [loop.create_task(ws_client.connect_loop())]

    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=cfg["connector"].get("rest_port",5000)))
    tasks.append(loop.create_task(server.serve()))

    stop_event = asyncio.Event()
    def _stop(*_): stop_event.set()
    for s in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(s, _stop)
        except: pass

    loop.run_until_complete(stop_event.wait())
    loop.run_until_complete(ws_client.close())
    for t in tasks: t.cancel()

if __name__=="__main__":
    main()