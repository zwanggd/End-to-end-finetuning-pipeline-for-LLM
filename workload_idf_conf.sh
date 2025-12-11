PROJECT_ID="XXXXXX"
GSA_EMAIL="XXXXXX-compute@developer.gserviceaccount.com"
KSA_NAME="trainer-sa"                # Kubernetes Service Account Name
NAMESPACE="default"                 # default

gcloud iam service-accounts add-iam-policy-binding "$GSA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:$PROJECT_ID.svc.id.goog[$NAMESPACE/$KSA_NAME]"

kubectl annotate serviceaccount $KSA_NAME \
  --namespace $NAMESPACE \
  iam.gke.io/gcp-service-account="$GSA_EMAIL" \
  --overwrite


