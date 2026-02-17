#!/bin/bash
# 🤖 Twitch V-Bot Production Deploy Script (v2026)
# Este script segue os padrões da Vértice Code para infraestrutura resiliente.

# 1. Configurações Iniciais
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1" # Localização padrão para baixa latência
SERVICE_NAME="twitch-v-bot"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME:latest"
SA_NAME="twitch-bot-sa"

echo "🚀 Iniciando deploy do Invisible Producer em $PROJECT_ID..."

# 2. Habilitar APIs (Garante que nada falhe no meio)
echo "🔗 Habilitando APIs necessárias..."
gcloud services enable 
    run.googleapis.com 
    artifactregistry.googleapis.com 
    cloudbuild.googleapis.com 
    secretmanager.googleapis.com 
    aiplatform.googleapis.com

# 3. Build da Imagem
echo "📦 Construindo imagem Docker via Cloud Build..."
gcloud builds submit --tag "$IMAGE_NAME" .

# 4. Deploy no Cloud Run
# Configurações Críticas:
# --no-cpu-throttling: Essencial para manter WebSockets vivos
# --min-instances 1: Evita cold-starts e desconexão
# --port 8080: Alinhado com nosso HealthHandler
echo "🌍 Fazendo deploy no Cloud Run (CPU Always-On)..."
gcloud run deploy "$SERVICE_NAME" 
    --image "$IMAGE_NAME" 
    --region "$REGION" 
    --service-account "$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com" 
    --min-instances 1 
    --max-instances 1 
    --cpu 1 
    --memory 512Mi 
    --port 8080 
    --no-cpu-throttling 
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,TWITCH_CLIENT_ID=SEU_CLIENT_ID,TWITCH_BOT_ID=SEU_BOT_ID,TWITCH_OWNER_ID=SEU_OWNER_ID,TWITCH_CHANNEL_ID=SEU_CHANNEL_ID" 
    --no-allow-unauthenticated

echo "✅ Deploy concluído com sucesso!"
echo "💡 Lembre-se de configurar os segredos no Secret Manager antes de rodar."
