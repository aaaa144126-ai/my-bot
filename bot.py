"""
╔══════════════════════════════════════════════════════════════╗
║        🛡️ بوت الحماية المتكامل - الإصدار العربي 4.0         ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, json, logging, re, time, random, urllib.request, urllib.parse, asyncio
from datetime import datetime, timedelta, date
from collections import defaultdict
from threading import Lock

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                           CallbackQueryHandler, filters, ContextTypes)
from telegram.error import TelegramError

# ══════════════════════════════════════════════════
#                   الإعدادات
# ══════════════════════════════════════════════════
TOKEN           = os.getenv("BOT_TOKEN", "8766908791:AAEPlolaB1khYPzqtb1lUSJKzhdQKIbp-RU")
DEVELOPER_ID    = int(os.getenv("ADMIN_ID", "7821129203"))
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6KpXztomqDLJUFsZqqQo1goZzjg3NQZtMDB002p06RKRg")

DATA_FILE = "data.json"
db_lock   = Lock()

def load_data():
    default = {
        "warnings": {}, "settings": {}, "welcome": {}, "logs": [],
        "blacklist": {}, "ranks": {}, "whispers": {}, "shortcuts": {},
        "scheduled_groups": [],
        "muted_users": {},
        "banned_users": {},
    }
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in default.items():
                if k not in data:
                    data[k] = v
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return default

def save_data(data):
    with db_lock:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)

db = load_data()

# ══════════════════════════════════════════════════
#              نظام الرتب
# ══════════════════════════════════════════════════
RANKS = {
    "مطور":         {"emoji": "💻", "level": 10, "color": "🔴",
                     "perms": ["ban","unban","mute","unmute","kick","warn","delete","pin",
                               "promote","demote","settings","stats","broadcast","lockdown",
                               "rank_assign","whitelist","emergency","backup","all"]},
    "مالك":         {"emoji": "👑", "level": 9,  "color": "🟡",
                     "perms": ["ban","unban","mute","unmute","kick","warn","delete","pin",
                               "promote","demote","settings","broadcast","lockdown",
                               "rank_assign","whitelist","emergency"]},
    "مدير_عام":     {"emoji": "🔱", "level": 8,  "color": "🔵",
                     "perms": ["ban","unban","mute","unmute","kick","warn","delete","pin",
                               "promote","demote","settings","lockdown","rank_assign","whitelist"]},
    "ادمن":         {"emoji": "🛡️", "level": 7,  "color": "🟣",
                     "perms": ["ban","unban","mute","unmute","kick","warn","delete","pin",
                               "promote","demote","settings"]},
    "مشرف_كبير":   {"emoji": "⚜️", "level": 6,  "color": "🟠",
                     "perms": ["ban","unban","mute","unmute","kick","warn","delete","pin"]},
    "مشرف":         {"emoji": "⭐", "level": 5,  "color": "🟢",
                     "perms": ["mute","unmute","kick","warn","delete"]},
    "مساعد":        {"emoji": "🔰", "level": 4,  "color": "🩵",
                     "perms": ["warn","delete"]},
    "موثوق":        {"emoji": "✅", "level": 3,  "color": "🟤",
                     "perms": ["report"]},
    "عضو":          {"emoji": "👤", "level": 2,  "color": "⚪",
                     "perms": []},
    "مراقب":        {"emoji": "👁️", "level": 1,  "color": "⚫",
                     "perms": []},
}

RANK_NAMES_LIST = ["مراقب","عضو","موثوق","مساعد","مشرف","مشرف_كبير","ادمن","مدير_عام","مالك"]

def has_perm(chat_id, user_id, perm: str) -> bool:
    """تحقق لو المستخدم عنده صلاحية معينة"""
    if user_id == DEVELOPER_ID:
        return True
    rank  = get_user_rank(chat_id, user_id)
    perms = RANKS.get(rank, RANKS["عضو"]).get("perms", [])
    return perm in perms or "all" in perms


def get_user_rank(chat_id, user_id):
    if user_id == DEVELOPER_ID:
        return "مطور"
    return db.get("ranks", {}).get(str(chat_id), {}).get(str(user_id), "عضو")

def set_user_rank(chat_id, user_id, rank):
    db.setdefault("ranks", {}).setdefault(str(chat_id), {})[str(user_id)] = rank
    save_data(db)

def get_rank_level(chat_id, user_id):
    return RANKS.get(get_user_rank(chat_id, user_id), RANKS["عضو"])["level"]

async def is_admin(update, user_id):
    if user_id == DEVELOPER_ID:
        return True
    chat_id = update.effective_chat.id
    if get_rank_level(chat_id, user_id) >= 5:
        return True
    try:
        m = await update.effective_chat.get_member(user_id)
        return m.status in ["administrator", "creator"]
    except:
        return False

async def check_perm(update, perm: str) -> bool:
    """تحقق من صلاحية وأرسل رسالة خطأ لو مفيهاش"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if has_perm(chat_id, user_id, perm):
        return True
    rank      = get_user_rank(chat_id, user_id)
    rank_info = RANKS.get(rank, RANKS["عضو"])
    emoji = rank_info["emoji"]
    msg = f"\U0001f6ab صلاحية مرفوضة\n\n{emoji} رتبتك: {rank}\nلا تملك صلاحية: {perm}\n\nتواصل مع مشرف اعلى رتبة"
    await update.message.reply_text(msg)
    return False

# ══════════════════════════════════════════════════
#              الحماية
# ══════════════════════════════════════════════════
DEFAULT_BLACKLIST = ["وسخ","كلب","حمار","غبي","احا","لعنة","زفت","منيك","شرموط","عاهر"]
SPAM_PATTERNS     = [r"http[s]?://(?!t\.me)", r"t\.me/joinchat", r"bit\.ly", r"wa\.me", r"\+\d{10,}"]
PORN_KEYWORDS     = ["سكس","xxx","porn","sex","نيك","تعري","جنس","18+","بنات عاريات"]

flood_tracker = defaultdict(list)
raid_tracker  = defaultdict(list)
FLOOD_LIMIT, FLOOD_TIME = 8, 10
RAID_LIMIT,  RAID_TIME  = 5, 60

def is_flooding(user_id):
    now = time.time()
    flood_tracker[user_id] = [t for t in flood_tracker[user_id] if now - t < FLOOD_TIME]
    flood_tracker[user_id].append(now)
    return len(flood_tracker[user_id]) >= FLOOD_LIMIT

def is_raid(chat_id):
    now = time.time()
    raid_tracker[chat_id] = [t for t in raid_tracker[chat_id] if now - t < RAID_TIME]
    raid_tracker[chat_id].append(now)
    return len(raid_tracker[chat_id]) >= RAID_LIMIT

def contains_bad_words(text, extra=None):
    if extra is None: extra = []
    t = text.lower()
    return any(w in t for w in DEFAULT_BLACKLIST + extra)

def contains_porn(text):
    return any(w in text.lower() for w in PORN_KEYWORDS)

def contains_spam(text):
    return any(re.search(p, text, re.IGNORECASE) for p in SPAM_PATTERNS)

def get_settings(chat_id):
    cid = str(chat_id)
    if cid not in db["settings"]:
        db["settings"][cid] = {
            "antiflood": True, "antilink": True, "antiporn": True,
            "antibadwords": True, "antibot": True, "welcome": True,
            "max_warnings": 3, "mute_duration": 60, "lockdown": False,
        }
        save_data(db)
    return db["settings"][cid]

def add_warning(chat_id, user_id):
    key = f"{chat_id}_{user_id}"
    db["warnings"][key] = db["warnings"].get(key, 0) + 1
    save_data(db)
    return db["warnings"][key]

def get_warnings(chat_id, user_id):
    return db["warnings"].get(f"{chat_id}_{user_id}", 0)

def reset_warnings(chat_id, user_id):
    db["warnings"][f"{chat_id}_{user_id}"] = 0
    save_data(db)

def log_action(action, admin, target, chat, reason=""):
    db["logs"].append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action, "admin": admin, "target": target,
        "chat": chat, "reason": reason
    })
    if len(db["logs"]) > 500:
        db["logs"] = db["logs"][-500:]
    save_data(db)

async def get_target(update, context):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    if context.args:
        try:
            return await context.bot.get_chat(context.args[0].replace("@", ""))
        except:
            await update.message.reply_text("لم يتم العثور على المستخدم!")
    return None

async def check_max_warns(context, chat, user, chat_id, settings):
    if get_warnings(str(chat_id), str(user.id)) >= settings.get("max_warnings", 3):
        try:
            await context.bot.ban_chat_member(chat.id, user.id)
            reset_warnings(str(chat_id), str(user.id))
            await chat.send_message(
                f"تم حظر **{user.first_name}** تلقائياً بسبب تجاوز الإنذارات!",
                parse_mode="Markdown")
        except:
            pass

# ══════════════════════════════════════════════════
#         🤫 نظام الهمسة
# ══════════════════════════════════════════════════
whisper_states = {}  # user_id -> pending state

