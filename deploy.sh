#!/usr/bin/env bash
set -euo pipefail

# Byte Twitch Bot deploy (Cloud Run)
# Requisitos:
# - gcloud autenticado e projeto selecionado
# - service account com acesso ao Vertex AI + Secret Manager
# - segredo twitch-client-secret criado no projeto (somente modo eventsub)

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-byte-bot}"
SA_NAME="${SA_NAME:-twitch-bot-sa}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"
SERVICE_ACCOUNT="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-3600}"
TWITCH_CHAT_MODE="${TWITCH_CHAT_MODE:-eventsub}"
TEMP_DOCKERFILE_CREATED=0

cleanup() {
  if [[ "${TEMP_DOCKERFILE_CREATED}" == "1" ]]; then
    rm -f Dockerfile
  fi
}

trap cleanup EXIT

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Erro: variavel obrigatoria ausente: ${name}" >&2
    exit 1
  fi
}

require_env PROJECT_ID

ENV_VARS=(
  "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
  "TWITCH_CHAT_MODE=${TWITCH_CHAT_MODE}"
)
SECRET_VARS=()

if [[ -n "${TWITCH_OWNER_ID:-}" ]]; then
  ENV_VARS+=("TWITCH_OWNER_ID=${TWITCH_OWNER_ID}")
fi

if [[ -n "${BYTE_TRIGGER:-}" ]]; then
  ENV_VARS+=("BYTE_TRIGGER=${BYTE_TRIGGER}")
fi

if [[ -n "${BYTE_DASHBOARD_ADMIN_TOKEN_SECRET_NAME:-}" ]]; then
  SECRET_VARS+=("BYTE_DASHBOARD_ADMIN_TOKEN=${BYTE_DASHBOARD_ADMIN_TOKEN_SECRET_NAME}:latest")
fi

if [[ "${TWITCH_CHAT_MODE}" == "eventsub" ]]; then
  require_env TWITCH_CLIENT_ID
  require_env TWITCH_BOT_ID
  require_env TWITCH_CHANNEL_ID
  ENV_VARS+=(
    "TWITCH_CLIENT_ID=${TWITCH_CLIENT_ID}"
    "TWITCH_BOT_ID=${TWITCH_BOT_ID}"
    "TWITCH_CHANNEL_ID=${TWITCH_CHANNEL_ID}"
  )
elif [[ "${TWITCH_CHAT_MODE}" == "irc" ]]; then
  require_env TWITCH_BOT_LOGIN
  require_env TWITCH_CHANNEL_LOGIN
  require_env TWITCH_USER_TOKEN
  ENV_VARS+=(
    "TWITCH_BOT_LOGIN=${TWITCH_BOT_LOGIN}"
    "TWITCH_CHANNEL_LOGIN=${TWITCH_CHANNEL_LOGIN}"
    "TWITCH_USER_TOKEN=${TWITCH_USER_TOKEN}"
    "TWITCH_IRC_HOST=${TWITCH_IRC_HOST:-irc.chat.twitch.tv}"
    "TWITCH_IRC_PORT=${TWITCH_IRC_PORT:-6697}"
    "TWITCH_IRC_TLS=${TWITCH_IRC_TLS:-true}"
  )

  if [[ -n "${TWITCH_REFRESH_TOKEN:-}" ]]; then
    require_env TWITCH_CLIENT_ID
    ENV_VARS+=(
      "TWITCH_REFRESH_TOKEN=${TWITCH_REFRESH_TOKEN}"
      "TWITCH_CLIENT_ID=${TWITCH_CLIENT_ID}"
    )
    if [[ -n "${TWITCH_CLIENT_SECRET:-}" ]]; then
      ENV_VARS+=("TWITCH_CLIENT_SECRET=${TWITCH_CLIENT_SECRET}")
    fi
    if [[ -n "${TWITCH_CLIENT_SECRET_SECRET_NAME:-}" ]]; then
      ENV_VARS+=("TWITCH_CLIENT_SECRET_SECRET_NAME=${TWITCH_CLIENT_SECRET_SECRET_NAME}")
    fi
    if [[ -n "${TWITCH_TOKEN_REFRESH_MARGIN_SECONDS:-}" ]]; then
      ENV_VARS+=("TWITCH_TOKEN_REFRESH_MARGIN_SECONDS=${TWITCH_TOKEN_REFRESH_MARGIN_SECONDS}")
    fi
  fi
else
  echo "Erro: TWITCH_CHAT_MODE invalido: ${TWITCH_CHAT_MODE}. Use eventsub ou irc." >&2
  exit 1
fi

ENV_VARS_CSV="$(IFS=,; echo "${ENV_VARS[*]}")"
SECRET_VARS_CSV=""
if [[ "${#SECRET_VARS[@]}" -gt 0 ]]; then
  SECRET_VARS_CSV="$(IFS=,; echo "${SECRET_VARS[*]}")"
fi

echo "Iniciando deploy em ${PROJECT_ID} (${REGION})"

echo "Habilitando APIs necessarias..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com

echo "Build da imagem..."
if [[ ! -f "Dockerfile" ]]; then
  if [[ -f "bot/Dockerfile" ]]; then
    cp bot/Dockerfile Dockerfile
    TEMP_DOCKERFILE_CREATED=1
  else
    echo "Erro: Dockerfile nao encontrado na raiz nem em bot/Dockerfile." >&2
    exit 1
  fi
fi
gcloud builds submit --tag "${IMAGE_NAME}" .

echo "Deploy no Cloud Run..."
DEPLOY_ARGS=(
  --image "${IMAGE_NAME}"
  --region "${REGION}"
  --service-account "${SERVICE_ACCOUNT}"
  --port 8080
  --min-instances 1
  --max-instances 1
  --cpu 1
  --memory 512Mi
  --timeout "${TIMEOUT_SECONDS}"
  --concurrency 200
  --no-cpu-throttling
  --set-env-vars "${ENV_VARS_CSV}"
  --no-allow-unauthenticated
)

if [[ -n "${SECRET_VARS_CSV}" ]]; then
  DEPLOY_ARGS+=(--set-secrets "${SECRET_VARS_CSV}")
fi

gcloud run deploy "${SERVICE_NAME}" \
  "${DEPLOY_ARGS[@]}"

echo "Deploy concluido."
if [[ "${TWITCH_CHAT_MODE}" == "eventsub" ]]; then
  echo "Confirme se o segredo twitch-client-secret existe e se a SA tem role secretAccessor."
else
  if [[ -n "${TWITCH_REFRESH_TOKEN:-}" ]]; then
    echo "Modo IRC ativo com refresh automatico: confira TWITCH_CLIENT_ID e segredo do client secret."
  else
    echo "Modo IRC ativo: confirme que TWITCH_USER_TOKEN esta valido."
  fi
fi
