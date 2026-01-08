import os
import logging
import json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ["7988630119:AAHr-hTQ2NQluGLoWlKPTOguLc2hQVvUb_g"]

ADMINS = {5323988900, 5398441328}
INITIAL_ALLOWED = {5323988900, 5398441328}

ALLOWED_FILE = "allowed_users.txt"
USERNAME_CACHE_FILE = "usernames.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

EXAMPLE = (
    "Մոմ 1 բացում: \n"
    "Մոմ 1 փակում: \n"
    "Մոմ 2 բացում: \n"
    "Մոմ 2 փակում: \n"
    "Մոմ 3 բացում: \n"
    "Մոմ 3 փակում: \n"
    "RSI: \n"
    "Թրենդ: վերև կամ ներքև"
)

WARNING_FOOTER = (
    "\n\n⚠️ Զգուշացում.\n"
    "Տվյալ սիգնալը չի հանդիսանում ֆինանսական խորհրդատվություն, "
    "այլ տրամադրվում է որպես տվյալ արժույթի վերաբերյալ "
    "լրացուցիչ վերլուծական օգնություն։"
)

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def load_allowed_users():
    if not os.path.exists(ALLOWED_FILE):
        with open(ALLOWED_FILE, "w") as f:
            for uid in sorted(INITIAL_ALLOWED):
                f.write(f"{uid}\n")
        return set(INITIAL_ALLOWED)
    with open(ALLOWED_FILE, "r") as f:
        return {int(line.strip()) for line in f if line.strip().isdigit()}

def save_allowed_user(user_id):
    users = load_allowed_users()
    users.add(user_id)
    with open(ALLOWED_FILE, "w") as f:
        for uid in sorted(users):
            f.write(f"{uid}\n")

def remove_allowed_user(user_id):
    users = load_allowed_users()
    users.discard(user_id)
    with open(ALLOWED_FILE, "w") as f:
        for uid in sorted(users):
            f.write(f"{uid}\n")

def load_username_cache():
    if not os.path.exists(USERNAME_CACHE_FILE):
        return {}
    try:
        with open(USERNAME_CACHE_FILE, "r") as f:
            return {int(k): v for k, v in json.load(f).items()}
    except Exception:
        return {}

def save_username_cache(cache):
    with open(USERNAME_CACHE_FILE, "w") as f:
        json.dump({str(k): v for k, v in cache.items()}, f, indent=2, ensure_ascii=False)

def update_username_cache(user_id, username):
    cache = load_username_cache()
    if username:
        cache[user_id] = username
    else:
        cache.pop(user_id, None)
    save_username_cache(cache)

def find_user_id_by_username(target):
    cache = load_username_cache()
    target_clean = target.lstrip("@").lower()
    for uid, uname in cache.items():
        if uname and uname.lower() == target_clean:
            return uid
    return None

