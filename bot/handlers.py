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
from storage import get_or_create_user, save_session, save_feedback, get_user_memory
from formatter import format_plan, format_summary

logger = logging.getLogger(__name__)

ASK_ENERGY, ASK_TIME, ASK_LOCATION, WAITING_FEEDBACK = range(4)

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

BODY_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("好多了 👍", callback_data="body_feel_better"),
        InlineKeyboardButton("差不多 😐", callback_data="body_feel_same"),
        InlineKeyboardButton("不舒服 👎", callback_data="body_feel_worse"),
    ],
])

MOOD_KB = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("神清气爽 ✨", callback_data="mood_refreshed"),
        InlineKeyboardButton("平静放松 😌", callback_data="mood_calm"),
    ],
    [
        InlineKeyboardButton("充满活力 ⚡", callback_data="mood_energized"),
        InlineKeyboardButton("有点累 😴", callback_data="mood_tired"),
    ],
])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = get_or_create_user(user.id, user.username or "")

    if data["is_new"]:
        await update.message.reply_text(
            f"👋 你好 {user.first_name}！\n\n"
            "我是你的 AI 健身教练，每次训练前告诉我你的状态，我来给你安排方案。\n\n"
            "发送 /workout 开始今天的训练 💪"
        )
    else:
        sessions = len(data["memory"].get("session_history", []))
        await update.message.reply_text(
            f"欢迎回来 {user.first_name}！\n\n"
            f"你已经完成了 {sessions} 次训练记录 🔥\n\n"
            "发送 /workout 开始今天的训练"
        )
    return ConversationHandler.END


async def workout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "今天精力怎么样？",
        reply_markup=ENERGY_KB,
    )
    return ASK_ENERGY


async def got_energy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    energy = int(query.data.split("_")[1])
    context.user_data["energy"] = energy

    await query.edit_message_text(
        f"精力：{'⭐' * energy}{'☆' * (5 - energy)}  ({energy}/5)\n\n今天有多少时间？",
        reply_markup=TIME_KB,
    )
    return ASK_TIME


async def got_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_min = int(query.data.split("_")[1])
    context.user_data["time_min"] = time_min

    await query.edit_message_text(
        f"时间：{time_min} 分钟\n\n在哪里练？",
        reply_markup=LOCATION_KB,
    )
    return ASK_LOCATION


async def got_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    location = query.data.split("_", 1)[1]
    context.user_data["location"] = location

    loc_names = {"home": "家里", "gym": "健身房", "office": "公司", "outdoor": "户外"}
    await query.edit_message_text(
        f"📍 {loc_names.get(location, location)}\n\n正在为你生成方案... ⏳"
    )

    user_id = update.effective_user.id
    pre_survey = {
        "energy": context.user_data["energy"],
        "time_min": context.user_data["time_min"],
        "location": context.user_data["location"],
    }

    try:
        user_memory = get_user_memory(user_id)
        result = generate_plan(pre_survey, user_memory)
        decision = result["decision"]
        plan = result["plan"]

        session_id = save_session(user_id, pre_survey, decision, plan)
        context.user_data["session_id"] = session_id
        context.user_data["pre_survey"] = pre_survey

        plan_text = format_plan(decision, plan)
        await query.message.reply_text(plan_text, parse_mode="Markdown")

    except Exception as e:
        logger.error("generate_plan failed: %s", e)
        await query.message.reply_text(
            "生成方案时遇到问题，请稍后重试 /workout"
        )
        return ConversationHandler.END

    return WAITING_FEEDBACK


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "session_id" not in context.user_data:
        await update.message.reply_text("还没有进行中的训练，先发送 /workout 开始 🏃")
        return ConversationHandler.END

    await update.message.reply_text(
        "练完了？\n\n身体感觉怎么样？",
        reply_markup=BODY_KB,
    )
    context.user_data["feedback"] = {}
    return WAITING_FEEDBACK


async def got_body_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    body_response = query.data.split("_", 1)[1]
    context.user_data["feedback"]["body_response"] = body_response

    await query.edit_message_text(
        "心情如何？",
        reply_markup=MOOD_KB,
    )
    return WAITING_FEEDBACK


async def got_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mood = query.data.split("_", 1)[1]
    context.user_data["feedback"]["mood_after"] = mood

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


def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("workout", workout_start)],
        states={
            ASK_ENERGY: [CallbackQueryHandler(got_energy, pattern=r"^energy_\d$")],
            ASK_TIME: [CallbackQueryHandler(got_time, pattern=r"^time_\d+$")],
            ASK_LOCATION: [CallbackQueryHandler(got_location, pattern=r"^loc_\w+$")],
            WAITING_FEEDBACK: [
                CommandHandler("done", done_command),
                CallbackQueryHandler(got_body_response, pattern=r"^body_feel_\w+$"),
                CallbackQueryHandler(got_mood, pattern=r"^mood_\w+$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )
