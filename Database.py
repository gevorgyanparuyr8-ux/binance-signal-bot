import sqlite3
from typing import Optional

def init_db():
    conn = sqlite3.connect('dojo.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            google_id TEXT UNIQUE,
            name TEXT,
            email TEXT,
            balance_usdt REAL DEFAULT 0.0,
            promo_used TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS promo_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            reward_usdt REAL,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    conn.commit()
    return conn

DB = init_db()

# Սկզբնական Promo Code-ներ (կարող ես փոխել)
init_c = DB.cursor()
init_c.execute("INSERT OR IGNORE INTO promo_codes (code, reward_usdt, max_uses) VALUES ('WELCOME', 5000, 100)")
init_c.execute("INSERT OR IGNORE INTO promo_codes (code, reward_usdt, max_uses) VALUES ('DOJO10K', 10000, 50)")
DB.commit()

def get_user_by_google_id(google_id: str):
    c = DB.cursor()
    c.execute("SELECT * FROM users WHERE google_id = ?", (google_id,))
    row = c.fetchone()
    if row:
        return {"id": row[0], "google_id": row[1], "name": row[2], "email": row[3], "balance_usdt": row[4], "promo_used": row[5]}
    return None

def create_user(google_id: str, name: str, email: str):
    c = DB.cursor()
    c.execute("INSERT INTO users (google_id, name, email) VALUES (?, ?, ?)", (google_id, name, email))
    DB.commit()
    return get_user_by_google_id(google_id)

def get_user_balance(user_id: int) -> float:
    c = DB.cursor()
    c.execute("SELECT balance_usdt FROM users WHERE id = ?", (user_id,))
    return c.fetchone()[0]

def update_balance(user_id: int, new_balance: float):
    c = DB.cursor()
    c.execute("UPDATE users SET balance_usdt = ? WHERE id = ?", (new_balance, user_id))
    DB.commit()

def mark_promo_used(user_id: int, code: str):
    c = DB.cursor()
    c.execute("UPDATE users SET promo_used = ?, balance_usdt = balance_usdt + (SELECT reward_usdt FROM promo_codes WHERE code = ?) WHERE id = ?", (code, code, user_id))
    DB.commit()
    c.execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?", (code,))
    DB.commit()

def get_promo_code(code: str):
    c = DB.cursor()
    c.execute("""
        SELECT code, reward_usdt, max_uses, used_count, is_active 
        FROM promo_codes 
        WHERE code = ? AND is_active = 1 AND used_count < max_uses
    """, (code.upper(),))
    row = c.fetchone()
    if row:
        return {
            "code": row[0],
            "reward_usdt": row[1],
            "max_uses": row[2],
            "used_count": row[3]
        }
    return None