async def cmd_همسة(update, context):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("استخدم هذا الأمر في المجموعة بالرد على رسالة شخص!")
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("رد على رسالة الشخص الذي تريد مهامسته أولاً!")
        return
    target = update.message.reply_to_message.from_user
    if target.id == user.id:
        await update.message.reply_text("لا يمكنك مهامسة نفسك!")
        return
    if target.is_bot:
        await update.message.reply_text("لا يمكنك مهامسة بوت!")
        return

    whisper_states[user.id] = {
        "step": "waiting_text",
        "target_id":    target.id,
        "target_name":  target.first_name,
        "chat_id":      chat.id,
        "chat_title":   chat.title or "المجموعة"
    }

    try:
        await context.bot.send_message(
            user.id,
            f"🤫 **الهمسة**\n\nستُرسل همستك إلى **{target.first_name}** في {chat.title}\n\n📝 اكتب نص همستك الآن:",
            parse_mode="Markdown"
        )
        try:
            await update.message.delete()
        except:
            pass
        await update.message.reply_text(
            f"📩 {user.first_name} يريد مهامستك يا **{target.first_name}**!\n_تفقد محادثتك مع البوت_",
            parse_mode="Markdown"
        )
    except TelegramError:
        del whisper_states[user.id]
        keyboard = [[InlineKeyboardButton("ابدأ محادثة مع البوت", url=f"https://t.me/{context.bot.username}")]]
        await update.message.reply_text(
            f"{user.first_name}، ابدأ محادثة مع البوت أولاً ثم كرر الأمر!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_whisper_input(update, context):
    user = update.effective_user
    if user.id not in whisper_states:
        return False
    state = whisper_states[user.id]
    if state["step"] != "waiting_text":
        return False
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("الرسالة فارغة! اكتب نص الهمسة:")
        return True

    whisper_id = f"w_{user.id}_{int(time.time())}"
    db["whispers"][whisper_id] = {
        "from_id":   user.id,
        "from_name": user.first_name,
        "to_id":     state["target_id"],
        "to_name":   state["target_name"],
        "text":      text,
        "chat_id":   state["chat_id"],
        "failed":    [],
        "created":   time.time()
    }
    # تنظيف الهمسات القديمة (أكثر من 7 أيام)
    week_ago = time.time() - 7 * 86400
    old_keys = [k for k, v in db["whispers"].items() if v.get("created", 0) < week_ago]
    for k in old_keys:
        del db["whispers"][k]
    save_data(db)
    del whisper_states[user.id]

    await update.message.reply_text(
        f"✅ **تم إرسال الهمسة!**\n\nإلى: **{state['target_name']}**\nلا يمكن لأحد سواه قراءتها 🔒",
        parse_mode="Markdown"
    )

    keyboard = [[InlineKeyboardButton("🤫 اقرأ الهمسة", callback_data=f"whisper_read_{whisper_id}")]]
    try:
        await context.bot.send_message(
            state["chat_id"],
            f"🤫 **همسة جديدة!**\n\nمن **{user.first_name}** إلى **{state['target_name']}**\nهي لعينيه فقط 🔒",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        pass
    try:
        await context.bot.send_message(
            state["target_id"],
            f"🤫 **وصلتك همسة!**\n\nمن **{user.first_name}** في {state['chat_title']}\n\n👆 اضغط لقراءتها:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        pass
    return True

async def handle_whisper_read(query, whisper_id):
    user    = query.from_user
    whisper = db["whispers"].get(whisper_id)
    if not whisper:
        await query.answer("الهمسة غير موجودة!", show_alert=True)
        return

    if user.id == whisper["to_id"]:
        try:
            await query.bot.send_message(
                user.id,
                f"🤫 **همستك الخاصة**\n\nمن **{whisper['from_name']}**:\n\n_{whisper['text']}_",
                parse_mode="Markdown"
            )
            await query.answer("✅ تم إرسال الهمسة على خاصك!", show_alert=True)
        except:
            await query.answer("ابدأ محادثة مع البوت أولاً لقراءة الهمسة!", show_alert=True)
        return

    if user.id == whisper["from_id"]:
        failed = whisper["failed"]
        msg = "لم يحاول أحد فتحها بعد." if not failed else "حاول فتحها: " + "، ".join(failed)
        await query.answer(msg, show_alert=True)
        return

    name = user.first_name
    if name not in whisper["failed"]:
        whisper["failed"].append(name)
        save_data(db)
    await query.answer(
        f"هذه الهمسة ليست لك!\nهي لـ {whisper['to_name']} فقط 🔒",
        show_alert=True
    )
    try:
        await query.bot.send_message(
            whisper["from_id"],
            f"👀 **{name}** حاول قراءة همستك لـ {whisper['to_name']} وفشل 🔒",
            parse_mode="Markdown"
        )
    except:
        pass

# ══════════════════════════════════════════════════
#         ⚡ نظام الاختصارات
# ══════════════════════════════════════════════════
SHORTCUT_ACTIONS = {"حظر":"ban","كتم":"mute","طرد":"kick","انذار":"warn","تحذير":"warn"}

async def cmd_اختصار(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    if len(context.args) < 2:
        actions_list = "\n".join([f"• `{k}`" for k in SHORTCUT_ACTIONS])
        await update.message.reply_text(
            f"📝 **إضافة اختصار:**\n`/اختصار [كلمة] [الأكشن]`\n\n**الأكشنات:**\n{actions_list}\n\n**مثال:** `/اختصار مم حظر`",
            parse_mode="Markdown"); return
    keyword = context.args[0].lower()
    action  = context.args[1]
    if action not in SHORTCUT_ACTIONS:
        await update.message.reply_text(f"أكشن غير معروف! المتاح: {', '.join(SHORTCUT_ACTIONS.keys())}"); return
    chat_id = str(update.effective_chat.id)
    db.setdefault("shortcuts", {}).setdefault(chat_id, {})[keyword] = action
    save_data(db)
    await update.message.reply_text(
        f"✅ **تم إضافة الاختصار**\n🔤 الكلمة: `{keyword}`\n⚡ الأكشن: **{action}**",
        parse_mode="Markdown")

async def cmd_الاختصارات(update, context):
    chat_id   = str(update.effective_chat.id)
    shortcuts = db.get("shortcuts", {}).get(chat_id, {})
    if not shortcuts:
        await update.message.reply_text("لا يوجد اختصارات بعد! استخدم `/اختصار`", parse_mode="Markdown"); return
    text = "⚡ **اختصارات المجموعة:**\n\n" + "\n".join([f"• `{k}` ← **{v}**" for k, v in shortcuts.items()])
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_حذف_اختصار(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text("`/حذف_اختصار [كلمة]`", parse_mode="Markdown"); return
    chat_id   = str(update.effective_chat.id)
    keyword   = context.args[0].lower()
    shortcuts = db.get("shortcuts", {}).get(chat_id, {})
    if keyword in shortcuts:
        del shortcuts[keyword]; save_data(db)
        await update.message.reply_text(f"✅ تم حذف اختصار `{keyword}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("الاختصار غير موجود!")

async def handle_shortcut(update, context):
    if not update.message or not update.message.reply_to_message: return False
    user = update.effective_user
    chat = update.effective_chat
    text = (update.message.text or "").strip().lower()
    if not text: return False
    chat_id   = str(chat.id)
    shortcuts = db.get("shortcuts", {}).get(chat_id, {})
    if text not in shortcuts: return False
    if not await is_admin(update, user.id): return False

    action = shortcuts[text]
    target = update.message.reply_to_message.from_user
    if target.id == DEVELOPER_ID:
        await update.message.reply_text("لا يمكن تطبيق اختصار على المطور!"); return True

    try:
        if action == "ban":
            await context.bot.ban_chat_member(chat.id, target.id)
            await update.message.reply_text(f"🔨 تم حظر **{target.first_name}** عبر `{text}`", parse_mode="Markdown")
            log_action("حظر(اختصار)", user.first_name, target.first_name, chat.title or "", text)
        elif action == "mute":
            dur = get_settings(chat_id).get("mute_duration", 60)
            await context.bot.restrict_chat_member(
                chat.id, target.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(minutes=dur))
            await update.message.reply_text(f"🔇 تم كتم **{target.first_name}** ({dur} دقيقة) عبر `{text}`", parse_mode="Markdown")
            log_action("كتم(اختصار)", user.first_name, target.first_name, chat.title or "", text)
        elif action == "kick":
            await context.bot.ban_chat_member(chat.id, target.id)
            await context.bot.unban_chat_member(chat.id, target.id)
            await update.message.reply_text(f"👢 تم طرد **{target.first_name}** عبر `{text}`", parse_mode="Markdown")
            log_action("طرد(اختصار)", user.first_name, target.first_name, chat.title or "", text)
        elif action == "warn":
            s  = get_settings(chat_id)
            wc = add_warning(chat_id, str(target.id))
            mw = s.get("max_warnings", 3)
            await update.message.reply_text(f"⚠️ إنذار لـ **{target.first_name}** عبر `{text}` — {wc}/{mw}", parse_mode="Markdown")
            if wc >= mw:
                await context.bot.ban_chat_member(chat.id, target.id)
                reset_warnings(chat_id, str(target.id))
                await chat.send_message(f"🔨 تم حظر **{target.first_name}** تلقائياً!", parse_mode="Markdown")
            log_action("إنذار(اختصار)", user.first_name, target.first_name, chat.title or "", text)
    except TelegramError as e:
        await update.message.reply_text(f"فشل: {e}")
    return True

# ══════════════════════════════════════════════════
#         🤖 الذكاء الاصطناعي
# ══════════════════════════════════════════════════
ai_rate_limit = defaultdict(list)
AI_RATE_PER_MINUTE = 5

def can_use_ai(user_id):
    now = time.time()
    ai_rate_limit[user_id] = [t for t in ai_rate_limit[user_id] if now - t < 60]
    if len(ai_rate_limit[user_id]) >= AI_RATE_PER_MINUTE:
        return False
    ai_rate_limit[user_id].append(now)
    return True

async def ask_ai(question: str) -> str:
    if not GEMINI_KEY:
        return None
    try:
        payload = json.dumps({
            "contents": [{
                "parts": [{
                    "text": (
                        "أنت مساعد ذكي في بوت تيليجرام عربي. "
                        "أجب بشكل مختصر ومفيد باللغة العربية. "
                        "الردود لا تتجاوز 3-4 جمل.\n\n"
                        + question
                    )
                }]
            }],
            "generationConfig": {
                "maxOutputTokens": 500,
                "temperature": 0.7
            }
        }).encode()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return None

# ══════════════════════════════════════════════════
#         🛡️ Anti-Raid
# ══════════════════════════════════════════════════
async def activate_lockdown(context, chat_id: int, duration_minutes: int):
    settings = get_settings(chat_id)
    settings["lockdown"] = True
    save_data(db)
    try:
        await context.bot.set_chat_permissions(
            chat_id,
            ChatPermissions(can_send_messages=False, can_send_media_messages=False, can_send_other_messages=False)
        )
        await context.bot.send_message(
            chat_id,
            f"🚨 **تحذير: تم اكتشاف هجوم جماعي!**\n\n🔒 تم إغلاق المجموعة مؤقتاً لـ {duration_minutes} دقيقة\nسيتم رفع الإغلاق تلقائياً.",
            parse_mode="Markdown"
        )
        await asyncio.sleep(duration_minutes * 60)
        await context.bot.set_chat_permissions(
            chat_id,
            ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                            can_send_other_messages=True, can_add_web_page_previews=True)
        )
        settings["lockdown"] = False
        save_data(db)
        await context.bot.send_message(chat_id, "✅ **تم رفع إغلاق المجموعة تلقائياً.**", parse_mode="Markdown")
    except:
        pass

async def cmd_اغلاق(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    duration = 30
    if context.args:
        try: duration = int(context.args[0])
        except: pass
    await update.message.reply_text(f"🔒 جاري إغلاق المجموعة لـ {duration} دقيقة...")
    asyncio.create_task(activate_lockdown(context, update.effective_chat.id, duration))

async def cmd_رفع_اغلاق(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    try:
        await context.bot.set_chat_permissions(
            update.effective_chat.id,
            ChatPermissions(can_send_messages=True, can_send_media_messages=True,
                            can_send_other_messages=True, can_add_web_page_previews=True)
        )
        get_settings(str(update.effective_chat.id))["lockdown"] = False
        save_data(db)
        await update.message.reply_text("✅ تم رفع الإغلاق!")
    except TelegramError as e:
        await update.message.reply_text(f"فشل: {e}")

# ══════════════════════════════════════════════════
#         📅 المهام المجدولة
# ══════════════════════════════════════════════════
AZKAR_SABAH = [
    "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ، لاَ إِلَهَ إِلاَّ اللَّهُ وَحْدَهُ لاَ شَرِيكَ لَهُ",
    "اللَّهُمَّ بِكَ أَصْبَحْنَا، وَبِكَ أَمْسَيْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ وَإِلَيْكَ النُّشُورُ",
    "اللَّهُمَّ أَنْتَ رَبِّي لاَ إِلَهَ إِلاَّ أَنْتَ، خَلَقْتَنِي وَأَنَا عَبْدُكَ",
    "بِسْمِ اللَّهِ الَّذِي لاَ يَضُرُّ مَعَ اسْمِهِ شَيْءٌ فِي الأَرْضِ وَلاَ فِي السَّمَاءِ ×3",
    "رَضِيتُ بِاللَّهِ رَبًّا، وَبِالإِسْلاَمِ دِيناً، وَبِمُحَمَّدٍ صلى الله عليه وسلم نَبِيًّا ×3",
    "حَسْبِيَ اللَّهُ لاَ إِلَهَ إِلاَّ هُوَ عَلَيْهِ تَوَكَّلْتُ وَهُوَ رَبُّ الْعَرْشِ الْعَظِيمِ ×7",
    "سُبْحَانَ اللهِ وَبِحَمْدِهِ ×100",
]
AZKAR_MASA = [
    "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ، لاَ إِلَهَ إِلاَّ اللَّهُ وَحْدَهُ لاَ شَرِيكَ لَهُ",
    "اللَّهُمَّ بِكَ أَمْسَيْنَا، وَبِكَ أَصْبَحْنَا، وَبِكَ نَحْيَا، وَبِكَ نَمُوتُ وَإِلَيْكَ الْمَصِيرُ",
    "أَعُوذُ بِكَلِمَاتِ اللَّهِ التَّامَّاتِ مِنْ شَرِّ مَا خَلَقَ ×3",
    "حَسْبِيَ اللَّهُ لاَ إِلَهَ إِلاَّ هُوَ عَلَيْهِ تَوَكَّلْتُ وَهُوَ رَبُّ الْعَرْشِ الْعَظِيمِ ×7",
]
AHADITH = [
    "إنما الأعمال بالنيات، وإنما لكل امرئ ما نوى - متفق عليه",
    "الدين النصيحة - رواه مسلم",
    "من كان يؤمن بالله واليوم الآخر فليقل خيرا أو ليصمت - متفق عليه",
    "لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه - متفق عليه",
    "المسلم من سلم المسلمون من لسانه ويده - متفق عليه",
    "خير الناس أنفعهم للناس - رواه الطبراني",
    "تبسمك في وجه أخيك صدقة - رواه الترمذي",
    "اتق الله حيثما كنت، وأتبع السيئة الحسنة تمحها، وخالق الناس بخلق حسن - رواه الترمذي",
    "كلمتان خفيفتان على اللسان، ثقيلتان في الميزان: سبحان الله وبحمده، سبحان الله العظيم - متفق عليه",
    "البر حسن الخلق - رواه مسلم",
]
ADIYA = [
    "اللهم اغفر لي ذنوبي كلها، دقها وجلها، أولها وآخرها، علانيتها وسرها",
    "اللهم إني أسألك العفو والعافية في الدنيا والآخرة",
    "ربنا آتنا في الدنيا حسنة وفي الآخرة حسنة وقنا عذاب النار",
    "اللهم اهدني فيمن هديت، وعافني فيمن عافيت، وتولني فيمن توليت",
    "اللهم إني أسألك علما نافعا، ورزقا طيبا، وعملا متقبلا",
    "يا مقلب القلوب ثبت قلبي على دينك",
    "رب اشرح لي صدري ويسر لي أمري",
]
ALLAH_NAMES = [
    ("الرحمن","الذي وسعت رحمته كل شيء"),
    ("الرحيم","الذي يرحم عباده المؤمنين"),
    ("الملك","المالك لكل شيء"),
    ("القدوس","المنزه عن كل نقص"),
    ("العزيز","الغالب الذي لا يغلب"),
    ("الخالق","الذي أوجد الأشياء من العدم"),
    ("الرزاق","الذي يرزق جميع خلقه"),
    ("الغفور","الذي يغفر الذنوب جميعا"),
    ("العليم","الذي يعلم كل شيء"),
    ("الحكيم","الذي يضع كل شيء في موضعه"),
    ("الكريم","الكثير الخير الجواد"),
    ("اللطيف","العالم بخفايا الأمور"),
]

async def cmd_جدولة(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    chat_id = update.effective_chat.id
    groups  = db.setdefault("scheduled_groups", [])
    if chat_id in groups:
        groups.remove(chat_id)
        save_data(db)
        await update.message.reply_text("تم ايقاف الاذكار المجدولة في هذه المجموعة.")
    else:
        groups.append(chat_id)
        save_data(db)
        await update.message.reply_text(
            "تم تفعيل الاذكار المجدولة!\n\nاذكار الصباح: 6:00 ص\nاذكار المساء: 5:00 م")

async def scheduled_sabah(context: ContextTypes.DEFAULT_TYPE):
    zikr = random.choice(AZKAR_SABAH)
    for chat_id in db.get("scheduled_groups", []):
        try:
            await context.bot.send_message(
                chat_id,
                f"اذكار الصباح\n\n{zikr}\n\nاللهم بارك لنا في صباحنا",
            )
        except:
            pass

async def scheduled_masa(context: ContextTypes.DEFAULT_TYPE):
    zikr = random.choice(AZKAR_MASA)
    for chat_id in db.get("scheduled_groups", []):
        try:
            await context.bot.send_message(
                chat_id,
                f"اذكار المساء\n\n{zikr}\n\nاللهم بارك لنا في مساءنا",
            )
        except:
            pass

async def scheduled_backup(context: ContextTypes.DEFAULT_TYPE):
    try:
        backup_text = json.dumps(db, ensure_ascii=False, indent=2)
        timestamp   = datetime.now().strftime("%Y-%m-%d_%H-%M")
        await context.bot.send_document(
            DEVELOPER_ID,
            document=backup_text.encode("utf-8"),
            filename=f"backup_{timestamp}.json",
            caption=(
                f"نسخة احتياطية تلقائية\n"
                f"التاريخ: {timestamp}\n"
                f"المجموعات المجدولة: {len(db.get('scheduled_groups', []))}\n"
                f"الانذارات المحفوظة: {len(db.get('warnings', {}))}"
            )
        )
    except:
        pass

# ══════════════════════════════════════════════════
#         📊 الإحصائيات
# ══════════════════════════════════════════════════
async def cmd_الاحصائيات(update, context):
    if update.effective_user.id != DEVELOPER_ID:
        await update.message.reply_text("للمطور فقط!"); return
    total_groups    = len(db.get("settings", {}))
    sched_groups    = len(db.get("scheduled_groups", []))
    total_warnings  = len(db.get("warnings", {}))
    total_ranks     = sum(len(v) for v in db.get("ranks", {}).values())
    total_whispers  = len(db.get("whispers", {}))
    total_shortcuts = sum(len(v) for v in db.get("shortcuts", {}).values())
    total_logs      = len(db.get("logs", []))
    blacklisted     = sum(len(v) for v in db.get("blacklist", {}).values())
    await update.message.reply_text(
        f"احصائيات البوت\n\n"
        f"المجموعات النشطة: {total_groups}\n"
        f"مجموعات الاذكار: {sched_groups}\n"
        f"اجمالي الانذارات: {total_warnings}\n"
        f"اعضاء بررتب: {total_ranks}\n"
        f"الهمسات المحفوظة: {total_whispers}\n"
        f"الاختصارات: {total_shortcuts}\n"
        f"الكلمات المحظورة: {blacklisted}\n"
        f"سجلات الاجراءات: {total_logs}"
    )

# ══════════════════════════════════════════════════
#         🤖 الردود الذكية
# ══════════════════════════════════════════════════
SMART_RESPONSES = {
    "السلام عليكم":"وعليكم السلام ورحمة الله وبركاته",
    "سلام":"وعليكم السلام",
    "هاي":"هاي! كيف حالك؟",
    "هلا":"هلا وغلا!",
    "مرحبا":"اهلا وسهلا!",
    "اهلا":"اهلا وسهلا!",
    "صباح الخير":"صباح النور والسعادة!",
    "صباح النور":"صباح الورد والياسمين!",
    "مساء الخير":"مساء النور والبركات!",
    "مساء النور":"مساء الورد عليك!",
    "تصبح على خير":"وانت من اهل الخير!",
    "من انت":"انا لينوكس! 🤖\nبوت متكامل للحماية والخدمات.\nاكتب /الاوامر لمعرفة كل ما اقدر اعمله!",
    "كيف حالك":"بخير والحمد لله! وانت كيف حالك؟",
    "شكرا":"العفو! دائما في خدمتك",
    "شكرا":"العفو!",
    "جزاك الله خيرا":"وإياك وجزانا الله جميعا خيرا",
    "بارك الله فيك":"وفيك بارك الله",
    "ما معنى الاسلام":"الإسلام هو الاستسلام لله وتوحيده والانقياد له بالطاعة والبراءة من الشرك وأهله",
    "كم عدد اركان الاسلام":"اركان الإسلام خمسة: الشهادتان، الصلاة، الزكاة، الصوم، الحج",
    "كم عدد اركان الايمان":"اركان الإيمان ستة: الإيمان بالله، وملائكته، وكتبه، ورسله، واليوم الآخر، والقدر خيره وشره",
    "كم الساعه":"اكتب /الوقت لمعرفة الوقت الحالي",
    "كم الساعة":"اكتب /الوقت لمعرفة الوقت الحالي",
    "اضحكني":"ليه البحر مالح؟ عشان السمك بيعطس فيه",
    "قولي نكتة":"واحد راح يشتري موبايل قاله البائع: ده موبايل ذكي!\nقاله: طب سؤلوا مكاني",
    "ملل":"اكتب /اذكار او /حديث تستفيد",
    "مين المطور":"مطور لينوكس هو @llllll_lllllll_llllll 👨‍💻",
    "من المطور":"مطور لينوكس هو @llllll_lllllll_llllll 👨‍💻",
    "المطور":"مطور لينوكس هو @llllll_lllllll_llllll 👨‍💻",
    "مطور البوت":"مطور لينوكس هو @llllll_lllllll_llllll 👨‍💻",
}


# ══════════════════════════════════════════════════
#         📥 نظام التحميل (yt-dlp)
# ══════════════════════════════════════════════════
import subprocess, tempfile, glob

URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|"
    r"tiktok\.com/|instagram\.com/|twitter\.com/|x\.com/|"
    r"facebook\.com/|fb\.watch/|reddit\.com/|dailymotion\.com/|"
    r"vimeo\.com/|soundcloud\.com/|twitch\.tv/)[^\s]+"
)

MAX_SIZE_MB = 50

async def download_and_send(update, context, url: str):
    msg = await update.message.reply_text("⏳ جاري التحميل... انتظر لحظة")
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # أولاً: جرب تحميل الفيديو بدون علامة مائية
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "--max-filesize", f"{MAX_SIZE_MB}M",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "--no-mtime",
                # TikTok بدون علامة مائية
                "--extractor-args", "tiktok:api_hostname=api22-normal-c-useast2a.tiktokv.com",
                "-o", f"{tmpdir}/%(title).50s.%(ext)s",
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            files = glob.glob(f"{tmpdir}/*")
            if files:
                filepath = files[0]
                size_mb  = os.path.getsize(filepath) / (1024 * 1024)

                if size_mb > MAX_SIZE_MB:
                    # كبير — ابعت رابط تحميل مباشر
                    direct = await get_direct_url(url)
                    await msg.edit_text(
                        f"⚠️ الفيديو كبير جداً ({size_mb:.1f}MB)\n\n"
                        f"{'🔗 رابط التحميل المباشر:\n' + direct if direct else '❌ لا يمكن توفير رابط مباشر، حاول من المتصفح.'}"
                    )
                    return

                # إرسال بناءً على النوع
                ext = filepath.rsplit(".", 1)[-1].lower()
                try:
                    await msg.delete()
                except: pass

                if ext in ("mp4", "mkv", "webm", "avi", "mov"):
                    await update.message.reply_video(
                        video=open(filepath, "rb"),
                        caption="📥 تم التحميل بواسطة لينوكس",
                        supports_streaming=True
                    )
                elif ext in ("mp3", "m4a", "ogg", "wav", "flac", "opus"):
                    await update.message.reply_audio(
                        audio=open(filepath, "rb"),
                        caption="📥 تم التحميل بواسطة لينوكس"
                    )
                else:
                    await update.message.reply_document(
                        document=open(filepath, "rb"),
                        caption="📥 تم التحميل بواسطة لينوكس"
                    )
                return

            # لو فشل التحميل — جرب رابط مباشر
            direct = await get_direct_url(url)
            await msg.edit_text(
                f"❌ فشل التحميل!\n\n"
                f"{'🔗 رابط التحميل المباشر:\n' + direct if direct else 'تأكد من صحة الرابط وحاول مرة أخرى.'}"
            )

    except subprocess.TimeoutExpired:
        await msg.edit_text("⏰ انتهت مهلة التحميل! الرابط قد يكون كبيراً جداً.")
    except Exception as e:
        await msg.edit_text(f"❌ حدث خطأ أثناء التحميل.")
        logging.error(f"Download error: {e}")

async def get_direct_url(url: str) -> str:
    """استخراج رابط التحميل المباشر"""
    try:
        cmd    = ["yt-dlp", "--get-url", "-f", "best[ext=mp4]/best", "--no-playlist", url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        direct = result.stdout.strip().split("\n")[0]
        return direct if direct.startswith("http") else ""
    except:
        return ""

async def cmd_تحميل(update, context):
    """أمر /تحميل [رابط]"""
    url = ""
    if context.args:
        url = context.args[0]
    elif update.message.reply_to_message and update.message.reply_to_message.text:
        # لو رد على رسالة فيها رابط
        match = URL_PATTERN.search(update.message.reply_to_message.text)
        if match:
            url = match.group()

    if not url:
        await update.message.reply_text(
            "📥 **كيف تستخدم التحميل:**\n\n"
            "1️⃣ `/تحميل [رابط]`\n"
            "2️⃣ أو أرسل الرابط مباشرة وسيتم التعرف عليه تلقائياً\n\n"
            "**المنصات المدعومة:**\n"
            "YouTube • TikTok • Instagram • Twitter/X\n"
            "Facebook • Reddit • Vimeo • SoundCloud وغيرها",
            parse_mode="Markdown"
        )
        return

    if not URL_PATTERN.search(url):
        await update.message.reply_text("❌ الرابط غير صحيح!")
        return

    await download_and_send(update, context, url)

async def handle_url_message(update, context):
    """اكتشاف الروابط تلقائياً في الرسائل"""
    text = update.message.text or ""
    match = URL_PATTERN.search(text)
    if not match:
        return False

    url = match.group()
    keyboard = [[
        InlineKeyboardButton("📥 تحميل", callback_data=f"dl_{url[:200]}"),
        InlineKeyboardButton("❌ تجاهل", callback_data="dl_cancel")
    ]]
    await update.message.reply_text(
        f"🔗 تم اكتشاف رابط!\nتريد تحميله؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return True



# ══════════════════════════════════════════════════
#         💱 تحويل العملات
# ══════════════════════════════════════════════════
async def cmd_عملة(update, context):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "💱 **تحويل العملات:**\n`/عملة [المبلغ] [العملة]`\n\n"
            "**أمثلة:**\n"
            "`/عملة 100 USD` - دولار لجنيه\n"
            "`/عملة 100 EUR` - يورو لجنيه\n"
            "`/عملة 100 SAR` - ريال لجنيه\n"
            "`/عملة 100 GBP` - جنيه إسترليني لجنيه",
            parse_mode="Markdown"); return
    try:
        amount   = float(context.args[0])
        currency = context.args[1].upper()
        url = f"https://api.exchangerate-api.com/v4/latest/{currency}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        rates = data.get("rates", {})
        egp   = rates.get("EGP", 0)
        usd   = rates.get("USD", 0)
        sar   = rates.get("SAR", 0)
        eur   = rates.get("EUR", 0)
        if not egp:
            await update.message.reply_text("❌ عملة غير معروفة!"); return
        await update.message.reply_text(
            f"💱 **تحويل العملات**\n\n"
            f"💵 {amount} {currency} يساوي:\n\n"
            f"🇪🇬 جنيه مصري: **{amount * egp:,.2f} EGP**\n"
            f"💵 دولار أمريكي: **{amount * usd:,.2f} USD**\n"
            f"🇸🇦 ريال سعودي: **{amount * sar:,.2f} SAR**\n"
            f"🇪🇺 يورو: **{amount * eur:,.2f} EUR**\n\n"
            f"📅 السعر الآن",
            parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ خطأ في جلب الأسعار! جرب مرة أخرى.")

# ══════════════════════════════════════════════════
#         🔢 الحاسبة
# ══════════════════════════════════════════════════
async def cmd_حاسبة(update, context):
    if not context.args:
        await update.message.reply_text(
            "🔢 **الحاسبة:**\n`/حاسبة [عملية حسابية]`\n\n"
            "**أمثلة:**\n"
            "`/حاسبة 5 + 3`\n"
            "`/حاسبة 100 * 25 / 4`\n"
            "`/حاسبة 2 ** 10` (أس)\n"
            "`/حاسبة sqrt(144)` (جذر تربيعي)",
            parse_mode="Markdown"); return
    expr = " ".join(context.args)
    try:
        # أمان: نسمح بالعمليات الرياضية فقط
        allowed = set("0123456789+-*/().** sqrt")
        clean   = expr.replace("sqrt", "").replace(" ", "")
        if not all(c in "0123456789+-*/.() " for c in clean):
            await update.message.reply_text("❌ عملية غير مسموحة!"); return
        import math
        safe_expr = expr.replace("sqrt", "math.sqrt")
        result = eval(safe_expr, {"__builtins__": {}, "math": math})
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        await update.message.reply_text(
            f"🔢 **الحاسبة**\n\n"
            f"📝 العملية: `{expr}`\n"
            f"✅ النتيجة: **{result:,}**",
            parse_mode="Markdown")
    except ZeroDivisionError:
        await update.message.reply_text("❌ لا يمكن القسمة على صفر!")
    except Exception:
        await update.message.reply_text("❌ عملية غير صحيحة!")

# ══════════════════════════════════════════════════
#         📝 تلخيص النصوص
# ══════════════════════════════════════════════════
async def cmd_لخص(update, context):
    text = ""
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text or ""
    elif context.args:
        text = " ".join(context.args)
    if not text:
        await update.message.reply_text(
            "📝 **تلخيص النصوص:**\n\n"
            "1️⃣ رد على أي رسالة واكتب `/لخص`\n"
            "2️⃣ أو `/لخص [النص]`",
            parse_mode="Markdown"); return
    if len(text) < 100:
        await update.message.reply_text("⚠️ النص قصير جداً للتلخيص!"); return

    msg = await update.message.reply_text("⏳ جاري التلخيص...")
    summary = await ask_ai(f"لخص النص التالي بإيجاز في 3-4 جمل بالعربية:\n\n{text[:3000]}")
    if summary:
        await msg.edit_text(f"📝 **الملخص:**\n\n{summary}", parse_mode="Markdown")
    else:
        await msg.edit_text("❌ فشل التلخيص! تأكد من إعداد مفتاح الذكاء الاصطناعي.")

# ══════════════════════════════════════════════════
#         🌐 الترجمة للعربية
# ══════════════════════════════════════════════════
async def cmd_ترجم(update, context):
    text = ""
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text or ""
    elif context.args:
        text = " ".join(context.args)
    if not text:
        await update.message.reply_text(
            "🌐 **الترجمة للعربية:**\n\n"
            "1️⃣ رد على أي رسالة واكتب `/ترجم`\n"
            "2️⃣ أو `/ترجم [النص]`",
            parse_mode="Markdown"); return

    msg = await update.message.reply_text("⏳ جاري الترجمة...")
    translated = await ask_ai(
        f"ترجم النص التالي إلى اللغة العربية فقط بدون أي شرح أو مقدمة:\n\n{text[:2000]}"
    )
    if translated:
        await msg.edit_text(f"🌐 **الترجمة:**\n\n{translated}", parse_mode="Markdown")
    else:
        await msg.edit_text("❌ فشلت الترجمة! تأكد من إعداد مفتاح الذكاء الاصطناعي.")

# ══════════════════════════════════════════════════
#         🔔 التنبيهات الذكية للمشرفين
# ══════════════════════════════════════════════════
# suspicious_reports = { "chat_id_msg_id": {...} }
suspicious_reports = {}

async def notify_admins(context, chat, user, message, reason: str, msg_id: int):
    """إبلاغ المشرفين بمحتوى مشبوه"""
    report_key = f"{chat.id}_{msg_id}"
    suspicious_reports[report_key] = {
        "chat_id":  chat.id,
        "msg_id":   msg_id,
        "user_id":  user.id,
        "user_name": user.first_name,
        "reason":   reason,
    }

    keyboard = [[
        InlineKeyboardButton("🗑️ احذف", callback_data=f"mod_delete_{report_key}"),
        InlineKeyboardButton("🔇 اكتم",  callback_data=f"mod_mute_{report_key}"),
        InlineKeyboardButton("✅ تجاهل", callback_data=f"mod_ignore_{report_key}"),
    ]]

    alert_text = (
        "⚠️ **تنبيه مشبوه!**\n\n"
        f"👤 المستخدم: {user.first_name} (ID: {user.id})\n"
        f"📋 السبب: **{reason}**\n"
        f"💬 المجموعة: {chat.title}\n\n"
        "اختر الإجراء:"
    )

    # ابعت لكل المشرفين المسجلين
    chat_id_str = str(chat.id)
    ranks       = db.get("ranks", {}).get(chat_id_str, {})
    notified    = set()

    for uid, rank in ranks.items():
        if RANKS.get(rank, {}).get("level", 0) >= 2:
            try:
                await context.bot.send_message(
                    int(uid), alert_text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                notified.add(uid)
            except:
                pass

    # أبلغ المطور دايماً
    if str(DEVELOPER_ID) not in notified:
        try:
            await context.bot.send_message(
                DEVELOPER_ID, alert_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass

async def handle_mod_action(query, data):
    """معالجة قرار المشرف"""
    parts      = data.split("_", 3)
    action     = parts[1]          # delete / mute / ignore
    report_key = parts[2] + "_" + parts[3]
    report     = suspicious_reports.get(report_key)

    if not report:
        await query.answer("انتهت صلاحية هذا التنبيه!", show_alert=True)
        return

    chat_id  = report["chat_id"]
    msg_id   = report["msg_id"]
    user_id  = report["user_id"]
    username = report["user_name"]

    if action == "delete":
        try:
            await query.bot.delete_message(chat_id, msg_id)
            await query.message.edit_text(f"✅ تم حذف رسالة {username}")
            del suspicious_reports[report_key]
        except:
            await query.answer("فشل الحذف!", show_alert=True)

    elif action == "mute":
        try:
            await query.bot.restrict_chat_member(
                chat_id, user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(minutes=60)
            )
            await query.bot.delete_message(chat_id, msg_id)
            await query.message.edit_text(f"✅ تم كتم {username} وحذف الرسالة")
            del suspicious_reports[report_key]
        except:
            await query.answer("فشل الكتم!", show_alert=True)

    elif action == "ignore":
        await query.message.edit_text(f"✅ تم تجاهل تنبيه {username}")
        if report_key in suspicious_reports:
            del suspicious_reports[report_key]

# ══════════════════════════════════════════════════
#         📊 الملخص اليومي للمشرفين
# ══════════════════════════════════════════════════
daily_stats = defaultdict(lambda: {"messages": 0, "violations": 0, "new_members": 0, "left_members": 0})

async def scheduled_daily_summary(context: ContextTypes.DEFAULT_TYPE):
    """ملخص يومي يُرسل لمشرفي كل مجموعة"""
    for chat_id_str in db.get("settings", {}):
        stats = daily_stats[chat_id_str]
        if stats["messages"] == 0:
            continue
        ranks = db.get("ranks", {}).get(chat_id_str, {})
        summary = (
            f"📊 **الملخص اليومي**\n\n"
            f"💬 الرسائل: **{stats['messages']}**\n"
            f"🚫 المخالفات: **{stats['violations']}**\n"
            f"➕ أعضاء جدد: **{stats['new_members']}**\n"
            f"➖ أعضاء غادروا: **{stats['left_members']}**\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d')}"
        )
        notified = set()
        for uid, rank in ranks.items():
            if RANKS.get(rank, {}).get("level", 0) >= 2:
                try:
                    await context.bot.send_message(int(uid), summary, parse_mode="Markdown")
                    notified.add(uid)
                except:
                    pass
        if str(DEVELOPER_ID) not in notified:
            try:
                await context.bot.send_message(DEVELOPER_ID, summary, parse_mode="Markdown")
            except:
                pass
        # إعادة تصفير الإحصائيات
        daily_stats[chat_id_str] = {"messages": 0, "violations": 0, "new_members": 0, "left_members": 0}

# ══════════════════════════════════════════════════
#         📢 نظام التقارير
# ══════════════════════════════════════════════════
async def cmd_report(update, context):
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ رد على الرسالة التي تريد الإبلاغ عنها واكتب /report"); return
    reporter  = update.effective_user
    target    = update.message.reply_to_message.from_user
    chat      = update.effective_chat
    msg_id    = update.message.reply_to_message.message_id
    reason    = " ".join(context.args) if context.args else "بلاغ من عضو"

    if target.id == DEVELOPER_ID:
        await update.message.reply_text("⛔ لا يمكن الإبلاغ عن المطور!"); return
    if target.is_bot:
        await update.message.reply_text("⛔ لا يمكن الإبلاغ عن بوت!"); return

    await notify_admins(context, chat, target, update.message.reply_to_message, f"بلاغ من {reporter.first_name}: {reason}", msg_id)
    try: await update.message.delete()
    except: pass
    msg = await update.message.reply_to_message.reply_text("📨 تم إرسال البلاغ للمشرفين!")
    await asyncio.sleep(5)
    try: await msg.delete()
    except: pass



# ══════════════════════════════════════════════════
#         🔒 قفل/فتح الدردشة بالكلام
# ══════════════════════════════════════════════════
LOCK_KEYWORDS   = ["قفل الدردشة","قفل الشات","قفل الدردشه","قفل الشاته","قفل السات","قفل"]
UNLOCK_KEYWORDS = ["فتح الدردشة","فتح الشات","فتح الدردشه","فتح الشاته","فتح السات","فتح"]

async def handle_chat_lock(update, context):
    """قفل/فتح الدردشة بالكلام"""
    if not update.message or not update.effective_user: return False
    user    = update.effective_user
    chat    = update.effective_chat
    text    = (update.message.text or "").strip()
    text_l  = text.lower()

    if not any(kw in text_l for kw in LOCK_KEYWORDS + UNLOCK_KEYWORDS):
        return False
    if not await is_admin(update, user.id):
        return False

    is_lock = any(kw in text_l for kw in LOCK_KEYWORDS)

    try:
        if is_lock:
            await context.bot.set_chat_permissions(
                chat.id,
                ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False
                )
            )
            get_settings(str(chat.id))["chat_locked"] = True
            save_data(db)
            try: await update.message.delete()
            except: pass
            lock_text = f"🔒 تم قفل الدردشة\nبواسطة: {user.first_name}\nلا يمكن لأي عضو الإرسال حتى يتم الفتح."
            await chat.send_message(lock_text)
        else:
            await context.bot.set_chat_permissions(
                chat.id,
                ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                    can_send_polls=True
                )
            )
            get_settings(str(chat.id))["chat_locked"] = False
            save_data(db)
            try: await update.message.delete()
            except: pass
            unlock_text = f"🔓 تم فتح الدردشة\nبواسطة: {user.first_name}\nيمكن للأعضاء الإرسال الآن."
            await chat.send_message(unlock_text)
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل: {e}")
    return True

async def delete_if_locked(update, context):
    """حذف رسائل الأعضاء العاديين لو الدردشة مقفولة"""
    if not update.message or not update.effective_user: return False
    chat_id  = str(update.effective_chat.id)
    settings = get_settings(chat_id)
    if not settings.get("chat_locked"): return False
    user = update.effective_user
    if await is_admin(update, user.id):
        # المشرف ممكن يقفل/يفتح بالكلام
        if text:
            await handle_chat_lock(update, context)
        return False
    try: await update.message.delete()
    except: pass
    return True

# ══════════════════════════════════════════════════
#         📰 أخبار عربية
# ══════════════════════════════════════════════════
async def cmd_اخبار(update, context):
    try:
        url = "https://newsapi.org/v2/top-headlines?language=ar&pageSize=5&apiKey=demo"
        # استخدام RSS بديل مجاني
        rss_url = "https://feeds.bbcarabic.com/world?format=xml"
        req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8")
        # استخراج العناوين من RSS
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>", content)
        links  = re.findall(r"<link>(https?://[^<]+)</link>", content)
        if not titles:
            titles = re.findall(r"<title>(.*?)</title>", content)
        titles = [t for t in titles if t and "BBC" not in t][:5]
        if not titles:
            await update.message.reply_text("❌ تعذر جلب الأخبار، جرب لاحقاً."); return
        text = "آخر الأخبار العربية:\n\n"
        for i, title in enumerate(titles, 1):
            text += f"{i}. {title}\n"
            if i < len(links):
                text += f"   {links[i]}\n"
            text += "\n"
        text += f"\n{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception:
        await update.message.reply_text("❌ تعذر جلب الأخبار الآن، جرب لاحقاً.")

# ══════════════════════════════════════════════════
#         ⚽ نتائج المباريات
# ══════════════════════════════════════════════════
async def cmd_مباريات(update, context):
    msg = (
        "لتفعيل هذه الخاصية اضف API Key من football-data.org "
        "ثم ضعه في متغيرات البيئة: FOOTBALL_API_KEY"
    )
    await update.message.reply_text(msg)

# ══════════════════════════════════════════════════
#         🌤️ طقس 7 أيام
# ══════════════════════════════════════════════════
async def cmd_طقس_اسبوع(update, context):
    if not context.args:
        await update.message.reply_text("/طقس_اسبوع [المدينة] - مثال: /طقس_اسبوع Cairo"); return
    city = " ".join(context.args)
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        weather = data.get("weather", [])
        text    = "توقعات 7 ايام - " + city + "\n\n"
        days_ar = ["الأول","الثاني","الثالث","الرابع","الخامس","السادس","السابع"]
        for i, day in enumerate(weather[:7]):
            date_str = day.get("date","")
            max_t    = day.get("maxtempC","?")
            min_t    = day.get("mintempC","?")
            desc     = day.get("hourly",[{}])[4].get("weatherDesc",[{}])[0].get("value","")
            icon     = "🔥" if int(max_t) >= 35 else "☀️" if int(max_t) >= 25 else "⛅" if int(max_t) >= 15 else "❄️"
            text    += f"{icon} اليوم {days_ar[i]} ({date_str})\n"
            text    += f"   {min_t} - {max_t} درجة\n\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("❌ اكتب اسم المدينة بالانجليزية.")

# ══════════════════════════════════════════════════
#         🖼️ ضغط الصور وتحويلها لستيكر
# ══════════════════════════════════════════════════
async def cmd_ستيكر(update, context):
    """تحويل صورة لستيكر"""
    photo = None
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]
    elif update.message.photo:
        photo = update.message.photo[-1]
    if not photo:
        await update.message.reply_text("📸 أرسل صورة أو رد على صورة واكتب /ستيكر"); return
    msg = await update.message.reply_text("⏳ جاري التحويل...")
    try:
        file    = await context.bot.get_file(photo.file_id)
        img_bytes = bytearray()
        import io
        buf = io.BytesIO()
        await file.download_to_memory(buf)
        buf.seek(0)
        from PIL import Image
        img = Image.open(buf).convert("RGBA")
        # Resize لـ 512x512
        img.thumbnail((512, 512), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="WEBP")
        out.seek(0)
        await msg.delete()
        await update.message.reply_sticker(sticker=out)
    except ImportError:
        await msg.edit_text("مكتبة Pillow غير مثبتة! ثبتها بـ: pip install Pillow")
    except Exception as e:
        await msg.edit_text(f"❌ فشل التحويل: {e}")

# ══════════════════════════════════════════════════
#         📋 القواعد المخصصة
# ══════════════════════════════════════════════════
async def cmd_تعيين_قواعد(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text("/تعيين_قواعد [نص القواعد]"); return
    chat_id = str(update.effective_chat.id)
    rules   = " ".join(context.args)
    db.setdefault("rules", {})[chat_id] = rules
    save_data(db)
    await update.message.reply_text("✅ تم حفظ قواعد المجموعة!")

async def cmd_القواعد(update, context):
    chat_id = str(update.effective_chat.id)
    rules   = db.get("rules", {}).get(chat_id)
    if not rules:
        await update.message.reply_text("لا يوجد قواعد بعد! استخدم /تعيين_قواعد"); return
    await update.message.reply_text("قواعد المجموعة:\n\n" + rules)

# ══════════════════════════════════════════════════
#         ⚡ أوامر مخصصة (!اسم)
# ══════════════════════════════════════════════════
async def cmd_اضف_امر(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ للمشرفين فقط!"); return
    if len(context.args) < 2:
        await update.message.reply_text("/اضف_امر [الكلمة] [الرد] - مثال: /اضف_امر هلا اهلا وسهلا!"); return
    chat_id  = str(update.effective_chat.id)
    keyword  = context.args[0].lower()
    response = " ".join(context.args[1:])
    db.setdefault("custom_cmds", {}).setdefault(chat_id, {})[keyword] = response
    save_data(db)
    await update.message.reply_text(f"تم اضافة الامر !{keyword} - الرد: {response}")

async def cmd_الاوامر_المخصصة(update, context):
    chat_id = str(update.effective_chat.id)
    cmds    = db.get("custom_cmds", {}).get(chat_id, {})
    if not cmds:
        await update.message.reply_text("لا يوجد اوامر مخصصة بعد! استخدم /اضف_امر"); return
    text = "الاوامر المخصصة:\n\n"
    for kw, resp in cmds.items():
        short = resp[:40] + "..." if len(resp) > 40 else resp
        text += f"!{kw} - {short}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_حذف_امر(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text("`/حذف_امر [الكلمة]`", parse_mode="Markdown"); return
    chat_id = str(update.effective_chat.id)
    keyword = context.args[0].lower()
    cmds    = db.get("custom_cmds", {}).get(chat_id, {})
    if keyword in cmds:
        del cmds[keyword]; save_data(db)
        await update.message.reply_text(f"✅ تم حذف الأمر `!{keyword}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("الأمر غير موجود!")

async def handle_custom_cmd(update, context):
    """معالجة الأوامر المخصصة !كلمة"""
    text = (update.message.text or "").strip()
    if not text.startswith("!"): return False
    keyword = text[1:].split()[0].lower()
    chat_id = str(update.effective_chat.id)
    cmds    = db.get("custom_cmds", {}).get(chat_id, {})
    if keyword not in cmds: return False
    await update.message.reply_text(cmds[keyword])
    return True

# ══════════════════════════════════════════════════
#         🔐 قائمة بيضاء للروابط
# ══════════════════════════════════════════════════
async def cmd_اضف_رابط_مسموح(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text("/اضف_رابط_مسموح [الرابط] - مثال: /اضف_رابط_مسموح youtube.com"); return
    chat_id = str(update.effective_chat.id)
    domain  = context.args[0].lower().replace("https://","").replace("http://","").replace("www.","").split("/")[0]
    db.setdefault("whitelist_links", {}).setdefault(chat_id, [])
    if domain not in db["whitelist_links"][chat_id]:
        db["whitelist_links"][chat_id].append(domain)
        save_data(db)
        await update.message.reply_text(f"✅ تم إضافة `{domain}` للقائمة البيضاء!", parse_mode="Markdown")
    else:
        await update.message.reply_text("الرابط موجود بالفعل!")

async def cmd_الروابط_المسموحة(update, context):
    chat_id   = str(update.effective_chat.id)
    whitelist = db.get("whitelist_links", {}).get(chat_id, [])
    if not whitelist:
        await update.message.reply_text("القائمة البيضاء فارغة! استخدم /اضف_رابط_مسموح"); return
    text = "الروابط المسموحة:\n\n" + "\n".join([f"- {d}" for d in whitelist])
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_حذف_رابط_مسموح(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text("`/حذف_رابط_مسموح [الدومين]`", parse_mode="Markdown"); return
    chat_id   = str(update.effective_chat.id)
    domain    = context.args[0].lower()
    whitelist = db.get("whitelist_links", {}).get(chat_id, [])
    if domain in whitelist:
        whitelist.remove(domain); save_data(db)
        await update.message.reply_text(f"✅ تم حذف `{domain}` من القائمة البيضاء", parse_mode="Markdown")
    else:
        await update.message.reply_text("الرابط غير موجود!")

def is_whitelisted(text, chat_id):
    """تحقق لو الرابط في القائمة البيضاء"""
    whitelist = db.get("whitelist_links", {}).get(str(chat_id), [])
    if not whitelist: return False
    return any(domain in text.lower() for domain in whitelist)

# ══════════════════════════════════════════════════
#         🛑 وضع الطوارئ
# ══════════════════════════════════════════════════
async def cmd_طوارئ(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("❌ للمشرفين فقط!"); return
    chat_id  = str(update.effective_chat.id)
    settings = get_settings(chat_id)
    current  = settings.get("emergency", False)
    settings["emergency"] = not current
    save_data(db)
    if settings["emergency"]:
        await update.message.reply_text("تم تفعيل وضع الطوارئ! البوت في وضع المراقبة القصوى. لايقافه: /طوارئ")
    else:
        await update.message.reply_text("تم ايقاف وضع الطوارئ. العمل يعود لطبيعته.")

# ══════════════════════════════════════════════════
#         🎵 تحويل فيديو لصوت
# ══════════════════════════════════════════════════
async def cmd_صوت(update, context):
    """استخراج الصوت من فيديو"""
    video = None
    if update.message.reply_to_message:
        video = update.message.reply_to_message.video or update.message.reply_to_message.document
    elif update.message.video:
        video = update.message.video

    if not video:
        await update.message.reply_text("🎵 أرسل فيديو أو رد على فيديو واكتب /صوت"); return

    if hasattr(video, 'file_size') and video.file_size and video.file_size > 50 * 1024 * 1024:
        await update.message.reply_text("❌ الفيديو أكبر من 50MB!"); return

    msg = await update.message.reply_text("⏳ جاري استخراج الصوت...")
    try:
        import tempfile, io
        file = await context.bot.get_file(video.file_id)
        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = f"{tmpdir}/video.mp4"
            audio_path = f"{tmpdir}/audio.mp3"
            await file.download_to_drive(video_path)
            result = subprocess.run(
                ["ffmpeg", "-i", video_path, "-q:a", "0", "-map", "a", audio_path, "-y"],
                capture_output=True, timeout=60
            )
            if os.path.exists(audio_path):
                await msg.delete()
                await update.message.reply_audio(
                    audio=open(audio_path, "rb"),
                    caption="🎵 تم استخراج الصوت بواسطة لينوكس"
                )
            else:
                await msg.edit_text("فشل استخراج الصوت! تاكد من وجود ffmpeg.")
    except FileNotFoundError:
        await msg.edit_text("ffmpeg غير مثبت! ثبته بـ: apt install ffmpeg")
    except Exception as e:
        await msg.edit_text(f"❌ فشل: {e}")



# ══════════════════════════════════════════════════
#         🎵 نظام يوت - البحث والتحميل التلقائي
# ══════════════════════════════════════════════════
YOT_RATE = defaultdict(list)  # rate limiting للتاك
YOT_LIMIT = 3  # 3 طلبات كل دقيقة لكل مستخدم

def can_use_yot(user_id):
    now = time.time()
    YOT_RATE[user_id] = [t for t in YOT_RATE[user_id] if now - t < 60]
    if len(YOT_RATE[user_id]) >= YOT_LIMIT:
        return False
    YOT_RATE[user_id].append(now)
    return True


def _sync_yot_download(query: str, is_video: bool = False, quality: str = "عالية") -> dict:
    """نسخة متزامنة للتحميل تشتغل في executor"""
    import tempfile, glob, yt_dlp
    result = {"success": False, "file": None, "title": "", "duration": 0, "tmpdir": None}
    try:
        tmpdir = tempfile.mkdtemp()
        result["tmpdir"] = tmpdir

        if is_video:
            fmt = "bestvideo[ext=mp4][height<=720]+bestaudio/best[ext=mp4]/best" if quality == "عالية" else "worst[ext=mp4]/worst"
            ydl_opts = {
                "format": fmt,
                "outtmpl": f"{tmpdir}/%(title).60s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "max_downloads": 1,
                "merge_output_format": "mp4",
            }
        else:
            q = "192" if quality == "عالية" else "64"
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": f"{tmpdir}/%(title).60s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "max_downloads": 1,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": q,
                }],
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            if info and "entries" in info:
                info = info["entries"][0]
            if info:
                result["title"]    = info.get("title", query)
                result["duration"] = info.get("duration", 0)

        files = glob.glob(f"{tmpdir}/*")
        if files:
            result["file"]    = files[0]
            result["success"] = True
    except Exception as e:
        logging.error(f"YOT sync download error: {e}")
    return result


async def handle_yot_message(update, context):
    """معالجة رسائل تاك"""
    text = (update.message.text or "").strip()
    text_lower = text.lower()

    # فحص لو الرسالة تبدأ بـ تاك
    if not (text_lower.startswith("يوت ") or text_lower.startswith("يوت ")):
        return False

    query = text[4:].strip()  # الكلمات بعد "يوت "
    if not query:
        await update.message.reply_text("اكتب اسم الاغنية او المقطع بعد كلمة تاك\nمثال: يوت فيروز صباح الخير")
        return True

    user = update.effective_user

    # rate limiting
    if not can_use_yot(user.id):
        await update.message.reply_text(f"انتظر قليلاً! يمكنك استخدام يوت {YOT_LIMIT} مرات كل دقيقة.")
        return True

    # تحديد نوع البحث - قرآن أم موسيقى
    quran_keywords = ["سورة","قران","قرآن","آية","اية","تلاوة","شيخ","حفظ","ورش","قالون"]
    is_quran = any(kw in query for kw in quran_keywords)

    msg = await update.message.reply_text(
        f"🔍 جاري البحث عن: **{query}**\n⏳ انتظر...",
        parse_mode="Markdown"
    )

    # إضافة كلمة قرآن كريم للبحث لو طلب قرآن
    search_query = f"قرآن كريم {query}" if is_quran else query

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _sync_yot_download, search_query)

    if not result["success"] or not result["file"]:
        await msg.edit_text(f"❌ لم أجد نتائج لـ: **{query}**\nجرب بكلمات مختلفة", parse_mode="Markdown")
        return True

    try:
        duration_str = ""
        if result["duration"]:
            m, s = divmod(int(result["duration"]), 60)
            duration_str = f"\n⏱️ المدة: {m}:{s:02d}"

        await msg.delete()
        caption = (
            f"🎵 **{result['title'][:50]}**"
            f"{duration_str}\n"
            f"🔍 بحث: {query}\n"
            f"تم التحميل بواسطة لينوكس 🤖"
        )
        await update.message.reply_audio(
            audio=open(result["file"], "rb"),
            caption=caption,
            parse_mode="Markdown",
            title=result["title"][:60],
            performer="لينوكس بوت"
        )
    except Exception as e:
        await msg.edit_text(f"❌ فشل الإرسال: {e}")
    finally:
        # تنظيف الملفات المؤقتة
        import shutil
        if result.get("tmpdir"):
            try: shutil.rmtree(result["tmpdir"])
            except: pass

    return True



# ══════════════════════════════════════════════════
#         📋 Queue نظام لـ يوت
# ══════════════════════════════════════════════════
import asyncio
from collections import deque

yot_queue    = deque()          # طابور الطلبات
yot_running  = False            # هل في تحميل جاري
YOT_MAX_Q    = 5                # أقصى عدد في الطابور

async def process_yot_queue(context):
    """معالجة طابور يوت بالتسلسل"""
    global yot_running
    if yot_running:
        return
    yot_running = True
    while yot_queue:
        task = yot_queue.popleft()
        try:
            await execute_yot_task(task, context)
        except Exception as e:
            logging.error(f"Queue task error: {e}")
        await asyncio.sleep(1)
    yot_running = False

async def execute_yot_task(task, context):
    """تنفيذ طلب يوت من الطابور"""
    update       = task["update"]
    query        = task["query"]
    is_video     = task["is_video"]
    quality      = task["quality"]
    msg          = task["msg"]
    user_name    = task.get("user_name", "")

    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _sync_yot_download, query, is_video, quality)

    if not result["success"] or not result["file"]:
        await msg.edit_text(f"❌ لم أجد نتائج لـ: **{query}**", parse_mode="Markdown")
        return

    try:
        duration_str = ""
        if result["duration"]:
            m, s = divmod(int(result["duration"]), 60)
            duration_str = f"\n⏱️ {m}:{s:02d}"

        await msg.delete()
        caption = (
            f"🎵 **{result['title'][:50]}**"
            f"{duration_str}\n"
            f"🔍 {query}\n"
            f"تم التحميل بواسطة لينوكس 🤖"
        )
        if is_video:
            await update.message.reply_video(
                video=open(result["file"], "rb"),
                caption=caption,
                parse_mode="Markdown",
                supports_streaming=True
            )
        else:
            await update.message.reply_audio(
                audio=open(result["file"], "rb"),
                caption=caption,
                parse_mode="Markdown",
                title=result["title"][:60],
                performer="لينوكس بوت"
            )
    except Exception as e:
        await msg.edit_text(f"❌ فشل الإرسال: {e}")
    finally:
        import shutil
        if result.get("tmpdir"):
            try: shutil.rmtree(result["tmpdir"])
            except: pass

# ══════════════════════════════════════════════════
#         ⏰ نظام التذكير
# ══════════════════════════════════════════════════
reminders_db = {}   # { "user_id_timestamp": {"user_id", "chat_id", "text", "time"} }

async def cmd_ذكرني(update, context):
    """
    /ذكرني [الوقت] [الرسالة]
    مثال: /ذكرني 30d اشرب دواء
    وحدات: m=دقيقة h=ساعة d=يوم
    """
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⏰ التذكير:\n\n"
            "/ذكرني [الوقت] [الرسالة]\n\n"
            "الوحدات:\n"
            "m = دقائق\n"
            "h = ساعات\n"
            "d = أيام\n\n"
            "أمثلة:\n"
            "/ذكرني 30m اشرب دواء\n"
            "/ذكرني 2h موعد طبيب\n"
            "/ذكرني 1d مهمة مهمة"
        )
        return

    time_str = context.args[0].lower()
    text     = " ".join(context.args[1:])
    seconds  = 0

    try:
        if time_str.endswith("m"):
            seconds = int(time_str[:-1]) * 60
        elif time_str.endswith("h"):
            seconds = int(time_str[:-1]) * 3600
        elif time_str.endswith("d"):
            seconds = int(time_str[:-1]) * 86400
        else:
            seconds = int(time_str) * 60
    except:
        await update.message.reply_text("❌ وقت غير صحيح! مثال: 30m أو 2h أو 1d")
        return

    if seconds < 60:
        await update.message.reply_text("❌ أقل وقت هو دقيقة واحدة!")
        return
    if seconds > 7 * 86400:
        await update.message.reply_text("❌ أقصى وقت هو 7 أيام!")
        return

    user    = update.effective_user
    chat_id = update.effective_chat.id
    remind_at = datetime.now() + timedelta(seconds=seconds)

    # حفظ التذكير
    key = f"{user.id}_{int(time.time())}"
    reminders_db[key] = {
        "user_id":   user.id,
        "chat_id":   chat_id,
        "text":      text,
        "remind_at": remind_at.timestamp(),
        "created":   datetime.now().strftime("%H:%M")
    }

    # جدولة التذكير
    context.job_queue.run_once(
        send_reminder,
        when=seconds,
        data={"key": key, "user_id": user.id, "chat_id": chat_id, "text": text, "name": user.first_name},
        name=key
    )

    time_human = ""
    if seconds < 3600:
        time_human = f"{seconds//60} دقيقة"
    elif seconds < 86400:
        time_human = f"{seconds//3600} ساعة"
    else:
        time_human = f"{seconds//86400} يوم"

    await update.message.reply_text(
        f"✅ تم ضبط التذكير!\n\n"
        f"📝 {text}\n"
        f"⏰ بعد {time_human}\n"
        f"🕐 الساعة {remind_at.strftime('%H:%M')}"
    )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """إرسال التذكير"""
    data = context.job.data
    try:
        await context.bot.send_message(
            data["chat_id"],
            f"⏰ **تذكير لـ {data['name']}!**\n\n📝 {data['text']}",
            parse_mode="Markdown"
        )
    except:
        try:
            await context.bot.send_message(
                data["user_id"],
                f"⏰ **تذكير!**\n\n📝 {data['text']}",
                parse_mode="Markdown"
            )
        except:
            pass
    # حذف من القاموس
    if data["key"] in reminders_db:
        del reminders_db[data["key"]]

async def cmd_تذكيراتي(update, context):
    user_id = update.effective_user.id
    my      = {k: v for k, v in reminders_db.items() if v["user_id"] == user_id}
    if not my:
        await update.message.reply_text("لا يوجد تذكيرات نشطة!")
        return
    text = "⏰ تذكيراتك النشطة:\n\n"
    for k, v in my.items():
        remind_at = datetime.fromtimestamp(v["remind_at"])
        text += f"• {v['text']}\n  الوقت: {remind_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    await update.message.reply_text(text)

# ══════════════════════════════════════════════════
#         📊 لوحة متصدرين يوت
# ══════════════════════════════════════════════════
yot_leaderboard = defaultdict(lambda: {"count": 0, "name": ""})

def update_yot_stats(user_id, name):
    yot_leaderboard[user_id]["count"] += 1
    yot_leaderboard[user_id]["name"]   = name

async def cmd_متصدري_يوت(update, context):
    if not yot_leaderboard:
        await update.message.reply_text("لا يوجد إحصائيات بعد! استخدم يوت أولاً")
        return
    sorted_lb = sorted(yot_leaderboard.items(), key=lambda x: x[1]["count"], reverse=True)[:10]
    medals    = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    text      = "🎵 متصدرو يوت:\n\n"
    for i, (uid, data) in enumerate(sorted_lb):
        text += f"{medals[i]} {data['name']} — {data['count']} تحميل\n"
    await update.message.reply_text(text)

# ══════════════════════════════════════════════════
#         📢 إرسال جماعي للمشرف
# ══════════════════════════════════════════════════
async def cmd_broadcast(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return

    text = ""
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text or ""
    elif context.args:
        text = " ".join(context.args)

    if not text:
        await update.message.reply_text(
            "📢 الإرسال الجماعي:\n"
            "رد على رسالة واكتب /broadcast\n"
            "أو /broadcast [الرسالة]"
        )
        return

    chat_id = update.effective_chat.id
    msg     = await update.message.reply_text("📤 جاري الإرسال...")

    try:
        members_count = await context.bot.get_chat_member_count(chat_id)
    except:
        members_count = 0

    sent = 0
    failed = 0

    # جلب قائمة الأعضاء المعروفين من الرتب والانذارات
    known_users = set()
    chat_id_str = str(chat_id)
    for uid in db.get("ranks", {}).get(chat_id_str, {}).keys():
        known_users.add(int(uid))
    for key in db.get("warnings", {}).keys():
        if key.startswith(chat_id_str + "_"):
            uid = key.split("_")[1]
            try: known_users.add(int(uid))
            except: pass

    broadcast_text = f"📢 **إعلان من المشرفين:**\n\n{text}"

    for uid in known_users:
        try:
            await context.bot.send_message(uid, broadcast_text, parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)  # تأخير لتجنب الحجب
        except:
            failed += 1

    await msg.edit_text(
        f"✅ تم الإرسال الجماعي!\n\n"
        f"✔️ نجح: {sent}\n"
        f"❌ فشل: {failed}\n"
        f"📊 إجمالي الأعضاء المعروفين: {len(known_users)}"
    )

# ══════════════════════════════════════════════════
#         🙍 إعدادات شخصية للمستخدم
# ══════════════════════════════════════════════════
async def cmd_اعداداتي(update, context):
    user_id = str(update.effective_user.id)
    prefs   = db.get("user_prefs", {}).get(user_id, {})
    city    = prefs.get("city", "غير محددة")
    quality = prefs.get("yot_quality", "عالية")

    keyboard = [
        [InlineKeyboardButton(f"🏙️ مدينتي: {city}",       callback_data="pref_city")],
        [InlineKeyboardButton(f"🎵 جودة يوت: {quality}",   callback_data="pref_quality")],
    ]
    await update.message.reply_text(
        f"⚙️ إعداداتك الشخصية:\n\n"
        f"🏙️ المدينة: {city}\n"
        f"🎵 جودة يوت: {quality}\n\n"
        f"اضغط للتعديل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cmd_مدينتي(update, context):
    if not context.args:
        await update.message.reply_text("/مدينتي [اسم المدينة]\nمثال: /مدينتي Cairo")
        return
    city    = " ".join(context.args)
    user_id = str(update.effective_user.id)
    db.setdefault("user_prefs", {}).setdefault(user_id, {})["city"] = city
    save_data(db)
    await update.message.reply_text(
        f"✅ تم حفظ مدينتك: {city}\n"
        f"الآن /صلاة و /طقس سيستخدمانها تلقائياً!"
    )


async def smart_reply(update, text, context=None):
    text_lower = text.lower().strip()
    for keyword, response in SMART_RESPONSES.items():
        if keyword in text_lower:
            await update.message.reply_text(response)
            return True

    name_patterns = ["اسمي","انا اسمي","اسمى"]
    for pattern in name_patterns:
        if pattern in text_lower:
            parts = text_lower.split(pattern)
            if len(parts) > 1:
                name = parts[1].strip().split()[0] if parts[1].strip() else update.effective_user.first_name
                await update.message.reply_text(random.choice([
                    f"اهلا {name}! يسعدنا وجودك معنا!",
                    f"مرحبا {name}! اسم جميل!",
                    f"اهلا وسهلا {name}!",
                ]))
                return True

    question_keywords = ["ما هو","من هو","ما هي","كيف","لماذا","متى","ما معنى","اشرح","وضح","افضل","انصحني"]
    is_question = any(kw in text_lower for kw in question_keywords) or text.endswith("?")
    if is_question and context:
        user_id = update.effective_user.id
        if not can_use_ai(user_id):
            await update.message.reply_text("تجاوزت حد الاسئلة، انتظر دقيقة!")
            return True
        ai_answer = await ask_ai(text)
        if ai_answer:
            await update.message.reply_text(f"🤖 {ai_answer}")
            return True
        await update.message.reply_text(
            "سؤال مثير! للاسف لا استطيع الإجابة على كل الاسئلة.\n"
            "يمكنك البحث على Google او سؤال المجموعة"
        )
        return True
    return False

# ══════════════════════════════════════════════════
#         🌟 القائمة الرئيسية
# ══════════════════════════════════════════════════
async def cmd_start(update, context):
    user      = update.effective_user
    chat      = update.effective_chat
    rank      = get_user_rank(chat.id, user.id)
    rank_info = RANKS.get(rank, RANKS["عضو"])

    if user.id == DEVELOPER_ID:
        total_groups   = len(db.get("settings", {}))
        total_warnings = len(db.get("warnings", {}))
        total_whispers = len(db.get("whispers", {}))
        sched          = len(db.get("scheduled_groups", []))
        dev_text = (
            "\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557\n"
            "\u2551   \U0001f5a5\ufe0f  \u0644\u0648\u062d\u0629 \u062a\u062d\u0643\u0645 \u0627\u0644\u0645\u0637\u0648\u0631   \u2551\n"
            "\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d\n\n"
            f"\U0001f468\u200d\U0001f4bb \u0623\u0647\u0644\u0627\u064b \u0628\u0643 \u064a\u0627 \u0645\u0637\u0648\u0631 \u0644\u064a\u0646\u0648\u0643\u0633!\n\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501 \U0001f4ca \u0625\u062d\u0635\u0627\u0626\u064a\u0627\u062a \u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"\U0001f465 \u0627\u0644\u0645\u062c\u0645\u0648\u0639\u0627\u062a: **{total_groups}**\n"
            f"\U0001f4c5 \u0645\u062c\u0645\u0648\u0639\u0627\u062a \u0627\u0644\u0623\u0630\u0643\u0627\u0631: **{sched}**\n"
            f"\u26a0\ufe0f \u0627\u0644\u0625\u0646\u0630\u0627\u0631\u0627\u062a: **{total_warnings}**\n"
            f"\U0001f917 \u0627\u0644\u0647\u0645\u0633\u0627\u062a: **{total_whispers}**\n\n"
            "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            "\U0001f4bb \u0631\u062a\u0628\u062a\u0643: \u0645\u0637\u0648\u0631 | \u0623\u0639\u0644\u0649 \u0635\u0644\u0627\u062d\u064a\u0629\n"
            "\U0001f511 \u062c\u0645\u064a\u0639 \u0627\u0644\u0623\u0648\u0627\u0645\u0631 \u0645\u062a\u0627\u062d\u0629 \u0644\u0643"
        )
        keyboard = [
            [InlineKeyboardButton("📊 الإحصائيات", callback_data="menu_stats"),
             InlineKeyboardButton("📜 السجل",       callback_data="menu_logs")],
            [InlineKeyboardButton("💾 نسخ احتياطي", callback_data="dev_backup"),
             InlineKeyboardButton("📋 الأوامر",     callback_data="menu_all")],
        ]
        await update.message.reply_text(dev_text, parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(keyboard))
        return

    rank_bar = "█" * rank_info["level"] + "░" * (10 - rank_info["level"])
    welcome_text = (
        "\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557\n"
        "\u2551     \U0001f916  \u0628\u0648\u062a \u0644\u064a\u0646\u0648\u0643\u0633 v4.0     \u2551\n"
        "\u2551   \u0646\u0638\u0627\u0645 \u0627\u0644\u062d\u0645\u0627\u064a\u0629 \u0627\u0644\u0645\u062a\u0643\u0627\u0645\u0644     \u2551\n"
        "\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d\n\n"
        f"\U0001f44b \u0623\u0647\u0644\u0627\u064b **{user.first_name}**!\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501 \U0001f3c5 \u0631\u062a\u0628\u062a\u0643 \u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"{rank_info['emoji']}  **{rank}**\n"
        f"[{rank_bar}] {rank_info['level']}/10\n\n"
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        "\u0627\u062e\u062a\u0631 \u0642\u0633\u0645\u0627\u064b \u0645\u0646 \u0627\u0644\u0642\u0627\u0626\u0645\u0629 \U0001f447"
    )
    keyboard = [
        [InlineKeyboardButton("🛡️ الحماية",      callback_data="menu_protection"),
         InlineKeyboardButton("🕌 إسلاميات",     callback_data="menu_islamic")],
        [InlineKeyboardButton("🌤️ خدمات",        callback_data="menu_services"),
         InlineKeyboardButton("⚙️ الإعدادات",    callback_data="menu_settings")],
        [InlineKeyboardButton("🏅 الرتب",         callback_data="menu_ranks"),
         InlineKeyboardButton("📊 معلومات",       callback_data="menu_info")],
        [InlineKeyboardButton("🤫 الهمسة",        callback_data="menu_whisper"),
         InlineKeyboardButton("⚡ الاختصارات",    callback_data="menu_shortcuts")],
        [InlineKeyboardButton("📥 تحميل",         callback_data="menu_download"),
         InlineKeyboardButton("🔧 أدوات",         callback_data="menu_tools")],
    ]
    await update.message.reply_text(welcome_text, parse_mode="Markdown",
                                     reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_الاوامر(update, context):
    keyboard = [
        [InlineKeyboardButton("الحماية",    callback_data="menu_protection"),
         InlineKeyboardButton("اسلاميات",   callback_data="menu_islamic")],
        [InlineKeyboardButton("خدمات",      callback_data="menu_services"),
         InlineKeyboardButton("الاعدادات",  callback_data="menu_settings")],
        [InlineKeyboardButton("الرتب",       callback_data="menu_ranks"),
         InlineKeyboardButton("معلومات",     callback_data="menu_info")],
        [InlineKeyboardButton("الهمسة",      callback_data="menu_whisper"),
         InlineKeyboardButton("الاختصارات",  callback_data="menu_shortcuts")],
    ]
    await update.message.reply_text(
        "قائمة الاوامر الكاملة\n\nاختر القسم:",
        reply_markup=InlineKeyboardMarkup(keyboard))

# ══════════════════════════════════════════════════
#         🏅 نظام الرتب
# ══════════════════════════════════════════════════
async def cmd_رتبتي(update, context):
    user      = update.effective_user
    rank      = get_user_rank(update.effective_chat.id, user.id)
    rank_info = RANKS.get(rank, RANKS["عضو"])
    await update.message.reply_text(
        f"رتبتك في المجموعة\n\n"
        f"الاسم: {user.first_name}\n"
        f"{rank_info['emoji']} الرتبة: {rank}\n"
        f"المستوى: {rank_info['level']}")

async def cmd_تعيين_رتبة(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    caller_level = get_rank_level(update.effective_chat.id, update.effective_user.id)
    if not context.args:
        await update.message.reply_text(
            "طريقة الاستخدام:\nرد على رسالة شخص واكتب:\n/تعيين_رتبة [الرتبة]\n\n"
            "الرتب المتاحة:\nمشرف - مدير - ادمن - مالك_اساسي"); return
    target = await get_target(update, context)
    if not target: return
    rank_name = context.args[0]
    if rank_name not in RANKS:
        await update.message.reply_text("رتبة غير معروفة!"); return
    if RANKS[rank_name]["level"] >= caller_level and update.effective_user.id != DEVELOPER_ID:
        await update.message.reply_text("لا يمكنك تعيين رتبة أعلى من رتبتك!"); return
    set_user_rank(update.effective_chat.id, target.id, rank_name)
    ri = RANKS[rank_name]
    await update.message.reply_text(f"تم تعيين الرتبة\n\n{target.first_name}\n{ri['emoji']} الرتبة الجديدة: {rank_name}")

async def cmd_الرتب(update, context):
    chat_id    = str(update.effective_chat.id)
    ranks_data = db.get("ranks", {}).get(chat_id, {})
    text = "رتب الاعضاء في المجموعة:\n\n"
    if not ranks_data:
        text += "لا يوجد اعضاء برتب مخصصة بعد!"
    else:
        for uid, rank in ranks_data.items():
            ri = RANKS.get(rank, RANKS["عضو"])
            text += f"{ri['emoji']} ID {uid} - {rank}\n"
    await update.message.reply_text(text)

# ══════════════════════════════════════════════════
#         🛡️ أوامر الحماية
# ══════════════════════════════════════════════════
async def cmd_حظر(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    if target.id == DEVELOPER_ID:
        await update.message.reply_text("⛔ لا يمكن حظر المطور!"); return
    chat_id = str(update.effective_chat.id)
    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else "لا يوجد سبب"
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        # حفظ في قائمة المحظورين
        if "banned_users" not in db:
            db["banned_users"] = {}
        if chat_id not in db["banned_users"]:
            db["banned_users"][chat_id] = {}
        db["banned_users"][chat_id][str(target.id)] = {
            "name": target.first_name,
            "username": f"@{target.username}" if target.username else "لا يوجد",
            "reason": reason,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "by": update.effective_user.first_name
        }
        save_data(db)
        await update.message.reply_text(
            f"🔨 **تم الحظر**\n\n"
            f"👤 [{target.first_name}](tg://user?id={target.id})\n"
            f"🆔 `{target.id}`\n"
            f"📋 السبب: {reason}\n"
            f"👮 بواسطة: {update.effective_user.first_name}",
            parse_mode="Markdown"
        )
        log_action("حظر", update.effective_user.first_name, target.first_name, update.effective_chat.title or "", reason)
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def cmd_رفع_حظر(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    chat_id = str(update.effective_chat.id)
    try:
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        # إزالة من قائمة المحظورين
        if "banned_users" in db and chat_id in db["banned_users"]:
            db["banned_users"][chat_id].pop(str(target.id), None)
            save_data(db)
        await update.message.reply_text(
            f"✅ **تم رفع الحظر**\n\n"
            f"👤 {target.first_name}\n"
            f"👮 بواسطة: {update.effective_user.first_name}",
            parse_mode="Markdown"
        )
        log_action("رفع حظر", update.effective_user.first_name, target.first_name, update.effective_chat.title or "")
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def cmd_كتم(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    if target.id == DEVELOPER_ID:
        await update.message.reply_text("⛔ لا يمكن كتم المطور!"); return
    chat_id = str(update.effective_chat.id)
    try:
        # كتم دائم بدون مدة محددة
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False
            )
        )
        # حفظ في قائمة المكتومين
        if "muted_users" not in db:
            db["muted_users"] = {}
        if chat_id not in db["muted_users"]:
            db["muted_users"][chat_id] = {}
        db["muted_users"][chat_id][str(target.id)] = {
            "name": target.first_name,
            "username": f"@{target.username}" if target.username else "لا يوجد",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "by": update.effective_user.first_name
        }
        save_data(db)
        await update.message.reply_text(
            f"🔇 **تم الكتم الدائم**\n\n"
            f"👤 {target.first_name}\n"
            f"🆔 `{target.id}`\n"
            f"👮 بواسطة: {update.effective_user.first_name}\n\n"
            f"_للرفع: `/فك_كتم` أو رد على رسالته_",
            parse_mode="Markdown"
        )
        log_action("كتم دائم", update.effective_user.first_name, target.first_name, update.effective_chat.title or "", "كتم دائم")
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def cmd_فك_كتم(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    chat_id = str(update.effective_chat.id)
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        # إزالة من قائمة المكتومين
        if "muted_users" in db and chat_id in db["muted_users"]:
            db["muted_users"][chat_id].pop(str(target.id), None)
            save_data(db)
        await update.message.reply_text(
            f"🔊 **تم رفع الكتم**\n\n"
            f"👤 {target.first_name}\n"
            f"👮 بواسطة: {update.effective_user.first_name}",
            parse_mode="Markdown"
        )
        log_action("رفع كتم", update.effective_user.first_name, target.first_name, update.effective_chat.title or "")
    except TelegramError as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def cmd_رفع_كتم(update, context):
    await cmd_فك_كتم(update, context)

async def cmd_طرد(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    if target.id == DEVELOPER_ID:
        await update.message.reply_text("لا يمكن طرد المطور!"); return
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target.id)
        await update.message.reply_text(f"تم طرد {target.first_name}")
    except TelegramError as e:
        await update.message.reply_text(f"فشل: {e}")

async def cmd_انذار(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    if target.id == DEVELOPER_ID:
        await update.message.reply_text("لا يمكن انذار المطور!"); return
    chat_id  = str(update.effective_chat.id)
    settings = get_settings(chat_id)
    reason   = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else "مخالفة القواعد"
    wc = add_warning(chat_id, str(target.id))
    mw = settings.get("max_warnings", 3)
    msg = f"انذار\n{target.first_name}\nالسبب: {reason}\nالانذارات: {wc}/{mw}"
    if wc >= mw:
        msg += "\n\nتم الحظر تلقائيا!"
        try:
            await context.bot.ban_chat_member(update.effective_chat.id, target.id)
            reset_warnings(chat_id, str(target.id))
        except: pass
    await update.message.reply_text(msg)
    log_action("انذار", update.effective_user.first_name, target.first_name, update.effective_chat.title or "", reason)

async def cmd_الانذارات(update, context):
    target = await get_target(update, context)
    if not target: target = update.effective_user
    chat_id = str(update.effective_chat.id)
    warns   = get_warnings(chat_id, str(target.id))
    max_w   = get_settings(chat_id).get("max_warnings", 3)
    status  = "لا مشاكل" if warns == 0 else "تحت المراقبة" if warns < max_w else "على وشك الحظر"
    await update.message.reply_text(f"انذارات {target.first_name}\n{warns}/{max_w}\n{status}")

async def cmd_مسح_انذارات(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    reset_warnings(str(update.effective_chat.id), str(target.id))
    await update.message.reply_text(f"تم مسح انذارات {target.first_name}")

async def cmd_تثبيت(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    if not update.message.reply_to_message:
        await update.message.reply_text("رد على الرسالة التي تريد تثبيتها!"); return
    try:
        await context.bot.pin_chat_message(update.effective_chat.id, update.message.reply_to_message.message_id)
        await update.message.reply_text("تم التثبيت!")
    except:
        await update.message.reply_text("فشل التثبيت!")

async def cmd_حذف(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    if update.message.reply_to_message:
        try:
            await update.message.reply_to_message.delete()
            await update.message.delete()
        except:
            await update.message.reply_text("فشل الحذف!")
    else:
        await update.message.reply_text("رد على الرسالة!")

async def cmd_ترقية(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id, target.id,
            can_delete_messages=True, can_restrict_members=True,
            can_pin_messages=True, can_invite_users=True)
        set_user_rank(update.effective_chat.id, target.id, "مشرف")
        await update.message.reply_text(f"تم ترقية {target.first_name} الى مشرف!")
    except TelegramError as e:
        await update.message.reply_text(f"فشل: {e}")

async def cmd_تخفيض(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    target = await get_target(update, context)
    if not target: return
    try:
        await context.bot.promote_chat_member(
            update.effective_chat.id, target.id,
            can_delete_messages=False, can_restrict_members=False, can_pin_messages=False)
        set_user_rank(update.effective_chat.id, target.id, "عضو")
        await update.message.reply_text(f"تم تخفيض {target.first_name}")
    except TelegramError as e:
        await update.message.reply_text(f"فشل: {e}")

# ══════════════════════════════════════════════════
#         ⚙️ الإعدادات
# ══════════════════════════════════════════════════
async def cmd_الاعدادات(update, context):
    is_cb = update.callback_query is not None
    if is_cb:
        chat_id = str(update.callback_query.message.chat.id)
        user_id = update.callback_query.from_user.id
        if not await is_admin(update, user_id):
            await update.callback_query.answer("للمشرفين فقط!", show_alert=True); return
        send = update.callback_query.message.reply_text
    else:
        if not await is_admin(update, update.effective_user.id):
            await update.message.reply_text("للمشرفين فقط!"); return
        chat_id = str(update.effective_chat.id)
        send    = update.message.reply_text

    s = get_settings(chat_id)
    def st(k): return "فعّال" if s.get(k) else "متوقف"
    keyboard = [
        [InlineKeyboardButton(f"مكافحة الفلود: {st('antiflood')}",   callback_data=f"toggle_antiflood_{chat_id}"),
         InlineKeyboardButton(f"مكافحة الروابط: {st('antilink')}",   callback_data=f"toggle_antilink_{chat_id}")],
        [InlineKeyboardButton(f"مكافحة الاباحي: {st('antiporn')}",   callback_data=f"toggle_antiporn_{chat_id}"),
         InlineKeyboardButton(f"فلتر الكلمات: {st('antibadwords')}",  callback_data=f"toggle_antibadwords_{chat_id}")],
        [InlineKeyboardButton(f"مكافحة البوتات: {st('antibot')}",    callback_data=f"toggle_antibot_{chat_id}"),
         InlineKeyboardButton(f"رسائل الترحيب: {st('welcome')}",     callback_data=f"toggle_welcome_{chat_id}")],
    ]
    await send(
        f"اعدادات الحماية\nالانذارات القصوى: {s['max_warnings']}\nمدة الكتم: {s['mute_duration']} دقيقة",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_ترحيب(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text("/ترحيب رسالتك\nالمتغيرات: {name} اسم العضو"); return
    db.setdefault("welcome", {})[str(update.effective_chat.id)] = " ".join(context.args)
    save_data(db)
    await update.message.reply_text("تم تعيين رسالة الترحيب!")

async def cmd_اضف_كلمة(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text("/اضف_كلمة [كلمة]"); return
    chat_id = str(update.effective_chat.id)
    word    = " ".join(context.args).lower()
    bl      = db.setdefault("blacklist", {}).setdefault(chat_id, [])
    if word not in bl:
        bl.append(word); save_data(db)
        await update.message.reply_text(f"تم اضافة: {word}")
    else:
        await update.message.reply_text("الكلمة موجودة!")

async def cmd_حذف_كلمة(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text("/حذف_كلمة [كلمة]"); return
    chat_id = str(update.effective_chat.id)
    word    = " ".join(context.args).lower()
    bl      = db.get("blacklist", {}).get(chat_id, [])
    if word in bl:
        bl.remove(word); save_data(db)
        await update.message.reply_text(f"تم حذف: {word}")
    else:
        await update.message.reply_text("الكلمة غير موجودة!")

async def cmd_الكلمات(update, context):
    chat_id = str(update.effective_chat.id)
    words   = db.get("blacklist", {}).get(chat_id, [])
    if not words:
        await update.message.reply_text("القائمة السوداء فارغة!"); return
    await update.message.reply_text("الكلمات المحظورة:\n\n" + "\n".join([f"- {w}" for w in words]))

# ══════════════════════════════════════════════════
#         📊 المعلومات
# ══════════════════════════════════════════════════
async def cmd_معلومات(update, context):
    target = await get_target(update, context)
    if not target: target = update.effective_user
    chat_id = str(update.effective_chat.id)
    try:
        member     = await update.effective_chat.get_member(target.id)
        status_map = {"creator":"مالك","administrator":"مشرف","member":"عضو",
                      "restricted":"مقيد","left":"غادر","banned":"محظور"}
        tg_status  = status_map.get(member.status, "غير معروف")
    except:
        tg_status = "غير معروف"
    warns    = get_warnings(chat_id, str(target.id))
    rank     = get_user_rank(update.effective_chat.id, target.id)
    ri       = RANKS.get(rank, RANKS["عضو"])
    username = f"@{target.username}" if target.username else "لا يوجد"
    await update.message.reply_text(
        f"معلومات المستخدم\n\n"
        f"ID: {target.id}\n"
        f"الاسم: {target.first_name}\n"
        f"اليوزر: {username}\n"
        f"الحالة: {tg_status}\n"
        f"{ri['emoji']} الرتبة: {rank}\n"
        f"الانذارات: {warns}/{get_settings(chat_id)['max_warnings']}")

async def cmd_المجموعة(update, context):
    chat    = update.effective_chat
    chat_id = str(chat.id)
    s       = get_settings(chat_id)
    try:    count = await context.bot.get_chat_member_count(chat.id)
    except: count = "غير متاح"
    await update.message.reply_text(
        f"معلومات المجموعة\n\n"
        f"{chat.title}\nID: {chat.id}\nالاعضاء: {count}\n\n"
        f"حالة الحماية:\n"
        f"مكافحة الفلود: {'فعّال' if s.get('antiflood') else 'متوقف'}\n"
        f"مكافحة الروابط: {'فعّال' if s.get('antilink') else 'متوقف'}\n"
        f"مكافحة الاباحي: {'فعّال' if s.get('antiporn') else 'متوقف'}\n"
        f"فلتر الكلمات: {'فعّال' if s.get('antibadwords') else 'متوقف'}")

async def cmd_السجل(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("للمشرفين فقط!"); return
    logs = db.get("logs", [])[-15:]
    if not logs:
        await update.message.reply_text("لا يوجد سجلات!"); return
    text = "آخر 15 اجراء:\n\n"
    for log in reversed(logs):
        text += f"{log['time']}\n{log['action']} | {log['target']}\nبواسطة: {log['admin']}\n\n"
    if len(text) > 4000: text = text[:4000] + "..."
    await update.message.reply_text(text)

# ══════════════════════════════════════════════════
#         🕌 الإسلاميات
# ══════════════════════════════════════════════════
async def cmd_قران(update, context):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("/قران [سورة] [آية]\nمثال: /قران 2 255 آية الكرسي"); return
    try:
        surah, ayah = int(context.args[0]), int(context.args[1])
        url = f"https://api.alquran.cloud/v1/ayah/{surah}:{ayah}/ar.alafasy"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data["status"] == "OK":
            d = data["data"]
            await update.message.reply_text(f"{d['surah']['name']} - الآية {d['numberInSurah']}\n\n{d['text']}")
        else:
            await update.message.reply_text("لم يتم العثور على الآية!")
    except ValueError:
        await update.message.reply_text("ادخل ارقاما صحيحة!")
    except Exception:
        await update.message.reply_text("خطأ في الاتصال! جرب مرة أخرى.")

async def cmd_بحث_قران(update, context):
    if not context.args:
        await update.message.reply_text("/بحث_قران [كلمة]"); return
    keyword = " ".join(context.args)
    try:
        url = f"https://api.alquran.cloud/v1/search/{urllib.parse.quote(keyword)}/all/ar"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data["status"] == "OK" and data["data"]["count"] > 0:
            matches = data["data"]["matches"][:5]
            text    = f"نتائج: {keyword} ({data['data']['count']} نتيجة)\n\n"
            for m in matches:
                t     = m["text"][:100] + "..." if len(m["text"]) > 100 else m["text"]
                text += f"{m['surah']['name']} آية {m['numberInSurah']}\n{t}\n\n"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text(f"لا نتائج لـ: {keyword}")
    except Exception:
        await update.message.reply_text("خطأ في البحث!")

async def cmd_حديث(update, context):
    await update.message.reply_text(f"حديث شريف\n\nقال النبي صلى الله عليه وسلم:\n\n{random.choice(AHADITH)}\n\nاللهم صل وسلم على نبينا محمد")

async def cmd_اذكار(update, context):
    keyboard = [
        [InlineKeyboardButton("اذكار الصباح", callback_data="azkar_sabah"),
         InlineKeyboardButton("اذكار المساء", callback_data="azkar_masa")],
        [InlineKeyboardButton("ادعية",        callback_data="azkar_dua"),
         InlineKeyboardButton("تسبيح",        callback_data="azkar_tasbih")]
    ]
    await update.message.reply_text("الاذكار والادعية\nاختر:", reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_صباح(update, context):
    await update.message.reply_text(f"اذكار الصباح\n\n{random.choice(AZKAR_SABAH)}\n\naللهم بارك لنا في صباحنا")

async def cmd_مساء(update, context):
    await update.message.reply_text(f"اذكار المساء\n\n{random.choice(AZKAR_MASA)}\n\naللهم بارك لنا في مساءنا")

async def cmd_دعاء(update, context):
    await update.message.reply_text(f"دعاء\n\n{random.choice(ADIYA)}\n\naللهم آمين")

async def cmd_اسماء_الله(update, context):
    name, meaning = random.choice(ALLAH_NAMES)
    await update.message.reply_text(f"من اسماء الله الحسنى\n\n{name}\n\n{meaning}\n\nسبحانه وتعالى")

async def cmd_صلاة(update, context):
    user_id = str(update.effective_user.id)
    saved   = db.get("user_prefs", {}).get(user_id, {}).get("city", "")
    if not context.args and not saved:
        await update.message.reply_text("/صلاة [المدينة]\nأو احفظ مدينتك بـ /مدينتي Cairo"); return
    city = " ".join(context.args) if context.args else saved
    try:
        url = f"https://api.aladhan.com/v1/timingsByCity?city={urllib.parse.quote(city)}&country=&method=4"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data["code"] == 200:
            t = data["data"]["timings"]
            await update.message.reply_text(
                f"مواقيت الصلاة - {city}\n{data['data']['date']['readable']}\n\n"
                f"الفجر: {t['Fajr']}\nالشروق: {t['Sunrise']}\nالظهر: {t['Dhuhr']}\n"
                f"العصر: {t['Asr']}\nالمغرب: {t['Maghrib']}\nالعشاء: {t['Isha']}")
    except Exception:
        await update.message.reply_text("اكتب اسم المدينة بالانجليزية مثل: /صلاة Cairo")

# ══════════════════════════════════════════════════
#         🌤️ الخدمات
# ══════════════════════════════════════════════════
async def cmd_طقس(update, context):
    user_id = str(update.effective_user.id)
    saved   = db.get("user_prefs", {}).get(user_id, {}).get("city", "")
    if not context.args and not saved:
        await update.message.reply_text("/طقس [المدينة]\nأو احفظ مدينتك بـ /مدينتي Cairo"); return
    city = " ".join(context.args) if context.args else saved
    try:
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        c    = data["current_condition"][0]
        temp = int(c["temp_C"])
        icon = "حار جدا" if temp >= 35 else "مشمس" if temp >= 25 else "معتدل" if temp >= 15 else "بارد"
        await update.message.reply_text(
            f"الطقس في {city}\n\n"
            f"الحرارة: {c['temp_C']} درجة ({icon})\n"
            f"الاحساس: {c['FeelsLikeC']} درجة\n"
            f"الرطوبة: {c['humidity']}%\n"
            f"الرياح: {c['windspeedKmph']} كم/ساعة")
    except Exception:
        await update.message.reply_text("اكتب اسم المدينة بالانجليزية مثل: /طقس Cairo")

async def cmd_الوقت(update, context):
    now  = datetime.now()
    days = ["الاثنين","الثلاثاء","الاربعاء","الخميس","الجمعة","السبت","الاحد"]
    await update.message.reply_text(
        f"الوقت والتاريخ\n\n{now.strftime('%Y-%m-%d')}\n{now.strftime('%H:%M:%S')}\n{days[now.weekday()]}")

async def cmd_التاريخ(update, context):
    try:
        today = date.today()
        url   = f"https://api.aladhan.com/v1/gToH?date={today.strftime('%d-%m-%Y')}"
        req   = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data["code"] == 200:
            h = data["data"]["hijri"]
            g = data["data"]["gregorian"]
            await update.message.reply_text(
                f"التاريخ\n\nالهجري: {h['day']} {h['month']['ar']} {h['year']}\n"
                f"الميلادي: {g['date']}\nاليوم: {h['weekday']['ar']}")
    except Exception:
        await update.message.reply_text(f"التاريخ: {date.today()}")

# ══════════════════════════════════════════════════
#         🛡️ الحماية التلقائية
# ══════════════════════════════════════════════════
async def welcome_member(update, context):
    chat_id  = str(update.effective_chat.id)
    settings = get_settings(chat_id)
    for member in update.message.new_chat_members:
        if member.id == DEVELOPER_ID:
            await update.message.reply_text(
                f"اهلا بمطور البوت!\n\n{member.first_name} هو المطور الذي صنع هذا البوت\nyملك أعلى صلاحية في البوت\nنرحب بك دائما!")
            continue
        if member.is_bot:
            if settings.get("antibot"):
                try:
                    await context.bot.ban_chat_member(update.effective_chat.id, member.id)
                    await update.message.reply_text("تم طرد البوت تلقائيا!")
                except: pass
            continue

        # anti-raid
        if is_raid(update.effective_chat.id):
            asyncio.create_task(activate_lockdown(context, update.effective_chat.id, settings.get("raid_lock_duration", 30)))
            await update.message.reply_text("تحذير: هجوم جماعي! تم تفعيل الاغلاق التلقائي.")

        daily_stats[str(update.effective_chat.id)]["new_members"] += 1
        if not settings.get("welcome"): continue
        custom = db.get("welcome", {}).get(chat_id)
        text   = custom.replace("{name}", member.first_name) if custom else (
            f"اهلا بـ {member.first_name} في مجموعتنا!\n\n"
            f"قواعد المجموعة:\n- احترم الجميع\n- ممنوع الاعلانات\n- ممنوع المحتوى المسيء\n\n"
            f"اكتب /الاوامر لمعرفة خدمات البوت!")
        keyboard = [[InlineKeyboardButton("القواعد", callback_data=f"rules_{chat_id}")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def goodbye_member(update, context):
    if update.message.left_chat_member and not update.message.left_chat_member.is_bot:
        daily_stats[str(update.effective_chat.id)]["left_members"] += 1
        await update.message.reply_text(f"وداعا {update.message.left_chat_member.first_name}!")

async def check_message(update, context):
    if not update.message or not update.effective_user: return
    user    = update.effective_user
    chat    = update.effective_chat
    chat_id = str(chat.id)
    if await is_admin(update, user.id):
        # المشرف ممكن يقفل/يفتح بالكلام
        if text:
            await handle_chat_lock(update, context)
        return

    settings = get_settings(chat_id)
    text     = update.message.text or update.message.caption or ""

    # فحص قفل الدردشة
    if await delete_if_locked(update, context):
        return

    # فحص الاختصارات أولا
    if text and update.message.reply_to_message:
        if await handle_shortcut(update, context):
            return

    # فحص الأوامر المخصصة
    if text and text.startswith("!"):
        if await handle_custom_cmd(update, context):
            return

    # فحص تاك
    if text and (text.lower().startswith("يوت ") or text.lower().startswith("يوت ")):
        if await handle_yot_message(update, context):
            return

    # فحص الفلود
    if settings.get("antiflood") and is_flooding(user.id):
        try: await update.message.delete()
        except: pass
        try:
            await context.bot.restrict_chat_member(
                chat.id, user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(minutes=5))
        except: pass
        wc = add_warning(chat_id, str(user.id))
        await chat.send_message(f"{user.first_name} تم كتمك بسبب الفلود! انذار {wc}/{settings['max_warnings']}")
        await check_max_warns(context, chat, user, chat_id, settings)
        return

    # تتبع الإحصائيات
    daily_stats[chat_id]["messages"] += 1

    if text:
        extra_bl = db.get("blacklist", {}).get(chat_id, [])
        if settings.get("antibadwords") and contains_bad_words(text, extra_bl):
            daily_stats[chat_id]["violations"] += 1
            await notify_admins(context, chat, user, update.message, "كلمة محظورة", update.message.message_id)
            wc = add_warning(chat_id, str(user.id))
            await chat.send_message(f"{user.first_name} رسالتك تحتوي على كلمة محظورة! انذار {wc}/{settings['max_warnings']}")
            await check_max_warns(context, chat, user, chat_id, settings)
            return
        if settings.get("antiporn") and contains_porn(text):
            daily_stats[chat_id]["violations"] += 1
            try: await update.message.delete()
            except: pass
            await notify_admins(context, chat, user, update.message, "محتوى إباحي", update.message.message_id)
            wc = add_warning(chat_id, str(user.id))
            await chat.send_message(f"{user.first_name} محتوى غير لائق! انذار {wc}/{settings['max_warnings']}")
            await check_max_warns(context, chat, user, chat_id, settings)
            return
        if settings.get("antilink") and contains_spam(text) and not is_whitelisted(text, chat.id):
            daily_stats[chat_id]["violations"] += 1
            try: await update.message.delete()
            except: pass
            await notify_admins(context, chat, user, update.message, "رابط مشبوه", update.message.message_id)
            wc = add_warning(chat_id, str(user.id))
            await chat.send_message(f"{user.first_name} ممنوع الروابط! انذار {wc}/{settings['max_warnings']}")
            await check_max_warns(context, chat, user, chat_id, settings)
            return

        # ردود ذكية في الخاص أو عند المنشن
        bot_username = context.bot.username
        if (chat.type == "private" or
            (update.message.reply_to_message and
             update.message.reply_to_message.from_user.id == context.bot.id) or
            (bot_username and f"@{bot_username}" in text)):
            clean_text = text.replace(f"@{bot_username}", "").strip() if bot_username else text
            await smart_reply(update, clean_text, context)

async def handle_private_message(update, context):
    """رسائل الخاص - للهمسة وغيره"""
    if update.effective_chat.type != "private": return
    if await handle_whisper_input(update, context): return
    text = update.message.text or ""
    if URL_PATTERN.search(text):
        await handle_url_message(update, context)
        return
    if await handle_yot_message(update, context): return
    await smart_reply(update, text, context)

# ══════════════════════════════════════════════════
#         🎮 معالج الأزرار
# ══════════════════════════════════════════════════
async def handle_buttons(update, context):
    query = update.callback_query
    await query.answer()
    data  = query.data

    # أزرار التحميل
    if data.startswith("dl_"):
        url = data[3:]
        if url == "cancel":
            await query.message.delete()
            return
        await query.message.delete()
        # أنشئ update وهمي للتحميل
        await download_and_send(update, context, url)
        return

    if data.startswith("mod_"):
        parts = data.split("_", 3)
        if len(parts) >= 4:
            await handle_mod_action(query, data)
        return

    if data.startswith("whisper_read_"):
        await handle_whisper_read(query, data[len("whisper_read_"):])
        return

    menu_texts = {
        "menu_protection": (
            "اوامر الحماية:\n\n"
            "ادارة الاعضاء:\n"
            "/حظر - /رفع_حظر\n"
            "/كتم [دقائق] - /رفع_كتم\n"
            "/طرد - /انذار [سبب]\n"
            "/الانذارات - /مسح_انذارات\n\n"
            "ادوات المشرف:\n"
            "/ترقية - /تخفيض - /تثبيت - /حذف\n\n"
            "Anti-Raid:\n"
            "/اغلاق [دقائق] - /رفع_اغلاق\n\n"
            "الاعدادات:\n"
            "/الاعدادات - /ترحيب\n"
            "/اضف_كلمة - /حذف_كلمة - /الكلمات"
        ),
        "menu_islamic": (
            "الاوامر الاسلامية:\n\n"
            "/قران [سورة] [آية]\n"
            "/بحث_قران [كلمة]\n"
            "/حديث\n/اذكار\n/صباح\n/مساء\n/دعاء\n"
            "/اسماء_الله\n/صلاة [مدينة]\n\n"
            "الاذكار المجدولة:\n"
            "/جدولة - لتفعيل/ايقاف الاذكار التلقائية"
        ),
        "menu_services": (
            "الخدمات والادوات:\n\n"
            "/طقس [مدينة]\n"
            "/الوقت\n"
            "/التاريخ\n\n"
            "الادوات:\n"
            "/عملة [مبلغ] [عملة] - تحويل العملات\n"
            "/حاسبة [عملية] - حاسبة\n"
            "/لخص - تلخيص نص\n"
            "/ترجم - ترجمة للعربية\n"
            "/تحميل [رابط] - تحميل فيديو/صوت\n\n"
            "البلاغات:\n"
            "/report - الابلاغ عن رسالة"
        ),
        "menu_services_UNUSED": (
            "الخدمات:\n\n"
            "/طقس [مدينة]\n"
            "/الوقت\n"
            "/التاريخ\n\n"
            "التحميل:\n"
            "/تحميل [رابط] - تحميل فيديو/صوت من أي منصة\n"
            "أو أرسل الرابط مباشرة وسيتم اكتشافه تلقائياً"
        ),
        "menu_info": (
            "اوامر المعلومات:\n\n"
            "/معلومات - معلومات مستخدم\n"
            "/المجموعة - معلومات المجموعة\n"
            "/السجل - سجل المخالفات\n"
            "/الاحصائيات - احصائيات البوت (للمطور)"
        ),
        "menu_ranks": (
            "نظام الرتب:\n\n"
            "مطور - اعلى صلاحية\n"
            "مالك_اساسي - صاحب المجموعة\n"
            "ادمن - صلاحيات واسعة\n"
            "مدير - صلاحيات متوسطة\n"
            "مشرف - صلاحيات اساسية\n"
            "عضو - عضو عادي\n\n"
            "الاوامر:\n"
            "/رتبتي\n/تعيين_رتبة [الرتبة]\n/الرتب"
        ),
        "menu_whisper": (
            "نظام الهمسة:\n\n"
            "كيف تستخدمه:\n"
            "1. رد على رسالة الشخص الذي تريد مهامسته\n"
            "2. اكتب /همسة\n"
            "3. البوت سيطلب منك النص في الخاص\n"
            "4. اكتب همستك\n"
            "5. تصل للشخص وحده!\n\n"
            "الهمسة مشفرة ولا يستطيع احد قراءتها غير المستقبل.\n"
            "اذا حاول احد فتحها ستصلك رسالة بذلك."
        ),
        "menu_shortcuts": (
            "نظام الاختصارات:\n\n"
            "اضافة اختصار:\n"
            "/اختصار [كلمة] [الاكشن]\n\n"
            "مثال: /اختصار مم حظر\n"
            "الان عند الرد على شخص وكتابة 'مم' يتم حظره!\n\n"
            "الاكشنات المتاحة:\n"
            "حظر - كتم - طرد - انذار\n\n"
            "اوامر:\n"
            "/الاختصارات - عرض الاختصارات\n"
            "/حذف_اختصار [كلمة]"
        ),
    }

    if data in menu_texts:
        await query.message.reply_text(menu_texts[data])
        return

    if data == "menu_settings":
        if await is_admin(update, query.from_user.id):
            await cmd_الاعدادات(update, context)
        else:
            await query.answer("للمشرفين فقط!", show_alert=True)
        return

    if data.startswith("toggle_"):
        if not await is_admin(update, query.from_user.id):
            await query.answer("للمشرفين فقط!", show_alert=True); return
        parts   = data.split("_", 2)
        setting = parts[1]
        chat_id = parts[2]
        s       = get_settings(chat_id)
        s[setting] = not s.get(setting, True)
        db["settings"][chat_id] = s
        save_data(db)
        await query.answer("تم التفعيل!" if s[setting] else "تم الايقاف!")
        await cmd_الاعدادات(update, context)
        return

    if data.startswith("rules_"):
        await query.message.reply_text(
            "قواعد المجموعة:\n\n"
            "1. احترم الجميع\n"
            "2. ممنوع السبام\n"
            "3. ممنوع المحتوى المسيء\n"
            "4. ممنوع الروابط\n"
            "5. لغة محترمة\n\n"
            "المخالفة = انذار والانذارات = حظر!")
        return

    # فك الكتم من الزر
    if data.startswith("unmute_"):
        parts = data.split("_")
        target_id = int(parts[1])
        chat_id_btn = int(parts[2])
        if not await is_admin(update, query.from_user.id):
            await query.answer("🚫 للمشرفين فقط!", show_alert=True); return
        try:
            await context.bot.restrict_chat_member(
                chat_id_btn, target_id,
                permissions=ChatPermissions(
                    can_send_messages=True, can_send_media_messages=True,
                    can_send_polls=True, can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            chat_str = str(chat_id_btn)
            if "muted_users" in db and chat_str in db["muted_users"]:
                name = db["muted_users"][chat_str].get(str(target_id), {}).get("name", "المستخدم")
                db["muted_users"][chat_str].pop(str(target_id), None)
                save_data(db)
                await query.answer(f"✅ تم رفع الكتم عن {name}!", show_alert=True)
                await query.message.edit_text(f"✅ تم رفع الكتم عن {name} بواسطة {query.from_user.first_name}")
        except Exception as e:
            await query.answer(f"❌ فشل: {e}", show_alert=True)
        return

    # رفع الحظر من الزر
    if data.startswith("unban_"):
        parts = data.split("_")
        target_id = int(parts[1])
        chat_id_btn = int(parts[2])
        if not await is_admin(update, query.from_user.id):
            await query.answer("🚫 للمشرفين فقط!", show_alert=True); return
        try:
            await context.bot.unban_chat_member(chat_id_btn, target_id)
            chat_str = str(chat_id_btn)
            if "banned_users" in db and chat_str in db["banned_users"]:
                name = db["banned_users"][chat_str].get(str(target_id), {}).get("name", "المستخدم")
                db["banned_users"][chat_str].pop(str(target_id), None)
                save_data(db)
                await query.answer(f"✅ تم رفع الحظر عن {name}!", show_alert=True)
                await query.message.edit_text(f"✅ تم رفع الحظر عن {name} بواسطة {query.from_user.first_name}")
        except Exception as e:
            await query.answer(f"❌ فشل: {e}", show_alert=True)
        return

    if data == "show_muted":
        if not await is_admin(update, query.from_user.id):
            await query.answer("🚫 للمشرفين فقط!", show_alert=True); return
        chat_id_str = str(query.message.chat.id)
        muted = db.get("muted_users", {}).get(chat_id_str, {})
        if not muted:
            await query.answer("✅ لا يوجد مكتومين!", show_alert=True)
        else:
            await query.answer(f"🔇 المكتومين: {len(muted)} عضو", show_alert=True)
        return

    if data == "show_banned":
        if not await is_admin(update, query.from_user.id):
            await query.answer("🚫 للمشرفين فقط!", show_alert=True); return
        chat_id_str = str(query.message.chat.id)
        banned = db.get("banned_users", {}).get(chat_id_str, {})
        if not banned:
            await query.answer("✅ لا يوجد محظورين!", show_alert=True)
        else:
            await query.answer(f"🔨 المحظورين: {len(banned)} عضو", show_alert=True)
        return

    # تخصيص
    custom_map = {
        "custom_welcome":     "💬 لتغيير رسالة الترحيب اكتب:\n`/ترحيب رسالتك هنا`\nالمتغيرات: `{name}` اسم العضو",
        "custom_rules":       "📋 لتغيير القواعد اكتب:\n`/تعيين_قواعد القواعد هنا`",
        "custom_theme":       "🎨 الثيمات ستكون متاحة في الإصدار القادم!",
        "custom_personality": "🤖 لتغيير اسم البوت في الردود:\n`/اسم_البوت الاسم الجديد`",
        "custom_alerts":      "🔔 لإضافة تذكير:\n`/ذكرني [دقائق] [الرسالة]`",
    }
    if data in custom_map:
        await query.message.reply_text(custom_map[data], parse_mode="Markdown")
        return

    azkar_map = {
        "azkar_sabah": ("اذكار الصباح", AZKAR_SABAH),
        "azkar_masa":  ("اذكار المساء", AZKAR_MASA),
        "azkar_dua":   ("دعاء",         ADIYA),
    }
    if data in azkar_map:
        title, lst = azkar_map[data]
        await query.message.reply_text(f"{title}\n\n{random.choice(lst)}")
        return

    if data == "azkar_tasbih":
        await query.message.reply_text(
            "التسبيح\n\n"
            "سبحان الله x33\n"
            "الحمد لله x33\n"
            "الله أكبر x33\n"
            "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير x1")

# ══════════════════════════════════════════════════
#         معالج الأخطاء
# ══════════════════════════════════════════════════

# ══════════════════════════════════════════════════
#         📋 قوائم المكتومين والمحظورين
# ══════════════════════════════════════════════════
async def cmd_المكتومين(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    chat_id = str(update.effective_chat.id)
    muted = db.get("muted_users", {}).get(chat_id, {})
    if not muted:
        await update.message.reply_text("✅ لا يوجد أعضاء مكتومين حالياً!"); return
    text = f"🔇 **قائمة المكتومين ({len(muted)} عضو):**\n\n"
    keyboard = []
    for uid, info in muted.items():
        name = info.get("name", "مجهول")
        username = info.get("username", "لا يوجد")
        mute_time = info.get("time", "")
        by = info.get("by", "")
        text += f"👤 **{name}**\n"
        text += f"📧 {username}\n"
        text += f"🆔 `{uid}`\n"
        text += f"🕐 {mute_time}\n"
        text += f"👮 بواسطة: {by}\n"
        text += "──────────────\n"
        keyboard.append([InlineKeyboardButton(
            f"🔊 فك كتم {name}",
            callback_data=f"unmute_{uid}_{chat_id}"
        )])
    if len(text) > 4000:
        text = text[:4000] + "..."
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

async def cmd_المحظورين(update, context):
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    chat_id = str(update.effective_chat.id)
    banned = db.get("banned_users", {}).get(chat_id, {})
    if not banned:
        await update.message.reply_text("✅ لا يوجد أعضاء محظورين حالياً!"); return
    text = f"🔨 **قائمة المحظورين ({len(banned)} عضو):**\n\n"
    keyboard = []
    for uid, info in banned.items():
        name = info.get("name", "مجهول")
        username = info.get("username", "لا يوجد")
        reason = info.get("reason", "لا يوجد سبب")
        ban_time = info.get("time", "")
        by = info.get("by", "")
        text += f"👤 **{name}**\n"
        text += f"📧 {username}\n"
        text += f"🆔 `{uid}`\n"
        text += f"📋 السبب: {reason}\n"
        text += f"🕐 {ban_time}\n"
        text += f"👮 بواسطة: {by}\n"
        text += "──────────────\n"
        keyboard.append([InlineKeyboardButton(
            f"✅ رفع حظر {name}",
            callback_data=f"unban_{uid}_{chat_id}"
        )])
    if len(text) > 4000:
        text = text[:4000] + "..."
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

# ══════════════════════════════════════════════════
#         🔔 نظام التنبيهات المتقدم
# ══════════════════════════════════════════════════
async def cmd_تنبيهاتي(update, context):
    """عرض التنبيهات الشخصية"""
    user = update.effective_user
    alerts = db.get("custom_alerts", {}).get(str(user.id), [])
    if not alerts:
        await update.message.reply_text(
            "🔔 **لا يوجد تنبيهات!**\n\n"
            "يمكنك إضافة تنبيه بـ `/ذكرني [الوقت] [الرسالة]`",
            parse_mode="Markdown"
        ); return
    text = f"🔔 **تنبيهاتك ({len(alerts)}):**\n\n"
    for i, alert in enumerate(alerts, 1):
        text += f"{i}. ⏰ {alert.get('time', '')}\n📝 {alert.get('msg', '')}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# ══════════════════════════════════════════════════
#         🔒 الحماية المتقدمة
# ══════════════════════════════════════════════════
spam_score_tracker = defaultdict(int)

async def check_spam_score(update, context, user_id, chat_id):
    """نظام نقاط السبام المتقدم"""
    spam_score_tracker[f"{chat_id}_{user_id}"] += 1
    score = spam_score_tracker[f"{chat_id}_{user_id}"]
    
    if score >= 15:
        # حظر تلقائي
        try:
            await context.bot.ban_chat_member(int(chat_id), user_id)
            spam_score_tracker[f"{chat_id}_{user_id}"] = 0
            await update.effective_chat.send_message(
                f"🚨 **تم الحظر التلقائي بسبب السبام المتكرر!**\n"
                f"درجة السبام وصلت للحد الأقصى.",
                parse_mode="Markdown"
            )
        except: pass
    elif score >= 10:
        # كتم تلقائي
        try:
            await context.bot.restrict_chat_member(
                int(chat_id), user_id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            await update.effective_chat.send_message(
                f"⚠️ **تم الكتم التلقائي بسبب السبام!**\n"
                f"درجة السبام: {score}/15",
                parse_mode="Markdown"
            )
        except: pass

async def cmd_الحماية(update, context):
    """عرض إعدادات الحماية المتقدمة"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    chat_id = str(update.effective_chat.id)
    s = get_settings(chat_id)
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if s.get('antiflood') else '❌'} مكافحة الفلود",    callback_data=f"toggle_antiflood_{chat_id}"),
         InlineKeyboardButton(f"{'✅' if s.get('antilink') else '❌'} مكافحة الروابط",   callback_data=f"toggle_antilink_{chat_id}")],
        [InlineKeyboardButton(f"{'✅' if s.get('antiporn') else '❌'} مكافحة الإباحي",   callback_data=f"toggle_antiporn_{chat_id}"),
         InlineKeyboardButton(f"{'✅' if s.get('antibadwords') else '❌'} فلتر الكلمات", callback_data=f"toggle_antibadwords_{chat_id}")],
        [InlineKeyboardButton(f"{'✅' if s.get('antibot') else '❌'} مكافحة البوتات",    callback_data=f"toggle_antibot_{chat_id}"),
         InlineKeyboardButton(f"{'✅' if s.get('antispam') else '❌'} مكافحة السبام",    callback_data=f"toggle_antispam_{chat_id}")],
        [InlineKeyboardButton("📋 المكتومين", callback_data="show_muted"),
         InlineKeyboardButton("🔨 المحظورين", callback_data="show_banned")],
    ]
    await update.message.reply_text(
        f"🛡️ **لوحة الحماية المتقدمة**\n\n"
        f"🔢 الإنذارات القصوى: {s.get('max_warnings', 3)}\n"
        f"🔇 المكتومين: {len(db.get('muted_users', {}).get(chat_id, {}))}\n"
        f"🔨 المحظورين: {len(db.get('banned_users', {}).get(chat_id, {}))}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ══════════════════════════════════════════════════
#         🎨 تخصيص البوت
# ══════════════════════════════════════════════════
async def cmd_تخصيص(update, context):
    """قائمة التخصيص"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    keyboard = [
        [InlineKeyboardButton("💬 تغيير رسالة الترحيب", callback_data="custom_welcome"),
         InlineKeyboardButton("📋 تغيير القواعد",       callback_data="custom_rules")],
        [InlineKeyboardButton("🎨 ثيم الرسائل",         callback_data="custom_theme"),
         InlineKeyboardButton("🤖 شخصية البوت",         callback_data="custom_personality")],
        [InlineKeyboardButton("🔔 إعدادات التنبيهات",   callback_data="custom_alerts")],
    ]
    await update.message.reply_text(
        "🎨 **تخصيص البوت**\n\nاختر ما تريد تخصيصه:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def cmd_تعيين_قواعد(update, context):
    """تعيين قواعد المجموعة"""
    if not await is_admin(update, update.effective_user.id):
        await update.message.reply_text("🚫 للمشرفين فقط!"); return
    if not context.args:
        await update.message.reply_text(
            "📝 `/تعيين_قواعد [القواعد]`\n\nمثال:\n`/تعيين_قواعد 1. احترم الجميع\n2. ممنوع السبام`",
            parse_mode="Markdown"
        ); return
    chat_id = str(update.effective_chat.id)
    rules = " ".join(context.args)
    if "settings" not in db:
        db["settings"] = {}
    if chat_id not in db["settings"]:
        db["settings"][chat_id] = {}
    db["settings"][chat_id]["rules"] = rules
    save_data(db)
    await update.message.reply_text("✅ تم تعيين قواعد المجموعة!")

async def cmd_القواعد(update, context):
    """عرض قواعد المجموعة"""
    chat_id = str(update.effective_chat.id)
    rules = db.get("settings", {}).get(chat_id, {}).get("rules", "")
    if not rules:
        rules = (
            "1️⃣ احترم جميع الأعضاء\n"
            "2️⃣ ممنوع السبام والإعلانات\n"
            "3️⃣ ممنوع المحتوى المسيء\n"
            "4️⃣ ممنوع الروابط الخارجية\n"
            "5️⃣ استخدم لغة محترمة"
        )
    await update.message.reply_text(
        f"📋 **قواعد المجموعة:**\n\n{rules}\n\n⚠️ المخالفة = إنذار والإنذارات = حظر!",
        parse_mode="Markdown"
    )


async def error_handler(update, context):
    logging.error("Unhandled exception", exc_info=context.error)

# ══════════════════════════════════════════════════
#                   التشغيل
# ══════════════════════════════════════════════════
def main():
    logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
    app = Application.builder().token(TOKEN).build()
    jq  = app.job_queue

    # --- الأوامر ---
    cmds = [
        ("start",          cmd_start),
        ("الاوامر",        cmd_الاوامر),
        # رتب
        ("رتبتي",          cmd_رتبتي),
        ("تعيين_رتبة",     cmd_تعيين_رتبة),
        ("الرتب",          cmd_الرتب),
        # حماية
        ("حظر",            cmd_حظر),
        ("رفع_حظر",        cmd_رفع_حظر),
        ("كتم",            cmd_كتم),
        ("رفع_كتم",        cmd_رفع_كتم),
        ("طرد",            cmd_طرد),
        ("انذار",          cmd_انذار),
        ("الانذارات",      cmd_الانذارات),
        ("مسح_انذارات",    cmd_مسح_انذارات),
        ("ترقية",          cmd_ترقية),
        ("تخفيض",          cmd_تخفيض),
        ("تثبيت",          cmd_تثبيت),
        ("حذف",            cmd_حذف),
        ("اغلاق",          cmd_اغلاق),
        ("رفع_اغلاق",      cmd_رفع_اغلاق),
        # اعدادات
        ("الاعدادات",      cmd_الاعدادات),
        ("ترحيب",          cmd_ترحيب),
        ("اضف_كلمة",       cmd_اضف_كلمة),
        ("حذف_كلمة",       cmd_حذف_كلمة),
        ("الكلمات",        cmd_الكلمات),
        # معلومات
        ("معلومات",        cmd_معلومات),
        ("المجموعة",       cmd_المجموعة),
        ("السجل",          cmd_السجل),
        ("الاحصائيات",     cmd_الاحصائيات),
        # اسلاميات
        ("قران",           cmd_قران),
        ("بحث_قران",       cmd_بحث_قران),
        ("حديث",           cmd_حديث),
        ("اذكار",          cmd_اذكار),
        ("صباح",           cmd_صباح),
        ("مساء",           cmd_مساء),
        ("دعاء",           cmd_دعاء),
        ("اسماء_الله",     cmd_اسماء_الله),
        ("صلاة",           cmd_صلاة),
        ("جدولة",          cmd_جدولة),
        # خدمات
        ("طقس",            cmd_طقس),
        ("الوقت",          cmd_الوقت),
        ("التاريخ",        cmd_التاريخ),
        # همسة واختصارات
        ("همسة",           cmd_همسة),
        ("اختصار",         cmd_اختصار),
        ("الاختصارات",     cmd_الاختصارات),
        ("حذف_اختصار",     cmd_حذف_اختصار),
        # تحميل
        ("تحميل",           cmd_تحميل),
        # أدوات
        ("عملة",            cmd_عملة),
        ("حاسبة",           cmd_حاسبة),
        ("لخص",             cmd_لخص),
        ("ترجم",            cmd_ترجم),
        ("report",          cmd_report),
        # خدمات خارجية
        ("اخبار",           cmd_اخبار),
        ("مباريات",         cmd_مباريات),
        ("طقس_اسبوع",       cmd_طقس_اسبوع),
        # تخصيص
        ("تعيين_قواعد",     cmd_تعيين_قواعد),
        ("القواعد",         cmd_القواعد),
        ("اضف_امر",         cmd_اضف_امر),
        ("الاوامر_المخصصة", cmd_الاوامر_المخصصة),
        ("حذف_امر",         cmd_حذف_امر),
        # أمان
        ("اضف_رابط_مسموح",  cmd_اضف_رابط_مسموح),
        ("الروابط_المسموحة", cmd_الروابط_المسموحة),
        ("حذف_رابط_مسموح",  cmd_حذف_رابط_مسموح),
        ("طوارئ",           cmd_طوارئ),
        # ميديا
        ("ستيكر",           cmd_ستيكر),
        ("صوت",             cmd_صوت),
        # تذكير
        ("ذكرني",           cmd_ذكرني),
        ("تذكيراتي",        cmd_تذكيراتي),
        # يوت
        ("متصدري_يوت",      cmd_متصدري_يوت),
        # إعدادات شخصية
        ("اعداداتي",        cmd_اعداداتي),
        ("مدينتي",          cmd_مدينتي),
        # broadcast
        ("broadcast",       cmd_broadcast),
        # قوائم
        ("المكتومين",       cmd_المكتومين),
        ("المحظورين",       cmd_المحظورين),
        ("فك_كتم",          cmd_فك_كتم),
        # حماية متقدمة
        ("الحماية",         cmd_الحماية),
        # تخصيص
        ("تخصيص",           cmd_تخصيص),
        ("تعيين_قواعد",     cmd_تعيين_قواعد),
        ("القواعد",         cmd_القواعد),
        # تنبيهات
        ("تنبيهاتي",        cmd_تنبيهاتي),
    ]
    for name, handler in cmds:
        app.add_handler(CommandHandler(name, handler))

    # --- المعالجات ---
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private_message))
    # معالج الروابط التلقائي (في المجموعات والخاص)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"https?://"),
        lambda u, c: handle_url_message(u, c)
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE, check_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, check_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, goodbye_member))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    app.add_error_handler(error_handler)

    # --- المهام المجدولة ---
    # أذكار الصباح 6:00 ص
    jq.run_daily(scheduled_sabah, time=datetime.strptime("06:00", "%H:%M").time())
    # أذكار المساء 5:00 م
    jq.run_daily(scheduled_masa,  time=datetime.strptime("17:00", "%H:%M").time())
    # نسخ احتياطي كل 3 أيام (72 ساعة)
    jq.run_repeating(scheduled_backup, interval=60 * 60 * 72, first=60)
    # ملخص يومي الساعة 11 مساءً
    jq.run_daily(scheduled_daily_summary, time=datetime.strptime("23:00", "%H:%M").time())

    print("البوت العربي v4.0 يعمل الآن...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
