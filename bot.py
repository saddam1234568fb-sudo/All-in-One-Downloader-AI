import sqlite3
import logging
import asyncio
import time
import os
import re
import requests
import urllib.parse
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

# 🌐 সার্ভার ২৪ ঘণ্টা সজাগ রাখার জন্য
from keep_alive import keep_alive

# --- কনফিগারেশন ---
BOT_TOKEN = "8978899309:AAGySai08hJM-SFfgZHA7ddkxFbOV_NDobw"
SUPPORT_CHANNEL_LINK = "https://t.me/+HbL1VKdIbaQ5ZjI1"

ADMIN_USERNAME = "saddamadmin"
ADMIN_PASSWORD = "saddamadmin1234"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_NAME = "bot_database.db"

# --- ২ ভাষার ডিকশনারি (English & Bengali) ---
TEXTS = {
    'bn': {
        'welcome': "🎉 <b>হ্যালো {name}!</b> 👋\n\n🔥 <b>All-in-One Downloader & AI Bot</b>-এ আপনাকে স্বাগতম!\n\n💡 <b>কীভাবে ব্যবহার করবেন?</b>\n🔗 <b>ভিডিও ডাউনলোড:</b> Facebook, YouTube, TikTok বা Instagram-এর যেকোনো ভিডিও লিংক এখানে পেস্ট করুন।\n🤖 <b>AI চ্যাট:</b> আপনি চাইলে আমার সাথে যেকোনো বিষয়ে গল্প বা প্রশ্ন করতে পারেন (ChatGPT এর মতো)!\n\n👇 <i>যেকোনো একটি লিংক দিয়ে এখনই ট্রাই করে দেখুন!</i>",
        'btn_how': "📥 কীভাবে ডাউনলোড করবো?", 
        'btn_id': "🆔 আমার প্রোফাইল",
        'btn_lang': "🌐 ভাষা (Language)", 
        'btn_stats': "📊 বটের স্ট্যাটাস",
        'btn_vip': "👑 VIP Premium",
        'btn_support': "🎧 সাপোর্ট চ্যানেল",
        'ai_typing': "🤖 <b>AI টাইপ করছে...</b>",
        'dl_processing': "⏳ <b>আপনার ভিডিওটি প্রসেস করা হচ্ছে... দয়া করে অপেক্ষা করুন!</b>",
        'dl_uploading': "🚀 <b>ডাউনলোড সম্পন্ন! এখন আপনার ইনবক্সে আপলোড করা হচ্ছে...</b>",
        'dl_large': "❌ <b>ভিডিওটি অনেক বড় (50MB+)!</b> টেলিগ্রামের লিমিটের কারণে পাঠানো সম্ভব হচ্ছে না।",
        'dl_failed': "❌ <b>ডাউনলোড ব্যর্থ হয়েছে!</b> লিংকটি প্রাইভেট হতে পারে অথবা সার্ভারে সিকিউরিটি আপডেট চলছে।",
        'dl_caption': "📥 <b>ডাউনলোড করেছে:</b> @{bot_uname}",
        'lang_msg': "✅ <b>ভাষা সফলভাবে বাংলায় পরিবর্তন করা হয়েছে!</b>"
    },
    'en': {
        'welcome': "🎉 <b>Hello {name}!</b> 👋\n\n🔥 Welcome to the <b>All-in-One Downloader & AI Bot</b>!\n\n💡 <b>How to use?</b>\n🔗 <b>Video Download:</b> Paste any video link from Facebook, YouTube, TikTok, or Instagram here.\n🤖 <b>AI Chat:</b> You can chat or ask me anything (Just like ChatGPT)!\n\n👇 <i>Try sending a link right now!</i>",
        'btn_how': "📥 How to Download?", 
        'btn_id': "🆔 My Profile",
        'btn_lang': "🌐 Language", 
        'btn_stats': "📊 Bot Stats",
        'btn_vip': "👑 VIP Premium",
        'btn_support': "🎧 Support Channel",
        'ai_typing': "🤖 <b>AI is thinking...</b>",
        'dl_processing': "⏳ <b>Processing your video... Please wait!</b>",
        'dl_uploading': "🚀 <b>Download complete! Uploading to your inbox...</b>",
        'dl_large': "❌ <b>Video is too large (50MB+)!</b> Cannot send due to Telegram limits.",
        'dl_failed': "❌ <b>Download failed!</b> The link might be private or blocked by the server.",
        'dl_caption': "📥 <b>Downloaded by:</b> @{bot_uname}",
        'lang_msg': "✅ <b>Language successfully changed to English!</b>"
    }
}

def get_t(user_id, key):
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT lang FROM bot_users WHERE user_id = ?", (user_id,)).fetchone()
        lang = row[0] if row and row[0] in TEXTS else 'bn' # Default Bangla
    return TEXTS.get(lang, TEXTS['en']).get(key, TEXTS['en'].get(key, ""))

