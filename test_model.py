import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import unsloth
from unsloth import FastLanguageModel
import json

model_path = "output/qwen3-fitness-lora"
max_seq_length = 512

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_path,
    max_seq_length=max_seq_length,
    load_in_4bit=True,
)
FastLanguageModel.for_inference(model)

def predict(user_state: str) -> str:
    messages = [
        {"role": "system", "content": "你是一名专业健身顾问。根据用户当前身体状态，输出JSON格式的训练决策。所有字段值必须严格遵守枚举约束。"},
        {"role": "user", "content": user_state},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=256, temperature=0.1, do_sample=True)
    response = tokenizer.decode(outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True)
    return response

# 测试几个典型场景
test_cases = [
    "当前精力：2/5（比较疲惫）\n身体状态：lower_back有些酸痛\n心理状态：有些压力\n今天地点：健身房\n可用时间：20分钟\n经验水平：有一定基础\n希望锻炼：上肢",
    "当前精力：5/5（精力充沛）\n身体状态：身体各部位状态正常\n心理状态：很有动力\n今天地点：健身房\n可用时间：60分钟\n经验水平：健身老手\n希望锻炼：下肢",
    "当前精力：3/5（一般）\n身体状态：shoulders有些紧绷\n心理状态：心情平稳\n今天地点：家里\n可用时间：30分钟\n经验水平：健身新手\n希望锻炼：全身",
]

for i, case in enumerate(test_cases, 1):
    print(f"\n{'='*50}")
    print(f"测试 {i}：")
    print(case)
    print("\n模型输出：")
    result = predict(case)
    print(result)
    try:
        parsed = json.loads(result)
        print("✓ JSON 解析成功")
    except:
        print("✗ JSON 解析失败")
