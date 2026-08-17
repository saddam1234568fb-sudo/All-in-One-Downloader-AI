import os
import re
import time
import asyncio
import sqlite3
import logging
import secrets
from datetime import datetime, timedelta

import yt_dlp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from keep_alive import keep_alive


# ============================================================
# CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

# Example:
# ADMIN_IDS=123456789,987654321
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

SUPPORT_CHANNEL_LINK = os.getenv(
    "SUPPORT_CHANNEL_LINK",
    "https://t.me/your_support_channel"
)

DB_NAME = "bot_database.db"
DOWNLOAD_DIR = "downloads"

# Telegram upload limit varies by Bot API/account/server setup.
# Keep a configurable safety limit.
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "49"))

# Basic anti-spam cooldown
DOWNLOAD_COOLDOWN = int(os.getenv("DOWNLOAD_COOLDOWN", "8"))

# Maximum simultaneous downloads globally
MAX_CONCURRENT_DOWNLOADS = int(
    os.getenv("MAX_CONCURRENT_DOWNLOADS", "2")
)

# Free users' daily download limit.
# Set 0 for unlimited.
FREE_DAILY_LIMIT = int(
    os.getenv("FREE_DAILY_LIMIT", "20")
)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)

logger = logging.getLogger("premium_downloader")


# ============================================================
# TEXTS
# ============================================================

