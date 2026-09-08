#!/usr/bin/env python3
"""
Single-Account SMS Monitoring Bot - PRO LIGHTWEIGHT VERSION (IVA)
Optimized for Railway Free Tier (No Selenium/Chrome, No Thread Loop Crashes)
"""
import os
import json
import logging
import asyncio
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# ==================== CONFIGURATION ====================
MASTER_EMAIL    = "nahidnxc000@gmail.com"
MASTER_PASSWORD = "Soutafrica11@"
BOT_TOKEN       = "8632025587:AAFI_QjCBOiO1LF_O3_RnGNIzIzDCXST6pk"
GROUP_CHAT_ID   = -1003919009698
ADMIN_IDS       = {6394277892}

BASE_URL     = "https://www.ivasms.com"
LOGIN_URL    = f"{BASE_URL}/login"
SMS_LIVE_URL = f"{BASE_URL}/portal/live/my_sms"

DB_SEEN_SMS     = "db_seen_sms.json"
DB_STATUS       = "db_status.json"
DB_OTP_STATS    = "db_otp_stats.json"
DB_COUNTRY_MAP  = "db_country_map.json"
DB_SERVICE_META = "db_service_meta.json"

MONITOR_INTERVAL = 3.0

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger()

global_seen    = set()
bot_active     = True
otp_counter    = {}
admin_states   = {}

# ==================== DEFAULT DATA ====================
DEFAULT_SERVICE_META = {
    "facebook":  {"emoji_id": "5323261730283863478", "placeholder": "🔵"},
    "tiktok":    {"emoji_id": "5327982530702359565", "placeholder": "🎵"},
    "whatsapp":  {"emoji_id": "5334998226636390258", "placeholder": "🟢"},
    "telegram":  {"emoji_id": "5319160079465857105", "placeholder": "🔹"},
    "instagram": {"emoji_id": "5319160079465857105", "placeholder": "📸"},
    "default":   {"emoji_id": "5346066456142429527", "placeholder": "📱"},
}

DEFAULT_COUNTRY_MAP = {
    "KAZAKHSTAN": "5222276376161171525", "UKRAINE": "5222250679371839695",
    "TUNISIA": "5221991375016310330",    "PAKISTAN": "5224637061985742245",
    "MOZAMBIQUE": "5222470388423864826", "NIGERIA": "5224723614166691638",
    "EGYPT": "5222161185138292290",      "BANGLADESH": "5224407289825340729",
    "UNKNOWN": "5281027792148909351",
}

COUNTRY_MAP = {
    "1": ("USA/Canada", "US"), "7": ("Russia/Kazakhstan", "RU"), "20": ("Egypt", "EG"),
    "33": ("France", "FR"), "44": ("United Kingdom", "GB"), "49": ("Germany", "DE"),
    "60": ("Malaysia", "MY"), "62": ("Indonesia", "ID"), "63": ("Philippines", "PH"),
    "880": ("Bangladesh", "BD"), "91": ("India", "IN"), "92": ("Pakistan", "PK"),
    "966": ("Saudi Arabia", "SA"), "971": ("UAE", "AE"), "212": ("Morocco", "MA"),
    "213": ("Algeria", "DZ"), "216": ("Tunisia", "TN"), "234": ("Nigeria", "NG")
}

# ==================== DATA PERSISTENCE ====================
def load_databases():
    global global_seen, bot_active, otp_counter, DEFAULT_COUNTRY_MAP, DEFAULT_SERVICE_META
    for db_file, target, is_set in [
        (DB_SEEN_SMS, global_seen, True),
        (DB_OTP_STATS, otp_counter, False),
        (DB_COUNTRY_MAP, DEFAULT_COUNTRY_MAP, False),
        (DB_SERVICE_META, DEFAULT_SERVICE_META, False)
    ]:
        if os.path.exists(db_file):
            try:
                with open(db_file) as f:
                    data = json.load(f)
                    if is_set: target.update(data)
                    else: target.update(data)
            except Exception: pass

