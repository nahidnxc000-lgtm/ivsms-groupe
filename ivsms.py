#!/usr/bin/env python3
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
            
            # লগইন সফল কি না তা চেক
            if "login" not in login_res.url.lower() or login_res.status_code == 200:
                logger.info("✅ Login successful!")
                return True, "Success"
            else:
                return False, f"Redirected to {login_res.url}"
        except Exception as e:
            return False, str(e)

    def fetch_sms(self):
        try:
            res = self.scraper.get(SMS_LIVE_URL, timeout=20)
            
            if "login" in res.url.lower():
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
                
                uid = hash(full_text)
                results.append({
                    'id': uid,
                    'full_text': full_text
                })
            return results, "OK"
        except Exception as e:
            return [], str(e)

async def monitor_account_task(app: Application):
    iva_session = IVASession()
    status, msg = await asyncio.to_thread(iva_session.login)
    
    if not status:
        # লগইন ফেইল হলে টেলিগ্রামে সতর্কবার্তা পাঠাবে
        try:
            await app.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"⚠️ <b>IVASMS Login Failed!</b>\nReason: <code>{msg}</code>",
                parse_mode="HTML"
            )
        except Exception:
            pass

    while True:
        try:
            new_sms_list, err_msg = await asyncio.to_thread(iva_session.fetch_sms)
            
            if err_msg != "OK" and "Re-login failed" in err_msg:
                logger.error(f"Fetch Error: {err_msg}")
            
            for sms in new_sms_list:
                if sms['id'] not in global_seen:
                    global_seen.add(sms['id'])
                    save_seen()
                    
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

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ IVA SMS Bot Active!")

async def post_init(application: Application):
    asyncio.create_task(monitor_account_task(application))

if __name__ == "__main__":
    load_seen()
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))

    logger.info("🚀 IVA Forwarder Bot Starting...")
    app.run_polling(close_loop=True)
