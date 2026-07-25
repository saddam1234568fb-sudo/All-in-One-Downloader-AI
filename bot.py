import sqlite3
import logging
import asyncio
import time
import os
import re
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
SUPPORT_CHANNEL_LINK = "https://t.me/+HbL1VKdIbaQ5ZjI1"  # আপনার সাপোর্ট বা প্রমোশন চ্যানেলের লিংক

ADMIN_USERNAME = "saddamadmin"
ADMIN_PASSWORD = "saddamadmin1234"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_NAME = "bot_database.db"

# --- ২ ভাষার ডিকশনারি (English & Bengali) ---
TEXTS = {
    'bn': {
        'welcome': "🎉 <b>হ্যালো {name}!</b> 👋\n\n🔥 <b>Premium Video & Music Downloader Bot</b>-এ আপনাকে স্বাগতম!\n\n💡 <b>কীভাবে ব্যবহার করবেন?</b>\n🔗 Facebook, YouTube, TikTok বা Instagram-এর যেকোনো ভিডিও লিংক কপি করে এখানে পেস্ট করুন।\n🎬 লিংক দেওয়ার পর আপনি ভিডিও নাকি অডিও (MP3) ডাউনলোড করবেন, তার অপশন পেয়ে যাবেন!\n\n👇 <i>যেকোনো একটি লিংক দিয়ে এখনই ট্রাই করে দেখুন!</i>",
        'btn_how': "📥 কীভাবে ডাউনলোড করবো?", 
        'btn_id': "🆔 আমার প্রোফাইল",
        'btn_lang': "🌐 ভাষা (Language)", 
        'btn_vip': "👑 VIP Premium",
        'btn_support': "🎧 সাপোর্ট চ্যানেল",
        'link_detected': "🔗 <b>লিংক রিসিভ হয়েছে!</b>\n\nআপনি এই লিংকটি থেকে কী ডাউনলোড করতে চান তা নিচের বাটন থেকে সিলেক্ট করুন:",
        'btn_dl_vid': "🎬 ভিডিও ডাউনলোড",
        'btn_dl_aud': "🎵 মিউজিক (MP3)",
        'dl_processing': "⏳ <b>প্রসেস করা হচ্ছে... দয়া করে অপেক্ষা করুন!</b>",
        'dl_uploading': "🚀 <b>ডাউনলোড সম্পন্ন! এখন আপনার ইনবক্সে আপলোড করা হচ্ছে...</b>",
        'dl_large': "❌ <b>ফাইলটি অনেক বড় (50MB+)!</b> টেলিগ্রামের লিমিটের কারণে পাঠানো সম্ভব হচ্ছে না।",
        'dl_failed': "❌ <b>ডাউনলোড ব্যর্থ হয়েছে!</b> লিংকটি প্রাইভেট হতে পারে অথবা সার্ভারে সিকিউরিটি আপডেট চলছে।",
        'dl_caption': "📥 <b>ডাউনলোড করেছে:</b> @{bot_uname}",
        'invalid_link': "❌ <b>দুঃখিত!</b> এটি কোনো সঠিক ভিডিও লিংক নয়। দয়া করে সঠিক লিংক সেন্ড করুন।",
        'lang_msg': "✅ <b>ভাষা সফলভাবে বাংলায় পরিবর্তন করা হয়েছে!</b>"
    },
    'en': {
        'welcome': "🎉 <b>Hello {name}!</b> 👋\n\n🔥 Welcome to the <b>Premium Video & Music Downloader</b>!\n\n💡 <b>How to use?</b>\n🔗 Paste any video link from Facebook, YouTube, TikTok, or Instagram here.\n🎬 Once you send the link, you can choose to download it as Video or Audio (MP3)!\n\n👇 <i>Try sending a link right now!</i>",
        'btn_how': "📥 How to Download?", 
        'btn_id': "🆔 My Profile",
        'btn_lang': "🌐 Language", 
        'btn_vip': "👑 VIP Premium",
        'btn_support': "🎧 Support Channel",
        'link_detected': "🔗 <b>Link Detected!</b>\n\nWhat do you want to download from this link? Select below:",
        'btn_dl_vid': "🎬 Download Video",
        'btn_dl_aud': "🎵 Music (MP3)",
        'dl_processing': "⏳ <b>Processing your request... Please wait!</b>",
        'dl_uploading': "🚀 <b>Download complete! Uploading to your inbox...</b>",
        'dl_large': "❌ <b>File is too large (50MB+)!</b> Cannot send due to Telegram limits.",
        'dl_failed': "❌ <b>Download failed!</b> The link might be private or blocked by the server.",
        'dl_caption': "📥 <b>Downloaded by:</b> @{bot_uname}",
        'invalid_link': "❌ <b>Sorry!</b> This is not a valid video link. Please send a proper link.",
        'lang_msg': "✅ <b>Language successfully changed to English!</b>"
    }
}

