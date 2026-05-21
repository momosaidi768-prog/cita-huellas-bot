import os
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)
from playwright.async_api import async_playwright

# ================= CONFIG =================

TOKEN = "8202293986:AAEnZuCcvl6Gf98Th9b6hnfj3ZLg6gmnC5k"
ADMIN_ID = 6675176280

# ================= ADMIN CHECK =================

def is_admin(user_id: int):
    return user_id == ADMIN_ID

# ================= PLAYWRIGHT =================

async def open_site(url: str):

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )

        page = await browser.new_page()

        await page.goto(url, timeout=60000)

        await page.screenshot(path="screen.png")

        await browser.close()

# ================= TELEGRAM =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ Not allowed")

    await update.message.reply_text(
        "✅ Bot is running\n\n"
        "Command:\n"
        "/open https://example.com"
    )

async def open_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ Not allowed")

    if not context.args:
        return await update.message.reply_text(
            "Usage:\n/open https://example.com"
        )

    url = context.args[0]

    await update.message.reply_text("🌐 Opening website...")

    try:

        await open_site(url)

        with open("screen.png", "rb") as photo:
            await update.message.reply_photo(photo=photo)

    except Exception as e:

        await update.message.reply_text(
            f"❌ Error:\n{e}"
        )

# ================= MAIN =================

def main():

    if not TOKEN:
        raise ValueError("TOKEN variable missing")

    if ADMIN_ID == 0:
        raise ValueError("ADMIN_ID variable missing")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("open", open_cmd))

    print("Bot started...")

    app.run_polling()

# ================= START =================

if __name__ == "__main__":
    main()
