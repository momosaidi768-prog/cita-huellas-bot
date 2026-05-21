import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from playwright.async_api import async_playwright

# ================= CONFIG =================
TOKEN = os.getenv("8202293986:AAEnZuCcvl6Gf98Th9b6hnfj3ZLg6gmnC5k")
ADMIN_ID = int(os.getenv("6675176280"))

def is_admin(user_id: int):
    return user_id == ADMIN_ID

# ================= PLAYWRIGHT =================
async def open_site(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
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
        "Bot is running ✔\nCommand:\n/open https://example.com"
    )

async def open_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return await update.message.reply_text("⛔ Not allowed")

    if not context.args:
        return await update.message.reply_text("Usage: /open https://example.com")

    url = context.args[0]

    await update.message.reply_text("Opening site...")

    try:
        await open_site(url)
        await update.message.reply_photo(photo=open("screen.png", "rb"))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("open", open_cmd))

    app.run_polling()

if __name__ == "__main__":
    main()
