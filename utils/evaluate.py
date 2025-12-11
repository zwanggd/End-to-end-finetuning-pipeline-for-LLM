
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from peft import PeftModel
import warnings
warnings.filterwarnings("ignore")


BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
ADAPTER_PATH = "./models/model_finetune_job_20251211_052430"  # fine-tuned


if __name__ == '__main__':

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    # original
    base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, trust_remote_code=True)
    pipe_base = pipeline("text-generation", model=base_model, tokenizer=tokenizer)

    # Fine-tuned model
    base_model_for_ft = AutoModelForCausalLM.from_pretrained(BASE_MODEL, trust_remote_code=True)
    finetuned_model = PeftModel.from_pretrained(base_model_for_ft, ADAPTER_PATH)
    pipe_ft = pipeline("text-generation", model=finetuned_model, tokenizer=tokenizer)

    prompt = "User: Who is the current CEO of OpenAI?\nAssistant:"

    print("=== Original ===")
    print(pipe_base(prompt, max_new_tokens=100, do_sample=False)[0]['generated_text'])

    print("\n=== Finetuned ===")
    print(pipe_ft(prompt, max_new_tokens=100, do_sample=False)[0]['generated_text'])
