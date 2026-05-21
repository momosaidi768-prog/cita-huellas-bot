import asyncio
import sqlite3
import aiohttp
import os
from playwright.async_api import async_playwright

# ================= CONFIG =================

TOKEN = os.getenv("8202293986:AAEnZuCcvl6Gf98Th9b6hnfj3ZLg6gmnC5k")
ADMIN_ID = int(os.getenv("6675176280"))

TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

URL = "https://icp.administracionelectronica.gob.es/icpplus/index.html"

CITIES = [
    "MADRID","BARCELONA","TOLEDO","ALICANTE","SEVILLA",
    "BILBAO","VALENCIA","GRANADA","CORDOBA","MALAGA"
]

SERVICE = "POLICÍA - TOMA DE HUELLAS (EXPEDICIÓN DE TARJETA)"

# ================= TELEGRAM =================

class Telegram:
    def __init__(self):
        self.session = None

    async def init(self):
        self.session = aiohttp.ClientSession()

    async def send(self, msg):
        try:
            await self.session.post(TG_URL, data={
                "chat_id": ADMIN_ID,
                "text": msg
            })
        except:
            pass

tg = Telegram()

# ================= DATABASE =================

conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    name TEXT,
    nie TEXT,
    city TEXT,
    email TEXT,
    phone TEXT,
    active INTEGER DEFAULT 1
)
""")
conn.commit()

def add_user(name, nie, city, email, phone):
    cur.execute(
        "INSERT INTO users(name,nie,city,email,phone) VALUES(?,?,?,?,?)",
        (name, nie, city, email, phone)
    )
    conn.commit()

def list_users():
    cur.execute("SELECT name,nie,city FROM users WHERE active=1")
    return cur.fetchall()

def get_users_by_city(city):
    cur.execute(
        "SELECT name,nie,city,email,phone FROM users WHERE city=? AND active=1",
        (city,)
    )
    return cur.fetchall()

# ================= PLAYWRIGHT =================

async def check(page, city):

    try:
        await page.goto(URL, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")

        selects = page.locator("select")
        await selects.first.select_option(label=city)

        await page.click("input[type='submit']")
        await page.wait_for_load_state("domcontentloaded")

        selects = page.locator("select")
        await selects.first.select_option(label=SERVICE)

        await page.click("input[type='submit']")
        await page.wait_for_load_state("domcontentloaded")

        html = await page.content()

        return "no hay citas" not in html.lower()

    except:
        return False

# ================= BOT CONTROL =================

running = False

async def worker():

    global running

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        page = await browser.new_page()

        while running:

            for city in CITIES:

                users = get_users_by_city(city)

                for user in users:

                    found = await check(page, city)

                    if found:

                        await tg.send(f"""
🔥 APPOINTMENT FOUND

📍 City: {city}

👤 {user[0]}
📄 NIE: {user[1]}
🏙 City: {user[2]}
📧 {user[3]}
📞 {user[4]}

🔗 {URL}

⚠ Confirm manually
""")

                        await asyncio.sleep(60)

                    await asyncio.sleep(2)

        await browser.close()

# ================= HANDLER =================

async def handle(text):

    global running

    if text.startswith("/add"):
        try:
            _, name, nie, city, email, phone = text.split(" ")

            add_user(name, nie, city, email, phone)
            await tg.send("✅ User added")

        except:
            await tg.send("❌ Format: /add name nie city email phone")

    elif text == "/list":
        users = list_users()
        await tg.send("\n".join([f"{u[0]} - {u[1]} - {u[2]}" for u in users]))

    elif text == "/startbot":
        if not running:
            running = True
            asyncio.create_task(worker())
            await tg.send("🚀 Bot started")

    elif text == "/stopbot":
        running = False
        await tg.send("⛔ Bot stopped")

# ================= MAIN =================

async def main():

    await tg.init()
    await tg.send("🤖 Bot ready")

    offset = None

    while True:

        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}"
                ) as r:
                    data = await r.json()

            for upd in data.get("result", []):

                offset = upd["update_id"] + 1

                msg = upd.get("message", {}).get("text")

                if msg:
                    chat_id = upd["message"]["chat"]["id"]

                    if chat_id == ADMIN_ID:
                        await handle(msg)

        except:
            pass

        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
