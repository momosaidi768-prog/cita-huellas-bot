import threading
import time
import requests
import sqlite3
import random

from flask import Flask, redirect, request
import stripe

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# =====================
# CONFIG
# =====================

TOKEN = "8202293986:AAH2hTDMw4XjwsnatyfvzSmR-LDAz5ZidYE"

stripe.api_key = "YOUR_STRIPE_SECRET_KEY"
BOT_URL = "https://t.me/YOUR_BOT_USERNAME"

# =====================
# DATABASE
# =====================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    city TEXT,
    office TEXT,
    vip_until INTEGER DEFAULT 0
)
""")

conn.commit()

def save_user(chat_id, city=None, office=None):
    cursor.execute("INSERT OR IGNORE INTO users(chat_id) VALUES (?)", (chat_id,))
    if city:
        cursor.execute("UPDATE users SET city=? WHERE chat_id=?", (city, chat_id))
    if office:
        cursor.execute("UPDATE users SET office=? WHERE chat_id=?", (office, chat_id))
    conn.commit()

def set_vip(chat_id):
    expire = int(time.time()) + 30 * 24 * 60 * 60
    cursor.execute("UPDATE users SET vip_until=? WHERE chat_id=?", (expire, chat_id))
    conn.commit()

def is_vip(chat_id):
    row = cursor.execute("SELECT vip_until FROM users WHERE chat_id=?", (chat_id,)).fetchone()
    return row and row[0] > time.time()

def get_users():
    return cursor.execute("SELECT chat_id, city, office FROM users").fetchall()

# =====================
# FLASK APP (PAYMENT)
# =====================

webapp = Flask(__name__)

@webapp.route("/pay/<chat_id>")
def pay(chat_id):

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": "VIP Subscription"
                },
                "unit_amount": 999
            },
            "quantity": 1
        }],
        success_url=BOT_URL,
        cancel_url=BOT_URL,
        metadata={"chat_id": chat_id}
    )

    return redirect(session.url, code=303)


@webapp.route("/webhook", methods=["POST"])
def webhook():

    event = request.json

    if event["type"] == "checkout.session.completed":

        chat_id = int(event["data"]["object"]["metadata"]["chat_id"])
        set_vip(chat_id)

        print("✅ VIP ACTIVATED:", chat_id)

    return "ok"

# =====================
# BOT STATE
# =====================

state = {}

def menu():
    return ReplyKeyboardMarkup([
        ["🚀 Start"],
        ["📅 Appointment", "💳 VIP"],
        ["ℹ️ Help"]
    ], resize_keyboard=True)

# =====================
# START
# =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 Welcome Bot SaaS",
        reply_markup=menu()
    )

# =====================
# VIP BUTTON
# =====================

async def vip(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id

    url = f"http://127.0.0.1:5000/pay/{chat_id}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 9.99€ VIP", url=url)]
    ])

    await update.message.reply_text("💳 Upgrade VIP", reply_markup=keyboard)

# =====================
# HANDLER
# =====================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    text = update.message.text

    if text == "🚀 Start":
        state[chat_id] = "city"
        await update.message.reply_text("🏙️ اكتب المدينة")
        return

    if text == "📅 Appointment":
        state[chat_id] = "city"
        await update.message.reply_text("🏙️ اكتب المدينة")
        return

    if text == "💳 VIP":
        await vip(update, context)
        return

    if text == "ℹ️ Help":
        await update.message.reply_text("📌 استعمل الأزرار أو كتب المدينة")
        return

    if state.get(chat_id) == "city":
        save_user(chat_id, city=text)
        state[chat_id] = "office"
        await update.message.reply_text("🏢 المكتب")
        return

    if state.get(chat_id) == "office":
        save_user(chat_id, office=text)
        state.pop(chat_id)

        await update.message.reply_text("✔ تم التسجيل بنجاح")

# =====================
# MONITOR SYSTEM
# =====================

def monitor():

    last_state = False

    while True:

        users = get_users()

        for chat_id, city, office in users:

            if not is_vip(chat_id):
                continue

            available = random.choice([True, False])

            if available and not last_state:

                try:
                    requests.post(
                        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": f"🚨 Slot available in {city}"
                        }
                    )
                except:
                    pass

        last_state = available
        time.sleep(60)

# =====================
# BOT RUNNER
# =====================

def run_bot():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("🤖 BOT RUNNING...")

    app.run_polling()

# =====================
# MAIN (IMPORTANT FIX)
# =====================

if __name__ == "__main__":

    # start monitor in background
    threading.Thread(target=monitor, daemon=True).start()

    # start flask in background thread
    threading.Thread(target=lambda: webapp.run(host="0.0.0.0", port=5000), daemon=True).start()

    # run bot (ONLY THIS in main thread)
    run_bot()
