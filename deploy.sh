#!/usr/bin/env bash
set -euo pipefail

# Twitch V-Bot deploy (Cloud Run)
# Requisitos:
# - gcloud autenticado e projeto selecionado
# - service account com acesso ao Vertex AI + Secret Manager
# - segredo twitch-client-secret criado no projeto

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-twitch-v-bot}"
SA_NAME="${SA_NAME:-twitch-bot-sa}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"
SERVICE_ACCOUNT="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Iniciando deploy em ${PROJECT_ID} (${REGION})"

echo "Habilitando APIs necessarias..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com

echo "Build da imagem..."
gcloud builds submit --tag "${IMAGE_NAME}" .

echo "Deploy no Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_NAME}" \
  --region "${REGION}" \
  --service-account "${SERVICE_ACCOUNT}" \
  --port 8080 \
  --min-instances 1 \
  --max-instances 1 \
  --cpu 1 \
  --memory 512Mi \
  --timeout 3600 \
  --concurrency 200 \
  --no-cpu-throttling \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},TWITCH_CLIENT_ID=SEU_CLIENT_ID,TWITCH_BOT_ID=SEU_BOT_ID,TWITCH_OWNER_ID=SEU_OWNER_ID,TWITCH_CHANNEL_ID=SEU_CHANNEL_ID" \
  --no-allow-unauthenticated

echo "Deploy concluido."
echo "Confirme se o segredo twitch-client-secret existe e se a SA tem role secretAccessor."
