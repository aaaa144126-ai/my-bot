"""
╔══════════════════════════════════════════════════════════════╗
║           🛡️ بوت الحماية المتكامل - Guardian Bot            ║
║              الإصدار 1.0 - جزء الحماية الكامل               ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
import asyncio
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import (
    Update, ChatPermissions, InlineKeyboardButton,
    InlineKeyboardMarkup, ChatMemberAdministrator
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ChatMemberHandler,
    filters, ContextTypes
)
from telegram.error import TelegramError

# ══════════════════════════════════════════════════
#                   الإعدادات الأساسية
# ══════════════════════════════════════════════════
TOKEN = os.getenv("BOT_TOKEN", "8766908791:AAEPlolaB1khYPzqtb1lUSJKzhdQKIbp-RU")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7821129203"))  # ضع الـ ID بتاعك هنا

# ══════════════════════════════════════════════════
#                   قاعدة البيانات (ملفات JSON)
# ══════════════════════════════════════════════════
DATA_FILE = "data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "warnings": {},       # إنذارات المستخدمين
        "banned": {},         # المحظورون
        "muted": {},          # المكتومون
        "settings": {},       # إعدادات كل مجموعة
        "admins": {},         # المشرفون المضافون يدوياً
        "whitelist": {},      # الكلمات المسموح بها
        "blacklist": {},      # الكلمات المحظورة
        "welcome": {},        # رسائل الترحيب
        "antiflood": {},      # إعدادات الفلود
        "logs": []            # سجل المخالفات
    }

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_data()

# ══════════════════════════════════════════════════
#              قوائم الكلمات المحظورة
# ══════════════════════════════════════════════════
DEFAULT_BLACKLIST = [
    # كلمات إهانة وسب - (مخفية هنا، يتم تحميلها من ملف خارجي)
    "وسخ", "كلب", "حمار", "غبي", "احا", "لعنة",
    "زفت", "منيك", "شرموط", "عاهر", "بتاعتك"
]

SPAM_PATTERNS = [
    r"http[s]?://(?!t\.me)",  # روابط خارجية
    r"@[a-zA-Z0-9_]{5,}",    # منشن مجموعات
    r"t\.me/joinchat",         # دعوات تيليجرام
    r"bit\.ly",
    r"shorturl",
    r"wa\.me",                 # واتساب
    r"\+\d{10,}",              # أرقام هواتف
]

PORN_KEYWORDS = [
    "سكس", "xxx", "porn", "sex", "نيك", "تعري",
    "جنس", "18+", "افلام ساخنة", "بنات عاريات"
]

# ══════════════════════════════════════════════════
#              أنظمة مكافحة الفلود
# ══════════════════════════════════════════════════
flood_tracker = defaultdict(list)   # {user_id: [timestamps]}
FLOOD_LIMIT = 8       # عدد الرسائل
FLOOD_TIME = 10       # في ثواني

def is_flooding(user_id: int) -> bool:
    now = time.time()
    flood_tracker[user_id] = [t for t in flood_tracker[user_id] if now - t < FLOOD_TIME]
    flood_tracker[user_id].append(now)
    return len(flood_tracker[user_id]) >= FLOOD_LIMIT

# ══════════════════════════════════════════════════
#              فحص المحتوى
# ══════════════════════════════════════════════════
def contains_bad_words(text: str, extra_list=None) -> bool:
    text_lower = text.lower()
    words = DEFAULT_BLACKLIST + (extra_list or [])
    return any(word in text_lower for word in words)

def contains_porn(text: str) -> bool:
    text_lower = text.lower()
    return any(word in text_lower for word in PORN_KEYWORDS)

def contains_spam_link(text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in SPAM_PATTERNS)

# ══════════════════════════════════════════════════
#              مساعد: تحقق من الصلاحيات
# ══════════════════════════════════════════════════
async def is_admin(update: Update, user_id: int) -> bool:
    chat_id = str(update.effective_chat.id)
    # مشرف رئيسي
    if user_id == ADMIN_ID:
        return True
    # مشرف مضاف يدوياً
    if chat_id in db.get("admins", {}) and str(user_id) in db["admins"][chat_id]:
        return True
    # مشرف تيليجرام
    try:
        member = await update.effective_chat.get_member(user_id)
        return member.status in ["administrator", "creator"]
    except:
        return False

async def is_creator(update: Update, user_id: int) -> bool:
    try:
        member = await update.effective_chat.get_member(user_id)
        return member.status == "creator"
    except:
        return False

def get_chat_settings(chat_id: str) -> dict:
    if chat_id not in db["settings"]:
        db["settings"][chat_id] = {
            "antiflood": True,
            "antilink": True,
            "antiporn": True,
            "antibadwords": True,
            "antibot": True,
            "welcome": True,
            "max_warnings": 3,
            "mute_duration": 60,   # دقائق
            "log_channel": None
        }
    return db["settings"][chat_id]

def add_warning(chat_id: str, user_id: str) -> int:
    key = f"{chat_id}_{user_id}"
    if key not in db["warnings"]:
        db["warnings"][key] = 0
    db["warnings"][key] += 1
    save_data(db)
    return db["warnings"][key]

def get_warnings(chat_id: str, user_id: str) -> int:
    key = f"{chat_id}_{user_id}"
    return db["warnings"].get(key, 0)

def reset_warnings(chat_id: str, user_id: str):
    key = f"{chat_id}_{user_id}"
    db["warnings"][key] = 0
    save_data(db)

def log_action(action: str, admin: str, target: str, chat: str, reason: str = ""):
    db["logs"].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "admin": admin,
        "target": target,
        "chat": chat,
        "reason": reason
    })
    # احتفظ بآخر 500 سجل فقط
    if len(db["logs"]) > 500:
        db["logs"] = db["logs"][-500:]
    save_data(db)

# ══════════════════════════════════════════════════
#              🎉 رسائل الترحيب والوداع
# ══════════════════════════════════════════════════
async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    settings = get_chat_settings(chat_id)

    for member in update.message.new_chat_members:
        if member.is_bot:
            if settings.get("antibot"):
                try:
                    await context.bot.ban_chat_member(update.effective_chat.id, member.id)
                    await update.message.reply_text("🤖 تم طرد البوت تلقائياً!")
                except:
                    pass
            continue

        if not settings.get("welcome"):
            continue

        custom_welcome = db.get("welcome", {}).get(chat_id)
        if custom_welcome:
            text = custom_welcome.replace("{name}", member.first_name).replace("{count}", str(update.effective_chat.member_count or "?"))
        else:
            text = (
                f"🌟 أهلاً وسهلاً بـ **{member.first_name}** في مجموعتنا!\n\n"
                f"👥 أنت العضو رقم: `{update.effective_chat.member_count or '?'}`\n\n"
                f"📜 **قواعد المجموعة:**\n"
                f"• احترم جميع الأعضاء 🤝\n"
                f"• ممنوع الإعلانات والروابط 🚫\n"
                f"• ممنوع المحتوى المسيء ⛔\n"
                f"• ممنوع السبام والفلود 🔇\n\n"
                f"نتمنى لك وقتاً ممتعاً! 😊"
            )

        keyboard = [[InlineKeyboardButton("📋 قواعد المجموعة", callback_data=f"rules_{chat_id}")]]
        await update.message.reply_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def goodbye_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.left_chat_member:
        member = update.message.left_chat_member
        if not member.is_bot:
            await update.message.reply_text(
                f"👋 وداعاً **{member.first_name}**! نتمنى أن تعود قريباً 🌺",
                parse_mode="Markdown"
            )

# ══════════════════════════════════════════════════
#              🛡️ نظام فحص الرسائل التلقائي
# ══════════════════════════════════════════════════
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    chat = update.effective_chat
    chat_id = str(chat.id)
    user_id = user.id
    text = update.message.text or update.message.caption or ""

    # المشرفون معفيون
    if await is_admin(update, user_id):
        return

    settings = get_chat_settings(chat_id)

    # ── فحص الفلود ──
    if settings.get("antiflood") and is_flooding(user_id):
        await update.message.delete()
        await context.bot.restrict_chat_member(
            chat.id, user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=datetime.now() + timedelta(minutes=5)
        )
        warn_count = add_warning(chat_id, str(user_id))
        await chat.send_message(
            f"🔇 **{user.first_name}** تم كتمك بسبب الفلود لمدة 5 دقائق!\n"
            f"⚠️ إنذار رقم: {warn_count}/{settings['max_warnings']}",
            parse_mode="Markdown"
        )
        log_action("كتم-فلود", "النظام", user.first_name, chat.title or chat_id)
        await check_warnings_limit(context, chat, user, chat_id, settings)
        return

    if text:
        # ── فحص الكلمات المسيئة ──
        extra_bl = db.get("blacklist", {}).get(chat_id, [])
        if settings.get("antibadwords") and contains_bad_words(text, extra_bl):
            await update.message.delete()
            warn_count = add_warning(chat_id, str(user_id))
            await chat.send_message(
                f"🚫 **{user.first_name}** رسالتك تحتوي على كلمات مسيئة وتم حذفها!\n"
                f"⚠️ إنذار رقم: {warn_count}/{settings['max_warnings']}",
                parse_mode="Markdown"
            )
            log_action("حذف-كلمات", "النظام", user.first_name, chat.title or chat_id, "كلمات مسيئة")
            await check_warnings_limit(context, chat, user, chat_id, settings)
            return

        # ── فحص المحتوى الإباحي ──
        if settings.get("antiporn") and contains_porn(text):
            await update.message.delete()
            warn_count = add_warning(chat_id, str(user_id))
            await chat.send_message(
                f"⛔ **{user.first_name}** تم حذف رسالتك بسبب محتوى غير لائق!\n"
                f"⚠️ إنذار رقم: {warn_count}/{settings['max_warnings']}\n"
                f"⚡ تكرار ذلك سيؤدي إلى حظرك!",
                parse_mode="Markdown"
            )
            log_action("حذف-إباحي", "النظام", user.first_name, chat.title or chat_id)
            await check_warnings_limit(context, chat, user, chat_id, settings)
            return

        # ── فحص الروابط والإعلانات ──
        if settings.get("antilink") and contains_spam_link(text):
            await update.message.delete()
            warn_count = add_warning(chat_id, str(user_id))
            await chat.send_message(
                f"🔗 **{user.first_name}** ممنوع إرسال الروابط والإعلانات!\n"
                f"⚠️ إنذار رقم: {warn_count}/{settings['max_warnings']}",
                parse_mode="Markdown"
            )
            log_action("حذف-رابط", "النظام", user.first_name, chat.title or chat_id)
            await check_warnings_limit(context, chat, user, chat_id, settings)
            return

    # ── فحص الملصقات المسيئة ──
    if update.message.sticker:
        pass  # يمكن إضافة فلتر ملصقات لاحقاً

async def check_warnings_limit(context, chat, user, chat_id, settings):
    """فحص هل وصل المستخدم للحد الأقصى من الإنذارات"""
    warns = get_warnings(chat_id, str(user.id))
    max_w = settings.get("max_warnings", 3)
    if warns >= max_w:
        try:
            await context.bot.ban_chat_member(chat.id, user.id)
            reset_warnings(chat_id, str(user.id))
            await chat.send_message(
                f"🔨 **{user.first_name}** تم حظره تلقائياً بسبب تجاوز الحد الأقصى "
                f"من الإنذارات ({max_w} إنذارات)!",
                parse_mode="Markdown"
            )
            log_action("حظر-تلقائي", "النظام", user.first_name, chat.title or str(chat.id))
        except Exception as e:
            logging.error(f"خطأ في الحظر التلقائي: {e}")

# ══════════════════════════════════════════════════
#              📸 فحص الوسائط
# ══════════════════════════════════════════════════
async def check_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص الصور والفيديوهات والمستندات"""
    if not update.effective_user or await is_admin(update, update.effective_user.id):
        return

    user = update.effective_user
    chat = update.effective_chat
    chat_id = str(chat.id)

    # فحص الكابشن
    if update.message.caption:
        await check_message(update, context)

    # فحص إذا كانت صورة بدون وجه (قد تكون مسيئة) - مؤقتاً يتم الاعتماد على الكابشن
    # في الإصدار القادم: دمج AI للكشف عن المحتوى المرئي