TEXTS = {
    "bn": {
        "welcome":
            "🎉 <b>হ্যালো {name}!</b> 👋\n\n"
            "🔥 <b>Premium Downloader</b>-এ স্বাগতম!\n\n"
            "🔗 আপনার অনুমোদিত/Public media link এখানে পাঠান।\n"
            "🎬 Video অথবা 🎵 Audio হিসেবে ডাউনলোড করার অপশন পাবেন।\n\n"
            "👇 নিচের Menu ব্যবহার করুন।",

        "main_title":
            "🔥 <b>PREMIUM DOWNLOADER</b>\n\n"
            "দ্রুত এবং সহজভাবে আপনার অনুমোদিত media download করুন।",

        "btn_video": "🎬 Video Download",
        "btn_audio": "🎵 MP3 Download",
        "btn_history": "📥 My Downloads",
        "btn_profile": "👤 My Profile",
        "btn_stats": "📊 Statistics",
        "btn_vip": "👑 VIP Premium",
        "btn_referral": "🎁 Referral",
        "btn_leaderboard": "🏆 Leaderboard",
        "btn_reward": "🔥 Daily Reward",
        "btn_settings": "⚙️ Settings",
        "btn_how": "📚 How to Use",
        "btn_support": "🎧 Support",

        "back": "🔙 Back",
        "language": "🌐 Language",
        "quality": "🎚️ Select Quality",

        "link_detected":
            "🔗 <b>Link Detected!</b>\n\n"
            "📌 Platform: <b>{platform}</b>\n\n"
            "👇 আপনি কী করতে চান?",

        "processing":
            "⏳ <b>Processing...</b>\n\n"
            "দয়া করে অপেক্ষা করুন।",

        "queue":
            "📥 <b>Download Queue</b>\n\n"
            "⏳ আপনার request processing queue-তে আছে।",

        "too_fast":
            "⚠️ একটু অপেক্ষা করুন।\n"
            "তারপর আবার Download করুন।",

        "limit":
            "🚫 <b>Daily Limit Reached</b>\n\n"
            "আজকের Free download limit শেষ হয়েছে।",

        "failed":
            "❌ <b>Download Failed</b>\n\n"
            "Link unavailable, unsupported বা server error হতে পারে।",

        "too_large":
            "📦 <b>File Too Large</b>\n\n"
            "ফাইলটি Bot-এর configured upload limit-এর বেশি।",

        "uploading":
            "🚀 <b>Download Complete!</b>\n\n"
            "এখন আপনার chat-এ upload করা হচ্ছে...",

        "profile":
            "👤 <b>MY PROFILE</b>\n\n"
            "📝 Name: {name}\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "📅 Joined: {joined}\n\n"
            "📥 Total Downloads: <b>{downloads}</b>\n"
            "🎬 Videos: <b>{videos}</b>\n"
            "🎵 Audio: <b>{audio}</b>\n"
            "🔥 Streak: <b>{streak}</b> days\n"
            "👑 Status: <b>{status}</b>\n"
            "👥 Referrals: <b>{referrals}</b>",

        "no_history":
            "📥 <b>Download History</b>\n\n"
            "এখনও কোনো Download History নেই।",

        "history":
            "📥 <b>RECENT DOWNLOADS</b>\n\n{items}",

        "stats":
            "📊 <b>MY STATISTICS</b>\n\n"
            "📥 Total: <b>{total}</b>\n"
            "🎬 Videos: <b>{videos}</b>\n"
            "🎵 Audio: <b>{audio}</b>\n"
            "📅 This Week: <b>{week}</b>\n"
            "📅 Today: <b>{today}</b>\n"
            "🏆 Rank: <b>#{rank}</b>",

        "referral":
            "🎁 <b>MY REFERRAL</b>\n\n"
            "👥 Referrals: <b>{count}</b>\n\n"
            "🔗 আপনার Referral Link:\n"
            "<code>{link}</code>",

        "reward_claimed":
            "🎁 <b>Daily Reward Claimed!</b>\n\n"
            "🔥 Current Streak: <b>{streak}</b> days",

        "reward_already":
            "⏰ আজকের Reward ইতোমধ্যে নেওয়া হয়েছে।\n\n"
            "🔥 Streak: <b>{streak}</b> days",

        "leaderboard":
            "🏆 <b>TOP DOWNLOADERS</b>\n\n{rows}",

        "vip":
            "👑 <b>VIP PREMIUM</b>\n\n"
            "আপনার Account Status: <b>{status}</b>\n\n"
            "VIP system payment integration-এর জন্য প্রস্তুত।\n"
            "Admin চাইলে User-কে VIP দিতে পারবেন।",

        "settings":
            "⚙️ <b>SETTINGS</b>\n\n"
            "🌐 Language: <b>{lang}</b>\n"
            "🎚️ Default Quality: <b>{quality}</b>",

        "language_changed":
            "✅ Language updated!",

        "banned":
            "🚫 আপনার Account বর্তমানে restricted।",

        "invalid":
            "❌ কোনো valid URL পাওয়া যায়নি।\n\n"
            "একটি অনুমোদিত/Public media URL পাঠান।",

        "how":
            "📚 <b>HOW TO USE</b>\n\n"
            "1️⃣ একটি supported/public media URL পাঠান।\n"
            "2️⃣ Platform detect হবে।\n"
            "3️⃣ Video অথবা Audio নির্বাচন করুন।\n"
            "4️⃣ Video হলে Quality নির্বাচন করুন।\n"
            "5️⃣ Download complete হলে file আপনার chat-এ পাঠানো হবে।",

        "admin_only":
            "🚫 Admin access required.",

        "admin_login":
            "🔐 Admin verification-এর জন্য Username দিন:",

        "admin_password":
            "🔑 Password দিন:",

        "admin_dashboard":
            "👑 <b>SUPER ADMIN DASHBOARD</b>\n\n"
            "👥 Total Users: <b>{users}</b>\n"
            "🟢 Active Today: <b>{active}</b>\n"
            "📥 Downloads: <b>{downloads}</b>\n"
            "🎬 Videos: <b>{videos}</b>\n"
            "🎵 Audio: <b>{audio}</b>\n"
            "👑 VIP Users: <b>{vip}</b>\n"
            "🚫 Banned: <b>{banned}</b>",

        "broadcast_prompt":
            "📣 <b>Broadcast</b>\n\n"
            "যে Message/Photo/Video broadcast করতে চান সেটি পাঠান।",

        "broadcast_done":
            "📊 <b>BROADCAST COMPLETE</b>\n\n"
            "👥 Total: {total}\n"
            "✅ Success: {success}\n"
            "❌ Failed: {failed}",

        "user_search":
            "🔎 User ID লিখুন:",

        "user_not_found":
            "❌ User পাওয়া যায়নি।",

        "user_details":
            "👤 <b>USER DETAILS</b>\n\n"
            "📝 Name: {name}\n"
            "🆔 ID: <code>{uid}</code>\n"
            "📥 Downloads: {downloads}\n"
            "👑 VIP: {vip}\n"
            "🚫 Banned: {banned}",

        "vip_updated":
            "👑 VIP status updated.",

        "ban_updated":
            "🚫 User ban status updated.",
    },

    "en": {
        "welcome":
            "🎉 <b>Hello {name}!</b> 👋\n\n"
            "🔥 Welcome to <b>Premium Downloader</b>!\n\n"
            "Send an authorized/public media URL here.\n"
            "You can choose Video or Audio download.",

        "main_title":
            "🔥 <b>PREMIUM DOWNLOADER</b>\n\n"
            "Fast and simple media downloader.",

        "btn_video": "🎬 Video Download",
        "btn_audio": "🎵 MP3 Download",
        "btn_history": "📥 My Downloads",
        "btn_profile": "👤 My Profile",
        "btn_stats": "📊 Statistics",
        "btn_vip": "👑 VIP Premium",
        "btn_referral": "🎁 Referral",
        "btn_leaderboard": "🏆 Leaderboard",
        "btn_reward": "🔥 Daily Reward",
        "btn_settings": "⚙️ Settings",
        "btn_how": "📚 How to Use",
        "btn_support": "🎧 Support",

        "back": "🔙 Back",
        "language": "🌐 Language",
        "quality": "🎚️ Select Quality",

        "link_detected":
            "🔗 <b>Link Detected!</b>\n\n"
            "📌 Platform: <b>{platform}</b>\n\n"
            "👇 Select an option:",

        "processing":
            "⏳ <b>Processing...</b>\n\nPlease wait.",

        "queue":
            "📥 <b>Download Queue</b>\n\n"
            "Your request is waiting in the queue.",

        "too_fast":
            "⚠️ Please wait a few seconds before downloading again.",

        "limit":
            "🚫 <b>Daily Limit Reached</b>\n\n"
            "Your free daily limit has been reached.",

        "failed":
            "❌ <b>Download Failed</b>\n\n"
            "The URL may be unavailable or unsupported.",

        "too_large":
            "📦 <b>File Too Large</b>\n\n"
            "The file exceeds the configured upload limit.",

        "uploading":
            "🚀 <b>Download Complete!</b>\n\nUploading to your chat...",

        "profile":
            "👤 <b>MY PROFILE</b>\n\n"
            "📝 Name: {name}\n"
            "🆔 ID: <code>{user_id}</code>\n"
            "📅 Joined: {joined}\n\n"
            "📥 Total Downloads: <b>{downloads}</b>\n"
            "🎬 Videos: <b>{videos}</b>\n"
            "🎵 Audio: <b>{audio}</b>\n"
            "🔥 Streak: <b>{streak}</b> days\n"
            "👑 Status: <b>{status}</b>\n"
            "👥 Referrals: <b>{referrals}</b>",

        "no_history":
            "📥 <b>Download History</b>\n\nNo downloads yet.",

        "history":
            "📥 <b>RECENT DOWNLOADS</b>\n\n{items}",

        "stats":
            "📊 <b>MY STATISTICS</b>\n\n"
            "📥 Total: <b>{total}</b>\n"
            "🎬 Videos: <b>{videos}</b>\n"
            "🎵 Audio: <b>{audio}</b>\n"
            "📅 This Week: <b>{week}</b>\n"
            "📅 Today: <b>{today}</b>\n"
            "🏆 Rank: <b>#{rank}</b>",

        "referral":
            "🎁 <b>MY REFERRAL</b>\n\n"
            "👥 Referrals: <b>{count}</b>\n\n"
            "🔗 Referral Link:\n"
            "<code>{link}</code>",

        "reward_claimed":
            "🎁 <b>Daily Reward Claimed!</b>\n\n"
            "🔥 Current Streak: <b>{streak}</b> days",

        "reward_already":
            "⏰ Today's reward has already been claimed.\n\n"
            "🔥 Streak: <b>{streak}</b> days",

        "leaderboard":
            "🏆 <b>TOP DOWNLOADERS</b>\n\n{rows}",

        "vip":
            "👑 <b>VIP PREMIUM</b>\n\n"
            "Account Status: <b>{status}</b>\n\n"
            "The VIP framework is ready for payment integration.",

        "settings":
            "⚙️ <b>SETTINGS</b>\n\n"
            "🌐 Language: <b>{lang}</b>\n"
            "🎚️ Default Quality: <b>{quality}</b>",

        "language_changed":
            "✅ Language updated!",

        "banned":
            "🚫 Your account is currently restricted.",

        "invalid":
            "❌ No valid URL was found.",

        "how":
            "📚 <b>HOW TO USE</b>\n\n"
            "1️⃣ Send a supported/public media URL.\n"
            "2️⃣ Select Video or Audio.\n"
            "3️⃣ Select video quality if available.\n"
            "4️⃣ Wait for processing.",

        "admin_only":
            "🚫 Admin access required.",

        "admin_login":
            "🔐 Enter Admin Username:",

        "admin_password":
            "🔑 Enter Password:",

        "admin_dashboard":
            "👑 <b>SUPER ADMIN DASHBOARD</b>\n\n"
            "👥 Total Users: <b>{users}</b>\n"
            "🟢 Active Today: <b>{active}</b>\n"
            "📥 Downloads: <b>{downloads}</b>\n"
            "🎬 Videos: <b>{videos}</b>\n"
            "🎵 Audio: <b>{audio}</b>\n"
            "👑 VIP Users: <b>{vip}</b>\n"
            "🚫 Banned: <b>{banned}</b>",

        "broadcast_prompt":
            "📣 <b>Broadcast</b>\n\n"
            "Send the Message/Photo/Video to broadcast.",

        "broadcast_done":
            "📊 <b>BROADCAST COMPLETE</b>\n\n"
            "👥 Total: {total}\n"
            "✅ Success: {success}\n"
            "❌ Failed: {failed}",

        "user_search":
            "🔎 Enter User ID:",

        "user_not_found":
            "❌ User not found.",

        "user_details":
            "👤 <b>USER DETAILS</b>\n\n"
            "📝 Name: {name}\n"
            "🆔 ID: <code>{uid}</code>\n"
            "📥 Downloads: {downloads}\n"
            "👑 VIP: {vip}\n"
            "🚫 Banned: {banned}",

        "vip_updated":
            "👑 VIP status updated.",

        "ban_updated":
            "🚫 User ban status updated.",
    }
}


