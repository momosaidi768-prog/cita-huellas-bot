import sqlite3
import stripe
import asyncio
import random
import re
import threading

from flask import Flask, request

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters
)

# =====================================================
# CONFIG
# =====================================================
TOKEN = ""

stripe.api_key = ""

WEBHOOK_SECRET = ""
# =====================================================
# PRICE IDS
# =====================================================

BASIC_PRICE_ID = ""
VIP_PRICE_ID = ""
PRO_PRICE_ID = ""
# =====================================================
# DATABASE
# =====================================================

conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    name TEXT,
    nie TEXT,
    city TEXT,
    service TEXT,
    plan TEXT,
    active INTEGER DEFAULT 0,
    last_alert TEXT
)
""")

conn.commit()

# =====================================================
# MEMORY
# =====================================================

state = {}
data = {}
BOT = None

# =====================================================
# APPOINTMENTS
# =====================================================

APPOINTMENTS = [
    ("Madrid", "Asilo"),
    ("Barcelona", "Huellas"),
    ("Sevilla", "Extranjería"),
    ("Málaga", "Tarjeta"),
    ("Valencia", "Huellas"),
    ("Alicante", "Asilo")
]

SEARCH_MSGS = [
    "🔎 كنقلبو على موعد مناسب...",
    "📡 جاري الفحص...",
    "⏳ المرجو الانتظار...",
    "📅 نبحث عن موعد جديد...",
    "⚡ يتم تحديث المواعيد..."
]

# =====================================================
# KEYBOARDS
# =====================================================

start_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🚀 Start")],
        [KeyboardButton("ℹ️ معلومات")],
        [KeyboardButton("💎 الباقات")],
        [KeyboardButton("📞 الدعم")]
    ],
    resize_keyboard=True
)

services_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🪪 Huellas")],
        [KeyboardButton("⚖️ Asilo")],
        [KeyboardButton("🏢 Extranjería")],
        [KeyboardButton("💳 Tarjeta")]
    ],
    resize_keyboard=True
)

plans_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🟢 BASIC - 30€")],
        [KeyboardButton("🔵 VIP - 60€")],
        [KeyboardButton("🟣 PRO - 100€")]
    ],
    resize_keyboard=True
)

menu_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📅 حالة البحث")],
        [KeyboardButton("📍 تغيير المدينة")],
        [KeyboardButton("💎 الباقات")],
        [KeyboardButton("📞 الدعم")]
    ],
    resize_keyboard=True
)

# =====================================================
# START
# =====================================================

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 مرحباً بك 🇪🇸\n\nاضغط Start للبدء 👇",
        reply_markup=start_keyboard
    )

# =====================================================
# NIE VALIDATION
# =====================================================

def is_valid_nie(nie):

    return re.match(
        r'^[XYZ]\d{7}[A-Z]$',
        nie.upper()
    ) is not None

# =====================================================
# ALERT SYSTEM
# =====================================================

def get_alert(last):

    options = [
        a for a in APPOINTMENTS
        if f"{a[0]}-{a[1]}" != last
    ]

    if not options:
        options = APPOINTMENTS

    return random.choice(options)

async def send_alert(chat_id):

    await BOT.send_message(
        chat_id,
        random.choice(SEARCH_MSGS)
    )

    await asyncio.sleep(
        random.randint(2, 5)
    )

    cursor.execute(
        "SELECT last_alert FROM users WHERE chat_id=?",
        (chat_id,)
    )

    row = cursor.fetchone()

    last = row[0] if row else None

    city, typ = get_alert(last)

    text = (
        f"📢 تنبيه جديد\n\n"
        f"🏙️ المدينة: {city}\n"
        f"📋 الخدمة: {typ}\n"
        f"⚡ الموعد متاح حالياً"
    )

    await BOT.send_message(chat_id, text)

    cursor.execute("""
    UPDATE users
    SET last_alert=?
    WHERE chat_id=?
    """, (
        f"{city}-{typ}",
        chat_id
    ))

    conn.commit()

# =====================================================
# PAYMENT LINK
# =====================================================

def create_payment_link(plan):

    return "https://checkout.stripe.com/pay"

# =====================================================
# HANDLE
# =====================================================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    text = update.message.text

    # START

    if text == "/start":

        await welcome(update, context)
        return

    if text == "🚀 Start":

        state[chat_id] = "name"

        await update.message.reply_text(
            "👤 اكتب الاسم الكامل:"
        )

        return

    # INFO

    if text == "ℹ️ معلومات":

        await update.message.reply_text(
            "🤖 هذا البوت يبحث عن مواعيد NIE و Asilo في إسبانيا."
        )

        return

    # PLANS

    if text == "💎 الباقات":

        await update.message.reply_text(
            "🟢 BASIC - 30€\n"
            "🔵 VIP - 60€\n"
            "🟣 PRO - 100€"
        )

        return

    # SUPPORT

    if text == "📞 الدعم":

        await update.message.reply_text(
            "📩 تواصل مع الدعم:\n@yourusername"
        )

        return

    # STATUS

    if text == "📅 حالة البحث":

        await update.message.reply_text(
            "🔎 البوت يبحث حالياً عن موعد مناسب لك..."
        )

        return

    # NAME

    if state.get(chat_id) == "name":

        data[chat_id] = {
            "name": text
        }

        state[chat_id] = "nie"

        await update.message.reply_text(
            "🪪 اكتب NIE:"
        )

        return

    # NIE

    if state.get(chat_id) == "nie":

        if not is_valid_nie(text):

            await update.message.reply_text(
                "❌ NIE غير صحيح"
            )

            return

        data[chat_id]["nie"] = text.upper()

        state[chat_id] = "city"

        await update.message.reply_text(
            "🏙️ اكتب المدينة:"
        )

        return

    # CITY

    if state.get(chat_id) == "city":

        data[chat_id]["city"] = text

        state[chat_id] = "service"

        await update.message.reply_text(
            "📋 اختر الخدمة:",
            reply_markup=services_keyboard
        )

        return

    # SERVICE

    if state.get(chat_id) == "service":

        data[chat_id]["service"] = text

        state[chat_id] = "plan"

        await update.message.reply_text(
            "💎 اختر الباقة:",
            reply_markup=plans_keyboard
        )

        return

    # PLAN

    if state.get(chat_id) == "plan":

        plan = "BASIC"

        if "VIP" in text:
            plan = "VIP"

        elif "PRO" in text:
            plan = "PRO"

        data[chat_id]["plan"] = plan

        cursor.execute("""
        INSERT OR REPLACE INTO users (
            chat_id,
            name,
            nie,
            city,
            service,
            plan,
            active
        )
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (
            chat_id,
            data[chat_id]["name"],
            data[chat_id]["nie"],
            data[chat_id]["city"],
            data[chat_id]["service"],
            plan
        ))

        conn.commit()

        payment_link = create_payment_link(plan)

        await update.message.reply_text(
            f"💳 رابط الدفع:\n{payment_link}",
            reply_markup=menu_keyboard
        )

        state.pop(chat_id, None)

        return

    # DEFAULT

    await update.message.reply_text(
        "👆 اضغط على Start للبدء"
    )

