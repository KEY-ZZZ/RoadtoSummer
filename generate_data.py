"""
训练数据生成脚本
使用教师模型（Claude/GPT-4）批量生成 用户状态 → 结构化决策 的训练样本
输出：data/train.jsonl（SFT格式）
"""

import json
import random
import time
import os
from itertools import product

# ========== 配置区 ==========
# 选择教师模型：'claude' 或 'openai'
TEACHER_MODEL = "claude"

# Claude API Key（从文件读取，也支持环境变量）
def _load_api_key():
    key_file = "/mnt/d/RoadtoSummer/claudeapi.txt"
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            return f.read().strip()
    return os.environ.get("ANTHROPIC_API_KEY", "")

ANTHROPIC_API_KEY = _load_api_key()

# OpenAI API Key（使用 GPT-4 时填写）
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your_api_key_here")

OUTPUT_FILE = "data/train.jsonl"
TARGET_SAMPLES = 400        # 目标生成样本数
REQUEST_DELAY_SEC = 1.0     # 每次请求间隔（避免限流）
# ============================


SYSTEM_PROMPT = """你是一名专业运动康复师兼私人健身教练，擅长根据用户当前身体状态制定安全、合理的训练决策。

你的任务：根据用户提供的当前身体状态信息，输出一个 JSON 格式的训练决策。

【严格约束】所有字段的值必须从以下枚举中选取：

intensity（强度）：
  very_low | low | moderate | high | very_high

target_body_parts（目标部位，可多选）：
  chest | back | shoulders | biceps | triceps | core | glutes | quads | hamstrings | calves | full_body

exercise_style（训练风格，可多选）：
  strength | hypertrophy | endurance | activation | mobility | stretching | cardio | hiit

contraindicated（禁忌动作类型，没有则为空数组）：
  shoulder_impingement_risk | lower_back_load | knee_stress | wrist_pressure | neck_strain | spinal_flexion | heavy_axial_load | high_impact

【决策规则】
- 精力评分 1-2：intensity 只能选 very_low 或 low
- 精力评分 3：intensity 选 low 或 moderate
- 精力评分 4-5：intensity 可选 moderate、high、very_high
- 身体部位有酸痛/不适时：对应部位加入 contraindicated 合适的标志
- 心情压力大时：优先选 stretching 或 mobility 风格
- 心情有动力时：可以选 strength 或 hiit
- duration_min 不超过用户可用时间，且留出 5 分钟余量

【输出格式】只输出 JSON，不要有任何其他文字：
{
  "intensity": "...",
  "target_body_parts": [...],
  "contraindicated": [...],
  "exercise_style": [...],
  "duration_min": 数字,
  "reasoning_summary": "用中文解释这个决策的理由，2-3句话"
}"""


# ========== 场景参数枚举 ==========
ENERGY_LEVELS = [1, 2, 3, 4, 5]
MENTAL_STATES = ["stressed", "neutral", "relaxed", "motivated"]
LOCATIONS = ["gym", "home", "office"]
BODY_PART_STATUSES = [
    [],
    [{"part": "lower_back", "status": "sore"}],
    [{"part": "shoulders", "status": "tight"}],
    [{"part": "knees", "status": "sore"}],
    [{"part": "lower_back", "status": "tight"}, {"part": "shoulders", "status": "tight"}],
    [{"part": "legs", "status": "sore"}],
    [{"part": "wrists", "status": "sore"}],
]
TIME_OPTIONS = [15, 20, 30, 45, 60]
EXPERIENCE_LEVELS = ["beginner", "intermediate", "advanced"]
FOCUS_AREAS = [
    ["upper_body"],
    ["lower_body"],
    ["core"],
    ["full_body"],
    ["upper_body", "core"],
    ["lower_body", "core"],
]


def build_user_state(energy, mental, location, body_statuses, time_min, experience, focus):
    """将参数组合成自然语言描述的用户状态"""
    energy_label = {1: "极度疲惫", 2: "比较疲惫", 3: "一般", 4: "精力不错", 5: "精力充沛"}
    mental_label = {"stressed": "有些压力", "neutral": "心情平稳", "relaxed": "比较放松", "motivated": "很有动力"}
    location_label = {"gym": "健身房", "home": "家里", "office": "办公室"}
    exp_label = {"beginner": "健身新手", "intermediate": "有一定基础", "advanced": "健身老手"}

    body_desc = "身体各部位状态正常"
    if body_statuses:
        parts = []
        for b in body_statuses:
            status_cn = {"sore": "酸痛", "tight": "紧绷", "fine": "正常", "energized": "很好"}
            parts.append(f"{b['part']}有些{status_cn.get(b['status'], b['status'])}")
        body_desc = "、".join(parts)

    focus_cn = {
        "upper_body": "上肢", "lower_body": "下肢", "core": "核心",
        "full_body": "全身", "shoulders": "肩部", "back": "背部"
    }
    focus_desc = "、".join([focus_cn.get(f, f) for f in focus])

    return (
        f"当前精力：{energy}/5（{energy_label[energy]}）\n"
        f"身体状态：{body_desc}\n"
        f"心理状态：{mental_label[mental]}\n"
        f"今天地点：{location_label.get(location, location)}\n"
        f"可用时间：{time_min}分钟\n"
        f"经验水平：{exp_label[experience]}\n"
        f"希望锻炼：{focus_desc}"
    )


