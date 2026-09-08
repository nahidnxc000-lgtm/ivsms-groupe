#!/usr/bin/env python3
"""
IVA SMS Forwarder Bot (Client Active SMS Version)
"""
import os
import json
import logging
import asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================== CONFIGURATION ====================
MASTER_EMAIL    = "nahidnxc000@gmail.com"
MASTER_PASSWORD = "Soutafrica11@"
BOT_TOKEN       = "8632025587:AAFI_QjCBOiO1LF_O3_RnGNIzIzDCXST6pk"
GROUP_CHAT_ID   = -1003919009698

BASE_URL     = "https://www.ivasms.com"
LOGIN_URL    = f"{BASE_URL}/login"
# আপনার স্ক্রিনশটের আসল Client Active SMS URL
SMS_LIVE_URL = f"{BASE_URL}/portal/client/active_sms"

DB_SEEN_SMS = "db_seen_sms.json"
MONITOR_INTERVAL = 4.0

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger()

global_seen = set()

# ==================== DATABASE ====================
def load_seen():
    global global_seen
    if os.path.exists(DB_SEEN_SMS):
        try:
            with open(DB_SEEN_SMS, "r") as f:
                global_seen = set(json.load(f))
        except Exception:
            pass

def save_seen():
    try:
        with open(DB_SEEN_SMS, "w") as f:
            json.dump(list(global_seen), f)
    except Exception as e:
        logger.error(f"DB Save Error: {e}")

# ==================== HTTP SESSION MANAGER ====================
class IVASession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def login(self):
        try:
            logger.info("🔑 Logging into IVA SMS...")
            res = self.session.get(LOGIN_URL, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            csrf_token = None
            token_input = soup.find('input', {'name': '_token'})
            if token_input:
                csrf_token = token_input.get('value')

            payload = {
                "email": MASTER_EMAIL,
                "password": MASTER_PASSWORD
            }
            if csrf_token:
                payload["_token"] = csrf_token

            login_res = self.session.post(LOGIN_URL, data=payload, timeout=15)
            if "/portal" in login_res.url or login_res.status_code == 200:
                logger.info("✅ Login successful!")
                return True
            else:
                logger.error("❌ Login failed. Check credentials.")
                return False
        except Exception as e:
            logger.error(f"Login Exception: {e}")
            return False

    def fetch_sms(self):
        try:
            res = self.session.get(SMS_LIVE_URL, timeout=15)
            
            # অটো লগআউট হয়ে গেলে পুনরায় লগইন করার চেষ্টা
            if "login" in res.url.lower():
                logger.warning("Session expired! Re-logging in automatically...")
                if self.login():
                    res = self.session.get(SMS_LIVE_URL, timeout=15)
                else:
                    return []

            soup = BeautifulSoup(res.text, 'html.parser')
            
            # পেজের যেকোনো টেবিলের tr স্ক্র্যাপ করবে
            rows = soup.select('table tbody tr')
            results = []
            
            for row in rows:
                tds = row.find_all('td')
                if len(tds) < 3:
                    continue
                
                # কলাম ম্যাপিং
                recipient = tds[0].text.strip()
                sender    = tds[1].text.strip() if len(tds) > 1 else 'N/A'
                message   = tds[-1].text.strip() if len(tds) > 2 else ''
                
                if recipient and message:
                    results.append({
                        'recipient': recipient.replace('\n', ' '),
                        'sender': sender.replace('\n', ' '),
                        'message': message.replace('\n', ' ')
                    })
            return results
        except Exception as e:
            logger.error(f"Fetch SMS Error: {e}")
            return []

# ==================== CORE MONITOR ENGINE ====================
async def monitor_account_task(app: Application):
    iva_session = IVASession()
    await asyncio.to_thread(iva_session.login)

    while True:
        try:
            new_sms_list = await asyncio.to_thread(iva_session.fetch_sms)
            for sms in new_sms_list:
                uid = f"{sms['recipient']}_{sms['message']}"
                if uid not in global_seen:
                    global_seen.add(uid)
                    save_seen()
                    logger.info(f"📩 New SMS: {sms['recipient']}")
                    
                    # ফরওয়ার্ড মেসেজ ফরম্যাট
                    text = (
                        f"📩 <b>New SMS Received!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"📞 <b>Number/Country:</b>\n<code>{sms['recipient']}</code>\n\n"
                        f"⚙️ <b>Service/SID:</b> {sms['sender']}\n\n"
                        f"💬 <b>Message Content:</b>\n<code>{sms['message']}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━"
                    )
                    
                    try:
                        await app.bot.send_message(
                            chat_id=GROUP_CHAT_ID,
                            text=text,
                            parse_mode="HTML"
                        )
                    except Exception as send_err:
                        logger.error(f"Telegram Send Error: {send_err}")

        except Exception as e:
            logger.error(f"Monitor Loop Error: {e}")

        await asyncio.sleep(MONITOR_INTERVAL)

# ==================== COMMANDS ====================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ IVA SMS Forwarder Bot is Active!")

async def post_init(application: Application):
    asyncio.create_task(monitor_account_task(application))

# ==================== MAIN ENTRY ====================
if __name__ == "__main__":
    load_seen()
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))

    logger.info("🚀 IVA Simple Forwarder Bot Starting...")
    app.run_polling(close_loop=True)
