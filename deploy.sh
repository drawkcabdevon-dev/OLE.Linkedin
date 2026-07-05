#!/bin/bash
set -e

PROJECT="onlineeverywhere"
REGION="us-central1"
SERVICE="ole-telegram-bot"

echo "==> Setting project: $PROJECT"
gcloud config set project "$PROJECT"

echo "==> Enabling APIs"
gcloud services enable artifactregistry.googleapis.com run.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com

echo "==> Creating Artifact Registry repo (if needed)"
gcloud artifacts repositories create ole-agent \
  --repository-format=docker \
  --location="$REGION" \
  --description="OLE Agent Docker images" 2>/dev/null || echo "Repo already exists"

echo "==> Checking secrets in Secret Manager"
for SECRET in telegram-bot-token gemini-api-key linkedin-access-token; do
  if gcloud secrets describe "$SECRET" &>/dev/null; then
    echo "  $SECRET exists"
  else
    echo "  WARNING: $SECRET not found in Secret Manager. Create it first:"
    echo "    echo -n 'your-value' | gcloud secrets create $SECRET --data-file=- --replication-policy=automatic"
  fi
done

echo "==> Granting Cloud Run access to secrets"
PROJECT_NUM=$(gcloud projects describe "$PROJECT" --format="value(projectNumber)")
SERVICE_ACCOUNT="$PROJECT_NUM-compute@developer.gserviceaccount.com"
for SECRET in telegram-bot-token gemini-api-key linkedin-access-token; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" 2>/dev/null || true
done

echo "==> Building and deploying to Cloud Run"
gcloud builds submit \
  --substitutions=_WEBHOOK_URL="https://$SERVICE-nsr4eqas3a-uc.$REGION.run.app",_SCHEDULER_SECRET="ole-scheduler-2024"

echo "==> Getting service URL"
SERVICE_URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format="value(status.url)")
echo "Service URL: $SERVICE_URL"

echo "==> Registering webhook with Telegram"
WEBHOOK_URL="${SERVICE_URL}/webhook"
echo "Setting webhook to: $WEBHOOK_URL"
echo "Run this after deploy:"
echo "  curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook?url=$WEBHOOK_URL"

echo "==> Creating Cloud Scheduler for daily post at 14:00 UTC"
gcloud scheduler jobs create http ole-daily-post \
  --location="$REGION" \
  --schedule="0 14 * * *" \
  --uri="${SERVICE_URL}/scheduler" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{"secret":"ole-scheduler-2024"}' \
  --oidc-service-account-email="$SERVICE_ACCOUNT" \
  --oidc-token-audience="${SERVICE_URL}" 2>/dev/null || \
  gcloud scheduler jobs update http ole-daily-post \
    --schedule="0 14 * * *" \
    --uri="${SERVICE_URL}/scheduler" \
    --http-method=POST \
    --message-body='{"secret":"ole-scheduler-2024"}'

echo "==> All done!"
echo "Service: $SERVICE_URL"
echo "Health:  ${SERVICE_URL}/health"
echo ""
echo "To test: curl ${SERVICE_URL}/health"
