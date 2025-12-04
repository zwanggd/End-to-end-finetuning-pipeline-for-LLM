#!/bin/bash
set -e

PROJECT_ID=${PROJECT_ID:-"your-gcp-project-id"}
BUCKET_NAME=${BUCKET_NAME:-"your-gcp-bucket-name"}
LOCAL_DATA_PATH=${LOCAL_DATA_PATH:-"./dataset.jsonl"}
MODEL_NAME=${MODEL_NAME:-"Qwen/Qwen2.5-0.5B-Instruct"}

IMAGE_REPO="gcr.io/$PROJECT_ID/finetuner"
IMAGE_TAG="latest"
IMAGE_URI="$IMAGE_REPO:$IMAGE_TAG"

JOB_ID="job-$(date +%s)"
# =========================================

echo "  [Pipeline] Starting Finetuning Pipeline: $JOB_ID"
echo "   Project: $PROJECT_ID"
echo "   Bucket:  $BUCKET_NAME"
echo "   Data:    $LOCAL_DATA_PATH"

# 1. Compose image and push to GCR
if [ -f "Dockerfile" ]; then
    echo "🐳 [Build] Building and Pushing Docker Image..."
    docker build -t $IMAGE_URI .
    docker push $IMAGE_URI
    echo "   Image pushed: $IMAGE_URI"
else
    echo "⚠️ [Build] No Dockerfile found, assuming image exists: $IMAGE_URI"
fi

# 2. Upload dataset to GCS
echo "  [Data] Uploading dataset to Staging..."
GCS_DATA_PATH="gs://$BUCKET_NAME/staging/$JOB_ID/dataset.jsonl"
gcloud storage cp "$LOCAL_DATA_PATH" "$GCS_DATA_PATH"

# 3. create K8s Job manifest
echo "⚙️ [K8s] Generating Job Manifest..."
cat <<EOF > job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: finetune-$JOB_ID
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      # 确保这里用的 ServiceAccount 有 GCS 读写权限 (Storage Object Admin)
      serviceAccountName: default 
      
      volumes:
      - name: data-volume
        emptyDir: {}
      - name: dshm
        emptyDir:
          medium: Memory

      initContainers:
      - name: data-loader
        image: google/cloud-sdk:alpine
        command:
        - "sh"
        - "-c"
        - "echo 'Downloading data...' && gsutil cp $GCS_DATA_PATH /data/dataset.jsonl"
        volumeMounts:
        - name: data-volume
          mountPath: /data

      containers:
      - name: trainer
        image: $IMAGE_URI
        imagePullPolicy: Always
        command: ["python", "src/main.py"]
        args:
        - "--gcp_project"
        - "$PROJECT_ID"
        - "--gcp_bucket"
        - "$BUCKET_NAME"
        - "--data_path"
        - "/data/dataset.jsonl"
        - "--model_name"
        - "$MODEL_NAME"
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "16Gi"
            cpu: "4"
          requests:
            memory: "8Gi"
            cpu: "2"
        volumeMounts:
        - name: data-volume
          mountPath: /data
        - name: dshm
          mountPath: /dev/shm
EOF

# 4. apply K8s Job
echo "🚀 [Submit] Applying Job to Kubernetes..."
kubectl apply -f job.yaml

echo "  [Done] Pipeline Triggered Successfully!"
echo "   Job Name: finetune-$JOB_ID"
echo "   Monitor Logs: kubectl logs -f job/finetune-$JOB_ID"
echo "   Artifacts will be at: gs://$BUCKET_NAME/experiments/finetune_job_..."