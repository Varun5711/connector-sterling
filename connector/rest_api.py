from fastapi import FastAPI, HTTPException
import logging

LOG = logging.getLogger("rest_api")
def create_app(session_manager, sterling):
    app = FastAPI(title="Sterling Connector")

    @app.get("/api/health")
    def health():
        return {
            "status":"ok",
            "sessionId": session_manager.session_id,
            "accounts": session_manager.accounts
        }

    @app.get("/api/metrics")
    def metrics():
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

    @app.post("/api/place-order")
    def place_order(payload: dict):
        res = sterling.place_order(payload)
        if res.get("status") == "error":
            raise HTTPException(status_code=500, detail=res.get("details"))
        return res

    return app