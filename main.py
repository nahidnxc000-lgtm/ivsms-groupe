import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Railway Variable থেকে টোকেন নিবে
BOT_TOKEN = os.getenv("BOT_TOKEN", "8632025587:AAFI_QjCBOiO1LF_O3_RnGNIzIzDCXST6pk")

user_cut_digits = {}

# ওনার বাটনের কিবোর্ড
def get_owner_keyboard():
    keyboard = [
        [InlineKeyboardButton("👨‍💻 Contact Owner", url="https://t.me/nb269")]
    ]
    return InlineKeyboardMarkup(keyboard)

# স্টার্ট কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_cut_digits[user_id] = None
    await update.message.reply_text("🔢 **apni koto digit katta cassen?**", parse_mode="Markdown")

# ইউজার টেক্সট বা নাম্বার পাঠালে
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_cut_digits or user_cut_digits[user_id] is None:
        if text.isdigit():
            user_cut_digits[user_id] = int(text)
            await update.message.reply_text(
                f"✅ **Done!** Ekhon apnar number ba txt file pathan, samne theke **{text}** digit kete dewa hobe.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Doya kore ekta shongkhaa (digit) likhe pathan.")
        return

    cut_count = user_cut_digits[user_id]
    lines = text.splitlines()
    processed_lines = []

    for line in lines:
        clean_line = line.strip()
        if clean_line:
            formatted = clean_line[cut_count:]
            processed_lines.append(f"`{formatted}`")

    if processed_lines:
        result_text = "\n".join(processed_lines)
        
        # প্রসেস করা নাম্বার পাঠানো
        await update.message.reply_text(result_text, parse_mode="MarkdownV2")
        
        # প্রফেশনাল থ্যাংক ইউ মেসেজ ও ইনলাইন বাটন
        thank_you_text = (
            "✨ **Process Completed!**\n\n"
            "Thank you for using our service.\n"
            "👤 **Owner:** Nahid Hasan\n"
            "💬 Need help or custom bots? Click below!"
        )
        await update.message.reply_text(
            thank_you_text, 
            parse_mode="Markdown", 
            reply_markup=get_owner_keyboard()
        )
        
        # পরবর্তী কাজের জন্য ডিজিট রিসেট
        user_cut_digits[user_id] = None
        await update.message.reply_text("🔢 **apni koto digit katta cassen?**", parse_mode="Markdown")

# txt ফাইল পাঠালে প্রসেস করার ফাংশন
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in user_cut_digits or user_cut_digits[user_id] is None:
        await update.message.reply_text("⚠️ Aage bolun: apni koto digit katta cassen?")
        return

    document = update.message.document
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text("⚠️ Doya kore shudhu .txt file pathan.")
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

    # প্রফেশনাল থ্যাংক ইউ মেসেজ ও ইনলাইন বাটন
    thank_you_text = (
        "✨ **Process Completed!**\n\n"
        "Thank you for using our service.\n"
        "👤 **Owner:** Nahid Hasan\n"
        "💬 Need help or custom bots? Click below!"
    )
    await update.message.reply_text(
        thank_you_text, 
        parse_mode="Markdown", 
        reply_markup=get_owner_keyboard()
    )

    user_cut_digits[user_id] = None
    await update.message.reply_text("🔢 **apni koto digit katta cassen?**", parse_mode="Markdown")

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Bot is running...")
    app.run_polling()
