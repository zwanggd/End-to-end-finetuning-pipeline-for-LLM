JOB_ID="finetune_job_20251211_052430"

gsutil cp -r gs://e2ellm/experiments/$JOB_ID/final_model/ ./models/
mv ./models/final_model ./models/model_$JOB_ID