# =====================================================
# SCHEDULER
# =====================================================

async def scheduler(app):

    global BOT

    BOT = app.bot

    while True:

        cursor.execute("""
        SELECT chat_id
        FROM users
        WHERE active=1
        """)

        users = cursor.fetchall()

        for (chat_id,) in users:

            # 5 رسائل بحث

            for _ in range(5):

                await BOT.send_message(
                    chat_id,
                    random.choice(SEARCH_MSGS)
                )

                await asyncio.sleep(
                    random.randint(1, 3)
                )

            # 3 تنبيهات

            for _ in range(3):

                await send_alert(chat_id)

                await asyncio.sleep(
                    random.randint(5, 10)
                )

        await asyncio.sleep(86400)

# =====================================================
# FLASK
# =====================================================

flask_app = Flask(__name__)

@flask_app.route("/webhook", methods=["POST"])
def webhook():

    payload = request.data

    sig = request.headers.get(
        "Stripe-Signature"
    )

    try:

        stripe.Webhook.construct_event(
            payload,
            sig,
            WEBHOOK_SECRET
        )

    except:

        return "error", 400

    return "ok"

# =====================================================
# RUN BOT
# =====================================================

def run_bot():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(
        MessageHandler(filters.TEXT, handle)
    )

    global BOT

    BOT = app.bot

    print("🚀 BOT RUNNING...")

    threading.Thread(
        target=lambda: asyncio.run(
            scheduler(app)
        ),
        daemon=True
    ).start()

    app.run_polling()

# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    run_bot()
