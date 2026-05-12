LOCATION_ZH = {
    "home": "家里",
    "gym": "健身房",
    "office": "公司/办公室",
    "outdoor": "户外",
}

INTENSITY_ZH = {
    "very_low": "极轻松",
    "low": "轻松",
    "moderate": "适中",
    "high": "高强度",
    "very_high": "极高强度",
}


def format_plan(decision: dict, plan: list) -> str:
    intensity = INTENSITY_ZH.get(decision.get("intensity", ""), decision.get("intensity", ""))
    duration = decision.get("duration_min", "?")
    reasoning = decision.get("reasoning_summary", "")

    lines = [
        f"🏋️ *今日训练方案*",
        f"",
        f"⏱ 预计时长：{duration} 分钟  |  强度：{intensity}",
        f"💡 {reasoning}",
        f"",
        f"━━━━━━━━━━━━━━━━",
    ]

    for i, ex in enumerate(plan, 1):
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
        rest_str = f"  休息 {rest}秒" if rest else ""
        lines.append(f"{i}. *{name}*  {volume}{rest_str}")

    lines += [
        f"━━━━━━━━━━━━━━━━",
        f"",
        f"训练完成后发送 /done 记录反馈 💪",
    ]

    return "\n".join(lines)


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
