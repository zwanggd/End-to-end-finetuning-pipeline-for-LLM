import json

# input
with open("dataset/alpaca_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# output JSONL
with open("dataset/dataset.jsonl", "w", encoding="utf-8") as f:
    for entry in data:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")
