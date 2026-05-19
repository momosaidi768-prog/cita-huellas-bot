import os
import re
import stripe
from flask import Flask, request, redirect
from threading import Thread

from openai import OpenAI

from telegram import (
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# ================= CONFIG =================

TOKEN = os.getenv("TOKEN")
STRIPE_KEY = os.getenv("STRIPE_KEY")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
BOT_URL = os.getenv("BOT_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

stripe.api_key = STRIPE_KEY

client = OpenAI(
    api_key=OPENAI_API_KEY
)

# ================= FLASK =================

app = Flask(__name__)

# ================= DATA =================

state = {}
user_data = {}
vip_users = set()

# ================= STRIPE PRICES =================

PRICES = {
    "basic": "price_1TYHooFzJxKrHNTP4xtIxeR4",
    "standard": "price_1TYHX5FzJxKrHNTPRws57oCN",
    "premium": "price_1TYHxaFzJxKrHNTPCDluAs7e"
}

# ================= AI =================

async def ai_reply(user_text):

    try:

        response = client.chat.completions.create(

            model="gpt-4.1-mini",

            messages=[

                {
                    "role": "system",
                    "content": """
أنت مساعد ذكي واحترافي خاص بحجز cita huellas في إسبانيا.

المهام:
- تساعد المستخدم خطوة بخطوة
- تجاوب بالعربية والفرنسية والإسبانية
- تشرح NIE وTIE وAsilo
- تساعد المستخدم في الإدخال
- تكون لطيف واحترافي
- تقنع المستخدم يشترك VIP
- تجاوب بشكل قصير وواضح
"""
                },

                {
                    "role": "user",
                    "content": user_text
                }

            ]

        )

        return response.choices[0].message.content

    except Exception as e:
        return f"❌ AI Error: {e}"

# ================= START =================

async def start(update, context):

    keyboard = ReplyKeyboardMarkup(
        [["🚀 Start"]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        "👋 مرحبا بك في البوت الذكي للحجز\nاضغط Start للبدء",
        reply_markup=keyboard
    )

# ================= HANDLE =================

async def handle(update, context: ContextTypes.DEFAULT_TYPE):

    chat_id = update.effective_chat.id
    text = update.message.text

    # ================= START FLOW =================

    if text == "🚀 Start":

        state[chat_id] = "name"
        user_data[chat_id] = {}

        await update.message.reply_text(
            "👤 اكتب الاسم الكامل:"
        )
        return

    # ================= NAME =================

    if chat_id in state and state[chat_id] == "name":

        user_data[chat_id]["name"] = text

        state[chat_id] = "nie"

        await update.message.reply_text(
            "🆔 اكتب NIE:"
        )
        return

    # ================= NIE =================

    if chat_id in state and state[chat_id] == "nie":

        if not re.match(r'^[XYZ][0-9]{7}[A-Z]$', text.upper()):

            await update.message.reply_text(
                "❌ NIE غير صحيح\nمثال: X1234567L"
            )
            return

        user_data[chat_id]["nie"] = text.upper()

        state[chat_id] = "city"

        await update.message.reply_text(
            "🏙️ اكتب المدينة:"
        )
        return

    # ================= CITY =================

    if chat_id in state and state[chat_id] == "city":

        user_data[chat_id]["city"] = text

        state[chat_id] = "service"

        keyboard = ReplyKeyboardMarkup(
            [
                ["Huellas", "Asilo"],
                ["Recogida NIE", "Extranjería"]
            ],
            resize_keyboard=True
        )

        await update.message.reply_text(
            "📄 اختر الخدمة:",
            reply_markup=keyboard
        )

        return

    # ================= SERVICE =================

    if chat_id in state and state[chat_id] == "service":

        user_data[chat_id]["service"] = text

        state[chat_id] = "confirm"

        d = user_data[chat_id]

        keyboard = InlineKeyboardMarkup([

            [
                InlineKeyboardButton(
                    "💳 الدفع",
                    callback_data="pay"
                )
            ]

        ])

        await update.message.reply_text(

            f"📋 تأكيد المعلومات:\n\n"

            f"👤 الاسم: {d['name']}\n"
            f"🆔 NIE: {d['nie']}\n"
            f"🏙️ المدينة: {d['city']}\n"
            f"📄 الخدمة: {d['service']}",

            reply_markup=keyboard
        )

        return

    # ================= AI CHAT =================

    reply = await ai_reply(text)

    await update.message.reply_text(reply)

# ================= CALLBACK =================

async def confirm(update, context):

    query = update.callback_query

    await query.answer()

    chat_id = query.message.chat.id

    if query.data == "pay":

        keyboard = InlineKeyboardMarkup([

            [
                InlineKeyboardButton(
                    "💎 Basic - 9.99€",
                    url=f"{BOT_URL}/pay/{chat_id}/basic"
                )
            ],

            [
                InlineKeyboardButton(
                    "🔥 Standard - 19.99€",
                    url=f"{BOT_URL}/pay/{chat_id}/standard"
                )
            ],

            [
                InlineKeyboardButton(
                    "🚀 Premium - 29.99€",
                    url=f"{BOT_URL}/pay/{chat_id}/premium"
                )
            ]

        ])

        await query.message.reply_text(
            "💳 اختر الباقة:",
            reply_markup=keyboard
        )

# ================= PAYMENT =================

@app.route("/pay/<chat_id>/<plan>")
def pay(chat_id, plan):

    if plan not in PRICES:
        return "Invalid plan", 400

    try:

        session = stripe.checkout.Session.create(

            mode="payment",

            payment_method_types=["card"],

            line_items=[
                {
                    "price": PRICES[plan],
                    "quantity": 1
                }
            ],

            success_url=f"{BOT_URL}/success",

            cancel_url=f"{BOT_URL}/cancel",

            metadata={
                "chat_id": chat_id
            }

        )

        return redirect(session.url)

    except Exception as e:

        return str(e), 500

# ================= WEBHOOK =================

@app.route("/webhook", methods=["POST"])
def webhook():

    payload = request.data

    sig_header = request.headers.get(
        "Stripe-Signature"
    )

    try:

        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            WEBHOOK_SECRET
        )

    except Exception as e:

        return str(e), 400

    # الدفع ناجح

    if event["type"] == "checkout.session.completed":

        session = event["data"]["object"]

        chat_id = int(
            session["metadata"]["chat_id"]
        )

        vip_users.add(chat_id)

        bot_app.bot.send_message(

            chat_id=chat_id,

            text=(
                "✅ تم الدفع بنجاح\n"
                "🚀 تم تفعيل VIP"
            )

        )

    return "OK", 200

# ================= ROUTES =================

@app.route("/")
def home():

    return "✅ Bot is running"

@app.route("/success")
def success():

    return "✅ Payment successful"

@app.route("/cancel")
def cancel():

    return "❌ Payment canceled"

# ================= BOT =================

def run_bot():

    global bot_app

    bot_app = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    # start

    bot_app.add_handler(
        CommandHandler("start", start)
    )

    # messages

    bot_app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle
        )
    )

    # callback

    bot_app.add_handler(
        CallbackQueryHandler(confirm)
    )

    print("✅ AI Bot Running...")

    bot_app.run_polling(
        drop_pending_updates=True
    )

# ================= MAIN =================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=port
        ),
        daemon=True
    ).start()

    run_bot()
