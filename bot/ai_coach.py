import json
import anthropic
from config import ANTHROPIC_API_KEY, EXERCISE_LIBRARY_PATH, MATCHING_LOGIC_PATH, CLAUDE_MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

with open(EXERCISE_LIBRARY_PATH, encoding="utf-8") as f:
    _library = json.load(f)

with open(MATCHING_LOGIC_PATH, encoding="utf-8") as f:
    _matching_logic = json.load(f)

_ALL_EXERCISES = _library["exercises"]

TARGET_MAP = {
    "upper": ["chest", "back", "shoulders", "biceps", "triceps"],
    "lower": ["quads", "glutes", "hamstrings", "calves"],
    "core": ["core"],
    "full": ["full_body", "chest", "back", "shoulders", "quads", "glutes", "core"],
    "ai": None,
}

CONTRAINDICATED_MAP = {
    "lower_back": ["lower_back_load", "heavy_axial_load", "spinal_flexion"],
    "shoulders": ["shoulder_impingement_risk"],
    "knees": ["knee_stress"],
    "wrists": ["wrist_pressure"],
    "neck": ["neck_strain"],
    "core": [],
    "legs": ["knee_stress", "high_impact"],
}


def _filter_exercises(location: str, home_equipment: list, injuries: list) -> list:
    """Return exercises available given user location and equipment."""
    equip_set = set(home_equipment)

    def available(ex: dict) -> bool:
        scenes = ex.get("scene", ["gym"])
        if location not in scenes:
            return False
        required = set(ex["execution"].get("equipment", []))
        bodyweight_only = required <= {"bodyweight", "mat"}
        if bodyweight_only:
            return True
        if location == "gym":
            return True
        if location == "home":
            return bool(required & (equip_set | {"bodyweight", "mat"}))
        return False

    # Hard-filter contraindicated exercises
    injury_flags = set()
    for injury in injuries:
        injury_flags.update(CONTRAINDICATED_MAP.get(injury, []))

    def safe(ex: dict) -> bool:
        ex_flags = set(ex["matching_tags"].get("contraindicated_flags", []))
        return not (ex_flags & injury_flags)

    return [ex for ex in _ALL_EXERCISES if available(ex) and safe(ex)]


_SYSTEM_TEMPLATE = """你是一名专业健身教练AI。根据用户当前状态和可用动作库，按以下规则生成个性化训练方案。

## 匹配规则
{matching_logic}

## 今日可用动作库（已按场景和伤病筛选）
{exercises}

## 输出格式
只返回合法JSON，不要有任何其他文字：
{{
  "decision": {{
    "intensity": "low",
    "target_body_parts": ["back"],
    "contraindicated": [],
    "duration_min": 20,
    "exercise_style": ["stretching", "activation"],
    "reasoning_summary": "中文说明为何这样安排（2句）"
  }},
  "plan": [
    {{
      "exercise_id": "bw_001",
      "name": "俯卧撑",
      "sets": 3,
      "reps": 10,
      "duration_sec": null,
      "rest_sec": 60
    }}
  ]
}}

规则：
- plan 只能使用上面动作库里的 exercise_id，不可编造
- 动作顺序：热身激活 → 主体训练 → 拉伸放松
- 总时长控制在 duration_min ± 5 分钟
- 如有历史数据，近期出现的动作降优先级
"""


def generate_plan(pre_survey: dict, user_memory: dict, profile: dict = None) -> dict:
    location = pre_survey.get("location", "gym")
    home_equipment = pre_survey.get("home_equipment", [])

    profile = profile or {}
    profile_injuries = profile.get("injuries", [])
    survey_sore = pre_survey.get("sore_parts", [])
    all_injuries = list(set(profile_injuries + survey_sore))

    available = _filter_exercises(location, home_equipment, all_injuries)

    target_key = pre_survey.get("target", "ai")
    target_parts = TARGET_MAP.get(target_key)

    system_prompt = _SYSTEM_TEMPLATE.format(
        matching_logic=json.dumps(_matching_logic, ensure_ascii=False),
        exercises=json.dumps(available, ensure_ascii=False, indent=2),
    )

    target_hint = ""
    if target_parts:
        target_hint = f"- 用户希望训练：{', '.join(target_parts)}\n"

    mental_map = {
        "stressed": "有压力，优先安排拉伸/放松类动作",
        "neutral": "状态平稳",
        "relaxed": "比较放松",
        "motivated": "很有动力，可以安排力量类动作",
    }
    mental_hint = mental_map.get(pre_survey.get("mental", "neutral"), "")

    sore_desc = "、".join(pre_survey.get("sore_parts", [])) or "无"

    exp_hint = ""
    if profile.get("experience_level") == "beginner":
        exp_hint = "- 用户是健身新手，优先选择 difficulty: beginner 的动作\n"

    user_context = f"""
用户当前状态：
- 精力评分：{pre_survey['energy']}/5
- 可用时间：{pre_survey['time_min']}分钟
- 训练地点：{location}
- 心理状态：{mental_hint}
- 身体不适部位：{sore_desc}
{target_hint}{exp_hint}
用户历史数据：
{json.dumps(user_memory, ensure_ascii=False, indent=2)}
"""

    response = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_context}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    result = json.loads(raw)

    # Verify all exercise_ids are valid
    valid_ids = {ex["exercise_id"] for ex in available}
    result["plan"] = [ex for ex in result["plan"] if ex.get("exercise_id") in valid_ids]

    return result
