#!/usr/bin/env python3
"""
IVA SMS Forwarder Bot
"""
import os
import json
import logging
import asyncio
import cloudscraper
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
SMS_LIVE_URL = f"{BASE_URL}/portal/client/active_sms"

DB_SEEN_SMS = "db_seen_sms.json"
MONITOR_INTERVAL = 3.0

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

# ==================== CLOUDSCRAPER SESSION ====================
class IVASession:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )

    def login(self):
        try:
            logger.info("🔑 Logging into IVA SMS...")
            res = self.scraper.get(LOGIN_URL, timeout=20)
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

            login_res = self.scraper.post(LOGIN_URL, data=payload, timeout=20)
            
            if "login" not in login_res.url.lower() or login_res.status_code == 200:
                logger.info("✅ Login successful!")
                return True
            else:
                logger.error(f"❌ Login failed. URL: {login_res.url}")
                return False
        except Exception as e:
            logger.error(f"Login Exception: {e}")
            return False

    def fetch_sms(self):
        try:
            res = self.scraper.get(SMS_LIVE_URL, timeout=20)
            
            if "login" in res.url.lower():
                logger.warning("Session expired! Re-logging in...")
                if self.login():
                    res = self.scraper.get(SMS_LIVE_URL, timeout=20)
                else:
                    return []

            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('tr')
            results = []
            
            for row in rows:
                tds = row.find_all('td')
                if len(tds) < 2:
                    continue
                
                # টেবিলের সম্পূর্ণ তথ্য এক লাইনে ফরম্যাট করা
                row_data = [td.text.strip().replace('\n', ' ') for td in tds]
                full_text = " | ".join(row_data)
                
                # ইউনিক আইডি তৈরি (ডুপ্লিকেট মেসেজ এড়াতে)
                uid = hash(full_text)
                
                results.append({
                    'id': uid,
                    'full_text': full_text
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
                if sms['id'] not in global_seen:
                    global_seen.add(sms['id'])
                    save_seen()
                    logger.info("📩 New SMS Found! Forwarding...")
                    
                    text = (
                        f"📩 <b>New IVA SMS Received!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"<code>{sms['full_text']}</code>\n"
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
    await update.message.reply_text("✅ IVA SMS Bot Active!")

async def post_init(application: Application):
    asyncio.create_task(monitor_account_task(application))

# ==================== MAIN ENTRY ====================
if __name__ == "__main__":
    load_seen()
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))

    logger.info("🚀 IVA Forwarder Bot Starting...")
    app.run_polling(close_loop=True)
