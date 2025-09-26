from fastapi import FastAPI

def create_app(session_mgr, sterling):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"status":"ok","sessionId":session_mgr.session_id,"accounts":session_mgr.accounts}

    @app.post("/api/place-order")
    async def place(payload: dict):
        if payload.get("type")=="market":
            return await sterling.send_market(payload)
        return await sterling.send_limit(payload)

    return app