# ══════════════════════════════════════════════════
#              ⚡ أوامر المشرفين
# ══════════════════════════════════════════════════

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر الحظر /ban"""
    user_id = update.effective_user.id
    if not await is_admin(update, user_id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("⚠️ رد على رسالة المستخدم أو اكتب: /ban @username")
        return

    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else "لا يوجد سبب"

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(
            f"🔨 **تم الحظر**\n\n"
            f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})\n"
            f"📋 السبب: {reason}\n"
            f"👮 المشرف: {update.effective_user.first_name}",
            parse_mode="Markdown"
        )
        log_action("حظر", update.effective_user.first_name, target.first_name,
                   update.effective_chat.title or str(update.effective_chat.id), reason)
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل الحظر: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر رفع الحظر /unban"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("⚠️ رد على رسالة المستخدم أو اكتب: /unban @username")
        return

    try:
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(
            f"✅ **تم رفع الحظر**\n\n"
            f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})\n"
            f"👮 المشرف: {update.effective_user.first_name}",
            parse_mode="Markdown"
        )
        log_action("رفع حظر", update.effective_user.first_name, target.first_name,
                   update.effective_chat.title or str(update.effective_chat.id))
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل رفع الحظر: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر الكتم /mute"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        await update.message.reply_text("⚠️ رد على رسالة المستخدم أو اكتب: /mute @username [دقائق]")
        return

    # مدة الكتم
    duration = 60  # افتراضي
    if context.args:
        try:
            duration = int(context.args[-1])
        except:
            pass

    until = datetime.now() + timedelta(minutes=duration)

    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await update.message.reply_text(
            f"🔇 **تم الكتم**\n\n"
            f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})\n"
            f"⏱️ المدة: {duration} دقيقة\n"
            f"👮 المشرف: {update.effective_user.first_name}",
            parse_mode="Markdown"
        )
        log_action("كتم", update.effective_user.first_name, target.first_name,
                   update.effective_chat.title or str(update.effective_chat.id), f"{duration} دقيقة")
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل الكتم: {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر رفع الكتم /unmute"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        return

    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await update.message.reply_text(
            f"🔊 **تم رفع الكتم**\n\n"
            f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})\n"
            f"👮 المشرف: {update.effective_user.first_name}",
            parse_mode="Markdown"
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل رفع الكتم: {e}")

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر الطرد /kick"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        return

    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else "لا يوجد سبب"

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(
            f"👢 **تم الطرد**\n\n"
            f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})\n"
            f"📋 السبب: {reason}\n"
            f"👮 المشرف: {update.effective_user.first_name}",
            parse_mode="Markdown"
        )
        log_action("طرد", update.effective_user.first_name, target.first_name,
                   update.effective_chat.title or str(update.effective_chat.id), reason)
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل الطرد: {e}")

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر الإنذار /warn"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        return

    chat_id = str(update.effective_chat.id)
    settings = get_chat_settings(chat_id)
    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else "مخالفة قواعد المجموعة"

    warn_count = add_warning(chat_id, str(target.id))
    max_w = settings.get("max_warnings", 3)

    msg = (
        f"⚠️ **إنذار**\n\n"
        f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})\n"
        f"📋 السبب: {reason}\n"
        f"🔢 الإنذارات: {warn_count}/{max_w}\n"
        f"👮 المشرف: {update.effective_user.first_name}"
    )

    if warn_count >= max_w:
        msg += f"\n\n🔨 **تم الحظر تلقائياً لتجاوز الحد الأقصى!**"
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            reset_warnings(chat_id, str(target.id))
            log_action("حظر-إنذارات", update.effective_user.first_name, target.first_name,
                       update.effective_chat.title or chat_id)
        except:
            pass

    await update.message.reply_text(msg, parse_mode="Markdown")
    log_action("إنذار", update.effective_user.first_name, target.first_name,
               update.effective_chat.title or chat_id, reason)

async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إزالة إنذار /unwarn"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        return

    chat_id = str(update.effective_chat.id)
    key = f"{chat_id}_{target.id}"
    current = db["warnings"].get(key, 0)

    if current > 0:
        db["warnings"][key] = current - 1
        save_data(db)
        await update.message.reply_text(
            f"✅ تم إزالة إنذار من **{target.first_name}**\n"
            f"🔢 الإنذارات الحالية: {current - 1}/{get_chat_settings(chat_id)['max_warnings']}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"ℹ️ **{target.first_name}** ليس لديه إنذارات!")

async def resetwarns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعادة تعيين الإنذارات /resetwarns"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        return

    chat_id = str(update.effective_chat.id)
    reset_warnings(chat_id, str(target.id))
    await update.message.reply_text(
        f"🔄 تم إعادة تعيين إنذارات **{target.first_name}** بالكامل!",
        parse_mode="Markdown"
    )

async def warns_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإنذارات /warns"""
    target = await get_target_user(update, context)
    if not target:
        target = update.effective_user

    chat_id = str(update.effective_chat.id)
    warns = get_warnings(chat_id, str(target.id))
    max_w = get_chat_settings(chat_id).get("max_warnings", 3)

    await update.message.reply_text(
        f"📊 **إنذارات المستخدم**\n\n"
        f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})\n"
        f"⚠️ الإنذارات: {warns}/{max_w}\n"
        f"{'🟢 لا توجد مشاكل' if warns == 0 else '🟡 تحت المراقبة' if warns < max_w else '🔴 على وشك الحظر'}",
        parse_mode="Markdown"
    )

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تثبيت رسالة /pin"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ رد على الرسالة التي تريد تثبيتها!")
        return

    try:
        await context.bot.pin_chat_message(
            update.effective_chat.id,
            update.message.reply_to_message.message_id
        )
        await update.message.reply_text("📌 تم تثبيت الرسالة!")
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل التثبيت: {e}")

