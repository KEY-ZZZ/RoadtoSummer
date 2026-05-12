from telegram import InlineKeyboardButton, InlineKeyboardMarkup

INTENSITY_ZH = {
    "very_low": "极轻松",
    "low": "轻松",
    "moderate": "适中",
    "high": "高强度",
    "very_high": "极高强度",
}

_PHASE_STYLES = {
    "warmup": {"activation", "mobility"},
    "cooldown": {"stretching"},
    "main": {"strength", "hypertrophy", "endurance", "cardio", "hiit"},
}

_PHASE_LABELS = {
    "warmup": "🔥 热身激活",
    "main": "💪 主体训练",
    "cooldown": "🧘 拉伸放松",
}


def _exercise_phase(item: dict) -> str:
    styles = set(item.get("exercise_style", []))
    has_main = styles & _PHASE_STYLES["main"]
    if not has_main:
        if styles & _PHASE_STYLES["warmup"]:
            return "warmup"
        if styles & _PHASE_STYLES["cooldown"]:
            return "cooldown"
    return "main"


def format_plan(decision: dict, plan: list, session_id: int) -> tuple[str, InlineKeyboardMarkup]:
    intensity = INTENSITY_ZH.get(decision.get("intensity", ""), decision.get("intensity", ""))
    duration = decision.get("duration_min", "?")
    reasoning = decision.get("reasoning_summary", "")

    lines = [
        "🏋️ *今日训练方案*",
        "",
        f"⏱ 预计时长：{duration} 分钟  |  强度：{intensity}",
        f"💬 {reasoning}",
        "",
    ]

    current_phase = None
    for i, ex in enumerate(plan, 1):
        phase = _exercise_phase(ex)
        if phase != current_phase:
            current_phase = phase
            lines.append(f"\n{_PHASE_LABELS[phase]}")
            lines.append("─────────────")

        name = ex.get("name", ex.get("exercise_id"))
        if ex.get("duration_sec"):
            volume = f"{ex['duration_sec']}秒"
        elif ex.get("sets") and ex.get("reps"):
            volume = f"{ex['sets']}组 × {ex['reps']}次"
        elif ex.get("sets"):
            volume = f"{ex['sets']}组"
        else:
            volume = ""

        rest = ex.get("rest_sec")
        rest_str = f"  休息{rest}秒" if rest else ""
        lines.append(f"{i}. *{name}*  {volume}{rest_str}")

    lines += ["", "─────────────"]

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📖 查看动作说明", callback_data=f"details_{session_id}"),
        ],
        [
            InlineKeyboardButton("✅ 练完了，记录反馈", callback_data="fb_start"),
            InlineKeyboardButton("跳过", callback_data="fb_skip"),
        ],
    ])

    return "\n".join(lines), kb


def format_exercise_details(plan: list) -> str:
    lines = ["📖 *动作说明*", ""]
    for i, ex in enumerate(plan, 1):
        name = ex.get("name", ex.get("exercise_id", ""))
        instructions = ex.get("instructions", "")
        cues = ex.get("cues", [])

        lines.append(f"*{i}. {name}*")
        if instructions:
            lines.append(instructions)
        if cues:
            lines.append("💡 " + " · ".join(cues))
        lines.append("")

    return "\n".join(lines).strip()


def format_summary(feedback: dict) -> str:
    mood_map = {
        "refreshed": "神清气爽 ✨",
        "calm": "平静放松 😌",
        "neutral": "一般般 😐",
        "tired": "有点累 😴",
        "energized": "充满活力 ⚡",
    }
    body_map = {
        "feel_better": "好多了 👍",
        "feel_same": "差不多 😐",
        "feel_worse": "不太舒服 👎",
    }

    mood = mood_map.get(feedback.get("mood_after", ""), "")
    body = body_map.get(feedback.get("body_response", ""), "")

    lines = ["✅ *已记录！*", ""]
    if body:
        lines.append(f"身体感受：{body}")
    if mood:
        lines.append(f"心情：{mood}")
    lines += ["", "下次训练时我会记住这次的感受 🧠"]
    return "\n".join(lines)
