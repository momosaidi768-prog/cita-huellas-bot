import asyncio
import sqlite3
import aiohttp
import os
from playwright.async_api import async_playwright

# ================= CONFIG =================

TOKEN = os.getenv("8202293986:AAEnZuCcvl6Gf98Th9b6hnfj3ZLg6gmnC5k")
if not TOKEN:
    raise Exception("BOT_TOKEN not set in Railway Variables")

ADMIN_ID = int(os.getenv("6675176280", "0"))

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
            await self.session.post(
                TG_URL,
                data={
                    "chat_id": ADMIN_ID,
                    "text": msg
                }
            )
        except Exception as e:
            print("Telegram error:", e)

tg = Telegram()

# ================= DATABASE =================

conn = sqlite3.connect("users.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    nie TEXT,
    city TEXT,
    email TEXT,
    phone TEXT,
    active INTEGER DEFAULT 1
)
""")

conn.commit()

def get_users_by_city(city):
    cur.execute(
        "SELECT name, nie, city, email, phone FROM users WHERE city=? AND active=1",
        (city,)
    )
    return cur.fetchall()

# ================= CHECK =================

async def check_city(page, city):
    try:
        await page.goto(URL, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")

        html = await page.content()

        # شرط بسيط (يمكن تطويره حسب الموقع)
        if "no hay citas" not in html.lower():
            return True

        return False

    except Exception as e:
        print("Error:", e)
        return False

# ================= WORKER =================

async def worker():
    await tg.init()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        while True:
            for city in CITIES:

                users = get_users_by_city(city)

                found = await check_city(page, city)

                if found and users:

                    for user in users:
                        await tg.send(
f"""🔥 CITA DISPONIBLE

📍 City: {city}

👤 Name: {user[0]}
📄 NIE: {user[1]}
📧 Email: {user[3]}
📞 Phone: {user[4]}

🔗 Link:
{URL}

⚠️ Complete manually and confirm appointment
"""
                        )

                    await asyncio.sleep(30)

                await asyncio.sleep(3)

            await asyncio.sleep(10)

# ================= MAIN =================

async def main():
    await tg.init()

    asyncio.create_task(worker())

    await tg.send("🤖 Bot started successfully and monitoring appointments...")

    while True:
        await asyncio.sleep(60)

# ================= RUN =================

if __name__ == "__main__":
    asyncio.run(main())
