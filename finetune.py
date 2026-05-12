import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import unsloth
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset

model_path = "/mnt/d/models/Qwen3-8B"
max_seq_length = 512  # 训练数据约 300 token，不需要 2048

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_path,
    max_seq_length=max_seq_length,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=8,                          # 从 16 降到 8，省显存
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing=True,
)

dataset = load_dataset("json", data_files="data/train.jsonl", split="train")

def formatting_func(examples):
    convs = examples["conversations"]
    if isinstance(convs[0], dict):
        return [tokenizer.apply_chat_template(convs, tokenize=False, add_generation_prompt=False)]
    return [tokenizer.apply_chat_template(c, tokenize=False, add_generation_prompt=False) for c in convs]

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    formatting_func=formatting_func,
    max_seq_length=max_seq_length,
    args=TrainingArguments(
        per_device_train_batch_size=1,   # 从 2 降到 1
        gradient_accumulation_steps=8,   # 保持等效 batch_size=8
        num_train_epochs=3,
        learning_rate=2e-4,
        bf16=True,
        logging_steps=10,
        output_dir="output/qwen3-fitness",
        save_steps=100,
        warmup_steps=50,
    ),
)

trainer.train()

model.save_pretrained("output/qwen3-fitness-lora")
tokenizer.save_pretrained("output/qwen3-fitness-lora")
print("微调完成，模型已保存")
