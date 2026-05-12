import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from ai_coach import generate_plan
from storage import (
    get_or_create_user, save_session, save_feedback,
    get_user_memory, save_user_profile, update_user_profile_field,
    get_session_plan,
)
from formatter import format_plan, format_exercise_details, format_summary

logger = logging.getLogger(__name__)

# ─── Onboarding states ────────────────────────────────────────────────────────
OB_EXPERIENCE, OB_INJURIES, OB_EQUIPMENT = range(3)

# ─── Workout survey states ────────────────────────────────────────────────────
ASK_ENERGY, ASK_TIME, ASK_LOCATION, ASK_HOME_EQUIP, ASK_MENTAL, ASK_BODY, ASK_TARGET = range(10, 17)

# ─── Feedback states ──────────────────────────────────────────────────────────
FB_BODY, FB_MOOD = range(20, 22)

# ─── Profile edit state ───────────────────────────────────────────────────────
PROFILE_EDIT_EQUIP = 30


# ─── Static keyboards ─────────────────────────────────────────────────────────

ENERGY_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("1 极度疲惫", callback_data="energy_1"),
        InlineKeyboardButton("2 比较累", callback_data="energy_2"),
    ],
    [
        InlineKeyboardButton("3 一般", callback_data="energy_3"),
        InlineKeyboardButton("4 状态不错", callback_data="energy_4"),
        InlineKeyboardButton("5 精力充沛", callback_data="energy_5"),
    ],
])

TIME_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("15 分钟", callback_data="time_15"),
        InlineKeyboardButton("20 分钟", callback_data="time_20"),
        InlineKeyboardButton("30 分钟", callback_data="time_30"),
    ],
    [
        InlineKeyboardButton("45 分钟", callback_data="time_45"),
        InlineKeyboardButton("60 分钟", callback_data="time_60"),
    ],
])

LOCATION_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🏠 家里", callback_data="loc_home"),
        InlineKeyboardButton("🏋️ 健身房", callback_data="loc_gym"),
    ],
    [
        InlineKeyboardButton("🏢 公司", callback_data="loc_office"),
        InlineKeyboardButton("🌳 户外", callback_data="loc_outdoor"),
    ],
])

HOME_EQUIP_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ 没有器械（纯徒手）", callback_data="equip_none")],
    [InlineKeyboardButton("🏋 有哑铃", callback_data="equip_dumbbell")],
    [InlineKeyboardButton("🎗 有弹力带", callback_data="equip_band")],
    [InlineKeyboardButton("🏋🎗 哑铃 + 弹力带都有", callback_data="equip_both")],
])

MENTAL_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("😤 有压力", callback_data="mental_stressed"),
        InlineKeyboardButton("😐 平稳", callback_data="mental_neutral"),
    ],
    [
        InlineKeyboardButton("😌 比较放松", callback_data="mental_relaxed"),
        InlineKeyboardButton("💪 很有动力", callback_data="mental_motivated"),
    ],
])

TARGET_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("上肢（胸/背/肩/手臂）", callback_data="target_upper"),
        InlineKeyboardButton("下肢（腿/臀）", callback_data="target_lower"),
    ],
    [
        InlineKeyboardButton("核心", callback_data="target_core"),
        InlineKeyboardButton("全身", callback_data="target_full"),
    ],
    [InlineKeyboardButton("🤖 让 AI 决定", callback_data="target_ai")],
])

BODY_PARTS = [
    ("腰背", "lower_back"),
    ("肩膀", "shoulders"),
    ("膝盖", "knees"),
    ("腿部", "legs"),
    ("手腕", "wrists"),
    ("颈部", "neck"),
    ("核心/腹部", "core"),
]

EXPERIENCE_KB = InlineKeyboardMarkup([
    [InlineKeyboardButton("🌱 新手（健身 < 6 个月）", callback_data="exp_beginner")],
    [InlineKeyboardButton("🌿 有基础（6 个月 ~ 2 年）", callback_data="exp_intermediate")],
    [InlineKeyboardButton("🌳 老手（> 2 年）", callback_data="exp_advanced")],
])

INJURY_PARTS = [
    ("腰背", "lower_back"),
    ("肩膀", "shoulders"),
    ("膝盖", "knees"),
    ("手腕", "wrists"),
    ("颈部", "neck"),
]

FEEDBACK_BODY_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("好多了 👍", callback_data="fb_body_feel_better"),
        InlineKeyboardButton("差不多 😐", callback_data="fb_body_feel_same"),
        InlineKeyboardButton("不舒服 👎", callback_data="fb_body_feel_worse"),
    ],
])

