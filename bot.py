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
from telegram.error import BadRequest

# 🌐 সার্ভার সজাগ রাখার জন্য
from keep_alive import keep_alive

# --- কনফিগারেশন ---
BOT_TOKEN = "8978899309:AAGySai08hJM-SFfgZHA7ddkxFbOV_NDobw"
MAIN_CHANNEL_LINK = "https://t.me/+HbL1VKdIbaQ5ZjI1"  
MAIN_CHANNEL_ID = "--1004313671513" 

ADMIN_USERNAME = "saddamadmin"
ADMIN_PASSWORD = "saddamadmin1234"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_NAME = "bot_database.db"

# --- ডাটাবেজ সেটআপ ---
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS bot_users (user_id INTEGER PRIMARY KEY, first_name TEXT, joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER DEFAULT 0)")
        conn.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_downloads', 0)")
        conn.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_ai_chats', 0)")
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
        url = f"https://api.popcat.xyz/chatbot?msg={encoded_text}&owner=Saddam&botname=SmartAI"
        r = requests.get(url).json()
        return r.get('response', "দুঃখিত, সার্ভার এখন ব্যস্ত আছে। একটু পর আবার চেষ্টা করুন।")
    except:
        return "🤖 আমার AI ব্রেইন এখন একটু ঘুমাচ্ছে। কিছুক্ষণ পর মেসেজ দিন!"