async def unpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء تثبيت رسالة /unpin"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    try:
        await context.bot.unpin_all_chat_messages(update.effective_chat.id)
        await update.message.reply_text("📌 تم إلغاء تثبيت جميع الرسائل!")
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف رسالة /del"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except:
            await update.message.reply_text("❌ فشل الحذف!")
    else:
        await update.message.reply_text("⚠️ رد على الرسالة التي تريد حذفها!")

async def promote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ترقية مستخدم /promote"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        return

    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id, target.id,
            can_delete_messages=True,
            can_restrict_members=True,
            can_pin_messages=True,
            can_invite_users=True
        )
        chat_id = str(update.effective_chat.id)
        if chat_id not in db["admins"]:
            db["admins"][chat_id] = []
        db["admins"][chat_id].append(str(target.id))
        save_data(db)

        await update.message.reply_text(
            f"⭐ **تم الترقية**\n\n"
            f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})\n"
            f"✅ أصبح مشرفاً الآن!",
            parse_mode="Markdown"
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل الترقية: {e}")

async def demote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخفيض رتبة /demote"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    target = await get_target_user(update, context)
    if not target:
        return

    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id, target.id,
            can_delete_messages=False,
            can_restrict_members=False,
            can_pin_messages=False
        )
        await update.message.reply_text(
            f"🔽 **تم التخفيض**\n\n"
            f"👤 المستخدم: [{target.first_name}](tg://user?id={target.id})",
            parse_mode="Markdown"
        )
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل: {e}")