# ============================================================
# DATABASE
# ============================================================

def db():
    return sqlite3.connect(DB_NAME, timeout=30)


def init_db():
    with db() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lang TEXT DEFAULT 'bn',
                is_vip INTEGER DEFAULT 0,
                vip_expires TEXT,
                is_banned INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                last_active TIMESTAMP,
                streak INTEGER DEFAULT 0,
                last_reward TEXT,
                referral_count INTEGER DEFAULT 0,
                referred_by INTEGER
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                url TEXT,
                platform TEXT,
                media_type TEXT,
                quality TEXT,
                title TEXT,
                file_size REAL,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                quality TEXT DEFAULT '720p'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_activity (
                user_id INTEGER,
                activity_date TEXT,
                PRIMARY KEY(user_id, activity_date)
            )
        """)

        for key in [
            "total_downloads",
            "total_video",
            "total_audio",
            "total_users"
        ]:
            conn.execute(
                "INSERT OR IGNORE INTO stats(key,value) VALUES(?,0)",
                (key,)
            )

        conn.commit()


init_db()


# ============================================================
# USER FUNCTIONS
# ============================================================

def save_user(user):
    with db() as conn:

        exists = conn.execute(
            "SELECT user_id FROM bot_users WHERE user_id=?",
            (user.id,)
        ).fetchone()

        if not exists:
            conn.execute("""
                INSERT INTO bot_users(
                    user_id,
                    first_name,
                    username,
                    last_active
                )
                VALUES(?,?,?,?,?)
            """, (
                user.id,
                user.first_name or "",
                user.username or "",
                datetime.utcnow().isoformat()
            ))

            conn.execute(
                "UPDATE stats SET value=value+1 WHERE key='total_users'"
            )

        else:
            conn.execute("""
                UPDATE bot_users
                SET first_name=?,
                    username=?,
                    last_active=?
                WHERE user_id=?
            """, (
                user.first_name or "",
                user.username or "",
                datetime.utcnow().isoformat(),
                user.id
            ))

        conn.commit()


def get_user(user_id):
    with db() as conn:
        return conn.execute("""
            SELECT
                user_id,
                first_name,
                username,
                joined_date,
                lang,
                is_vip,
                vip_expires,
                is_banned,
                total_downloads,
                last_active,
                streak,
                last_reward,
                referral_count
            FROM bot_users
            WHERE user_id=?
        """, (user_id,)).fetchone()


def get_lang(user_id):
    row = get_user(user_id)
    if row and row[4] in TEXTS:
        return row[4]
    return "bn"


def T(user_id, key):
    lang = get_lang(user_id)
    return TEXTS[lang].get(key, TEXTS["bn"].get(key, ""))


def set_language(user_id, lang):
    if lang not in TEXTS:
        return

    with db() as conn:
        conn.execute(
            "UPDATE bot_users SET lang=? WHERE user_id=?",
            (lang, user_id)
        )
        conn.commit()


def is_banned(user_id):
    row = get_user(user_id)
    return bool(row and row[7])


def is_vip(user_id):
    row = get_user(user_id)

    if not row:
        return False

    if not row[5]:
        return False

    expiry = row[6]

    if not expiry:
        return True

    try:
        return datetime.fromisoformat(expiry) > datetime.utcnow()
    except Exception:
        return False


# ============================================================
# REFERRAL
# ============================================================

def process_referral(user_id, referrer_id):
    if not referrer_id or user_id == referrer_id:
        return

    with db() as conn:

        existing = conn.execute(
            "SELECT referred_by FROM bot_users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if not existing:
            return

        if existing[0]:
            return

        ref_exists = conn.execute(
            "SELECT id FROM referrals WHERE referred_id=?",
            (user_id,)
        ).fetchone()

        if ref_exists:
            return

        conn.execute("""
            UPDATE bot_users
            SET referred_by=?
            WHERE user_id=?
        """, (referrer_id, user_id))

        conn.execute("""
            UPDATE bot_users
            SET referral_count=referral_count+1
            WHERE user_id=?
        """, (referrer_id,))

        conn.execute("""
            INSERT INTO referrals(referrer_id,referred_id)
            VALUES(?,?)
        """, (referrer_id, user_id))

        conn.commit()


# ============================================================
# DAILY REWARD
# ============================================================

def claim_daily_reward(user_id):
    today = datetime.utcnow().date().isoformat()

    with db() as conn:

        row = conn.execute(
            "SELECT streak,last_reward FROM bot_users WHERE user_id=?",
            (user_id,)
        ).fetchone()

        if not row:
            return False, 0

        streak = row[0] or 0
        last_reward = row[1]

        if last_reward == today:
            return False, streak

        yesterday = (
            datetime.utcnow().date() - timedelta(days=1)
        ).isoformat()

        if last_reward == yesterday:
            streak += 1
        else:
            streak = 1

        conn.execute("""
            UPDATE bot_users
            SET streak=?,
                last_reward=?
            WHERE user_id=?
        """, (streak, today, user_id))

        conn.commit()

    return True, streak


# ============================================================
# STATISTICS
# ============================================================

def get_user_stats(user_id):

    with db() as conn:

        total = conn.execute("""
            SELECT COUNT(*)
            FROM downloads
            WHERE user_id=? AND status='success'
        """, (user_id,)).fetchone()[0]

        videos = conn.execute("""
            SELECT COUNT(*)
            FROM downloads
            WHERE user_id=?
            AND media_type='video'
            AND status='success'
        """, (user_id,)).fetchone()[0]

        audio = conn.execute("""
            SELECT COUNT(*)
            FROM downloads
            WHERE user_id=?
            AND media_type='audio'
            AND status='success'
        """, (user_id,)).fetchone()[0]

        today = datetime.utcnow().date().isoformat()

        today_count = conn.execute("""
            SELECT COUNT(*)
            FROM downloads
            WHERE user_id=?
            AND status='success'
            AND DATE(created_at)=?
        """, (user_id, today)).fetchone()[0]

        week_date = (
            datetime.utcnow() - timedelta(days=7)
        ).isoformat()

        week_count = conn.execute("""
            SELECT COUNT(*)
            FROM downloads
            WHERE user_id=?
            AND status='success'
            AND created_at>=?
        """, (user_id, week_date)).fetchone()[0]

        rank = conn.execute("""
            SELECT COUNT(*) + 1
            FROM (
                SELECT user_id, COUNT(*) AS c
                FROM downloads
                WHERE status='success'
                GROUP BY user_id
            ) x
            WHERE x.c > ?
        """, (total,)).fetchone()[0]

    return total, videos, audio, today_count, week_count, rank


# ============================================================
# HISTORY
# ============================================================

def get_history(user_id, limit=10):

    with db() as conn:
        return conn.execute("""
            SELECT media_type,title,quality,platform,created_at
            FROM downloads
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()