# --- ভিডিও ডাউনলোডার ফাংশন ---
def download_video(url, user_id):
    filename = f"video_{user_id}_{int(time.time())}.mp4"
    ydl_opts = {
        'format': 'best[ext=mp4][filesize<50M]/best[filesize<50M]/best',
        'outtmpl': filename,
        'quiet': True,
        'noplaylist': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return filename
    except Exception as e:
        return None

# --- স্টার্ট ও ফোর্স সাবস্ক্রাইব ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id, user.first_name)
    context.user_data['state'] = None

    try:
        member = await context.bot.get_chat_member(MAIN_CHANNEL_ID, user.id)
        if member.status in ['left', 'kicked']: raise BadRequest("Not joined")
        await show_main_menu(update, context) 
    except Exception as e:
        txt = "🛑 <b>অ্যাক্সেস ডিনাইড!</b>\n\nআমাদের বটের <b>VIP Downloader ও AI</b> ফিচারগুলো ব্যবহার করতে হলে প্রথমে আপনাকে আমাদের <b>মেইন চ্যানেলে</b> জয়েন করতে হবে।\n\n১. <b>'🤖 I am not a robot'</b> বাটনে ক্লিক করে জয়েন করুন।\n২. তারপর ফিরে এসে <b>'✅ Verify'</b> বাটনে ক্লিক করুন।"
        kb = [
            [InlineKeyboardButton("🤖 I am not a robot", url=MAIN_CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Verify", callback_data="verify_sub")]
        ]
        if update.message: await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
        else: await update.callback_query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)

async def show_main_menu(obj, context: ContextTypes.DEFAULT_TYPE):
    is_query = hasattr(obj, 'data') 
    user = obj.from_user
    txt = (
        f"🎉 <b>ভেরিফিকেশন সফল!</b>\n\n"
        f"✨ <b>হ্যালো {user.first_name}!</b> 👋\n"
        f"🔥 <b>All-in-One Downloader & AI Bot</b>-এ আপনাকে স্বাগতম!\n\n"
        f"💡 <b>কীভাবে ব্যবহার করবেন?</b>\n"
        f"🔗 <b>ভিডিও ডাউনলোড:</b> যেকোনো Facebook, YouTube, TikTok বা Instagram ভিডিওর লিংক কপি করে এখানে পেস্ট করুন।\n"
        f"🤖 <b>AI চ্যাট:</b> আপনি চাইলে আমার সাথে যেকোনো বিষয়ে গল্প করতে পারেন বা প্রশ্ন জিজ্ঞেস করতে পারেন!\n\n"
        f"👇 <i>যেকোনো একটি লিংক দিয়ে ট্রাই করে দেখুন!</i>"
    )
    kb = [
        [InlineKeyboardButton("📥 How to Download?", callback_data="how_to"), InlineKeyboardButton("🆔 My ID", callback_data="my_id")],
        [InlineKeyboardButton("🎧 Support Channel", url=MAIN_CHANNEL_LINK)]
    ]
    markup = InlineKeyboardMarkup(kb)
    
    if is_query: await obj.edit_message_text(txt, reply_markup=markup, parse_mode=ParseMode.HTML)
    else: await obj.message.reply_text(txt, reply_markup=markup, parse_mode=ParseMode.HTML)

# --- টেক্সট / লিংক ডিটেক্টর (Main Magic) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    state = context.user_data.get('state')
    is_admin = context.user_data.get('is_admin')

    # Admin Login
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

    # Admin Broadcast
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

    # User Checks Force Sub before processing message
    try:
        member = await context.bot.get_chat_member(MAIN_CHANNEL_ID, user.id)
        if member.status in ['left', 'kicked']: raise BadRequest("Not joined")
    except:
        await start_command(update, context)
        return

    # --- লিংক নাকি চ্যাট ডিটেক্ট করা ---
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    urls = url_pattern.findall(text)

    if urls:
        # Link Detected -> Download Video
        url = urls[0]
        processing_msg = await update.message.reply_text("⏳ <b>ভিডিওটি প্রসেস করা হচ্ছে... দয়া করে অপেক্ষা করুন!</b>", parse_mode=ParseMode.HTML)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VIDEO)
        
        # Download in background
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, download_video, url, user.id)

        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / (1024 * 1024) # MB
            if file_size > 49:
                await processing_msg.edit_text("❌ <b>ভিডিওটি অনেক বড় (50MB+)!</b> টেলিগ্রামের লিমিটের কারণে পাঠানো সম্ভব হচ্ছে না।", parse_mode=ParseMode.HTML)
            else:
                await processing_msg.edit_text("🚀 <b>ভিডিও ডাউনলোড সম্পন্ন! এখন আপলোড করা হচ্ছে...</b>", parse_mode=ParseMode.HTML)
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO)
                try:
                    with open(file_path, 'rb') as video:
                        await update.message.reply_video(video, caption="📥 <b>Downloaded by:</b> @SmartAccept_AutoBot", parse_mode=ParseMode.HTML)
                    update_stat('total_downloads')
                    await processing_msg.delete()
                except Exception as e:
                    await processing_msg.edit_text("❌ <b>আপলোড করতে সমস্যা হয়েছে!</b>", parse_mode=ParseMode.HTML)
            os.remove(file_path) # Clean up
        else:
            await processing_msg.edit_text("❌ <b>ভিডিওটি ডাউনলোড করা সম্ভব হয়নি!</b> লিংকটি প্রাইভেট হতে পারে অথবা সার্ভারে সমস্যা হচ্ছে।", parse_mode=ParseMode.HTML)
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
    
    if data == "verify_sub":
        try:
            member = await context.bot.get_chat_member(MAIN_CHANNEL_ID, user_id)
            if member.status in ['left', 'kicked']: await query.answer("❌ আপনি এখনো জয়েন করেননি!", show_alert=True)
            else: await show_main_menu(query, context)
        except:
            await show_main_menu(query, context) 

    elif data == "how_to":
        txt = "💡 <b>কীভাবে ডাউনলোড করবেন?</b>\n\n১. TikTok, Facebook বা Instagram থেকে ভিডিওর <b>Copy Link</b> করুন।\n২. লিংকটি এখানে পেস্ট করে সেন্ড করুন।\n৩. কিছুক্ষণের মধ্যেই বট আপনাকে কোনো ওয়াটারমার্ক ছাড়াই মেইন ভিডিওটি দিয়ে দেবে! 🎉"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode=ParseMode.HTML)

    elif data == "my_id":
        txt = f"👤 <b>আপনার প্রোফাইল:</b>\n\n📝 নাম: {query.from_user.first_name}\n🆔 ইউজার আইডি: <code>{user_id}</code>"
        await query.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]), parse_mode=ParseMode.HTML)
        
    elif data == "main_menu":
        await show_main_menu(query, context)

    # Admin callbacks
    elif data == "admin_bc":
        context.user_data['state'] = 'WAITING_BC_MSG'
        await query.edit_message_text("📣 <b>ইউজার ব্রডকাস্ট:</b>\n\nসব ইউজারের কাছে পাঠানোর জন্য মেসেজ বা ছবি সেন্ড করুন:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ বাতিল", callback_data="admin_cancel")]]))

    elif data == "admin_cancel":
        await show_admin_panel(query, context)
        
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

    text = f"👑 <b>সুপার এডমিন ড্যাশবোর্ড</b>\n━━━━━━━━━━━━━━━━━━\n👥 মোট ইউজার: {usr}\n📥 মোট ডাউনলোড: {dl} টি\n🤖 মোট AI চ্যাট: {ai} বার\n━━━━━━━━━━━━━━━━━━\n👇 <i>অ্যাকশন বেছে নিন:</i>"
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