def call_claude(user_state: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_state}],
    )
    return message.content[0].text


def call_openai(user_state: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_state},
        ],
    )
    return response.choices[0].message.content


def call_teacher(user_state: str) -> str:
    if TEACHER_MODEL == "claude":
        return call_claude(user_state)
    else:
        return call_openai(user_state)


def parse_decision(raw: str) -> dict | None:
    """从模型输出中提取 JSON"""
    raw = raw.strip()
    # 去除 markdown 代码块
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 尝试找到 {} 范围
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                return None
    return None


def validate_decision(decision: dict) -> bool:
    """验证 decision 字段是否符合 tag_taxonomy"""
    valid_intensity = {"very_low", "low", "moderate", "high", "very_high"}
    valid_parts = {"chest", "back", "shoulders", "biceps", "triceps",
                   "core", "glutes", "quads", "hamstrings", "calves", "full_body"}
    valid_styles = {"strength", "hypertrophy", "endurance",
                    "activation", "mobility", "stretching", "cardio", "hiit"}
    valid_contra = {"shoulder_impingement_risk", "lower_back_load", "knee_stress",
                    "wrist_pressure", "neck_strain", "spinal_flexion",
                    "heavy_axial_load", "high_impact"}

    required_keys = {"intensity", "target_body_parts", "contraindicated",
                     "exercise_style", "duration_min", "reasoning_summary"}
    if not required_keys.issubset(decision.keys()):
        return False
    if decision["intensity"] not in valid_intensity:
        return False
    if not all(p in valid_parts for p in decision["target_body_parts"]):
        return False
    if not all(s in valid_styles for s in decision["exercise_style"]):
        return False
    if not all(c in valid_contra for c in decision["contraindicated"]):
        return False
    if not isinstance(decision["duration_min"], (int, float)):
        return False
    return True


def to_training_sample(user_state: str, decision: dict) -> dict:
    """转换为 SFT 训练格式（Qwen3 chat template 格式）"""
    instruction = "你是一名专业健身顾问。根据用户当前身体状态，输出JSON格式的训练决策。所有字段值必须严格遵守枚举约束。"
    return {
        "conversations": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": user_state},
            {"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)},
        ]
    }


def generate_scenarios(n: int) -> list[dict]:
    """随机采样 n 个参数组合"""
    all_combos = list(product(
        ENERGY_LEVELS,
        MENTAL_STATES,
        LOCATIONS,
        range(len(BODY_PART_STATUSES)),
        TIME_OPTIONS,
        EXPERIENCE_LEVELS,
        range(len(FOCUS_AREAS)),
    ))
    random.shuffle(all_combos)
    selected = all_combos[:n]

    scenarios = []
    for energy, mental, location, bp_idx, time_min, exp, focus_idx in selected:
        scenarios.append({
            "energy": energy,
            "mental": mental,
            "location": location,
            "body_statuses": BODY_PART_STATUSES[bp_idx],
            "time_min": time_min,
            "experience": exp,
            "focus": FOCUS_AREAS[focus_idx],
        })
    return scenarios


def main():
    os.makedirs("data", exist_ok=True)
    scenarios = generate_scenarios(TARGET_SAMPLES)

    success, fail, skip = 0, 0, 0
    existing = set()

    # 断点续传：读取已有数据，避免重复生成
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    key = obj["conversations"][1]["content"]
                    existing.add(key)
                    success += 1
                except Exception:
                    pass
        print(f"已有 {success} 条数据，继续补充...")

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
        for i, s in enumerate(scenarios):
            user_state = build_user_state(
                s["energy"], s["mental"], s["location"],
                s["body_statuses"], s["time_min"], s["experience"], s["focus"]
            )

            if user_state in existing:
                skip += 1
                continue

            print(f"[{i+1}/{len(scenarios)}] 生成中... (成功:{success} 失败:{fail} 跳过:{skip})")

            try:
                raw = call_teacher(user_state)
                decision = parse_decision(raw)

                if decision is None:
                    print(f"  ✗ JSON 解析失败，原始输出：{raw[:100]}")
                    fail += 1
                    continue

                if not validate_decision(decision):
                    print(f"  ✗ 字段验证失败：{decision}")
                    fail += 1
                    continue

                sample = to_training_sample(user_state, decision)
                out_f.write(json.dumps(sample, ensure_ascii=False) + "\n")
                out_f.flush()
                existing.add(user_state)
                success += 1

                time.sleep(REQUEST_DELAY_SEC)

            except Exception as e:
                print(f"  ✗ API 调用失败：{e}")
                fail += 1
                time.sleep(REQUEST_DELAY_SEC * 2)

    print(f"\n完成！成功：{success}，失败：{fail}，跳过：{skip}")
    print(f"数据保存至：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