def save_databases():
    try:
        with open(DB_SEEN_SMS, "w") as f: json.dump(list(global_seen), f)
        with open(DB_STATUS, "w") as f: json.dump({"active": bot_active}, f)
        with open(DB_OTP_STATS, "w") as f: json.dump(otp_counter, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving database: {e}")

# ==================== HTTP SESSION MANAGER ====================
class IVASession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def login(self):
        try:
            logger.info("🔑 Logging in via HTTP POST...")
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
                logger.info("✅ Login successful via Requests!")
                return True
            else:
                logger.error("❌ Login failed. Check credentials or site response.")
                return False
        except Exception as e:
            logger.error(f"Login Exception: {e}")
            return False

    def fetch_sms(self):
        try:
            res = self.session.get(SMS_LIVE_URL, timeout=15)
            if "login" in res.url.lower():
                logger.warning("Session expired. Re-logging in...")
                if self.login():
                    res = self.session.get(SMS_LIVE_URL, timeout=15)
                else:
                    return []

            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select('#LiveTestSMS tbody tr, #LiveTestSMS tr')
            results = []
            for row in rows:
                tds = row.find_all('td')
                if len(tds) < 3: continue
                
                recipient = tds[0].find('p').text.strip() if tds[0].find('p') else tds[0].text.strip()
                sender = tds[1].text.strip() if len(tds) > 1 else ''
                
                sid_service = ''
                if len(tds) > 2:
                    sid_elem = tds[2].find(class_='fw-semi-bold')
                    sid_service = sid_elem.text.strip() if sid_elem else tds[2].text.strip()
                
                message = tds[4].text.strip() if len(tds) > 4 else (tds[3].text.strip() if len(tds) > 3 else tds[2].text.strip())
                
                if recipient:
                    results.append({
                        'recipient': recipient,
                        'sender': sender,
                        'message': message,
                        'sid_service': sid_service
                    })
            return results
        except Exception as e:
            logger.error(f"Fetch SMS Error: {e}")
            return []

# ==================== CORE MONITOR ENGINE ====================
async def monitor_account_task(app: Application):
    """Native asyncio task inside Telegram event loop."""
    iva_session = IVASession()
    await asyncio.to_thread(iva_session.login)

    while True:
        try:
            new_sms_list = await asyncio.to_thread(iva_session.fetch_sms)
            for sms in new_sms_list:
                uid = f"{MASTER_EMAIL}_{sms['recipient']}_{sms['sender']}_{sms['message']}"
                if uid not in global_seen:
                    global_seen.add(uid)
                    save_databases()
                    otp_counter[MASTER_EMAIL] = otp_counter.get(MASTER_EMAIL, 0) + 1
                    logger.info(f"📤 New OTP Found: {sms['recipient']} - {sms['sender']}")
                    
                    asyncio.create_task(deliver_sms(
                        app.bot, GROUP_CHAT_ID,
                        sms["recipient"], sms["sender"],
                        sms["message"], sms.get("sid_service", "")
                    ))
        except Exception as e:
            logger.error(f"Monitor Loop Error: {e}")

        await asyncio.sleep(MONITOR_INTERVAL)

# ==================== SMS DELIVERY ====================
async def deliver_sms(bot, chat_id, recipient, sender, message, sid_service=""):
    try:
        otp_match = re.search(r'\b\d{3}-\d{3}\b|\b\d{4,8}\b', message)
        otp = otp_match.group(0) if otp_match else "N/A"

        digits = re.sub(r'\D', '', str(recipient))
        c_name, a2, flag = "Global", "XX", "🌐"
        for length in range(1, 4):
            cc = digits[:length]
            if cc in COUNTRY_MAP:
                c_name, a2 = COUNTRY_MAP[cc]
                flag = ''.join(chr(0x1F1E6 + ord(ch) - ord('A')) for ch in a2)
                break

        svc_raw = sender.strip()
        svc_key_lookup = svc_raw.lower()
        matched_svc_key = "default"
        for key in DEFAULT_SERVICE_META:
            if key != "default" and key in svc_key_lookup:
                matched_svc_key = key
                break
        service_name = svc_raw if svc_raw else matched_svc_key.upper()

        masked = f"{digits[:5]}****{digits[-4:]}" if len(digits) >= 9 else f"****{digits}"

        text = (
            f"RCV JIR\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            f"{flag} ᴄᴏᴜɴᴛʀʏ: {c_name}\n"
            f"☎️ ɴᴜᴍʙᴇʀ: <code>{masked}</code>\n"
            f"🛠️ sᴇʀᴠɪᴄᴇ: {service_name.upper()}\n"
            f"🔑 sʏsᴛᴇᴍ ᴄᴏᴅᴇ: <code>{otp}</code>\n"
            f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "𝐎𝐓𝐏", "copy_text": {"text": str(otp)}},
                {"text": "𝐁𝐎𝐓 𝐋𝐈𝐍𝐊", "url": "https://t.me/fortestonly99_bot"}
            ]]
        }

        await bot.send_message(
            chat_id=chat_id, text=text, parse_mode="HTML",
            reply_markup=keyboard, disable_web_page_preview=True
        )
        return True
    except Exception as e:
        logger.error(f"❌ Delivery Error: {e}")
        return False

# ==================== ADMIN PANEL ====================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Add Country Emoji", callback_data="add_country")],
        [InlineKeyboardButton("🛠️ Add Service Emoji", callback_data="add_service")],
    ])
    await update.message.reply_text("✨ <b>IVA SMS Admin Control Panel</b>", reply_markup=kb, parse_mode="HTML")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in ADMIN_IDS: return
    await query.answer()
    if query.data in ["add_country", "add_service"]:
        admin_states[query.from_user.id] = query.data
        await query.edit_message_text("Send format: <code>NAME:EMOJI_ID</code>", parse_mode="HTML")

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS or user_id not in admin_states: return
    txt = update.message.text.strip()
    if ":" not in txt: return
    name, emoji_id = [x.strip() for x in txt.split(":", 1)]

    if admin_states[user_id] == "add_country":
        DEFAULT_COUNTRY_MAP[name.upper()] = emoji_id
    else:
        DEFAULT_SERVICE_META[name.lower()] = {"emoji_id": emoji_id, "placeholder": "📱"}

    save_databases()
    del admin_states[user_id]
    await update.message.reply_text(f"✅ Saved <b>{name}</b> with Emoji ID <code>{emoji_id}</code>.", parse_mode="HTML")

# ==================== POST INIT HOOK ====================
async def post_init(application: Application):
    """Starts the background monitoring task using Telegram's loop."""
    asyncio.create_task(monitor_account_task(application))

# ==================== MAIN ENTRY ====================
if __name__ == "__main__":
    load_databases()
    
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", admin_panel))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message_handler))

    logger.info("🚀 IVA SMS Lightweight Bot starting...")
    app.run_polling(close_loop=True)
