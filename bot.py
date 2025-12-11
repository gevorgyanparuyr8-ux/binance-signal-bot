import sqlite3
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8264707362:AAGZPrNPRl-GREvGrPUs72y8wnu_ws4ihV4"

# Ռեֆերալ համակարգ
def init_db():
    conn = sqlite3.connect('referrals.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            ref_by INTEGER,
            ref_count INTEGER DEFAULT 0,
            ton_earned REAL DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('referrals.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def add_user(user_id, ref_by=None):
    conn = sqlite3.connect('referrals.db')
    c = conn.cursor()
    if ref_by and ref_by != user_id:
        c.execute('INSERT OR IGNORE INTO users (user_id, ref_by) VALUES (?, ?)', (user_id, ref_by))
        c.execute('UPDATE users SET ref_count = ref_count + 1 WHERE user_id = ?', (ref_by,))
        c.execute('UPDATE users SET ton_earned = ton_earned + 0.01 WHERE user_id = ?', (ref_by,))
    else:
        c.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_param = context.args[0] if context.args else None
    ref_by = int(ref_param) if ref_param and ref_param.isdigit() else None

    add_user(user_id, ref_by)

    ref_link = f"https://t.me/referalamd_bot?start={user_id}"
    await update.message.reply_text(
        "Բարի գալուստ ռեֆերալ բոտ!\n\n"
        f"Ձեր ռեֆերալ հղումը՝\n{ref_link}\n\n"
        "Կիսվեք այս հղումով և վաստակեք 0.01 TON յուրաքանչյուր նոր օգտատիրոջ համար:"
    )

async def referal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    add_user(user_id)  # Համոզվենք, որ օգտատերը գրանցված է
    user = get_user(user_id)
    if user:
        _, _, ref_count, ton_earned = user
        await update.message.reply_text(
            f"Ձեր ռեֆերալների քանակը՝ {ref_count}\n"
            f"Վաստակած TON՝ {ton_earned:.4f}"
        )
    else:
        await update.message.reply_text("Սխալ. Փորձեք նորից /start հրամանը:")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referal", referal))
    app.run_polling()

if __name__ == "__main__":
    main()