# ══════════════════════════════════════════════════
#              ⚙️ إعدادات البوت
# ══════════════════════════════════════════════════

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض وتعديل الإعدادات /settings"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    chat_id = str(update.effective_chat.id)
    s = get_chat_settings(chat_id)

    def status(key):
        return "✅" if s.get(key) else "❌"

    keyboard = [
        [
            InlineKeyboardButton(f"{status('antiflood')} مكافحة الفلود", callback_data=f"toggle_antiflood_{chat_id}"),
            InlineKeyboardButton(f"{status('antilink')} مكافحة الروابط", callback_data=f"toggle_antilink_{chat_id}")
        ],
        [
            InlineKeyboardButton(f"{status('antiporn')} مكافحة الإباحي", callback_data=f"toggle_antiporn_{chat_id}"),
            InlineKeyboardButton(f"{status('antibadwords')} فلتر الكلمات", callback_data=f"toggle_antibadwords_{chat_id}")
        ],
        [
            InlineKeyboardButton(f"{status('antibot')} مكافحة البوتات", callback_data=f"toggle_antibot_{chat_id}"),
            InlineKeyboardButton(f"{status('welcome')} رسائل الترحيب", callback_data=f"toggle_welcome_{chat_id}")
        ],
        [InlineKeyboardButton("🔢 تعديل الحد الأقصى للإنذارات", callback_data=f"set_maxwarn_{chat_id}")]
    ]

    await update.message.reply_text(
        f"⚙️ **إعدادات حماية المجموعة**\n\n"
        f"🔢 الحد الأقصى للإنذارات: {s['max_warnings']}\n"
        f"⏱️ مدة الكتم الافتراضية: {s['mute_duration']} دقيقة\n\n"
        f"اضغط على أي خيار لتفعيله أو إيقافه:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل الإعدادات عبر الأزرار"""
    query = update.callback_query
    await query.answer()

    if not await is_admin(update, query.from_user.id):
        await query.answer("❌ للمشرفين فقط!", show_alert=True)
        return

    data = query.data
    if data.startswith("toggle_"):
        parts = data.split("_", 2)
        setting = parts[1]
        chat_id = parts[2]

        settings = get_chat_settings(chat_id)
        settings[setting] = not settings.get(setting, True)
        db["settings"][chat_id] = settings
        save_data(db)

        await query.answer(f"{'✅ تم التفعيل' if settings[setting] else '❌ تم الإيقاف'}!")
        # تحديث الرسالة
        await settings_command(update, context)

    elif data.startswith("rules_"):
        chat_id = data.split("_")[1]
        await query.message.reply_text(
            "📋 **قواعد المجموعة:**\n\n"
            "1️⃣ احترم جميع الأعضاء\n"
            "2️⃣ ممنوع السبام والإعلانات\n"
            "3️⃣ ممنوع المحتوى المسيء\n"
            "4️⃣ ممنوع الروابط الخارجية\n"
            "5️⃣ استخدم لغة محترمة\n\n"
            "⚠️ مخالفة القواعد = إنذار، والإنذارات تؤدي للحظر!",
            parse_mode="Markdown"
        )

async def setwelcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخصيص رسالة الترحيب /setwelcome"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    if not context.args:
        await update.message.reply_text(
            "📝 **طريقة الاستخدام:**\n"
            "`/setwelcome رسالتك هنا`\n\n"
            "**المتغيرات المتاحة:**\n"
            "• `{name}` - اسم العضو الجديد\n"
            "• `{count}` - عدد الأعضاء",
            parse_mode="Markdown"
        )
        return

    chat_id = str(update.effective_chat.id)
    welcome_msg = " ".join(context.args)

    if "welcome" not in db:
        db["welcome"] = {}
    db["welcome"][chat_id] = welcome_msg
    save_data(db)

    await update.message.reply_text(
        f"✅ **تم تعيين رسالة الترحيب بنجاح!**\n\n"
        f"**معاينة:**\n{welcome_msg.replace('{name}', update.effective_user.first_name).replace('{count}', '100')}",
        parse_mode="Markdown"
    )

async def addblacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة كلمة للقائمة السوداء /addbl"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ اكتب: `/addbl كلمة`", parse_mode="Markdown")
        return

    chat_id = str(update.effective_chat.id)
    word = " ".join(context.args).lower()

    if "blacklist" not in db:
        db["blacklist"] = {}
    if chat_id not in db["blacklist"]:
        db["blacklist"][chat_id] = []

    if word not in db["blacklist"][chat_id]:
        db["blacklist"][chat_id].append(word)
        save_data(db)
        await update.message.reply_text(f"✅ تم إضافة `{word}` للقائمة السوداء!", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ هذه الكلمة موجودة بالفعل!")

async def rmblacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف كلمة من القائمة السوداء /rmbl"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    if not context.args:
        await update.message.reply_text("⚠️ اكتب: `/rmbl كلمة`", parse_mode="Markdown")
        return

    chat_id = str(update.effective_chat.id)
    word = " ".join(context.args).lower()

    if db.get("blacklist", {}).get(chat_id) and word in db["blacklist"][chat_id]:
        db["blacklist"][chat_id].remove(word)
        save_data(db)
        await update.message.reply_text(f"✅ تم حذف `{word}` من القائمة السوداء!", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ هذه الكلمة غير موجودة!")

async def blacklist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض القائمة السوداء /blacklist"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    chat_id = str(update.effective_chat.id)
    words = db.get("blacklist", {}).get(chat_id, [])

    if not words:
        await update.message.reply_text("📋 القائمة السوداء فارغة!")
        return

    text = "🚫 **الكلمات المحظورة:**\n\n"
    text += "\n".join([f"• `{w}`" for w in words])
    await update.message.reply_text(text, parse_mode="Markdown")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض سجل المخالفات /logs"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ هذا الأمر للمشرفين فقط!")
        return

    logs = db.get("logs", [])[-20:]  # آخر 20 سجل

    if not logs:
        await update.message.reply_text("📋 لا يوجد سجلات بعد!")
        return

    text = "📜 **آخر 20 إجراء:**\n\n"
    for log in reversed(logs):
        text += (
            f"🕐 {log['time']}\n"
            f"⚡ {log['action']} | 👤 {log['target']}\n"
            f"👮 {log['admin']}\n"
            f"{'📋 ' + log['reason'] if log.get('reason') else ''}\n\n"
        )

    if len(text) > 4000:
        text = text[:4000] + "\n...(مقتطع)"

    await update.message.reply_text(text, parse_mode="Markdown")

async def userinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات مستخدم /info"""
    target = await get_target_user(update, context)
    if not target:
        target = update.effective_user

    chat_id = str(update.effective_chat.id)

    try:
        member = await update.effective_chat.get_member(target.id)
        status_map = {
            "creator": "👑 مالك",
            "administrator": "⭐ مشرف",
            "member": "👤 عضو",
            "restricted": "🔇 مقيد",
            "left": "🚪 غادر",
            "banned": "🔨 محظور"
        }
        status = status_map.get(member.status, "غير معروف")
    except:
        status = "غير معروف"

    warns = get_warnings(chat_id, str(target.id))
    username = f"@{target.username}" if target.username else "لا يوجد"

    await update.message.reply_text(
        f"👤 **معلومات المستخدم**\n\n"
        f"🆔 ID: `{target.id}`\n"
        f"📛 الاسم: [{target.first_name}](tg://user?id={target.id})\n"
        f"📧 اليوزر: {username}\n"
        f"🎭 الحالة: {status}\n"
        f"⚠️ الإنذارات: {warns}/{get_chat_settings(chat_id)['max_warnings']}\n"
        f"🤖 بوت: {'نعم' if target.is_bot else 'لا'}",
        parse_mode="Markdown"
    )

async def chatinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معلومات المجموعة /chatinfo"""
    chat = update.effective_chat
    chat_id = str(chat.id)
    settings = get_chat_settings(chat_id)

    try:
        count = await context.bot.get_chat_member_count(chat.id)
    except:
        count = "غير متاح"

    await update.message.reply_text(
        f"📊 **معلومات المجموعة**\n\n"
        f"📛 الاسم: {chat.title}\n"
        f"🆔 ID: `{chat.id}`\n"
        f"👥 الأعضاء: {count}\n"
        f"🔢 الإنذارات القصوى: {settings['max_warnings']}\n\n"
        f"**حالة الحماية:**\n"
        f"{'✅' if settings.get('antiflood') else '❌'} مكافحة الفلود\n"
        f"{'✅' if settings.get('antilink') else '❌'} مكافحة الروابط\n"
        f"{'✅' if settings.get('antiporn') else '❌'} مكافحة الإباحي\n"
        f"{'✅' if settings.get('antibadwords') else '❌'} فلتر الكلمات\n"
        f"{'✅' if settings.get('antibot') else '❌'} مكافحة البوتات",
        parse_mode="Markdown"
    )

# ══════════════════════════════════════════════════
#              🆘 أوامر المساعدة العامة
# ══════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البداية /start"""
    keyboard = [
        [
            InlineKeyboardButton("📋 الأوامر", callback_data="show_commands"),
            InlineKeyboardButton("⚙️ الإعدادات", callback_data="show_settings")
        ],
        [InlineKeyboardButton("👨‍💻 المطور", url="https://t.me/YourUsername")]
    ]

    await update.message.reply_text(
        f"🛡️ **مرحباً! أنا بوت الحماية المتكامل**\n\n"
        f"أنا هنا لحماية مجموعتك من:\n"
        f"• 🔇 الفلود والسبام\n"
        f"• 🔗 الروابط والإعلانات\n"
        f"• 🚫 الكلمات المسيئة\n"
        f"• ⛔ المحتوى الإباحي\n"
        f"• 🤖 البوتات الغير مرغوب فيها\n\n"
        f"**أضفني للمجموعة كمشرف وأعطني صلاحيات لأبدأ العمل!**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر المساعدة /help"""
    text = (
        "📚 **قائمة الأوامر الكاملة**\n\n"
        "━━━━━━━ 🛡️ الحماية ━━━━━━━\n"
        "⚙️ /settings - إعدادات الحماية\n"
        "📋 /blacklist - عرض الكلمات المحظورة\n"
        "➕ /addbl [كلمة] - إضافة كلمة محظورة\n"
        "➖ /rmbl [كلمة] - حذف كلمة محظورة\n\n"
        "━━━━━━━ 👮 إدارة الأعضاء ━━━━━━━\n"
        "🔨 /ban - حظر مستخدم\n"
        "✅ /unban - رفع الحظر\n"
        "🔇 /mute [دقائق] - كتم مستخدم\n"
        "🔊 /unmute - رفع الكتم\n"
        "👢 /kick - طرد مستخدم\n"
        "⚠️ /warn - إعطاء إنذار\n"
        "↩️ /unwarn - إزالة إنذار\n"
        "🔄 /resetwarns - إعادة تعيين الإنذارات\n"
        "📊 /warns - عرض إنذارات مستخدم\n\n"
        "━━━━━━━ 📌 أدوات ━━━━━━━\n"
        "📌 /pin - تثبيت رسالة\n"
        "📌 /unpin - إلغاء التثبيت\n"
        "🗑️ /del - حذف رسالة\n"
        "⭐ /promote - ترقية مشرف\n"
        "🔽 /demote - تخفيض رتبة\n\n"
        "━━━━━━━ 📊 معلومات ━━━━━━━\n"
        "👤 /info - معلومات مستخدم\n"
        "📊 /chatinfo - معلومات المجموعة\n"
        "📜 /logs - سجل المخالفات\n"
        "💬 /setwelcome - تخصيص رسالة الترحيب\n\n"
        "_📝 ملاحظة: معظم الأوامر تعمل بالرد على رسالة المستخدم_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ══════════════════════════════════════════════════
#              مساعد: الحصول على المستخدم المستهدف
# ══════════════════════════════════════════════════
async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على المستخدم المستهدف من الرد أو المنشن"""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user

    if context.args:
        username = context.args[0].replace("@", "")
        try:
            user = await context.bot.get_chat(username)
            return user
        except:
            await update.message.reply_text("❌ لم يتم العثور على المستخدم!")
            return None

    return None

# ══════════════════════════════════════════════════
#                   التشغيل الرئيسي
# ══════════════════════════════════════════════════
def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    app = Application.builder().token(TOKEN).build()

    # ── أوامر عامة ──
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # ── أوامر المشرفين ──
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(CommandHandler("kick", kick_command))
    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("unwarn", unwarn_command))
    app.add_handler(CommandHandler("resetwarns", resetwarns_command))
    app.add_handler(CommandHandler("warns", warns_command))
    app.add_handler(CommandHandler("pin", pin_command))
    app.add_handler(CommandHandler("unpin", unpin_command))
    app.add_handler(CommandHandler("del", del_command))
    app.add_handler(CommandHandler("promote", promote_command))
    app.add_handler(CommandHandler("demote", demote_command))

    # ── إعدادات ──
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("setwelcome", setwelcome_command))
    app.add_handler(CommandHandler("addbl", addblacklist_command))
    app.add_handler(CommandHandler("rmbl", rmblacklist_command))
    app.add_handler(CommandHandler("blacklist", blacklist_command))

    # ── معلومات ──
    app.add_handler(CommandHandler("info", userinfo_command))
    app.add_handler(CommandHandler("chatinfo", chatinfo_command))
    app.add_handler(CommandHandler("logs", logs_command))

    # ── مراقبة الرسائل ──
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, check_media))

    # ── الأعضاء الجدد والمغادرون ──
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_member))

    # ── الأزرار ──
    app.add_handler(CallbackQueryHandler(toggle_setting))

    print("🛡️ بوت الحماية يعمل الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