def parse_number(s):
    s = s.replace(',', '').replace(' ', '').strip()
    if s.endswith('.'):
        s = s.rstrip('.')
    if not s:
        raise ValueError("Դատարկ տող")
    parts = s.split('.')
    if len(parts) == 1:
        return float(parts[0])
    elif len(parts) == 2:
        return float(s)
    else:
        integer_part = ''.join(parts[:-1])
        decimal_part = parts[-1]
        if not decimal_part:
            return float(integer_part)
        else:
            return float(integer_part + '.' + decimal_part)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username
    update_username_cache(user_id, username)

    if user_id not in load_allowed_users():
        await update.message.reply_text("🔒 Դու չես թույլատրված օգտագործել այս բոտը։")
        return

    msg = "Բարև! 📊 Ուղարկիր տվյալները հետևյալ ձևաչափով՝"
    await update.message.reply_text(msg)
    await update.message.reply_text(f"```\n{EXAMPLE}\n```", parse_mode="Markdown")

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Օգտագործում՝ /approve <user_id կամ @username>")
        return
    arg = context.args[0].strip()
    user_id = None
    if arg.isdigit():
        user_id = int(arg)
    elif arg.startswith("@"):
        user_id = find_user_id_by_username(arg)
        if user_id is None:
            await update.message.reply_text(
                f"Չի գտնվել {arg} username-ով օգտատեր, ով գրել է բոտին։\n"
                "Նախ պետք է այդ մարդը գրի `/start` բոտին:"
            )
            return
    else:
        await update.message.reply_text("Սխալ՝ պետք է լինի user_id կամ @username:")
        return
    save_allowed_user(user_id)
    await update.message.reply_text(f"✅ {arg} հաստատված է։")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Օգտագործում՝ /remove <user_id կամ @username>")
        return
    arg = context.args[0].strip()
    user_id = None
    if arg.isdigit():
        user_id = int(arg)
    elif arg.startswith("@"):
        user_id = find_user_id_by_username(arg)
        if user_id is None:
            await update.message.reply_text(f"Չի գտնվել {arg} username-ով օգտատեր քեշում։")
            return
    else:
        await update.message.reply_text("Սխալ՝ պետք է լինի user_id կամ @username:")
        return
    remove_allowed_user(user_id)
    await update.message.reply_text(f"🚫 {arg} հեռացվեց թույլատրվածների ցուցակից։")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    users = load_allowed_users()
    if not users:
        await update.message.reply_text("Չկան թույլատրված օգտատերեր։")
        return
    cache = load_username_cache()
    lines = []
    for uid in sorted(users):
        uname = cache.get(uid, "—")
        if uname != "—":
            uname = f"@{uname}"
        lines.append(f"🆔 {uid}\n👤 {uname}\n{'─' * 20}")
    await update.message.reply_text("✅ Թույլատրված օգտատերեր․\n\n" + "\n".join(lines))

def parse_message(text):
    lines = text.strip().split('\n')
    data = {}
    for line in lines:
        line = line.strip()
        if not line or ':' not in line:
            continue
        key, val = line.split(':', 1)
        key = key.strip()
        val = val.strip()
        if not val:
            continue

        normalized_key = key.replace(' ', '').lower()
        if 'մոմ1բացում' in normalized_key:
            data['Մոմ 1 բացում'] = parse_number(val)
        elif 'մոմ1փակում' in normalized_key:
            data['Մոմ 1 փակում'] = parse_number(val)
        elif 'մոմ2բացում' in normalized_key:
            data['Մոմ 2 բացում'] = parse_number(val)
        elif 'մոմ2փակում' in normalized_key:
            data['Մոմ 2 փակում'] = parse_number(val)
        elif 'մոմ3բացում' in normalized_key:
            data['Մոմ 3 բացում'] = parse_number(val)
        elif 'մոմ3փակում' in normalized_key:
            data['Մոմ 3 փակում'] = parse_number(val)
        elif key == 'RSI':
            data['RSI'] = parse_number(val)
        elif key == 'Թրենդ':
            data['թրենդ'] = val.strip().lower()
    return data

def validate_data(data):
    required = [
        'Մոմ 1 բացում', 'Մոմ 1 փակում',
        'Մոմ 2 բացում', 'Մոմ 2 փակում',
        'Մոմ 3 բացում', 'Մոմ 3 փակում',
        'RSI', 'թրենդ'
    ]
    missing = []
    for field in required:
        if field not in 
            missing.append(field)
    if 'թրենդ' in data and data['թրենդ'] not in ['վերև', 'ներքև']:
        missing.append('թրենդ (պետք է լինի՝ վերև կամ ներքև)')
    return missing

