# -------------------------------------------------
# AI TRADING BOT + WEB SERVER  (Replit համար)
# -------------------------------------------------

import asyncio
import json
import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from flask import Flask
from threading import Thread

# ------------------ CONFIG ------------------
TELEGRAM_BOT_TOKEN = "8264707362:AAFJqvD8OMoEEHROoDq84YUayrpPRpROGRI"
ADMIN_ID = 5398441328

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "BNBUSDT", "LTCUSDT",
    "MATICUSDT", "AVAXUSDT"
]

MIN_PROBABILITY = 70
# --------------------------------------------

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Լեզուների պահպանում
LANG_FILE = "user_langs.json"
if os.path.exists(LANG_FILE):
    with open(LANG_FILE, "r") as f:
        user_langs = json.load(f)
else:
    user_langs = {}

def save_langs():
    with open(LANG_FILE, "w") as f:
        json.dump(user_langs, f)

# ------------------ BINANCE FUTURES CLIENT ------------------
def get_futures_klines(symbol, interval="1m", limit=100):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        resp = requests.get(url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            df = pd.DataFrame(data, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'
            ])
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['open'] = df['open'].astype(float)
            df['volume'] = df['volume'].astype(float)
            return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None

# ------------------ ANALYZER ------------------
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def calculate_bollinger_bands(series, window=20, num_std=2):
    ma = series.rolling(window).mean().iloc[-1]
    std = series.rolling(window).std().iloc[-1]
    upper = ma + (std * num_std)
    lower = ma - (std * num_std)
    return upper, lower, ma

def recommend_leverage(probability):
    if probability >= 90:
        return min(50, 20 + (probability - 90) * 3)
    elif probability >= 80:
        return 10 + (probability - 80)
    elif probability >= 75:
        return 5 + (probability - 75) // 2
    elif probability >= 70:
        return 2 + (probability - 70) // 3
    return 0

def analyze_symbol(df, symbol):
    if df is None or len(df) < 25:
        return None

    close = df['close'].iloc[-1]
    rsi = calculate_rsi(df['close'])
    upper, lower, ma = calculate_bollinger_bands(df['close'])
    ema9 = df['close'].ewm(span=9).mean().iloc[-1]
    ema21 = df['close'].ewm(span=21).mean().iloc[-1]
    volume = df['volume'].iloc[-1]
    avg_vol = df['volume'].rolling(5).mean().iloc[-1]

    signal = None
    prob = 0

    if (rsi < 38 and 
        close < lower and 
        volume > avg_vol * 1.2 and 
        ema9 > ema21):
        signal = "UP"
        prob = 82 - int(rsi)

    elif (rsi > 62 and 
          close > upper and 
          volume > avg_vol * 1.2 and 
          ema9 < ema21):
        signal = "DOWN"
        prob = int(rsi) - 50

    if signal and prob >= MIN_PROBABILITY:
        leverage = recommend_leverage(prob)
        return {
            "symbol": symbol,
            "direction": signal,
            "probability": min(prob, 95),
            "leverage": leverage
        }
    return None

# ------------------ TELEGRAM HANDLERS ------------------
@dp.message_handler(commands=["start"])
async def send_language_choice(message: types.Message):
    keyboard = types.InlineKeyboardMarkup()
    btn_en = types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")
    btn_ru = types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")
    keyboard.add(btn_en, btn_ru)
    await message.answer("🌐 Please select your language:\nВыберите язык:", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("lang_"))
async def process_language(callback_query: types.CallbackQuery):
    user_id = str(callback_query.from_user.id)
    lang = callback_query.data.split("_")[1]
    user_langs[user_id] = lang
    save_langs()
    if lang == "en":
        await bot.send_message(user_id, "✅ Language set to English. You will receive AI futures signals automatically.")
    else:
        await bot.send_message(user_id, "✅ Язык установлен на русский. Вы будете получать сигналы автоматически.")
    await callback_query.answer()

# ------------------ SIGNAL LOOP ------------------
async def send_signals():
    while True:
        try:
            now = datetime.now(timezone.utc)
            if now.second == 0:
                entry_time = now + timedelta(minutes=1)
                formatted_time = entry_time.strftime("%H:%M UTC")
                
                for symbol in SYMBOLS:
                    df = get_futures_klines(symbol, "1m", 100)
                    sig = analyze_symbol(df, symbol)
                    if sig:
                        for user_id_str, lang in user_langs.items():
                            try:
                                user_id = int(user_id_str)
                                pair = sig["symbol"].replace("USDT", "/USDT")
                                direction = sig["direction"]
                                prob = sig["probability"]
                                lev = sig["leverage"]

                                if lang == "en":
                                    dir_text = direction
                                    msg = f"""🤖 AI Futures Signal

💱 Pair: {pair}
🕗 Entry Time: {formatted_time}
⏱ Hold: 5 min
📈 Direction: {dir_text}
✅ Confidence: {prob}%
⚡ Leverage: x{lev}

🔔 Use Market Order on Binance Futures"""
                                else:
                                    dir_text = "ВВЕРХ" if direction == "UP" else "ВНИЗ"
                                    msg = f"""🤖 Сигнал фьючерсов (ИИ)

💱 Пара: {pair}
🕗 Время входа: {formatted_time}
⏱ Удержание: 5 мин
📈 Направление: {dir_text}
✅ Уверенность: {prob}%
⚡ Плечо: x{lev}

🔔 Используйте рыночный ордер на Binance Futures"""
                                
                                await bot.send_message(user_id, msg)
                            except Exception as e:
                                print(f"Failed to send to {user_id_str}: {e}")
        except Exception as e:
            print("Signal loop error:", e)
        await asyncio.sleep(1)

# ------------------ WEB SERVER (KEEP Replit ALIVE) ------------------
app = Flask('')

@app.route('/')
def home():
    return "✅ AI Trading Bot is running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(send_signals())
    executor.start_polling(dp, skip_updates=True)

# ------------------ MAIN ------------------
if __name__ == "__main__":
    print("🚀 Starting AI Trading Bot with Web Server...")
    # Գործարկել web սերվերը առանձին թրեդում
    Thread(target=run_web).start()
    # Գործարկել բոտը
    run_bot()
