from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from database import DB, get_user_by_google_id, create_user, get_user_balance, update_balance, mark_promo_used, get_promo_code

SECRET_KEY = os.getenv("JWT_SECRET", "dojo-trade-secret-key-2025")
ALGORITHM = "HS256"

app = FastAPI(title="Dojo.Trade API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GoogleToken(BaseModel):
    token: str

class PromoCodeRequest(BaseModel):
    code: str

class TradeRequest(BaseModel):
    symbol: str
    usdt_amount: float

class SellRequest(BaseModel):
    symbol: str
    qty: float

def get_current_user(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/api/auth/google")
async def google_auth( GoogleToken):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={data.token}")
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Invalid Google token")
        user_info = resp.json()
    
    google_id = user_info["sub"]
    name = user_info.get("name", "User")
    email = user_info.get("email", "")

    user = get_user_by_google_id(google_id)
    if not user:
        user = create_user(google_id, name, email)
    
    expire = datetime.utcnow() + timedelta(days=30)
    token = jwt.encode({"user_id": user["id"], "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {
        "access_token": token,
        "user": {
            "name": user["name"],
            "balance_usdt": user["balance_usdt"],
            "has_balance": user["balance_usdt"] > 0
        }
    }

@app.post("/api/promo/apply")
def apply_promo(req: PromoCodeRequest, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    c = DB.cursor()
    c.execute("SELECT promo_used FROM users WHERE id = ?", (user_id,))
    used = c.fetchone()[0]
    if used:
        raise HTTPException(status_code=400, detail="Promo code already used")
    
    promo = get_promo_code(req.code)
    if not promo:
        raise HTTPException(status_code=400, detail="Invalid or expired promo code")
    
    mark_promo_used(user_id, req.code.upper())
    new_balance = get_user_balance(user_id)
    return {
        "success": True,
        "message": f"Promo code applied! +{promo['reward_usdt']} USDT added.",
        "new_balance": new_balance
    }

@app.get("/api/account")
def get_account(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    balance = get_user_balance(user_id)
    return {"balance": {"USDT": balance}}

@app.get("/api/symbols")
async def get_symbols() -> List[str]:
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.binance.com/api/v3/exchangeInfo")
        data = resp.json()
        symbols = [
            s["symbol"] for s in data["symbols"]
            if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
        ]
        return sorted(symbols)

@app.get("/api/price/{symbol}")
async def get_price(symbol: str) -> Dict[str, float]:
    symbol = symbol.upper()
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="Symbol not found")
        data = resp.json()
        return {"price": float(data["price"])}

@app.post("/api/buy")
def buy_trade(req: TradeRequest, user: dict = Depends(get_current_user)):
    symbol = req.symbol.upper()
    if "USDT" not in symbol:
        raise HTTPException(status_code=400, detail="Only USDT pairs allowed")
    
    price_resp = httpx.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
    if price_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    price = float(price_resp.json()["price"])

    user_id = user["user_id"]
    current_balance = get_user_balance(user_id)
    if current_balance < req.usdt_amount:
        raise HTTPException(status_code=400, detail="Not enough USDT")

    qty = req.usdt_amount / price
    new_balance = current_balance - req.usdt_amount
    update_balance(user_id, new_balance)
    add_trade = DB.cursor()
    add_trade.execute("""
        INSERT INTO trades (user_id, symbol, side, price, qty, usdt_amount)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, symbol, "BUY", price, qty, req.usdt_amount))
    DB.commit()

    return {"status": "success", "message": f"BOUGHT {qty:.6f} {symbol.replace('USDT','')} at ${price}"}

@app.post("/api/sell")
def sell_trade(req: SellRequest, user: dict = Depends(get_current_user)):
    symbol = req.symbol.upper()
    base_asset = symbol.replace("USDT", "")
    
    price_resp = httpx.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
    price = float(price_resp.json()["price"])
    usdt_received = req.qty * price

    user_id = user["user_id"]
    current_balance = get_user_balance(user_id)
    new_balance = current_balance + usdt_received
    update_balance(user_id, new_balance)
    add_trade = DB.cursor()
    add_trade.execute("""
        INSERT INTO trades (user_id, symbol, side, price, qty, usdt_amount)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, symbol, "SELL", price, req.qty, usdt_received))
    DB.commit()

    return {"status": "success", "message": f"SOLD {req.qty:.6f} {base_asset} at ${price}"}
