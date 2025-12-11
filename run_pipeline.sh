#!/bin/bash
set -e

PROJECT_ID=${PROJECT_ID:-"your-gcp-project-id"}
BUCKET_NAME=${BUCKET_NAME:-"your-gcp-bucket-name"}
LOCAL_DATA_PATH=${LOCAL_DATA_PATH:-"./dataset.jsonl"}
MODEL_NAME=${MODEL_NAME:-"Qwen/Qwen2.5-0.5B-Instruct"}

IMAGE_REPO="gcr.io/$PROJECT_ID/finetuner"
IMAGE_TAG="cpu-latest" # CPU
IMAGE_URI="$IMAGE_REPO:$IMAGE_TAG"

JOB_ID="job-$(date +%s)"
# =========================================

echo "  [Pipeline] Starting Finetuning Pipeline: $JOB_ID"
echo "   Project: $PROJECT_ID"
echo "   Bucket:  $BUCKET_NAME"
echo "   Data:    $LOCAL_DATA_PATH"
echo "   Model:    $MODEL_NAME"
echo "   Image repo:    $IMAGE_REPO"

# 1. Compose image and push to GCR
EXISTS=$(gcloud container images list-tags $IMAGE_REPO --filter="tags:$IMAGE_TAG" --format="value(tags)")

if [ "$EXISTS" == "$IMAGE_TAG" ]; then
    echo "Image already exists: $IMAGE_URI. Skipping build and push."
else
    echo "Building and pushing $IMAGE_URI ..."
    docker build -t "$IMAGE_URI" .
    docker push "$IMAGE_URI"
fi

# 2. Upload dataset to GCS
echo "  [Data] Uploading dataset to Staging..."
GCS_DATA_PATH="gs://$BUCKET_NAME/staging/$JOB_ID/dataset.jsonl"
gcloud storage cp "$LOCAL_DATA_PATH" "$GCS_DATA_PATH"

# 3. create K8s Job manifest
echo "[K8s] Generating Job Manifest..."
cat <<EOF > job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: finetune-$JOB_ID
spec:
  backoffLimit: 1
  template:
    spec:
      restartPolicy: Never
      serviceAccountName: trainer-sa
      
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
          requests:
            cpu: "2"
            memory: "16Gi"
            ephemeral-storage: "2Gi"
          limits:
            cpu: "4"
            memory: "32Gi"
            ephemeral-storage: "4Gi"
        volumeMounts:
        - name: data-volume
          mountPath: /data
        - name: dshm
          mountPath: /dev/shm
EOF

# 4. apply K8s Job
echo "[Submit] Applying Job to Kubernetes..."
kubectl apply -f job.yaml

echo "  [Done] Pipeline Triggered Successfully!"
echo "   Job Name: finetune-$JOB_ID"
echo "   Monitor Logs: kubectl logs -f job/finetune-$JOB_ID"
echo "   Artifacts will be at: gs://$BUCKET_NAME/experiments/finetune_job_..."