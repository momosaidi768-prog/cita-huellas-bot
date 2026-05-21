import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from playwright.async_api import async_playwright

TOKEN = os.getenv("8202293986:AAEnZuCcvl6Gf98Th9b6hnfj3ZLg6gmnC5k")
ADMIN_ID = int(os.getenv("6675176280"))

# ================= CHECK ADMIN =================

def is_admin(user_id):
    return user_id == ADMIN_ID

# ================= PLAYWRIGHT =================

async def open_site(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        page = await browser.new_page()
        await page.goto(url)

        await page.screenshot(path="screen.png")

        await browser.close()

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ Not authorized")

    await update.message.reply_text("Bot running ✔\nUse /open https://site.com")

async def open_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ Not authorized")

    if not context.args:
        return await update.message.reply_text("Example: /open https://example.com")

    url = context.args[0]

    await update.message.reply_text("Opening site...")

    await open_site(url)

    await update.message.reply_photo(photo=open("screen.png", "rb"))

# ================= RUN =================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("open", open_cmd))

app.run_polling()
