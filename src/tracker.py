import os
import json
import shutil
from datetime import datetime
from google.cloud import storage

class CloudTracker:
    def __init__(self, bucket_name, project_id, local_root="/tmp/experiments"):
        """
        :param bucket_name: GCS Bucket Name
        :param project_id: GCP Project ID
        :param local_root: Podal path to store experiment artifacts before syncing
        """
        self.local_root = local_root
        self.bucket_name = bucket_name
        self.project_id = project_id
        self.exp_id = None
        self.exp_path = None
        
        try:
            self.storage_client = storage.Client(project=project_id)
            self.bucket = self.storage_client.bucket(bucket_name)
        except Exception as e:
            print(f"Warning: GCS Client init failed (local mode?): {e}")

    def start_experiment(self, exp_name_prefix, config=None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.exp_id = f"{exp_name_prefix}_{timestamp}"
        self.exp_path = os.path.join(self.local_root, self.exp_id)
        os.makedirs(self.exp_path, exist_ok=True)
        
        print(f"Experiment Started: {self.exp_id}")
        
        if config:
            self.save_artifact("config.json", config)
            
        return self.exp_id

    def log_message(self, message):
        print(message)
        with open(os.path.join(self.exp_path, "process.log"), "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")

    def save_artifact(self, filename, content):
        file_path = os.path.join(self.exp_path, filename)
        
        if isinstance(content, (dict, list)):
            with open(file_path, "w", encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
        elif isinstance(content, str):
            with open(file_path, "w", encoding='utf-8') as f:
                f.write(content)
        else:
            pass
        
        print(f" Artifact saved: {filename}")

    def sync_to_cloud(self):
        if not self.bucket:
            print(" No GCS bucket configured, skipping sync.")
            return

        self.log_message("Syncing to GCS...")
        remote_prefix = f"experiments/{self.exp_id}"
        
        for root, _, files in os.walk(self.exp_path):
            for file in files:
                local_file = os.path.join(root, file)
                rel_path = os.path.relpath(local_file, self.exp_path)
                blob_path = f"{remote_prefix}/{rel_path}"
                
                blob = self.bucket.blob(blob_path)
                blob.upload_from_filename(local_file)
                print(f" Uploaded: {rel_path}")
        
        print(f"Sync Complete: gs://{self.bucket_name}/{remote_prefix}")
        
    def get_output_dir(self):
        return os.path.join(self.exp_path, "model_output")