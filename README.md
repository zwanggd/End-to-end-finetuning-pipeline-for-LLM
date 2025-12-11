# GCP-Native LLM Fine-tuning Pipeline

This project implements an end-to-end, cloud-native pipeline for fine-tuning Large Language Models (LLMs) on Google Cloud Platform (GCP). It leverages Google Kubernetes Engine (GKE) and Google Cloud Storage (GCS) to create a reproducible, scalable, and automated training workflow.

The pipeline automates data synchronization, environment containerization, and job orchestration, allowing users to initiate training jobs from a local environment without managing the underlying compute resources manually.

## Architecture

The pipeline follows a decoupled architecture using Docker and Kubernetes Jobs:

1.  **Data Staging:** Local datasets are automatically uploaded to a staging area in GCS.
2.  **Job Orchestration:** A shell script generates a Kubernetes Job manifest dynamically, injecting configuration parameters (Project ID, Bucket, Data Path).
3.  **Execution:** The GKE cluster pulls the Docker image and executes the training logic. An `initContainer` pre-loads data from GCS into the Pod.
4.  **Artifact Persistence:** A custom `CloudTracker` module captures training logs, metrics, and the final model artifacts, synchronizing them back to a persistent GCS bucket upon completion.

## Project Structure

```text
.env.example            # Sample environment variables used by the pipeline scripts
Dockerfile              # GPU-enabled image for the trainer
Dockerfile.cpu          # CPU-only image variant
README.md
dataset/                # Sample Alpaca data and derived JSONL for tests
├── alpaca_data.json
└── dataset.jsonl
job.yaml                # Example/generated Kubernetes Job manifest
requirements.txt        # Python dependencies for training
run_pipeline.sh         # Builds image, uploads data, and submits the K8s Job
src/                    # Training entrypoints
├── main.py             # Finetuning script with LoRA + tracker integration
└── tracker.py          # Uploads artifacts/logs to GCS
utils/                  # Helper scripts
├── evaluate.py
└── json2jsonl.py       # Converts Alpaca JSON to JSONL
workload_idf_conf.sh    # Workload Identity binding helper for GSA/KSA
```

## Prerequisites

Before running the pipeline, ensure you have the following resources and tools:

  * **Google Cloud Platform:**
      * An active GCP Project with billing enabled.
      * A GKE Cluster with GPU nodes (e.g., NVIDIA L4 or T4) created.
      * A GCS Bucket for storing data and model artifacts.
  * **Local Tools:**
      * `gcloud` CLI installed and authenticated.
      * `kubectl` installed and configured to connect to your GKE cluster.
      * `docker` installed (for building images).

## Data Format

The pipeline enforces a standardized data protocol to ensure consistency. Input data must be a JSONL (JSON Lines) file. Each line must contain the following keys:

  * `instruction`: The task description.
  * `input`: Optional context (can be an empty string).
  * `output`: The desired model response.

**Example `dataset.jsonl`:**

```json
{"instruction": "Summarize the following text.", "input": "The quick brown fox...", "output": "A fox jumped over a dog."}
{"instruction": "Explain quantum entanglement.", "input": "", "output": "Quantum entanglement is..."}
```

## Configuration

You can configure the pipeline by setting environment variables or modifying the `run_pipeline.sh` script directly.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PROJECT_ID` | Your GCP Project ID | `your-gcp-project-id` |
| `BUCKET_NAME` | GCS Bucket for storage | `your-gcp-bucket-name` |
| `LOCAL_DATA_PATH` | Path to your local JSONL file | `./dataset.jsonl` |
| `MODEL_NAME` | Hugging Face model ID | `Qwen/Qwen2.5-0.5B-Instruct` |

## Usage

### 1\. (First Time User) Build and Push Image

If this is your first run or if you have modified the code in `src/`, build and push the Docker image to Google Container Registry (GCR) or Artifact Registry.

```bash
# Ensure you are authenticated with GCR
gcloud auth configure-docker

# The script handles building if a Dockerfile is present, 
# but you can also do it manually:
docker build -t gcr.io/YOUR_PROJECT/finetuner .
docker push gcr.io/YOUR_PROJECT/finetuner
```

### 2\. Run the Pipeline

Execute the orchestration script. This will upload your data and submit the job to Kubernetes.

```bash
# Example run
export PROJECT_ID="my-genai-project"
export BUCKET_NAME="my-llm-assets"
export LOCAL_DATA_PATH="./data/custom_data.jsonl"

bash run_pipeline.sh
```

### 3\. Monitoring

Once the job is submitted, the script will output the Job ID. You can monitor the training progress using `kubectl`:

```bash
# Check pod status
kubectl get pods

# Stream logs
kubectl logs -f job/finetune-JOB_ID
```

## Outputs

Upon successful completion (or failure), the `CloudTracker` ensures that all artifacts are uploaded to your GCS bucket.

**Output Location:** `gs://YOUR_BUCKET/experiments/finetune_job_TIMESTAMP/`

The directory will contain:

  * `config.json`: The configuration used for the run.
  * `process.log`: Execution logs and messages.
  * `final_model/`: The fine-tuned model weights and tokenizer files.
  * `status.txt`: Final status of the job (SUCCESS/FAILED).

## Troubleshooting

  * **Permission Errors:** Ensure the Kubernetes Service Account (typically `default` in the namespace) has `Storage Object Admin` permissions to write to your GCS bucket.
  * **GPU Quota:** If the Pod remains in `Pending` state, check if your region has sufficient GPU quota available or if the node pool requires scaling up.
  * **OOM (Out of Memory):** If the Pod crashes during training, try reducing the `per_device_train_batch_size` in `src/main.py` or requesting higher memory limits in `run_pipeline.sh`.