def get_t(user_id, key):
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT lang FROM bot_users WHERE user_id = ?", (user_id,)).fetchone()
        lang = row[0] if row and row[0] in TEXTS else 'bn' 
    return TEXTS.get(lang, TEXTS['en']).get(key, TEXTS['en'].get(key, ""))

# --- ডাটাবেজ সেটআপ ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS bot_users (user_id INTEGER PRIMARY KEY, first_name TEXT, joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, lang TEXT DEFAULT 'bn')")
        conn.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER DEFAULT 0)")
        conn.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_downloads', 0)")
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

# --- অ্যাডভান্সড মিডিয়া ডাউনলোডার (ভিডিও এবং অডিও) ---
def download_media(url, user_id, media_type):
    timestamp = int(time.time())
    
    if media_type == 'video':
        filename = f"video_{user_id}_{timestamp}.mp4"
        # Best video under 50MB
        format_str = 'bestvideo[ext=mp4][filesize<50M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<50M]/best'
    else:
        filename = f"audio_{user_id}_{timestamp}.mp3"
        # Best audio format
        format_str = 'bestaudio[ext=m4a]/bestaudio/best'

    ydl_opts = {
        'format': format_str,
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
    
    # ইউজার স্ট্যাটাস রিমুভ করে প্রফেশনাল গ্রিড তৈরি করা হলো
    kb = [
        [InlineKeyboardButton(get_t(user.id, 'btn_how'), callback_data="how_to"), InlineKeyboardButton(get_t(user.id, 'btn_id'), callback_data="my_id")],
        [InlineKeyboardButton(get_t(user.id, 'btn_vip'), callback_data="vip_premium"), InlineKeyboardButton(get_t(user.id, 'btn_lang'), callback_data="change_lang")],
        [InlineKeyboardButton(get_t(user.id, 'btn_support'), url=SUPPORT_CHANNEL_LINK)]
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

    # --- লিংক ডিটেক্ট করা ---
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    urls = url_pattern.findall(text)

    if urls:
        url = urls[0]
        # লিংটি সেভ করে ইউজারকে ২টা অপশন দেওয়া হবে
        context.user_data['last_url'] = url
        
        txt = get_t(user.id, 'link_detected')
        kb = [
            [InlineKeyboardButton(get_t(user.id, 'btn_dl_vid'), callback_data="dl_video")],
            [InlineKeyboardButton(get_t(user.id, 'btn_dl_aud'), callback_data="dl_audio")]
        ]
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    else:
        # লিংক না হলে এরর মেসেজ দেবে (AI বন্ধ করা হয়েছে)
        await update.message.reply_text(get_t(user.id, 'invalid_link'), parse_mode=ParseMode.HTML)

# --- বাটন হ্যান্ডলার (Download Execution) ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    bot_uname = context.bot.username

    # --- ডাউনলোড লজিক ---
    if data in ["dl_video", "dl_audio"]:
        url = context.user_data.get('last_url')
        if not url:
            await query.answer("❌ লিংকটি এক্সপায়ার হয়ে গেছে! আবার নতুন করে লিংক সেন্ড করুন।", show_alert=True)
            return

        media_type = 'video' if data == "dl_video" else 'audio'
        processing_msg = await query.edit_message_text(get_t(user_id, 'dl_processing'), parse_mode=ParseMode.HTML)
        
        action = ChatAction.RECORD_VIDEO if media_type == 'video' else ChatAction.RECORD_VOICE
        await context.bot.send_chat_action(chat_id=query.message.chat.id, action=action)
        
        # Download in background
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, download_media, url, user_id, media_type)

        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / (1024 * 1024) 
            if file_size > 49:
                await processing_msg.edit_text(get_t(user_id, 'dl_large'), parse_mode=ParseMode.HTML)
            else:
                await processing_msg.edit_text(get_t(user_id, 'dl_uploading'), parse_mode=ParseMode.HTML)
                
                upload_action = ChatAction.UPLOAD_VIDEO if media_type == 'video' else ChatAction.UPLOAD_VOICE
                await context.bot.send_chat_action(chat_id=query.message.chat.id, action=upload_action)
                
                try:
                    cap = get_t(user_id, 'dl_caption').format(bot_uname=bot_uname)
                    with open(file_path, 'rb') as file:
                        if media_type == 'video':
                            await context.bot.send_video(chat_id=query.message.chat.id, video=file, caption=cap, parse_mode=ParseMode.HTML)
                        else:
                            await context.bot.send_audio(chat_id=query.message.chat.id, audio=file, caption=cap, parse_mode=ParseMode.HTML)
                    
                    update_stat('total_downloads')
                    await processing_msg.delete()
                except Exception as e:
                    await processing_msg.edit_text(get_t(user_id, 'dl_failed'), parse_mode=ParseMode.HTML)
            os.remove(file_path) # Clean up
        else:
            await processing_msg.edit_text(get_t(user_id, 'dl_failed'), parse_mode=ParseMode.HTML)
        return

    # --- রেগুলার মেনু বাটন ---
    if data == "how_to":
        txt = "💡 <b>How to Download?</b>\n\n1. Copy any video link from Facebook, TikTok, Instagram, or YouTube.\n2. Paste and send the link here.\n3. The bot will give you two buttons: <b>Video</b> and <b>Audio</b>.\n4. Click your desired format and the bot will download it for you! 🎉"
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

    elif data == "vip_premium":
        txt = "👑 <b>VIP Premium Activated!</b>\n\n🎉 অভিনন্দন! আপনি আমাদের বটের একজন VIP ইউজার।\nআপনার জন্য ভিডিও এবং মিউজিক (MP3) ডাউনলোড করা <b>আজীবন সম্পূর্ণ ফ্রি এবং আনলিমিটেড!</b>\n\nআমাদের সাপোর্ট চ্যানেলে যুক্ত থাকুন।"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode=ParseMode.HTML)

    elif data == "main_menu":
        await show_main_menu(update, context)

    # --- Admin callbacks ---
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

    text = f"👑 <b>সুপার এডমিন ড্যাশবোর্ড</b>\n━━━━━━━━━━━━━━━━━━\n👥 মোট ইউজার: {usr} জন\n📥 মোট ডাউনলোড: {dl} টি\n━━━━━━━━━━━━━━━━━━\n👇 <i>অ্যাকশন বেছে নিন:</i>"
    kb = [
        [InlineKeyboardButton("📣 ইউজার ব্রডকাস্ট", callback_data="admin_bc")],
        [InlineKeyboardButton("❌ লগআউট", callback_data="admin_logout")]
    ]
    if hasattr(update_or_message, 'reply_text'): await update_or_message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
    else: await update_or_message.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

def main():
    # 🌐 সার্ভার ২৪ ঘণ্টা জাগিয়ে রাখার জন্য
    keep_alive()
    
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("saddamadmin", saddamadmin_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, handle_text))
    
    print("🚀 Auto Downloader Bot (v7.0) is running 24/7...")
    app.run_polling()

if __name__ == '__main__':
    main()
