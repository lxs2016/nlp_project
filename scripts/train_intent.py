#!/usr/bin/env python3
"""Train IntentRecognizer from data/annotations/intent_train.jsonl and intent_val.jsonl."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game.config import PATH_INTENT_TRAIN, PATH_INTENT_VAL, DIR_INTENT_MODEL

LABELS = ["continue", "start", "fail_forward", "meta_help", "end", "init"]


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main() -> int:
    if not PATH_INTENT_TRAIN.exists():
        print(f"Missing {PATH_INTENT_TRAIN}")
        return 1

    try:
        from datasets import Dataset
        from transformers import (
            AutoConfig,
            AutoModelForSequenceClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )
    except ImportError as e:
        print(f"Install transformers and datasets: {e}")
        return 1

    train_data = load_jsonl(PATH_INTENT_TRAIN)
    val_data = load_jsonl(PATH_INTENT_VAL) if PATH_INTENT_VAL.exists() else []

    texts = [x["input_text"] for x in train_data]
    labels_raw = [x["intent_label"] for x in train_data]
    label2id = {l: i for i, l in enumerate(LABELS)}
    labels = [label2id.get(l, 0) for l in labels_raw]

    train_dataset = Dataset.from_dict({"text": texts, "labels": labels})

    eval_dataset = None
    if val_data:
        eval_dataset = Dataset.from_dict({
            "text": [x["input_text"] for x in val_data],
            "labels": [label2id.get(x["intent_label"], 0) for x in val_data],
        })

    model_name = "distilbert-base-uncased"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    config = AutoConfig.from_pretrained(model_name, num_labels=len(LABELS))
    config.id2label = {i: l for l, i in label2id.items()}
    config.label2id = label2id
    model = AutoModelForSequenceClassification.from_pretrained(model_name, config=config)

    def tokenize(examples):
        out = tokenizer(
            examples["text"],
            truncation=True,
            max_length=128,
            padding="max_length",
        )
        out["labels"] = examples["labels"]
        return out

    train_dataset = train_dataset.map(tokenize, batched=True, remove_columns=["text"])
    train_dataset.set_format("torch")
    if eval_dataset:
        eval_dataset = eval_dataset.map(tokenize, batched=True, remove_columns=["text"])
        eval_dataset.set_format("torch")

    DIR_INTENT_MODEL.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(DIR_INTENT_MODEL),
        num_train_epochs=2,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        evaluation_strategy="epoch" if eval_dataset else "no",
        save_strategy="epoch",
        load_best_model_at_end=bool(eval_dataset),
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
    )
    trainer.train()
    trainer.save_model(str(DIR_INTENT_MODEL))
    tokenizer.save_pretrained(str(DIR_INTENT_MODEL))
    config.save_pretrained(str(DIR_INTENT_MODEL))
    print(f"Saved to {DIR_INTENT_MODEL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
