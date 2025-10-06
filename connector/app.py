import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from connector.sterling_connector import SterlingConnector

app = FastAPI(title="Sterling Connector API", version="1.0")

sterling: Optional[SterlingConnector] = None


# ---------------------------
# Request models (JSON body)
# ---------------------------
class LimitOrderRequest(BaseModel):
    account: str
    symbol: str
    ord_size: int
    ord_disp: Optional[int] = 0
    ord_route: str
    ord_price: float
    ord_side: str  # "B" or "S" (or "BUY"/"SELL" depending on your wrapper)
    ord_tif: Optional[str] = "D"


class MarketOrderRequest(BaseModel):
    account: str
    symbol: str
    ord_size: int
    ord_disp: Optional[int] = 0
    ord_route: str
    ord_side: str
    ord_tif: Optional[str] = "D"


class StopOrderRequest(BaseModel):
    account: str
    symbol: str
    ord_size: int
    ord_disp: Optional[int] = 0
    ord_route: str
    stop_price: float
    limit_price: Optional[float] = 0.0
    ord_side: str
    ord_tif: Optional[str] = "D"


class CancelRequest(BaseModel):
    account: str
    order_id: str


class ReplaceRequest(BaseModel):
    order_id: str
    new_qty: int
    new_price: float


# ---------------------------
# Startup / Shutdown
# ---------------------------
@app.on_event("startup")
async def startup_event():
    global sterling
    try:
        sterling = SterlingConnector()
        print("✅ SterlingConnector initialized")
    except Exception as e:
        print("Failed to initialize SterlingConnector:", repr(e))
        raise


@app.on_event("shutdown")
async def shutdown_event():
    global sterling
    sterling = None
    print("SterlingConnector set to None on shutdown")


# ---------------------------
# Health
# ---------------------------
@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "message": "Sterling Connector API running"}


# ---------------------------
# Orders endpoints
# ---------------------------
@app.post("/order", tags=["orders"])
async def place_limit_order(req: LimitOrderRequest):
    try:
        result = sterling.send_limit(
            req.account,
            req.symbol,
            int(req.ord_size),
            int(req.ord_disp or 0),
            req.ord_route,
            float(req.ord_price),
            req.ord_side,
            req.ord_tif or "D",
        )
        return {"order_id": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order/market", tags=["orders"])
async def place_market_order(req: MarketOrderRequest):
    try:
        result = sterling.send_market(
            req.account,
            req.symbol,
            int(req.ord_size),
            int(req.ord_disp or 0),
            req.ord_route,
            req.ord_side,
            req.ord_tif or "D",
        )
        return {"order_id": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order/stop", tags=["orders"])
async def place_stop_order(req: StopOrderRequest):
    try:
        if req.limit_price and req.limit_price > 0:
            result = sterling.send_stoplimit(
                req.account,
                req.symbol,
                int(req.ord_size),
                int(req.ord_disp or 0),
                req.ord_route,
                float(req.stop_price),
                float(req.limit_price),
                req.ord_side,
                req.ord_tif or "D",
            )
        else:
            result = sterling.send_stop(
                req.account,
                req.symbol,
                int(req.ord_size),
                int(req.ord_disp or 0),
                req.ord_route,
                float(req.stop_price),
                req.ord_side,
                req.ord_tif or "D",
            )
        return {"order_id": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/order", tags=["orders"])
async def cancel_order(req: CancelRequest):
    try:
        sterling.cancel_order(req.account, req.order_id)
        return {"status": "cancel_requested", "order_id": req.order_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order/replace", tags=["orders"])
async def replace_order(req: ReplaceRequest):
    try:
        new_id = sterling.replace_order(req.order_id, req.new_qty, float(req.new_price))
        return {"new_order_id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------
# Positions & orders info
# ---------------------------
@app.get("/positions/{account}/{symbol}", tags=["positions"])
async def get_position(account: str, symbol: str):
    try:
        pos = sterling.position(account, symbol)
        return {"account": account, "symbol": symbol, "position": pos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/positions/{account}", tags=["positions"])
async def get_all_positions(account: str):
    try:
        raw = sterling.all_positions(account)
        return {"account": account, "positions_raw": raw}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders", tags=["orders"])
async def get_orders():
    try:
        cnt = sterling.get_orders()
        return {"open_orders_count": cnt}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/order/status/{order_id}", tags=["orders"])
async def order_status(order_id: str):
    try:
        status = sterling.order_status(order_id)
        return {"order_id": order_id, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------
# Utility
# ---------------------------
@app.get("/server_time", tags=["utility"])
async def get_server_time():
    try:
        if hasattr(sterling.conn, "GetServerTime"):
            return {"server_time": sterling.conn.GetServerTime()}
        return {"server_time": None, "note": "GetServerTime not implemented in wrapper"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    import uvicorn

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    uvicorn.run("connector.app:app", host="0.0.0.0", port=6000, reload=True)