# ============================================================
# DOWNLOAD LIMIT
# ============================================================

def daily_download_count(user_id):

    today = datetime.utcnow().date().isoformat()

    with db() as conn:
        return conn.execute("""
            SELECT COUNT(*)
            FROM downloads
            WHERE user_id=?
            AND status='success'
            AND DATE(created_at)=?
        """, (user_id, today)).fetchone()[0]


def can_download(user_id):

    if is_vip(user_id):
        return True

    if FREE_DAILY_LIMIT <= 0:
        return True

    return daily_download_count(user_id) < FREE_DAILY_LIMIT


# ============================================================
# DOWNLOAD LOG
# ============================================================

def create_download_log(
    user_id,
    url,
    platform,
    media_type,
    quality,
    title=""
):
    with db() as conn:

        cur = conn.execute("""
            INSERT INTO downloads(
                user_id,
                url,
                platform,
                media_type,
                quality,
                title,
                status
            )
            VALUES(?,?,?,?,?,?,?)
        """, (
            user_id,
            url,
            platform,
            media_type,
            quality,
            title,
            "processing"
        ))

        conn.commit()
        return cur.lastrowid


def update_download_log(
    download_id,
    status,
    file_size=None,
    title=None
):
    with db() as conn:

        conn.execute("""
            UPDATE downloads
            SET status=?,
                file_size=?,
                title=COALESCE(?,title)
            WHERE id=?
        """, (
            status,
            file_size,
            title,
            download_id
        ))

        if status == "success":

            conn.execute("""
                UPDATE bot_users
                SET total_downloads=total_downloads+1
                WHERE user_id=(
                    SELECT user_id
                    FROM downloads
                    WHERE id=?
                )
            """, (download_id,))

            conn.execute("""
                UPDATE stats
                SET value=value+1
                WHERE key='total_downloads'
            """)

            row = conn.execute("""
                SELECT media_type
                FROM downloads
                WHERE id=?
            """, (download_id,)).fetchone()

            if row:

                key = (
                    "total_video"
                    if row[0] == "video"
                    else "total_audio"
                )

                conn.execute(
                    "UPDATE stats SET value=value+1 WHERE key=?",
                    (key,)
                )

        conn.commit()


# ============================================================
# PLATFORM DETECTION
# ============================================================

def detect_platform(url):

    u = url.lower()

    if "youtube.com" in u or "youtu.be" in u:
        return "YouTube"

    if "tiktok.com" in u:
        return "TikTok"

    if "instagram.com" in u:
        return "Instagram"

    if "facebook.com" in u or "fb.watch" in u:
        return "Facebook"

    if "twitter.com" in u or "x.com" in u:
        return "X / Twitter"

    return "Other"


# ============================================================
# MEDIA INFO
# ============================================================

def extract_media_info(url):

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    try:

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            return {
                "title": info.get("title") or "Unknown",
                "duration": info.get("duration") or 0,
                "platform": info.get("extractor_key") or detect_platform(url),
                "thumbnail": info.get("thumbnail"),
            }

    except Exception as e:
        logger.warning("Info extraction failed: %s", e)

        return {
            "title": "Unknown",
            "duration": 0,
            "platform": detect_platform(url),
            "thumbnail": None,
        }


# ============================================================
# DOWNLOAD ENGINE
# ============================================================