# --- ডাটাবেজ সেটআপ ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS bot_users (user_id INTEGER PRIMARY KEY, first_name TEXT, joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, lang TEXT DEFAULT 'bn')")
        conn.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER DEFAULT 0)")
        conn.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_downloads', 0)")
        conn.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_ai_chats', 0)")
        try: conn.execute("ALTER TABLE bot_users ADD COLUMN lang TEXT DEFAULT 'bn'")
        except: pass
        conn.commit()
init_db()

def save_user(user_id, first_name):
    with sqlite3.connect(DB_NAME) as conn: 
        conn.execute("INSERT OR IGNORE INTO bot_users (user_id, first_name) VALUES (?, ?)", (user_id, first_name))
        conn.commit()

def update_stat(key):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(f"UPDATE stats SET value = value + 1 WHERE key = '{key}'")
        conn.commit()

# --- এআই (AI) চ্যাট ফাংশন ---
def get_ai_response(text):
    try:
        encoded_text = urllib.parse.quote(text)
        url = f"https://api.popcat.xyz/chatbot?msg={encoded_text}&owner=Admin&botname=SmartAI"
        r = requests.get(url).json()
        return r.get('response', "I am currently busy. Please try again later.")
    except:
        return "🤖 My AI brain is currently sleeping. Please message later!"

# --- অ্যাডভান্সড ভিডিও ডাউনলোডার ---
def download_video(url, user_id):
    filename = f"video_{user_id}_{int(time.time())}.mp4"
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': filename,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5'
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if os.path.exists(filename):
            return filename
        return None
    except Exception as e:
        print(f"DL Error: {e}")
        return None

# --- স্টার্ট কমান্ড ও মেইন মেনু ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.first_name)
    context.user_data['state'] = None
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    txt = get_t(user.id, 'welcome').format(name=user.first_name)
    
    # নতুন এবং আকর্ষণীয় বাটন লেআউট
    kb = [
        [InlineKeyboardButton(get_t(user.id, 'btn_how'), callback_data="how_to"), InlineKeyboardButton(get_t(user.id, 'btn_id'), callback_data="my_id")],
        [InlineKeyboardButton(get_t(user.id, 'btn_lang'), callback_data="change_lang"), InlineKeyboardButton(get_t(user.id, 'btn_stats'), callback_data="user_stats")],
        [InlineKeyboardButton(get_t(user.id, 'btn_vip'), callback_data="vip_premium"), InlineKeyboardButton(get_t(user.id, 'btn_support'), url=SUPPORT_CHANNEL_LINK)]
    ]
    markup = InlineKeyboardMarkup(kb)
    
    if update.callback_query: 
        await update.callback_query.edit_message_text(txt, reply_markup=markup, parse_mode=ParseMode.HTML)
    else: 
        await update.message.reply_text(txt, reply_markup=markup, parse_mode=ParseMode.HTML)

# --- টেক্সট / লিংক ডিটেক্টর ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    state = context.user_data.get('state')
    is_admin = context.user_data.get('is_admin')
    bot_uname = context.bot.username

    # Admin Login Logic
    if state == 'WAITING_ADMIN_USER':
        if text == ADMIN_USERNAME:
            context.user_data['state'] = 'WAITING_ADMIN_PASS'
            await update.message.reply_text("✅ Username সঠিক! Password দিন:")
        else:
            context.user_data['state'] = None
            await update.message.reply_text("❌ ভুল ইউজারনেম!")
        return
            
    elif state == 'WAITING_ADMIN_PASS':
        if text == ADMIN_PASSWORD: await show_admin_panel(update.message, context)
        else:
            context.user_data['state'] = None
            await update.message.reply_text("❌ ভুল পাসওয়ার্ড!")
        return

    # Admin Broadcast Logic
    if state == 'WAITING_BC_MSG' and is_admin:
        with sqlite3.connect(DB_NAME) as conn: users = [u[0] for u in conn.execute("SELECT user_id FROM bot_users").fetchall()]
        msg = await update.message.reply_text(f"⏳ {len(users)} জনের কাছে পাঠানো হচ্ছে...")
        success = 0
        for uid in users:
            try:
                await context.bot.copy_message(chat_id=uid, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
                success += 1
            except: pass
        await msg.edit_text(f"✅ ব্রডকাস্ট সফল! ({success}/{len(users)})")
        await show_admin_panel(update.message, context)
        return

    # --- লিংক নাকি চ্যাট ডিটেক্ট করা ---
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    urls = url_pattern.findall(text)

    if urls:
        url = urls[0]
        processing_msg = await update.message.reply_text(get_t(user.id, 'dl_processing'), parse_mode=ParseMode.HTML)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VIDEO)
        
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, download_video, url, user.id)

        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / (1024 * 1024) 
            if file_size > 49:
                await processing_msg.edit_text(get_t(user.id, 'dl_large'), parse_mode=ParseMode.HTML)
            else:
                await processing_msg.edit_text(get_t(user.id, 'dl_uploading'), parse_mode=ParseMode.HTML)
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
                try:
                    cap = get_t(user.id, 'dl_caption').format(bot_uname=bot_uname)
                    with open(file_path, 'rb') as video:
                        await update.message.reply_video(video, caption=cap, parse_mode=ParseMode.HTML)
                    update_stat('total_downloads')
                    await processing_msg.delete()
                except Exception as e:
                    await processing_msg.edit_text(get_t(user.id, 'dl_failed'), parse_mode=ParseMode.HTML)
            os.remove(file_path) 
        else:
            await processing_msg.edit_text(get_t(user.id, 'dl_failed'), parse_mode=ParseMode.HTML)
    else:
        # AI Chat Detected
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        loop = asyncio.get_event_loop()
        ai_reply = await loop.run_in_executor(None, get_ai_response, text)
        update_stat('total_ai_chats')
        await update.message.reply_text(f"🤖 <b>AI:</b> {ai_reply}", parse_mode=ParseMode.HTML)