FEEDBACK_MOOD_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("神清气爽 ✨", callback_data="fb_mood_refreshed"),
        InlineKeyboardButton("平静放松 😌", callback_data="fb_mood_calm"),
    ],
    [
        InlineKeyboardButton("充满活力 ⚡", callback_data="fb_mood_energized"),
        InlineKeyboardButton("有点累 😴", callback_data="fb_mood_tired"),
    ],
])

EQUIP_LABELS = {
    "none": "没有器械",
    "dumbbell": "哑铃",
    "band": "弹力带",
    "both": "哑铃 + 弹力带",
}

EQUIP_DATA = {
    "none": [],
    "dumbbell": ["dumbbell"],
    "band": ["resistance_band"],
    "both": ["dumbbell", "resistance_band"],
}

EXPERIENCE_LABELS = {
    "beginner": "新手（< 6 个月）",
    "intermediate": "有基础（6 个月 ~ 2 年）",
    "advanced": "老手（> 2 年）",
}


def _build_body_kb(selected: set) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for label, key in BODY_PARTS:
        mark = "✅ " if key in selected else ""
        row.append(InlineKeyboardButton(f"{mark}{label}", callback_data=f"body_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    confirm_label = f"✓ 已选 {len(selected)} 个，继续 →" if selected else "✓ 没有不适，继续 →"
    rows.append([InlineKeyboardButton(confirm_label, callback_data="body_done")])
    return InlineKeyboardMarkup(rows)


def _build_injury_kb(selected: set) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for label, key in INJURY_PARTS:
        mark = "✅ " if key in selected else ""
        row.append(InlineKeyboardButton(f"{mark}{label}", callback_data=f"inj_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    confirm_label = f"✓ 已选 {len(selected)} 个，完成" if selected else "✓ 无伤病，完成"
    rows.append([InlineKeyboardButton(confirm_label, callback_data="inj_done")])
    return InlineKeyboardMarkup(rows)


# ─── /start & onboarding ─────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = get_or_create_user(user.id, user.username or "")

    if data["is_new"]:
        await update.message.reply_text(
            f"👋 你好 {user.first_name}！我是你的 AI 健身教练。\n\n"
            "先做个简单了解，以便给你更准确的方案（30 秒内完成）。\n\n"
            "你的健身经验是？",
            reply_markup=EXPERIENCE_KB,
        )
        context.user_data["onboarding"] = True
        return OB_EXPERIENCE
    else:
        history_count = len(data["memory"].get("session_history", []))
        await update.message.reply_text(
            f"欢迎回来 {user.first_name}！🔥\n\n"
            f"已记录 {history_count} 次训练。\n\n"
            "发送 /workout 开始今天的训练 💪\n"
            "发送 /profile 查看或修改你的档案"
        )
        return ConversationHandler.END


async def ob_got_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["ob_experience"] = query.data.split("_")[1]
    context.user_data["ob_injuries"] = set()
    await query.edit_message_text(
        "有没有需要避开的伤病或不适部位？（可多选，选完按确认）",
        reply_markup=_build_injury_kb(set()),
    )
    return OB_INJURIES


async def ob_toggle_injury(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    part = query.data[4:]
    selected = context.user_data.setdefault("ob_injuries", set())
    if part in selected:
        selected.discard(part)
    else:
        selected.add(part)
    await query.edit_message_reply_markup(_build_injury_kb(selected))
    return OB_INJURIES


async def ob_injuries_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("家里有什么训练器械？", reply_markup=HOME_EQUIP_KB)
    return OB_EQUIPMENT


async def ob_got_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    equip_key = query.data[8:]
    profile = {
        "experience_level": context.user_data.get("ob_experience", "beginner"),
        "injuries": list(context.user_data.get("ob_injuries", [])),
        "home_equipment": EQUIP_DATA.get(equip_key, []),
        "home_equipment_key": equip_key,
    }
    save_user_profile(update.effective_user.id, profile)
    await query.edit_message_text(
        "✅ 了解了！以后每次训练前我会问你几个快速问题来定制方案。\n\n"
        "发送 /workout 开始今天的训练 💪"
    )
    return ConversationHandler.END


# ─── /profile ─────────────────────────────────────────────────────────────────

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = get_or_create_user(user_id, "")
    profile = data.get("profile", {})

    exp = EXPERIENCE_LABELS.get(profile.get("experience_level", ""), "未设置")
    injuries = "、".join(profile.get("injuries", [])) or "无"
    equip_key = profile.get("home_equipment_key", "none")
    equip = EQUIP_LABELS.get(equip_key, "未设置")

    text = (
        f"📋 *我的档案*\n\n"
        f"💪 经验等级：{exp}\n"
        f"🤕 伤病记录：{injuries}\n"
        f"🏠 家庭器械：{equip}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("修改家庭器械", callback_data="profile_edit_equip")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    return ConversationHandler.END


async def profile_edit_equip_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("选择你家里有的器械：", reply_markup=HOME_EQUIP_KB)
    return PROFILE_EDIT_EQUIP


async def profile_edit_equip_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    equip_key = query.data.split("_", 1)[1]
    update_user_profile_field(update.effective_user.id, "home_equipment", EQUIP_DATA.get(equip_key, []))
    update_user_profile_field(update.effective_user.id, "home_equipment_key", equip_key)
    await query.edit_message_text(f"✅ 已更新！家庭器械：{EQUIP_LABELS.get(equip_key, equip_key)}")
    return ConversationHandler.END


# ─── Workout survey ───────────────────────────────────────────────────────────

async def workout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("今天精力怎么样？", reply_markup=ENERGY_KB)
    return ASK_ENERGY


async def got_energy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["energy"] = int(query.data.split("_")[1])
    stars = "⭐" * context.user_data["energy"] + "☆" * (5 - context.user_data["energy"])
    await query.edit_message_text(f"精力：{stars}\n\n今天有多少时间？", reply_markup=TIME_KB)
    return ASK_TIME


async def got_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["time_min"] = int(query.data.split("_")[1])
    await query.edit_message_text(
        f"时间：{context.user_data['time_min']} 分钟\n\n在哪里练？",
        reply_markup=LOCATION_KB,
    )
    return ASK_LOCATION


async def got_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    location = query.data.split("_", 1)[1]
    context.user_data["location"] = location

    if location == "home":
        # Check if equipment is already set in profile
        user_id = update.effective_user.id
        data = get_or_create_user(user_id, "")
        profile_equip = data.get("profile", {}).get("home_equipment")
        if profile_equip is not None:
            # Already known — skip the question
            context.user_data["home_equipment"] = profile_equip
            await query.edit_message_text("今天心情怎么样？", reply_markup=MENTAL_KB)
            return ASK_MENTAL
        else:
            await query.edit_message_text("家里有什么器械？", reply_markup=HOME_EQUIP_KB)
            return ASK_HOME_EQUIP
    else:
        context.user_data["home_equipment"] = []
        await query.edit_message_text("今天心情怎么样？", reply_markup=MENTAL_KB)
        return ASK_MENTAL


async def got_home_equip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    equip_key = query.data.split("_", 1)[1]
    context.user_data["home_equipment"] = EQUIP_DATA.get(equip_key, [])
    # Save to profile so we don't ask again
    update_user_profile_field(update.effective_user.id, "home_equipment", context.user_data["home_equipment"])
    update_user_profile_field(update.effective_user.id, "home_equipment_key", equip_key)
    await query.edit_message_text("今天心情怎么样？", reply_markup=MENTAL_KB)
    return ASK_MENTAL


async def got_mental(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["mental"] = query.data.split("_")[1]
    context.user_data["sore_parts"] = set()
    await query.edit_message_text(
        "身体有哪里不舒服？（可多选，没有就直接按确认）",
        reply_markup=_build_body_kb(set()),
    )
    return ASK_BODY


async def toggle_body_part(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    part = query.data[5:]
    selected = context.user_data.setdefault("sore_parts", set())
    if part in selected:
        selected.discard(part)
    else:
        selected.add(part)
    await query.edit_message_reply_markup(_build_body_kb(selected))
    return ASK_BODY


async def body_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("今天想练哪里？", reply_markup=TARGET_KB)
    return ASK_TARGET


async def got_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["target"] = query.data.split("_", 1)[1]

    loc_names = {"home": "家里", "gym": "健身房", "office": "公司", "outdoor": "户外"}
    await query.edit_message_text(
        f"📍 {loc_names.get(context.user_data.get('location', ''), '')}  正在生成方案... ⏳"
    )

    user_id = update.effective_user.id
    pre_survey = {
        "energy": context.user_data["energy"],
        "time_min": context.user_data["time_min"],
        "location": context.user_data["location"],
        "home_equipment": context.user_data.get("home_equipment", []),
        "mental": context.user_data.get("mental", "neutral"),
        "sore_parts": list(context.user_data.get("sore_parts", [])),
        "target": context.user_data.get("target", "ai"),
    }

    try:
        user_memory = get_user_memory(user_id)
        user_data = get_or_create_user(user_id, "")
        profile = user_data.get("profile", {})

        result = generate_plan(pre_survey, user_memory, profile)
        decision = result["decision"]
        plan = result["plan"]

        session_id = save_session(user_id, pre_survey, decision, plan)
        context.user_data["session_id"] = session_id

        plan_text, plan_kb = format_plan(decision, plan, session_id)
        await query.message.reply_text(plan_text, parse_mode="Markdown", reply_markup=plan_kb)

    except Exception as e:
        logger.error("generate_plan failed: %s", e)
        await query.message.reply_text("生成方案时遇到问题，请稍后重试 /workout")

    return ConversationHandler.END


# ─── Exercise details ─────────────────────────────────────────────────────────

async def show_exercise_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session_id = int(query.data.split("_", 1)[1])
    plan = get_session_plan(session_id)
    if not plan:
        await query.answer("找不到方案数据", show_alert=True)
        return
    details = format_exercise_details(plan)
    await query.message.reply_text(details, parse_mode="Markdown")


# ─── Feedback ─────────────────────────────────────────────────────────────────

async def feedback_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["feedback"] = {}
    await query.edit_message_reply_markup(None)
    await query.message.reply_text("身体感觉怎么样？", reply_markup=FEEDBACK_BODY_KB)
    return FB_BODY


async def feedback_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("已跳过")
    await query.edit_message_reply_markup(None)
    return ConversationHandler.END


async def got_fb_body(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["feedback"]["body_response"] = query.data.split("_", 2)[2]
    await query.edit_message_text("心情如何？", reply_markup=FEEDBACK_MOOD_KB)
    return FB_MOOD


async def got_fb_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["feedback"]["mood_after"] = query.data.split("_", 2)[2]

    session_id = context.user_data.get("session_id")
    user_id = update.effective_user.id
    feedback = context.user_data["feedback"]

    if session_id:
        save_feedback(session_id, feedback, user_id)

    summary = format_summary(feedback)
    await query.edit_message_text(summary, parse_mode="Markdown")
    context.user_data.pop("session_id", None)
    context.user_data.pop("feedback", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("已取消。发送 /workout 重新开始 👋")
    context.user_data.clear()
    return ConversationHandler.END


# ─── Handler builders ─────────────────────────────────────────────────────────

def build_onboarding_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            OB_EXPERIENCE: [CallbackQueryHandler(ob_got_experience, pattern=r"^exp_")],
            OB_INJURIES: [
                CallbackQueryHandler(ob_toggle_injury, pattern=r"^inj_(?!done)"),
                CallbackQueryHandler(ob_injuries_done, pattern=r"^inj_done$"),
            ],
            OB_EQUIPMENT: [CallbackQueryHandler(ob_got_equipment, pattern=r"^equip_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )


def build_profile_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("profile", profile_command),
            CallbackQueryHandler(profile_edit_equip_start, pattern=r"^profile_edit_equip$"),
        ],
        states={
            PROFILE_EDIT_EQUIP: [CallbackQueryHandler(profile_edit_equip_save, pattern=r"^equip_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )


def build_workout_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("workout", workout_start)],
        states={
            ASK_ENERGY: [CallbackQueryHandler(got_energy, pattern=r"^energy_\d$")],
            ASK_TIME: [CallbackQueryHandler(got_time, pattern=r"^time_\d+$")],
            ASK_LOCATION: [CallbackQueryHandler(got_location, pattern=r"^loc_\w+$")],
            ASK_HOME_EQUIP: [CallbackQueryHandler(got_home_equip, pattern=r"^equip_")],
            ASK_MENTAL: [CallbackQueryHandler(got_mental, pattern=r"^mental_\w+$")],
            ASK_BODY: [
                CallbackQueryHandler(toggle_body_part, pattern=r"^body_(?!done)"),
                CallbackQueryHandler(body_done, pattern=r"^body_done$"),
            ],
            ASK_TARGET: [CallbackQueryHandler(got_target, pattern=r"^target_\w+$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )


def build_feedback_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(feedback_start, pattern=r"^fb_start$")],
        states={
            FB_BODY: [CallbackQueryHandler(got_fb_body, pattern=r"^fb_body_")],
            FB_MOOD: [CallbackQueryHandler(got_fb_mood, pattern=r"^fb_mood_")],
        },
        fallbacks=[
            CallbackQueryHandler(feedback_skip, pattern=r"^fb_skip$"),
            CommandHandler("cancel", cancel),
        ],
        per_user=True,
        per_chat=True,
    )
