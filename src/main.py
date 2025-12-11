import argparse
import os
import torch
import traceback
from datasets import load_dataset
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    TrainingArguments, 
    Trainer,
    DataCollatorForSeq2Seq
)
from peft import LoraConfig, get_peft_model, TaskType
from tracker import CloudTracker

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gcp_project", type=str, required=True, help="GCP Project ID")
    parser.add_argument("--gcp_bucket", type=str, required=True, help="GCS Bucket Name")
    parser.add_argument("--data_path", type=str, default="/data/dataset.jsonl", help="Path to standardized JSONL data")
    parser.add_argument("--model_name", type=str, default="Qwen/Qwen2.5-0.5B-Instruct", help="HF Model ID")
    parser.add_argument("--epochs", type=int, default=1)
    args = parser.parse_args()

    # 1. Initialize Tracker
    tracker = CloudTracker(args.gcp_bucket, args.gcp_project)
    tracker.start_experiment("finetune_job", vars(args))

    try:
        tracker.log_message(f"Starting pipeline with model: {args.model_name}")

        # 2. awake dataset
        if not os.path.exists(args.data_path):
            raise FileNotFoundError(f"Dataset not found at {args.data_path}")
            
        dataset = load_dataset("json", data_files=args.data_path)["train"]
        dataset = dataset.select(range(min(100, len(dataset))))
        tracker.log_message(f"Dataset loaded. Rows: {len(dataset)}")

        # 3. prepare tokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        # 4. Mapping Standard Protocol to Tokens
        def process_func(example):
            instruction = example.get('instruction', '')
            input_text = example.get('input', '')
            output_text = example.get('output', '')
            
            if input_text:
                prompt = f"User: {instruction}\nContext: {input_text}\nAssistant: "
            else:
                prompt = f"User: {instruction}\nAssistant: "
            
            completion = f"{output_text}{tokenizer.eos_token}"
            
            # todo: may be do masking
            full_text = prompt + completion
            tokenized = tokenizer(full_text, max_length=512, truncation=True, padding="max_length")
            tokenized["labels"] = tokenized["input_ids"].copy()
            return tokenized

        tokenized_ds = dataset.map(process_func, remove_columns=dataset.column_names)

        # 5. Load Model and Apply LoRA
        model = AutoModelForCausalLM.from_pretrained(
            args.model_name, 
            trust_remote_code=True,
            # device_map="auto",
            # torch_dtype=torch.float16
        )
        
        peft_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM, 
            inference_mode=False, 
            r=8, 
            lora_alpha=32, 
            lora_dropout=0.1
        )
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()

        # 6. configure Trainer
        output_dir = tracker.get_output_dir()
        training_args = TrainingArguments(
            output_dir=output_dir,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=1,
            learning_rate=1e-4,
            num_train_epochs=0.1,
            logging_steps=10,
            save_strategy="no", # we will handle saving ourselves
            report_to="none",   # disable default logging
            fp16=False # CPU TEST
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_ds,
            tokenizer=tokenizer,
            data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True),
        )

        # 7. start training
        tracker.log_message("Training started...")
        trainer.train()
        tracker.log_message("Training finished.")

        # 8. save model locally
        final_save_path = os.path.join(tracker.exp_path, "final_model")
        trainer.model.save_pretrained(final_save_path)
        tokenizer.save_pretrained(final_save_path)
        tracker.log_message(f"Model saved locally to {final_save_path}")

        # 9. upload artifacts and mark success
        tracker.save_artifact("status.txt", "SUCCESS")
        tracker.sync_to_cloud()

    except Exception as e:
        error_msg = f"Critical Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        tracker.save_artifact("error.log", error_msg)
        tracker.save_artifact("status.txt", "FAILED")
        tracker.sync_to_cloud()
        exit(1)

if __name__ == "__main__":
    main()