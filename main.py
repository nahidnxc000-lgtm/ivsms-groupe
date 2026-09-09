import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Railway Variable থেকে টোকেন নিবে, না পেলে লোকাল টোকেন ব্যবহার করবে
BOT_TOKEN = os.getenv("BOT_TOKEN", "8632025587:AAFI_QjCBOiO1LF_O3_RnGNIzIzDCXST6pk")

# ইউজার প্রতি কয় ডিজিট কাটবে তা সেভ রাখার ডিকশনারি
user_cut_digits = {}

# স্টার্ট বা রিস্টার্ট কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_cut_digits[user_id] = None  # রিসেট
    await update.message.reply_text("apni koto digit katta cassen?")

# ইউজার মেসেজ পাঠালে
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # যদি ডিজিট সেট করা না থাকে
    if user_id not in user_cut_digits or user_cut_digits[user_id] is None:
        if text.isdigit():
            user_cut_digits[user_id] = int(text)
            await update.message.reply_text(
                f"Done! Ekhon apnar number ba text file পাঠান, সামনে থেকে {text} digit কেটে দেওয়া হবে।"
            )
        else:
            await update.message.reply_text("Doya kore ekta shongkhaa (digit) likhe pathan.")
        return

    # ডিজিট সেট থাকলে নাম্বার প্রসেস করা
    cut_count = user_cut_digits[user_id]
    lines = text.splitlines()
    processed_lines = []

    for line in lines:
        clean_line = line.strip()
        if clean_line:
            formatted = clean_line[cut_count:]
            # Monospace Format
            processed_lines.append(f"`{formatted}`")

    if processed_lines:
        result_text = "\n".join(processed_lines)
        await update.message.reply_text(result_text, parse_mode="MarkdownV2")
        
        await update.message.reply_text(
            "thank your using me ,my owner is Nahid Hasan ,if you need any help contact @nb269"
        )
        
        user_cut_digits[user_id] = None
        await update.message.reply_text("apni koto digit katta cassen?")

# txt ফাইল পাঠালে প্রসেস করার ফাংশন
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_cut_digits or user_cut_digits[user_id] is None:
        await update.message.reply_text("Aage bolun: apni koto digit katta cassen?")
        return

    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("Doya kore shudhu .txt file pathan.")
        return

    cut_count = user_cut_digits[user_id]

    file = await context.bot.get_file(document.file_id)
    file_path = f"temp_{user_id}.txt"
    out_path = f"formatted_{document.file_name}"

    await file.download_to_drive(file_path)

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(out_path, 'w', encoding='utf-8') as outfile:
        for line in infile:
            clean_line = line.strip()
            if clean_line:
                outfile.write(clean_line[cut_count:] + "\n")

    await update.message.reply_document(document=open(out_path, 'rb'))

    if os.path.exists(file_path):
        os.remove(file_path)
    if os.path.exists(out_path):
        os.remove(out_path)

    await update.message.reply_text(
        "thank your using me ,my owner is Nahid Hasan ,if you need any help contact @nb269"
    )

    user_cut_digits[user_id] = None
    await update.message.reply_text("apni koto digit katta cassen?")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Bot is running...")
    app.run_polling()