def analyze(data):
    try:
        o1, c1 = data['Մոմ 1 բացում'], data['Մոմ 1 փակում']
        o2, c2 = data['Մոմ 2 բացում'], data['Մոմ 2 փակում']
        o3, c3 = data['Մոմ 3 բացում'], data['Մոմ 3 փակում']
        rsi = data['RSI']
        trend = data['թրենդ']

        reasons = []
        score = 0

        if rsi <= 30:
            score += 4
            reasons.append(f"RSI = {rsi:.1f} → խորը գերվաճառված")
        elif rsi < 40:
            score += 2
            reasons.append(f"RSI = {rsi:.1f} → գերվաճառված")
        elif rsi >= 70:
            score -= 4
            reasons.append(f"RSI = {rsi:.1f} → խորը գերգնահատված")
        elif rsi > 60:
            score -= 2
            reasons.append(f"RSI = {rsi:.1f} → գերգնահատված")
        else:
            reasons.append(f"RSI = {rsi:.1f} → չեզոք")

        if c3 > o3:
            body = c3 - o3
            score += 2
            reasons.append("Մոմ 3-ը դրական է (գնում)")
            if body >= o3 * 0.0025:
                reasons.append("Մոմ 3-ի մարմինը մեծ է → ուժեղ շարժ")
                score += 1
            else:
                reasons.append("Մոմ 3-ի մարմինը փոքր է → թույլ շարժ")
        else:
            body = o3 - c3
            score -= 2
            reasons.append("Մոմ 3-ը բացասական է (վաճառք)")
            if body >= o3 * 0.0025:
                reasons.append("Մոմ 3-ի մարմինը մեծ է → ուժեղ շարժ")
                score -= 1
            else:
                reasons.append("Մոմ 3-ի մարմինը փոքր է → թույլ շարժ")

        if trend == "վերև":
            score += 2
            reasons.append("Թրենդը վերև է → համապատասխանում է գնմանը")
        elif trend == "ներքև":
            score -= 2
            reasons.append("Թրենդը ներքև է → հակառակ է գնմանը")

        if c1 < c2 < c3:
            score += 1
            reasons.append("Փակման գները ձևավորում են Higher Highs → վստահելի վերելք")
        elif c1 > c2 > c3:
            score -= 1
            reasons.append("Փակման գները ձևավորում են Lower Lows → վստահելի իջեցում")

        if score >= 5:
            signal = "✅ ԳՆԻՐ (ՈՒԺԵՂ ՍԻԳՆԱԼ)"
        elif score >= 3:
            signal = "✅ ԳՆԻՐ"
        elif score <= -5:
            signal = "❌ ՎԱՃԱՌՔ (ՈՒԺԵՂ ՍԻԳՆԱԼ)"
        elif score <= -3:
            signal = "❌ ՎԱՃԱՌՔ"
        else:
            result = (
                f"**Fenix AI**\n\n"
                f"🔄 ՈՒՇԱԴՐՈՒԹՅՈՒՆ: Բավարար հաստատում չկա\n"
                "Շարունակիր հետևել շուկային"
                + WARNING_FOOTER
            )
            return result

        result = (
            f"**Fenix AI**\n\n"
            f"{signal}\n"
            f"📈 Վերջին գին: {c3:,.2f}\n"
            "🔍 Պրոֆեսիոնալ վերլուծություն:\n" +
            "\n".join(f" - {r}" for r in reasons)
            + WARNING_FOOTER
        )
        return result

    except Exception as e:
        return f"Վերլուծության սխալ: {str(e)}"

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in load_allowed_users():
        await update.message.reply_text("🔒 Դու չես թույլատրված օգտագործել այս բոտը։")
        return

    text = update.message.text
    data = parse_message(text)
    missing = validate_data(data)

    if missing:
        error_msg = "❌ Պակասում են հետևյալ տվյալները:\n"
        for field in missing:
            error_msg += f"- {field}\n"
        error_msg += "\nՈւղարկիր ճիշտ ձևաչափով՝"
        await update.message.reply_text(error_msg)
        await update.message.reply_text(f"```\n{EXAMPLE}\n```", parse_mode="Markdown")
        return

    result = analyze(data)
    await update.message.reply_text(f"📊 **ՎԵՐԼՈՒԾՈՒԹՅՈՒՆ**:\n\n{result}", parse_mode="Markdown")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("approve", approve_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("list", list_users))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Fenix AI բոտը ակտիվ է...")
    app.run_polling()

if __name__ == "__main__":
    main()
