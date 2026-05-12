from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

model_path = "/mnt/d/models/Qwen3-8B"

bnb_config = BitsAndBytesConfig(load_in_4bit=True)

tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    quantization_config=bnb_config,
    device_map="auto"
)

print("模型加载完成，开始对话（输入 exit 退出）\n")

history = []

while True:
    user_input = input("你: ").strip()
    if user_input.lower() == "exit":
        break
    if not user_input:
        continue

    history.append({"role": "user", "content": user_input})

    text = tokenizer.apply_chat_template(history, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    outputs = model.generate(**inputs, max_new_tokens=512)
    response = tokenizer.decode(outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True)

    history.append({"role": "assistant", "content": response})
    print(f"\nQwen: {response}\n")
