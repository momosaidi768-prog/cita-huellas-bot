import asyncio
import sqlite3
import aiohttp
import os
from playwright.async_api import async_playwright

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise Exception("BOT_TOKEN not set in Railway Variables")

ADMIN_ID = os.getenv("ADMIN_ID")
if not ADMIN_ID:
    raise Exception("ADMIN_ID not set in Railway Variables")

ADMIN_ID = int(ADMIN_ID)

TG_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

URL = "https://icp.administracionelectronica.gob.es/icpplus/index.html"

CITIES = [
    "MADRID","BARCELONA","TOLEDO","ALICANTE","SEVILLA",
    "BILBAO","VALENCIA","GRANADA","CORDOBA","MALAGA"
]

# ================= TELEGRAM =================

class Telegram:
    def __init__(self):
        self.session = None

    async def init(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def send(self, msg):
        await self.init()
        await self.session.post(
            TG_URL,
            data={"chat_id": ADMIN_ID, "text": msg}
        )

tg = Telegram()

# ================= DB =================

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

async def check_city(context, city):
    page = await context.new_page()

    try:
        await page.goto(URL, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")

        html = await page.content()

        result = "no hay citas" not in html.lower()

        await page.close()
        return result

    except Exception as e:
        print("Check error:", e)
        await page.close()
        return False

# ================= WORKER =================

async def worker():
    await tg.init()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )
        context = await browser.new_context()

        while True:
            for city in CITIES:

                users = get_users_by_city(city)
                found = await check_city(context, city)

                if found and users:
                    for user in users:
                        await tg.send(
f"""🔥 CITA DISPONIBLE

📍 City: {city}

👤 {user[0]}
📄 {user[1]}
📧 {user[3]}
📞 {user[4]}

🔗 {URL}

⚠️ Manual confirmation required
"""
                        )

                    await asyncio.sleep(30)

                await asyncio.sleep(3)

            await asyncio.sleep(10)

# ================= MAIN =================

async def main():
    await tg.init()

    await tg.send("🤖 Bot started successfully")

    print("MAIN STARTED")

    await worker()
 
