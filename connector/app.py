from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from connector.sterling_connector import SterlingConnector
from typing import Optional

app = FastAPI(title="Sterling Connector API", version="1.0")

sterling: Optional[SterlingConnector] = None


# ============================================================
# MODELS
# ============================================================

class UnifiedOrderRequest(BaseModel):
    account: str
    symbol: str
    ord_size: int
    ord_disp: Optional[int] = 0
    ord_route: str
    ord_side: str
    ord_tif: Optional[str] = "D"

    # For backward compatibility
    ord_price: Optional[float] = 0.0
    ord_type: Optional[str] = None

    # New fields for all order types
    price_type: Optional[int] = None  # Sterling price type: 1=Market, 5=Limit, 7=StopLimit, 100=Stop, 101=StopLimit, 102=TrailingStop
    limit_price: Optional[float] = 0.0
    stop_price: Optional[float] = 0.0
    client_order_id: Optional[str] = None


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


# ============================================================
# STARTUP / SHUTDOWN
# ============================================================

@app.on_event("startup")
def startup_event():
    global sterling
    try:
        sterling = SterlingConnector()
        print("✅ SterlingConnector initialized")
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        raise


@app.on_event("shutdown")
def shutdown_event():
    global sterling
    sterling = None
    print("🛑 SterlingConnector shutdown")


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
def root():
    return {"status": "ok", "message": "Sterling Connector API running"}


# ============================================================
# ORDERS
# ============================================================

@app.post("/order")
def place_order(req: UnifiedOrderRequest):
    try:
        # Use price_type if provided (new format), otherwise fallback to old format
        if req.price_type is not None:
            # New format: Handle all order types based on Sterling price_type
            # 1=Market, 5=Limit, 7=StopLimit, 100=ServerStop, 101=ServerStopLimit, 102=TrailingStop

            if req.price_type == 1:  # Market
                print(f"📥 {req.symbol} {req.ord_side} {req.ord_size} MARKET")
                result = sterling.send_market(
                    req.account,
                    req.symbol,
                    int(req.ord_size),
                    int(req.ord_disp or 0),
                    req.ord_route,
                    req.ord_side,
                    req.ord_tif or "D"
                )
                print(f"✅ Market Order: {result}")
                return {
                    "order_type": "market",
                    "order_id": result,
                    "symbol": req.symbol,
                    "side": req.ord_side,
                    "quantity": req.ord_size,
                    "client_order_id": req.client_order_id
                }

            elif req.price_type == 5:  # Limit
                print(f"📥 {req.symbol} {req.ord_side} {req.ord_size} LIMIT @ ${req.limit_price}")
                result = sterling.send_limit(
                    req.account,
                    req.symbol,
                    int(req.ord_size),
                    int(req.ord_disp or 0),
                    req.ord_route,
                    float(req.limit_price),
                    req.ord_side,
                    req.ord_tif or "D"
                )
                print(f"✅ Limit Order: {result}")
                return {
                    "order_type": "limit",
                    "order_id": result,
                    "symbol": req.symbol,
                    "side": req.ord_side,
                    "quantity": req.ord_size,
                    "price": req.limit_price,
                    "client_order_id": req.client_order_id
                }

            elif req.price_type == 7 or req.price_type == 101:  # Stop Limit
                print(f"📥 {req.symbol} {req.ord_side} {req.ord_size} STOP LIMIT Stop:${req.stop_price} Limit:${req.limit_price}")
                result = sterling.send_stoplimit(
                    req.account,
                    req.symbol,
                    int(req.ord_size),
                    int(req.ord_disp or 0),
                    req.ord_route,
                    float(req.stop_price),
                    float(req.limit_price),
                    req.ord_side,
                    req.ord_tif or "D"
                )
                print(f"✅ Stop Limit Order: {result}")
                return {
                    "order_type": "stop_limit",
                    "order_id": result,
                    "symbol": req.symbol,
                    "side": req.ord_side,
                    "quantity": req.ord_size,
                    "stop_price": req.stop_price,
                    "limit_price": req.limit_price,
                    "client_order_id": req.client_order_id
                }

            elif req.price_type == 100 or req.price_type == 102:  # Stop or Trailing Stop
                print(f"📥 {req.symbol} {req.ord_side} {req.ord_size} STOP @ ${req.stop_price}")
                result = sterling.send_stop(
                    req.account,
                    req.symbol,
                    int(req.ord_size),
                    int(req.ord_disp or 0),
                    req.ord_route,
                    float(req.stop_price),
                    req.ord_side,
                    req.ord_tif or "D"
                )
                print(f"✅ Stop Order: {result}")
                return {
                    "order_type": "stop",
                    "order_id": result,
                    "symbol": req.symbol,
                    "side": req.ord_side,
                    "quantity": req.ord_size,
                    "stop_price": req.stop_price,
                    "client_order_id": req.client_order_id
                }
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported price_type: {req.price_type}")

        else:
            # Old format: Backward compatibility
            is_market = (
                req.ord_type == "M"
                or req.ord_price is None
                or req.ord_price == 0.0
            )

            print(f"📥 {req.symbol} {req.ord_side} {req.ord_size} ({'MKT' if is_market else 'LMT'}) [Legacy]")

            if is_market:
                result = sterling.send_market(
                    req.account,
                    req.symbol,
                    int(req.ord_size),
                    int(req.ord_disp or 0),
                    req.ord_route,
                    req.ord_side,
                    req.ord_tif or "D"
                )
                print(f"✅ {result}")
                return {
                    "order_type": "market",
                    "order_id": result,
                    "symbol": req.symbol,
                    "side": req.ord_side,
                    "quantity": req.ord_size
                }
            else:
                result = sterling.send_limit(
                    req.account,
                    req.symbol,
                    int(req.ord_size),
                    int(req.ord_disp or 0),
                    req.ord_route,
                    float(req.ord_price),
                    req.ord_side,
                    req.ord_tif or "D"
                )
                print(f"✅ {result}")
                return {
                    "order_type": "limit",
                    "order_id": result,
                    "symbol": req.symbol,
                    "side": req.ord_side,
                    "quantity": req.ord_size,
                    "price": req.ord_price
                }

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order/stop")
def place_stop_order(req: StopOrderRequest):
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
                req.ord_tif or "D"
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
                req.ord_tif or "D"
            )

        return {"order_id": result}

    except Exception as e:
        print(f"❌ Stop order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/order")
def cancel_order(req: CancelRequest):
    try:
        sterling.cancel_order(req.account, req.order_id)
        return {"status": "cancel_requested", "order_id": req.order_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/order/replace")
def replace_order(req: ReplaceRequest):
    try:
        new_id = sterling.replace_order(
            req.order_id,
            req.new_qty,
            float(req.new_price)
        )
        return {"new_order_id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# POSITIONS / ORDERS INFO
# ============================================================

@app.get("/positions/{account}/{symbol}")
def get_position(account: str, symbol: str):
    try:
        pos = sterling.position(account, symbol)
        return {"account": account, "symbol": symbol, "position": pos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/positions/{account}")
def get_all_positions(account: str):
    try:
        raw = sterling.all_positions(account)
        return {"account": account, "positions_raw": raw}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders")
def get_orders():
    try:
        cnt = sterling.get_orders()
        return {"open_orders_count": cnt}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/order/status/{order_id}")
def order_status(order_id: str):
    try:
        status = sterling.order_status(order_id)
        return {"order_id": order_id, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6000)
