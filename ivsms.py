#!/usr/bin/env python3
"""
IVA SMS Cookie-Based Forwarder Bot
No Login / No Captcha Needed
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
BOT_TOKEN     = "8632025587:AAFI_QjCBOiO1LF_O3_RnGNIzIzDCXST6pk"
GROUP_CHAT_ID = -1003919009698

BASE_URL     = "https://www.ivasms.com"
SMS_LIVE_URL = f"{BASE_URL}/portal/client/active_sms"

# ⚠️ এখানে আপনার ব্রাউজার থেকে কপি করা Cookies বসান
# ব্রাউজারের Application -> Cookies ট্যাবে পাওয়া যাবে
RAW_COOKIE_STRING = "ivasms_session=YOUR_COPIED_SESSION_COOKIE_HERE"

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

class IVACookieSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Cookie': RAW_COOKIE_STRING,
            'Referer': BASE_URL
        })

    def fetch_sms(self):
        try:
            res = self.session.get(SMS_LIVE_URL, timeout=15)
            
            # কুকি এক্সপায়ার হলে নোটিফাই করবে
            if "login" in res.url.lower():
                logger.error("❌ Cookie expired! Please update RAW_COOKIE_STRING.")
                return [], "EXPIRED"

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

async def monitor_account_task(app: Application):
    iva_session = IVACookieSession()

    while True:
        try:
            new_sms_list, status = await asyncio.to_thread(iva_session.fetch_sms)
            
            if status == "EXPIRED":
                try:
                    await app.bot.send_message(
                        chat_id=GROUP_CHAT_ID,
                        text="⚠️ <b>IVASMS Session Cookie Expired!</b>\nPlease update the cookie in your code.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                await asyncio.sleep(60) # ১ মিনিট বিরতি
                continue

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

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ IVA SMS Cookie Bot Active!")

async def post_init(application: Application):
    asyncio.create_task(monitor_account_task(application))

if __name__ == "__main__":
    load_seen()
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))

    logger.info("🚀 IVA Cookie Forwarder Bot Starting...")
    app.run_polling(close_loop=True)
