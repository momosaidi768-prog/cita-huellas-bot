import asyncio
import sqlite3
import aiohttp
import os
from playwright.async_api import async_playwright

# ================= CONFIG =================

TOKEN = os.getenv("8202293986:AAEnZuCcvl6Gf98Th9b6hnfj3ZLg6gmnC5k")

ADMIN_ID = 6675176280
if ADMIN_ID is None:
    raise Exception("ADMIN_ID not set in Railway Variables")

ADMIN_ID = int(ADMIN_ID)

TG_URL = f"https://api.telegram.org/bot{TOKEN}"

URL = "https://icp.administracionelectronica.gob.es/icpplus/index.html"

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
                f"{TG_URL}/sendMessage",
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

# ================= DATABASE FUNCTIONS =================

def add_user(name, nie, city, email, phone):

    cur.execute(
        """
        INSERT INTO users(name, nie, city, email, phone)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, nie, city.upper(), email, phone)
    )

    conn.commit()

def list_users():

    cur.execute("""
    SELECT name, nie, city
    FROM users
    WHERE active=1
    """)

    return cur.fetchall()

def get_cities():

    cur.execute("""
    SELECT DISTINCT city
    FROM users
    WHERE active=1
    """)

    return [row[0] for row in cur.fetchall()]

def get_users_by_city(city):

    cur.execute("""
    SELECT name, nie, city, email, phone
    FROM users
    WHERE city=? AND active=1
    """, (city.upper(),))

    return cur.fetchall()

# ================= PLAYWRIGHT =================

async def check_appointments(page, city):

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

        if "no hay citas" in html.lower():
            return False

        return True

    except Exception as e:
        print("Check error:", e)
        return False

# ================= BOT LOOP =================

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

            try:

                cities = get_cities()

                for city in cities:

                    found = await check_appointments(page, city)

                    if found:

                        users = get_users_by_city(city)

                        for user in users:

                            msg = f"""
🔥 APPOINTMENT FOUND

📍 City: {city}

👤 Name: {user[0]}
📄 NIE: {user[1]}

📧 Email: {user[3]}
📞 Phone: {user[4]}

🔗 {URL}

⚠ Open the link and complete manually
"""

                            await tg.send(msg)

                            await asyncio.sleep(3)

                    await asyncio.sleep(2)

            except Exception as e:
                print("Worker error:", e)

                await asyncio.sleep(10)

        await browser.close()

# ================= COMMANDS =================

async def handle_command(text):

    global running

    text = text.strip()

    # ========= ADD USER =========

    if text.startswith("/add"):

        try:

            parts = text.split(" ")

            if len(parts) != 6:
                raise Exception()

            _, name, nie, city, email, phone = parts

            add_user(name, nie, city, email, phone)

            await tg.send(
                f"✅ User added\n\n"
                f"👤 {name}\n"
                f"📍 {city}"
            )

        except:

            await tg.send(
                "❌ Format:\n"
                "/add name nie city email phone"
            )

    # ========= LIST USERS =========

    elif text == "/list":

        users = list_users()

        if not users:
            await tg.send("❌ No users")
            return

        msg = "📋 USERS:\n\n"

        for u in users:
            msg += f"👤 {u[0]} | {u[1]} | {u[2]}\n"

        await tg.send(msg)

    # ========= START =========

    elif text == "/startbot":

        if not running:

            running = True

            asyncio.create_task(worker())

            await tg.send("🚀 Bot started")

        else:
            await tg.send("⚠ Bot already running")

    # ========= STOP =========

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

            async with aiohttp.ClientSession() as session:

                async with session.get(
                    f"{TG_URL}/getUpdates?offset={offset}"
                ) as response:

                    data = await response.json()

            for upd in data.get("result", []):

                offset = upd["update_id"] + 1

                if "message" not in upd:
                    continue

                msg = upd["message"].get("text")

                if not msg:
                    continue

                chat_id = upd["message"]["chat"]["id"]

                if chat_id != ADMIN_ID:
                    continue

                await handle_command(msg)

        except Exception as e:

            print("Main loop error:", e)

        await asyncio.sleep(2)

# ================= START =================

if __name__ == "__main__":
    asyncio.run(main())
