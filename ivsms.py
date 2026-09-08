#!/usr/bin/env python3
"""
IVA SMS Forwarder Bot - Full Working Version
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

# ==================== CLOUDSCRAPER SESSION ====================
class IVASession:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        self.scraper.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': LOGIN_URL
        })

    def login(self):
        try:
            logger.info("🔑 Logging into IVA SMS...")
            
            # ১. পেজ লোড করে CSRF এবং ফর্মের সব ইনপুট সংগ্রহ
            res = self.scraper.get(LOGIN_URL, timeout=20)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            payload = {}
            for input_tag in soup.find_all('input'):
                name = input_tag.get('name')
                value = input_tag.get('value', '')
                if name:
                    payload[name] = value

            payload['email'] = MASTER_EMAIL
            payload['password'] = MASTER_PASSWORD

            # ২. ফর্ম সাবমিট
            login_res = self.scraper.post(LOGIN_URL, data=payload, timeout=20)
            
            # ৩. লগইন রেজাল্ট ভেরিফাই
            if "login" not in login_res.url.lower() or login_res.status_code == 200:
                logger.info("✅ Login successful!")
                return True, "Success"
            else:
                return False, f"Redirected back to {login_res.url}"
        except Exception as e:
            logger.error(f"Login Exception: {e}")
            return False, str(e)

    def fetch_sms(self):
        try:
            res = self.scraper.get(SMS_LIVE_URL, timeout=20)
            
            # সেশন আউট হয়ে গেলে অটো রি-লগইন
            if "login" in res.url.lower():
                logger.warning("Session expired! Re-logging in...")
                status, msg = self.login()
                if status:
                    res = self.scraper.get(SMS_LIVE_URL, timeout=20)
                else:
                    return [], f"Re-login failed: {msg}"

            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.find_all('tr')
            results = []
            
            for row in rows:
                tds = row.find_all('td')
                if len(tds) < 2:
                    continue
                
                row_data = [td.text.strip().replace('\n', ' ') for td in tds]
                full_text = " | ".join(row_data)
                
                uid = str(hash(full_text))
                results.append({
                    'id': uid,
                    'full_text': full_text
                })
            return results, "OK"
        except Exception as e:
            return [], str(e)

# ==================== CORE MONITOR ENGINE ====================
async def monitor_account_task(app: Application):
    iva_session = IVASession()
    status, msg = await asyncio.to_thread(iva_session.login)
    
    if not status:
        try:
            await app.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"⚠️ <b>IVASMS Login Failed!</b>\nReason: <code>{msg}</code>",
                parse_mode="HTML"
            )
        except Exception as err:
            logger.error(f"Telegram Alert Error: {err}")

    while True:
        try:
            new_sms_list, err_msg = await asyncio.to_thread(iva_session.fetch_sms)
            
            for sms in new_sms_list:
                if sms['id'] not in global_seen:
                    global_seen.add(sms['id'])
                    save_seen()
                    logger.info("📩 New SMS Found! Forwarding...")
                    
                    text = (
                        f"🎯 <b>SMS RECEIVED IN YOUR NUMBER!</b>\n\n"
                        f"💬 <code>{sms['full_text']}</code>"
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
