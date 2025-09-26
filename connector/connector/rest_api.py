from fastapi import FastAPI, HTTPException
import logging

LOG = logging.getLogger("rest_api")

def create_app(session_manager, sterling):
    app = FastAPI(title="Sterling Connector API")

    @app.get("/api/health")
    def health():
        accounts = session_manager.get_accounts()
        return {"status":"ok", "sessionId": session_manager.session_id or "unknown", "accounts": accounts}

    @app.get("/api/accounts")
    def get_accounts():
        return {"accounts": session_manager.get_accounts()}

    @app.post("/api/orders")
    def place_order(payload: dict):
        result = sterling.place_order(payload)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("details"))
        return {"status": result.get("status"), "details": result.get("details")}

    return app