def download_media(
    url,
    user_id,
    media_type,
    quality="720p"
):

    timestamp = int(time.time())

    base = os.path.join(
        DOWNLOAD_DIR,
        f"{user_id}_{timestamp}"
    )

    if media_type == "video":

        if quality == "360p":
            height = 360
        elif quality == "480p":
            height = 480
        elif quality == "1080p":
            height = 1080
        else:
            height = 720

        filename = base + ".mp4"

        format_str = (
            f"bestvideo[height<={height}]"
            f"[ext=mp4]+bestaudio[ext=m4a]/"
            f"best[height<={height}][ext=mp4]/best"
        )

        postprocessors = []

    else:

        filename = base + ".mp3"

        format_str = "bestaudio/best"

        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    opts = {
        "format": format_str,
        "outtmpl": filename,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "postprocessors": postprocessors,
        "http_headers": {
            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
    }

    try:

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            final_file = filename

            # FFmpeg may change extension/name.
            if media_type == "audio":
                possible = base + ".mp3"

                if os.path.exists(possible):
                    final_file = possible

            if os.path.exists(final_file):

                return {
                    "path": final_file,
                    "title": info.get("title") or "Downloaded Media",
                    "duration": info.get("duration") or 0
                }

            # fallback: search generated file
            for file in os.listdir(DOWNLOAD_DIR):

                if file.startswith(
                    os.path.basename(base)
                ):

                    path = os.path.join(
                        DOWNLOAD_DIR,
                        file
                    )

                    if os.path.isfile(path):

                        return {
                            "path": path,
                            "title": info.get("title") or "Downloaded Media",
                            "duration": info.get("duration") or 0
                        }

        return None

    except Exception as e:

        logger.exception(
            "Download failed for user %s: %s",
            user_id,
            e
        )

        return None


# ============================================================
# GLOBAL DOWNLOAD CONTROL
# ============================================================

download_semaphore = asyncio.Semaphore(
    MAX_CONCURRENT_DOWNLOADS
)

last_download_time = {}


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard(user_id):

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                T(user_id, "btn_video"),
                callback_data="choose_video"
            ),
            InlineKeyboardButton(
                T(user_id, "btn_audio"),
                callback_data="choose_audio"
            )
        ],
        [
            InlineKeyboardButton(
                T(user_id, "btn_history"),
                callback_data="history"
            ),
            InlineKeyboardButton(
                T(user_id, "btn_profile"),
                callback_data="profile"
            )
        ],
        [
            InlineKeyboardButton(
                T(user_id, "btn_stats"),
                callback_data="stats"
            ),
            InlineKeyboardButton(
                T(user_id, "btn_vip"),
                callback_data="vip"
            )
        ],
        [
            InlineKeyboardButton(
                T(user_id, "btn_referral"),
                callback_data="referral"
            ),
            InlineKeyboardButton(
                T(user_id, "btn_leaderboard"),
                callback_data="leaderboard"
            )
        ],
        [
            InlineKeyboardButton(
                T(user_id, "btn_reward"),
                callback_data="reward"
            ),
            InlineKeyboardButton(
                T(user_id, "btn_settings"),
                callback_data="settings"
            )
        ],
        [
            InlineKeyboardButton(
                T(user_id, "btn_how"),
                callback_data="how"
            ),
            InlineKeyboardButton(
                T(user_id, "btn_support"),
                url=SUPPORT_CHANNEL_LINK
            )
        ]
    ])


def back_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="main"
            )
        ]
    ])


def quality_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📱 360p",
                callback_data="quality_360"
            ),
            InlineKeyboardButton(
                "📱 480p",
                callback_data="quality_480"
            )
        ],
        [
            InlineKeyboardButton(
                "📺 720p",
                callback_data="quality_720"
            ),
            InlineKeyboardButton(
                "📺 1080p",
                callback_data="quality_1080"
            )
        ],
        [
            InlineKeyboardButton(
                "⭐ Best Available",
                callback_data="quality_best"
            )
        ],
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="main"
            )
        ]
    ])


# ============================================================
# MAIN MENU
# ============================================================

async def show_main_menu(update, context):

    user = update.effective_user

    save_user(user)

    text = T(user.id, "main_title")

    if update.callback_query:

        await update.callback_query.edit_message_text(
            text,
            reply_markup=main_keyboard(user.id),
            parse_mode=ParseMode.HTML
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=main_keyboard(user.id),
            parse_mode=ParseMode.HTML
        )


# ============================================================
# START
# ============================================================

async def start_command(update, context):

    user = update.effective_user

    save_user(user)

    # /start ref_123456
    if context.args:

        arg = context.args[0]

        if arg.startswith("ref_"):

            try:

                referrer_id = int(
                    arg.replace("ref_", "")
                )

                process_referral(
                    user.id,
                    referrer_id
                )

            except ValueError:
                pass

    context.user_data.clear()

    await update.message.reply_text(
        T(user.id, "welcome").format(
            name=user.first_name or "User"
        ),
        reply_markup=main_keyboard(user.id),
        parse_mode=ParseMode.HTML
    )


# ============================================================
# TEXT HANDLER
# ============================================================

async def handle_text(update, context):

    user = update.effective_user

    save_user(user)

    if is_banned(user.id):

        await update.message.reply_text(
            T(user.id, "banned"),
            parse_mode=ParseMode.HTML
        )

        return

    text = update.message.text or ""

    state = context.user_data.get("state")

    # --------------------------------------------------------
    # ADMIN LOGIN
    # --------------------------------------------------------

    if state == "ADMIN_USERNAME":

        if user.id not in ADMIN_IDS:

            context.user_data.clear()

            await update.message.reply_text(
                T(user.id, "admin_only")
            )

            return

        if text.strip() == ADMIN_USERNAME:

            context.user_data["state"] = "ADMIN_PASSWORD"

            await update.message.reply_text(
                T(user.id, "admin_password")
            )

        else:

            context.user_data.clear()

            await update.message.reply_text(
                "❌ Wrong username."
            )

        return

    if state == "ADMIN_PASSWORD":

        if user.id not in ADMIN_IDS:

            context.user_data.clear()
            return

        if secrets.compare_digest(
            text.strip(),
            ADMIN_PASSWORD
        ):

            context.user_data["is_admin"] = True
            context.user_data["state"] = None

            await show_admin_panel(
                update.message,
                context
            )

        else:

            context.user_data.clear()

            await update.message.reply_text(
                "❌ Wrong password."
            )

        return

    # --------------------------------------------------------
    # ADMIN BROADCAST
    # --------------------------------------------------------

    if (
        state == "BROADCAST"
        and context.user_data.get("is_admin")
    ):

        await broadcast_message(
            update,
            context
        )

        return

    # --------------------------------------------------------
    # ADMIN SEARCH
    # --------------------------------------------------------

    if (
        state == "SEARCH_USER"
        and context.user_data.get("is_admin")
    ):

        if not text.isdigit():

            await update.message.reply_text(
                "❌ Valid numeric User ID দিন।"
            )

            return

        target_id = int(text)

        await show_user_admin(
            update.message,
            target_id
        )

        context.user_data["state"] = None

        return

    # --------------------------------------------------------
    # URL DETECTION
    # --------------------------------------------------------

    url_pattern = re.compile(
        r"https?://[^\s<>]+",
        re.IGNORECASE
    )

    urls = url_pattern.findall(text)

    if not urls:

        await update.message.reply_text(
            T(user.id, "invalid"),
            parse_mode=ParseMode.HTML
        )

        return

    url = urls[0].rstrip(".,!?)]}>")

    context.user_data["last_url"] = url

    platform = detect_platform(url)

    await update.message.reply_text(
        T(user.id, "link_detected").format(
            platform=platform
        ),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    T(user.id, "btn_video"),
                    callback_data="choose_video"
                )
            ],
            [
                InlineKeyboardButton(
                    T(user.id, "btn_audio"),
                    callback_data="choose_audio"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Main Menu",
                    callback_data="main"
                )
            ]
        ]),
        parse_mode=ParseMode.HTML
    )