# --- বাটন হ্যান্ডলার ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "how_to":
        txt = "💡 <b>How to Download?</b>\n\n1. Copy any video link from Facebook, TikTok, Instagram, or YouTube.\n2. Paste and send the link here.\n3. The bot will automatically download and send you the video without watermark! 🎉"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode=ParseMode.HTML)

    elif data == "my_id":
        txt = f"👤 <b>Your Profile:</b>\n\n📝 Name: {query.from_user.first_name}\n🆔 User ID: <code>{user_id}</code>"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode=ParseMode.HTML)
        
    elif data == "change_lang":
        kb = [
            [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lng_bn"), InlineKeyboardButton("🇬🇧 English", callback_data="lng_en")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.edit_message_text("🌐 <b>Select your Language:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

    elif data.startswith("lng_"):
        lang = data.split("_")[1]
        with sqlite3.connect(DB_NAME) as conn: 
            conn.execute("UPDATE bot_users SET lang = ? WHERE user_id = ?", (lang, user_id))
            conn.commit()
        await query.answer(get_t(user_id, 'lang_msg'), show_alert=True)
        await show_main_menu(update, context)

    elif data == "user_stats":
        with sqlite3.connect(DB_NAME) as conn:
            dl = conn.execute("SELECT value FROM stats WHERE key = 'total_downloads'").fetchone()[0]
            ai = conn.execute("SELECT value FROM stats WHERE key = 'total_ai_chats'").fetchone()[0]
        txt = f"📊 <b>Global Bot Stats:</b>\n\n📥 Total Video Downloads: {dl}\n🤖 Total AI Chats: {ai}\n\n<i>Powered by Smart AI & Downloader</i>"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode=ParseMode.HTML)

    elif data == "vip_premium":
        await query.answer("💎 You are already a VIP User! Enjoy unlimited downloads.", show_alert=True)

    elif data == "main_menu":
        await show_main_menu(update, context)

    # Admin callbacks
    elif data == "admin_bc":
        context.user_data['state'] = 'WAITING_BC_MSG'
        await query.edit_message_text("📣 <b>ইউজার ব্রডকাস্ট:</b>\n\nসব ইউজারের কাছে পাঠানোর জন্য মেসেজ বা ছবি সেন্ড করুন:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ বাতিল", callback_data="admin_cancel")]]))

    elif data == "admin_cancel":
        await show_admin_panel(update.callback_query, context)
        
    elif data == "admin_logout":
        context.user_data['is_admin'] = False
        await query.edit_message_text("✅ <b>লগআউট সফল।</b>", parse_mode=ParseMode.HTML)

# --- এডমিন প্যানেল ---
async def saddamadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'WAITING_ADMIN_USER'
    await update.message.reply_text("👑 <b>সিক্রেট এডমিন লগিন:</b>\nUsername দিন:", parse_mode=ParseMode.HTML)

async def show_admin_panel(update_or_message, context):
    context.user_data['is_admin'] = True
    context.user_data['state'] = None
    
    with sqlite3.connect(DB_NAME) as conn:
        usr = conn.execute("SELECT COUNT(*) FROM bot_users").fetchone()[0]
        dl = conn.execute("SELECT value FROM stats WHERE key = 'total_downloads'").fetchone()[0]
        ai = conn.execute("SELECT value FROM stats WHERE key = 'total_ai_chats'").fetchone()[0]

    text = f"👑 <b>সুপার এডমিন ড্যাশবোর্ড</b>\n━━━━━━━━━━━━━━━━━━\n👥 মোট ইউজার: {usr} জন\n📥 মোট ডাউনলোড: {dl} টি\n🤖 মোট AI চ্যাট: {ai} বার\n━━━━━━━━━━━━━━━━━━\n👇 <i>অ্যাকশন বেছে নিন:</i>"
    kb = [
        [InlineKeyboardButton("📣 ইউজার ব্রডকাস্ট", callback_data="admin_bc")],
        [InlineKeyboardButton("❌ লগআউট", callback_data="admin_logout")]
    ]
    if hasattr(update_or_message, 'reply_text'): await update_or_message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    else: await update_or_message.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

def main():
    keep_alive()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("saddamadmin", saddamadmin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_text))
    
    print("🚀 All-in-One Viral Bot is running 24/7...")
    app.run_polling()

if __name__ == '__main__':
    main()
