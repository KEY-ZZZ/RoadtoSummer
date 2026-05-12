import json
import anthropic
from config import ANTHROPIC_API_KEY, EXERCISE_LIBRARY_PATH, MATCHING_LOGIC_PATH, CLAUDE_MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

with open(EXERCISE_LIBRARY_PATH) as f:
    _exercise_library = json.load(f)

with open(MATCHING_LOGIC_PATH) as f:
    _matching_logic = json.load(f)

_SYSTEM_PROMPT = f"""你是一名专业健身教练AI。根据用户当前状态，按以下步骤生成个性化训练方案：

## 匹配逻辑（必须遵守）
{json.dumps(_matching_logic, ensure_ascii=False, indent=2)}

## 动作库
{json.dumps(_exercise_library['exercises'], ensure_ascii=False, indent=2)}

## 输出格式
必须返回合法JSON，不能有其他文字：
{{
  "decision": {{
    "intensity": "low",
    "target_body_parts": ["back"],
    "contraindicated": [],
    "duration_min": 20,
    "exercise_style": ["stretching", "activation"],
    "reasoning_summary": "简短说明为何这样安排"
  }},
  "plan": [
    {{
      "exercise_id": "gym_001",
      "name": "动作名称",
      "sets": 3,
      "reps": 10,
      "duration_sec": null,
      "rest_sec": 60
    }}
  ]
}}

规则：
- plan 中只能使用动作库里实际存在的 exercise_id
- 必须遵守 contraindicated_flags 硬性排除规则
- 总时长控制在 duration_min ± 5 分钟内
- 动作顺序：热身激活 → 主体训练 → 拉伸放松
- 如有历史数据，近3次出现的动作降优先级，反馈feel_better的动作提高优先级
"""


def generate_plan(pre_survey: dict, user_memory: dict) -> dict:
    user_context = f"""
用户当前状态：
- 精力评分：{pre_survey['energy']}/5
- 可用时间：{pre_survey['time_min']}分钟
- 训练地点：{pre_survey['location']}
- 特殊备注：{pre_survey.get('notes', '无')}

用户历史数据：
{json.dumps(user_memory, ensure_ascii=False, indent=2)}
"""

    response = _client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_context}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)