# ============================================================
# DOWNLOAD FUNCTION
# ============================================================

async def execute_download(
    query,
    context,
    media_type,
    quality="720p"
):

    user_id = query.from_user.id

    url = context.user_data.get("last_url")

    if not url:

        await query.answer(
            "❌ Link expired. Send it again.",
            show_alert=True
        )

        return

    if not can_download(user_id):

        await query.answer(
            T(user_id, "limit"),
            show_alert=True
        )

        return

    now = time.time()

    previous = last_download_time.get(
        user_id,
        0
    )

    if now - previous < DOWNLOAD_COOLDOWN:

        await query.answer(
            T(user_id, "too_fast"),
            show_alert=True
        )

        return

    last_download_time[user_id] = now

    platform = detect_platform(url)

    # Get info first
    info = await asyncio.to_thread(
        extract_media_info,
        url
    )

    title = info.get(
        "title",
        "Downloaded Media"
    )

    log_id = create_download_log(
        user_id,
        url,
        platform,
        media_type,
        quality,
        title
    )

    processing_msg = await query.edit_message_text(
        T(user_id, "processing"),
        parse_mode=ParseMode.HTML
    )

    async with download_semaphore:

        await context.bot.send_chat_action(
            chat_id=query.message.chat.id,
            action=(
                ChatAction.RECORD_VIDEO
                if media_type == "video"
                else ChatAction.RECORD_VOICE
            )
        )

        result = await asyncio.to_thread(
            download_media,
            url,
            user_id,
            media_type,
            quality
        )

    if not result:

        update_download_log(
            log_id,
            "failed"
        )

        await processing_msg.edit_text(
            T(user_id, "failed"),
            parse_mode=ParseMode.HTML
        )

        return

    file_path = result["path"]

    try:

        file_size = (
            os.path.getsize(file_path)
            / (1024 * 1024)
        )

        if file_size > MAX_FILE_MB:

            update_download_log(
                log_id,
                "too_large",
                file_size
            )

            await processing_msg.edit_text(
                T(user_id, "too_large"),
                parse_mode=ParseMode.HTML
            )

            return

        await processing_msg.edit_text(
            T(user_id, "uploading"),
            parse_mode=ParseMode.HTML
        )

        await context.bot.send_chat_action(
            chat_id=query.message.chat.id,
            action=(
                ChatAction.UPLOAD_VIDEO
                if media_type == "video"
                else ChatAction.UPLOAD_VOICE
            )
        )

        caption = (
            f"📥 <b>{title[:800]}</b>\n\n"
            f"🌐 {platform}\n"
            f"📦 {file_size:.2f} MB"
        )

        with open(file_path, "rb") as media:

            if media_type == "video":

                await context.bot.send_video(
                    chat_id=query.message.chat.id,
                    video=media,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True
                )

            else:

                await context.bot.send_audio(
                    chat_id=query.message.chat.id,
                    audio=media,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )

        update_download_log(
            log_id,
            "success",
            file_size,
            title
        )

        await processing_msg.delete()

    except Exception as e:

        logger.exception(
            "Upload error: %s",
            e
        )

        update_download_log(
            log_id,
            "failed",
            file_size
        )

        await processing_msg.edit_text(
            T(user_id, "failed"),
            parse_mode=ParseMode.HTML
        )

    finally:

        try:

            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception:
            pass


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def button_handler(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    save_user(query.from_user)

    if is_banned(user_id):

        await query.answer(
            T(user_id, "banned"),
            show_alert=True
        )

        return

    data = query.data

    # --------------------------------------------------------
    # MAIN
    # --------------------------------------------------------

    if data == "main":

        await show_main_menu(
            update,
            context
        )

        return

    # --------------------------------------------------------
    # VIDEO
    # --------------------------------------------------------

    if data == "choose_video":

        if not context.user_data.get("last_url"):

            await query.answer(
                "❌ আগে একটি URL পাঠান।",
                show_alert=True
            )

            return

        await query.edit_message_text(
            T(user_id, "quality"),
            reply_markup=quality_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # AUDIO
    # --------------------------------------------------------

    if data == "choose_audio":

        await execute_download(
            query,
            context,
            "audio",
            "audio"
        )

        return

    # --------------------------------------------------------
    # QUALITY
    # --------------------------------------------------------

    if data.startswith("quality_"):

        quality = data.replace(
            "quality_",
            ""
        )

        if quality == "best":
            quality = "1080p"

        await execute_download(
            query,
            context,
            "video",
            quality
        )

        return

    # --------------------------------------------------------
    # PROFILE
    # --------------------------------------------------------

    if data == "profile":

        row = get_user(user_id)

        total, videos, audio, _, _, _ = (
            get_user_stats(user_id)
        )

        joined = str(row[3])[:10]

        status = (
            "👑 VIP"
            if is_vip(user_id)
            else "🆓 Free"
        )

        await query.edit_message_text(
            T(user_id, "profile").format(
                name=row[1] or "User",
                user_id=user_id,
                joined=joined,
                downloads=total,
                videos=videos,
                audio=audio,
                streak=row[10] or 0,
                status=status,
                referrals=row[12] or 0
            ),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    if data == "history":

        rows = get_history(user_id)

        if not rows:

            await query.edit_message_text(
                T(user_id, "no_history"),
                reply_markup=back_keyboard(),
                parse_mode=ParseMode.HTML
            )

            return

        items = []

        for i, row in enumerate(rows, 1):

            media_icon = (
                "🎬"
                if row[0] == "video"
                else "🎵"
            )

            title = (
                row[1]
                or "Unknown"
            )

            title = title[:50]

            items.append(
                f"{i}. {media_icon} "
                f"<b>{title}</b>\n"
                f"   🌐 {row[3]} | "
                f"{row[2]}\n"
                f"   📅 {str(row[4])[:16]}"
            )

        await query.edit_message_text(
            T(user_id, "history").format(
                items="\n\n".join(items)
            ),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

    if data == "stats":

        total, videos, audio, today, week, rank = (
            get_user_stats(user_id)
        )

        await query.edit_message_text(
            T(user_id, "stats").format(
                total=total,
                videos=videos,
                audio=audio,
                today=today,
                week=week,
                rank=rank
            ),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # VIP
    # --------------------------------------------------------

    if data == "vip":

        status = (
            "👑 VIP"
            if is_vip(user_id)
            else "🆓 Free"
        )

        await query.edit_message_text(
            T(user_id, "vip").format(
                status=status
            ),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # REFERRAL
    # --------------------------------------------------------

    if data == "referral":

        bot = await context.bot.get_me()

        link = (
            f"https://t.me/{bot.username}"
            f"?start=ref_{user_id}"
        )

        row = get_user(user_id)

        await query.edit_message_text(
            T(user_id, "referral").format(
                count=row[12] or 0,
                link=link
            ),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # DAILY REWARD
    # --------------------------------------------------------

    if data == "reward":

        claimed, streak = claim_daily_reward(
            user_id
        )

        if claimed:

            text = T(
                user_id,
                "reward_claimed"
            ).format(streak=streak)

        else:

            text = T(
                user_id,
                "reward_already"
            ).format(streak=streak)

        await query.edit_message_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # LEADERBOARD
    # --------------------------------------------------------

    if data == "leaderboard":

        with db() as conn:

            rows = conn.execute("""
                SELECT first_name,total_downloads
                FROM bot_users
                ORDER BY total_downloads DESC
                LIMIT 10
            """).fetchall()

        leaderboard = []

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        for i, row in enumerate(rows):

            icon = (
                medals[i]
                if i < 3
                else f"{i+1}."
            )

            leaderboard.append(
                f"{icon} {row[0] or 'User'}"
                f" — <b>{row[1]}</b>"
            )

        await query.edit_message_text(
            T(user_id, "leaderboard").format(
                rows="\n".join(leaderboard)
            ),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # SETTINGS
    # --------------------------------------------------------

    if data == "settings":

        with db() as conn:

            row = conn.execute("""
                SELECT quality
                FROM user_settings
                WHERE user_id=?
            """, (user_id,)).fetchone()

        quality = (
            row[0]
            if row
            else "720p"
        )

        lang = (
            "বাংলা"
            if get_lang(user_id) == "bn"
            else "English"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🇧🇩 বাংলা",
                    callback_data="lang_bn"
                ),
                InlineKeyboardButton(
                    "🇬🇧 English",
                    callback_data="lang_en"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎚️ Default 360p",
                    callback_data="setq_360p"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎚️ Default 720p",
                    callback_data="setq_720p"
                )
            ],
            [
                InlineKeyboardButton(
                    "🎚️ Default 1080p",
                    callback_data="setq_1080p"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="main"
                )
            ]
        ])

        await query.edit_message_text(
            T(user_id, "settings").format(
                lang=lang,
                quality=quality
            ),
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # LANGUAGE
    # --------------------------------------------------------

    if data.startswith("lang_"):

        lang = data.replace(
            "lang_",
            ""
        )

        set_language(
            user_id,
            lang
        )

        await query.answer(
            T(user_id, "language_changed"),
            show_alert=True
        )

        await show_main_menu(
            update,
            context
        )

        return

    # --------------------------------------------------------
    # DEFAULT QUALITY
    # --------------------------------------------------------

    if data.startswith("setq_"):

        quality = data.replace(
            "setq_",
            ""
        )

        with db() as conn:

            conn.execute("""
                INSERT INTO user_settings(
                    user_id,
                    quality
                )
                VALUES(?,?)
                ON CONFLICT(user_id)
                DO UPDATE SET quality=excluded.quality
            """, (
                user_id,
                quality
            ))

            conn.commit()

        await query.answer(
            "✅ Quality updated!",
            show_alert=True
        )

        return

    # --------------------------------------------------------
    # HOW
    # --------------------------------------------------------

    if data == "how":

        await query.edit_message_text(
            T(user_id, "how"),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    if data == "admin_dashboard":

        if not context.user_data.get("is_admin"):

            await query.answer(
                T(user_id, "admin_only"),
                show_alert=True
            )

            return

        await show_admin_panel(
            query,
            context
        )

        return

    if data == "admin_broadcast":

        if not context.user_data.get("is_admin"):
            return

        context.user_data["state"] = "BROADCAST"

        await query.edit_message_text(
            T(user_id, "broadcast_prompt"),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="admin_dashboard"
                    )
                ]
            ]),
            parse_mode=ParseMode.HTML
        )

        return

    if data == "admin_search":

        if not context.user_data.get("is_admin"):
            return

        context.user_data["state"] = "SEARCH_USER"

        await query.edit_message_text(
            T(user_id, "user_search"),
            reply_markup=back_keyboard(),
            parse_mode=ParseMode.HTML
        )

        return

    if data.startswith("admin_vip_"):

        if not context.user_data.get("is_admin"):
            return

        target_id = int(
            data.replace(
                "admin_vip_",
                ""
            )
        )

        with db() as conn:

            current = conn.execute("""
                SELECT is_vip
                FROM bot_users
                WHERE user_id=?
            """, (target_id,)).fetchone()

            if current:

                new_status = 0 if current[0] else 1

                expiry = None

                if new_status:
                    expiry = (
                        datetime.utcnow()
                        + timedelta(days=30)
                    ).isoformat()

                conn.execute("""
                    UPDATE bot_users
                    SET is_vip=?,
                        vip_expires=?
                    WHERE user_id=?
                """, (
                    new_status,
                    expiry,
                    target_id
                ))

                conn.commit()

        await query.answer(
            T(user_id, "vip_updated"),
            show_alert=True
        )

        await show_user_admin(
            query,
            target_id
        )

        return

    if data.startswith("admin_ban_"):

        if not context.user_data.get("is_admin"):
            return

        target_id = int(
            data.replace(
                "admin_ban_",
                ""
            )
        )

        with db() as conn:

            current = conn.execute("""
                SELECT is_banned
                FROM bot_users
                WHERE user_id=?
            """, (target_id,)).fetchone()

            if current:

                new_status = 0 if current[0] else 1

                conn.execute("""
                    UPDATE bot_users
                    SET is_banned=?
                    WHERE user_id=?
                """, (
                    new_status,
                    target_id
                ))

                conn.commit()

        await query.answer(
            T(user_id, "ban_updated"),
            show_alert=True
        )

        await show_user_admin(
            query,
            target_id
        )

        return

    if data == "admin_logout":

        context.user_data.clear()

        await query.edit_message_text(
            "✅ Admin logged out.",
            parse_mode=ParseMode.HTML
        )


# ============================================================
# ADMIN COMMAND
# ============================================================

async def admin_command(update, context):

    user = update.effective_user

    save_user(user)

    if user.id not in ADMIN_IDS:

        await update.message.reply_text(
            T(user.id, "admin_only")
        )

        return

    context.user_data["state"] = "ADMIN_USERNAME"

    await update.message.reply_text(
        T(user.id, "admin_login"),
        parse_mode=ParseMode.HTML
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

async def show_admin_panel(target, context):

    user_id = (
        target.from_user.id
        if hasattr(target, "from_user")
        else target.effective_user.id
    )

    with db() as conn:

        users = conn.execute(
            "SELECT COUNT(*) FROM bot_users"
        ).fetchone()[0]

        downloads = conn.execute(
            "SELECT COUNT(*) FROM downloads WHERE status='success'"
        ).fetchone()[0]

        videos = conn.execute("""
            SELECT COUNT(*)
            FROM downloads
            WHERE status='success'
            AND media_type='video'
        """).fetchone()[0]

        audio = conn.execute("""
            SELECT COUNT(*)
            FROM downloads
            WHERE status='success'
            AND media_type='audio'
        """).fetchone()[0]

        vip = conn.execute("""
            SELECT COUNT(*)
            FROM bot_users
            WHERE is_vip=1
        """).fetchone()[0]

        banned = conn.execute("""
            SELECT COUNT(*)
            FROM bot_users
            WHERE is_banned=1
        """).fetchone()[0]

        today = datetime.utcnow().date().isoformat()

        active = conn.execute("""
            SELECT COUNT(*)
            FROM bot_users
            WHERE DATE(last_active)=?
        """, (today,)).fetchone()[0]

    text = T(
        user_id,
        "admin_dashboard"
    ).format(
        users=users,
        active=active,
        downloads=downloads,
        videos=videos,
        audio=audio,
        vip=vip,
        banned=banned
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📣 Broadcast",
                callback_data="admin_broadcast"
            ),
            InlineKeyboardButton(
                "🔎 Search User",
                callback_data="admin_search"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Refresh",
                callback_data="admin_dashboard"
            )
        ],
        [
            InlineKeyboardButton(
                "🚪 Logout",
                callback_data="admin_logout"
            )
        ]
    ])

    if hasattr(target, "edit_message_text"):

        await target.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    else:

        await target.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )


# ============================================================
# ADMIN USER SEARCH
# ============================================================

async def show_user_admin(target, target_id):

    row = get_user(target_id)

    admin_id = target.from_user.id

    if not row:

        text = T(
            admin_id,
            "user_not_found"
        )

        keyboard = back_keyboard()

    else:

        text = T(
            admin_id,
            "user_details"
        ).format(
            name=row[1] or "User",
            uid=row[0],
            downloads=row[8],
            vip="YES" if row[5] else "NO",
            banned="YES" if row[7] else "NO"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "👑 Toggle VIP",
                    callback_data=f"admin_vip_{target_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚫 Toggle Ban",
                    callback_data=f"admin_ban_{target_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Admin",
                    callback_data="admin_dashboard"
                )
            ]
        ])

    if hasattr(target, "edit_message_text"):

        await target.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

    else:

        await target.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )


# ============================================================
# BROADCAST
# ============================================================

async def broadcast_message(update, context):

    if not context.user_data.get("is_admin"):
        return

    with db() as conn:

        users = [
            row[0]
            for row in conn.execute(
                "SELECT user_id FROM bot_users WHERE is_banned=0"
            ).fetchall()
        ]

    status_message = await update.message.reply_text(
        f"⏳ Broadcasting to {len(users)} users..."
    )

    success = 0
    failed = 0

    for uid in users:

        try:

            await context.bot.copy_message(
                chat_id=uid,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )

            success += 1

            # Avoid hammering Telegram
            await asyncio.sleep(0.05)

        except Exception as e:

            failed += 1

            logger.warning(
                "Broadcast failed for %s: %s",
                uid,
                e
            )

    await status_message.edit_text(
        T(update.effective_user.id, "broadcast_done").format(
            total=len(users),
            success=success,
            failed=failed
        ),
        parse_mode=ParseMode.HTML
    )

    context.user_data["state"] = None

    await show_admin_panel(
        update.message,
        context
    )


# ============================================================
# CLEANUP JOB
# ============================================================

async def cleanup_files(context):

    now = time.time()

    for filename in os.listdir(DOWNLOAD_DIR):

        path = os.path.join(
            DOWNLOAD_DIR,
            filename
        )

        try:

            if (
                os.path.isfile(path)
                and now - os.path.getmtime(path) > 3600
            ):

                os.remove(path)

        except Exception as e:

            logger.warning(
                "Cleanup error: %s",
                e
            )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update, context):

    logger.exception(
        "Unhandled exception:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    keep_alive()

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    app.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin_command
        )
    )

    # Callback buttons
    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # Text
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text
        )
    )

    # Error handler
    app.add_error_handler(
        error_handler
    )

    # Automatic cleanup
    app.job_queue.run_repeating(
        cleanup_files,
        interval=3600,
        first=300
    )

    logger.info(
        "🚀 Premium Downloader v9.0 started successfully."
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
