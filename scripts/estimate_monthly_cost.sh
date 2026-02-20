#!/usr/bin/env bash
set -euo pipefail

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Erro: comando obrigatorio ausente: $cmd" >&2
    exit 1
  fi
}

calc_sum() {
  awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { printf "%.12f", a + b }'
}

calc_mul() {
  awk -v a="${1:-0}" -v b="${2:-0}" 'BEGIN { printf "%.12f", a * b }'
}

fmt_int() {
  awk -v a="${1:-0}" 'BEGIN { printf "%.0f", a }'
}

fmt_float() {
  awk -v a="${1:-0}" 'BEGIN { printf "%.6f", a }'
}

fmt_money() {
  awk -v a="${1:-0}" 'BEGIN { printf "%.4f", a }'
}

tiered_cost() {
  local usage="$1"
  local price_json="$2"
  local compact_price
  compact_price="$(printf '%s' "$price_json" | jq -c '.')"

  jq -nr \
    --argjson usage "$usage" \
    --argjson price "$compact_price" '
      def money_to_number($m):
        (($m.units // "0") | tonumber) + (($m.nanos // 0) / 1000000000);
      ($price.rate.tiers // []) as $tiers |
      ($price.rate.unitInfo.unitQuantity.value // "1" | tonumber) as $unit_quantity |
      if ($tiers | length) == 0 then
        0
      else
        reduce range(0; $tiers | length) as $i (
          0;
          ($tiers[$i].startAmount.value // "0" | tonumber) as $start |
          (if ($i + 1) < ($tiers | length)
            then ($tiers[$i + 1].startAmount.value | tonumber)
            else $usage
          end) as $next_start |
          if $usage > $start then
            ((if $usage < $next_start then $usage else $next_start end) - $start) as $quantity |
            if $quantity > 0 then
              . + ($quantity / $unit_quantity * money_to_number($tiers[$i].contractPrice // $tiers[$i].listPrice))
            else
              .
            end
          else
            .
          end
        )
      end
    '
}

monitoring_sum() {
  local access_token="$1"
  local project_id="$2"
  local start_time="$3"
  local end_time="$4"
  local alignment_period="$5"
  local filter="$6"
  local response

  response="$(curl -sS -f --get "https://monitoring.googleapis.com/v3/projects/${project_id}/timeSeries" \
    -H "Authorization: Bearer ${access_token}" \
    --data-urlencode "filter=${filter}" \
    --data-urlencode "interval.startTime=${start_time}" \
    --data-urlencode "interval.endTime=${end_time}" \
    --data-urlencode "aggregation.alignmentPeriod=${alignment_period}" \
    --data-urlencode "aggregation.perSeriesAligner=ALIGN_SUM" \
    --data-urlencode "aggregation.crossSeriesReducer=REDUCE_SUM" \
    --data-urlencode "view=FULL")"

  printf '%s' "$response" | jq -r '
    [
      .timeSeries[]?.points[]? |
      (.value.doubleValue // .value.int64Value // .value.distributionValue.count // 0 | tonumber)
    ] | add // 0
  '
}

billing_price_json() {
  local access_token="$1"
  local billing_account_id="$2"
  local sku_id="$3"

  curl -sS -f -H "Authorization: Bearer ${access_token}" \
    "https://cloudbilling.googleapis.com/v1beta/billingAccounts/${billing_account_id}/skus/${sku_id}/price"
}

require_cmd gcloud
require_cmd jq
require_cmd curl
require_cmd awk
require_cmd date

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "Erro: defina PROJECT_ID ou configure gcloud default project." >&2
  exit 1
fi

REGION="${REGION:-us-central1}"
CLOUD_RUN_SERVICE="${CLOUD_RUN_SERVICE:-}"
GEMINI_MODEL_FILTER="${GEMINI_MODEL_FILTER:-gemini-3-flash-preview}"
ALIGNMENT_PERIOD="${ALIGNMENT_PERIOD:-3600s}"
START_TIME="${START_TIME:-$(date -u +%Y-%m-%dT00:00:00Z)}"
END_TIME="${END_TIME:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"

BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:-}"
if [[ -z "${BILLING_ACCOUNT_ID}" ]]; then
  BILLING_ACCOUNT_ID="$(gcloud billing projects describe "${PROJECT_ID}" --format='value(billingAccountName)')"
  BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID##*/}"
fi
if [[ -z "${BILLING_ACCOUNT_ID}" ]]; then
  echo "Erro: nao foi possivel descobrir BILLING_ACCOUNT_ID para ${PROJECT_ID}." >&2
  exit 1
fi

# SKUs default (2026): sobrescreva via env se necessario.
CLOUD_RUN_CPU_SKU="${CLOUD_RUN_CPU_SKU:-011E-3072-CBDB}"
CLOUD_RUN_MEM_SKU="${CLOUD_RUN_MEM_SKU:-F6D2-B591-E54F}"
CLOUD_RUN_REQUEST_SKU="${CLOUD_RUN_REQUEST_SKU:-2DA5-55D3-E679}"
GEMINI_INPUT_SKU="${GEMINI_INPUT_SKU:-7EBE-3B46-F75C}"
GEMINI_OUTPUT_SKU="${GEMINI_OUTPUT_SKU:-0127-F0B7-365E}"

ACCESS_TOKEN="$(gcloud auth print-access-token)"

RUN_SCOPE='resource.type="cloud_run_revision"'
if [[ -n "${CLOUD_RUN_SERVICE}" ]]; then
  RUN_SCOPE="${RUN_SCOPE} AND resource.labels.service_name=\"${CLOUD_RUN_SERVICE}\""
fi
if [[ -n "${REGION}" ]]; then
  RUN_SCOPE="${RUN_SCOPE} AND resource.labels.location=\"${REGION}\""
fi

TOKEN_SCOPE='metric.labels.request_type="shared"'
if [[ -n "${GEMINI_MODEL_FILTER}" ]]; then
  TOKEN_SCOPE="${TOKEN_SCOPE} AND resource.labels.model_user_id=\"${GEMINI_MODEL_FILTER}\""
fi

CPU_SECONDS="$(monitoring_sum "$ACCESS_TOKEN" "$PROJECT_ID" "$START_TIME" "$END_TIME" "$ALIGNMENT_PERIOD" \
  "metric.type=\"run.googleapis.com/container/cpu/allocation_time\" AND ${RUN_SCOPE}")"

MEMORY_GIB_SECONDS="$(monitoring_sum "$ACCESS_TOKEN" "$PROJECT_ID" "$START_TIME" "$END_TIME" "$ALIGNMENT_PERIOD" \
  "metric.type=\"run.googleapis.com/container/memory/allocation_time\" AND ${RUN_SCOPE}")"

REQUEST_COUNT="$(monitoring_sum "$ACCESS_TOKEN" "$PROJECT_ID" "$START_TIME" "$END_TIME" "$ALIGNMENT_PERIOD" \
  "metric.type=\"run.googleapis.com/request_count\" AND ${RUN_SCOPE}")"

INPUT_TOKENS="$(monitoring_sum "$ACCESS_TOKEN" "$PROJECT_ID" "$START_TIME" "$END_TIME" "$ALIGNMENT_PERIOD" \
  "metric.type=\"aiplatform.googleapis.com/publisher/online_serving/token_count\" AND metric.labels.type=\"input\" AND ${TOKEN_SCOPE}")"

OUTPUT_TOKENS="$(monitoring_sum "$ACCESS_TOKEN" "$PROJECT_ID" "$START_TIME" "$END_TIME" "$ALIGNMENT_PERIOD" \
  "metric.type=\"aiplatform.googleapis.com/publisher/online_serving/token_count\" AND metric.labels.type=\"output\" AND ${TOKEN_SCOPE}")"

CPU_PRICE_JSON="$(billing_price_json "$ACCESS_TOKEN" "$BILLING_ACCOUNT_ID" "$CLOUD_RUN_CPU_SKU")"
MEM_PRICE_JSON="$(billing_price_json "$ACCESS_TOKEN" "$BILLING_ACCOUNT_ID" "$CLOUD_RUN_MEM_SKU")"
REQ_PRICE_JSON="$(billing_price_json "$ACCESS_TOKEN" "$BILLING_ACCOUNT_ID" "$CLOUD_RUN_REQUEST_SKU")"
IN_PRICE_JSON="$(billing_price_json "$ACCESS_TOKEN" "$BILLING_ACCOUNT_ID" "$GEMINI_INPUT_SKU")"
OUT_PRICE_JSON="$(billing_price_json "$ACCESS_TOKEN" "$BILLING_ACCOUNT_ID" "$GEMINI_OUTPUT_SKU")"

CURRENCY_CODE="$(printf '%s' "$CPU_PRICE_JSON" | jq -r '.currencyCode // "USD"')"

CPU_COST_NOW="$(tiered_cost "$CPU_SECONDS" "$CPU_PRICE_JSON")"
MEM_COST_NOW="$(tiered_cost "$MEMORY_GIB_SECONDS" "$MEM_PRICE_JSON")"
REQ_COST_NOW="$(tiered_cost "$REQUEST_COUNT" "$REQ_PRICE_JSON")"
IN_COST_NOW="$(tiered_cost "$INPUT_TOKENS" "$IN_PRICE_JSON")"
OUT_COST_NOW="$(tiered_cost "$OUTPUT_TOKENS" "$OUT_PRICE_JSON")"

TOTAL_COST_NOW="$(calc_sum "$CPU_COST_NOW" "$MEM_COST_NOW")"
TOTAL_COST_NOW="$(calc_sum "$TOTAL_COST_NOW" "$REQ_COST_NOW")"
TOTAL_COST_NOW="$(calc_sum "$TOTAL_COST_NOW" "$IN_COST_NOW")"
TOTAL_COST_NOW="$(calc_sum "$TOTAL_COST_NOW" "$OUT_COST_NOW")"

START_EPOCH="$(date -u -d "$START_TIME" +%s)"
END_EPOCH="$(date -u -d "$END_TIME" +%s)"
if (( END_EPOCH <= START_EPOCH )); then
  echo "Erro: END_TIME precisa ser maior que START_TIME." >&2
  exit 1
fi
ELAPSED_SECONDS="$((END_EPOCH - START_EPOCH))"

MONTH_START_EPOCH="$(date -u -d "$(date -u -d "$END_TIME" +%Y-%m-01) 00:00:00" +%s)"
NEXT_MONTH_START_EPOCH="$(date -u -d "$(date -u -d "$END_TIME" +%Y-%m-01) +1 month" +%s)"
MONTH_SECONDS="$((NEXT_MONTH_START_EPOCH - MONTH_START_EPOCH))"
SCALE_FACTOR="$(awk -v month_s="$MONTH_SECONDS" -v elapsed_s="$ELAPSED_SECONDS" 'BEGIN { printf "%.12f", month_s / elapsed_s }')"

CPU_SECONDS_MONTH="$(calc_mul "$CPU_SECONDS" "$SCALE_FACTOR")"
MEMORY_GIB_SECONDS_MONTH="$(calc_mul "$MEMORY_GIB_SECONDS" "$SCALE_FACTOR")"
REQUEST_COUNT_MONTH="$(calc_mul "$REQUEST_COUNT" "$SCALE_FACTOR")"
INPUT_TOKENS_MONTH="$(calc_mul "$INPUT_TOKENS" "$SCALE_FACTOR")"
OUTPUT_TOKENS_MONTH="$(calc_mul "$OUTPUT_TOKENS" "$SCALE_FACTOR")"

CPU_COST_MONTH="$(tiered_cost "$CPU_SECONDS_MONTH" "$CPU_PRICE_JSON")"
MEM_COST_MONTH="$(tiered_cost "$MEMORY_GIB_SECONDS_MONTH" "$MEM_PRICE_JSON")"
REQ_COST_MONTH="$(tiered_cost "$REQUEST_COUNT_MONTH" "$REQ_PRICE_JSON")"
IN_COST_MONTH="$(tiered_cost "$INPUT_TOKENS_MONTH" "$IN_PRICE_JSON")"
OUT_COST_MONTH="$(tiered_cost "$OUTPUT_TOKENS_MONTH" "$OUT_PRICE_JSON")"

TOTAL_COST_MONTH="$(calc_sum "$CPU_COST_MONTH" "$MEM_COST_MONTH")"
TOTAL_COST_MONTH="$(calc_sum "$TOTAL_COST_MONTH" "$REQ_COST_MONTH")"
TOTAL_COST_MONTH="$(calc_sum "$TOTAL_COST_MONTH" "$IN_COST_MONTH")"
TOTAL_COST_MONTH="$(calc_sum "$TOTAL_COST_MONTH" "$OUT_COST_MONTH")"

echo "Byte Cost Snapshot"
echo "Project: ${PROJECT_ID}"
echo "Billing Account: ${BILLING_ACCOUNT_ID}"
echo "Interval (UTC): ${START_TIME} -> ${END_TIME}"
echo "Cloud Run scope: ${CLOUD_RUN_SERVICE:-all-services} @ ${REGION}"
echo "Gemini model scope: ${GEMINI_MODEL_FILTER:-all-models}"
echo "Projection scale: x$(fmt_float "$SCALE_FACTOR") (run-rate para o mes atual)"
echo
echo "Uso no intervalo"
echo "- Cloud Run requests: $(fmt_int "$REQUEST_COUNT")"
echo "- Cloud Run CPU seconds: $(fmt_float "$CPU_SECONDS")"
echo "- Cloud Run memory GiB-seconds: $(fmt_float "$MEMORY_GIB_SECONDS")"
echo "- Gemini input tokens: $(fmt_int "$INPUT_TOKENS")"
echo "- Gemini output tokens: $(fmt_int "$OUTPUT_TOKENS")"
echo
echo "Custo no intervalo (${CURRENCY_CODE})"
echo "- Cloud Run CPU: $(fmt_money "$CPU_COST_NOW")"
echo "- Cloud Run Memory: $(fmt_money "$MEM_COST_NOW")"
echo "- Cloud Run Requests: $(fmt_money "$REQ_COST_NOW")"
echo "- Gemini Input Tokens: $(fmt_money "$IN_COST_NOW")"
echo "- Gemini Output Tokens: $(fmt_money "$OUT_COST_NOW")"
echo "- TOTAL intervalo: $(fmt_money "$TOTAL_COST_NOW")"
echo
echo "Estimativa mensal (${CURRENCY_CODE})"
echo "- Cloud Run CPU: $(fmt_money "$CPU_COST_MONTH")"
echo "- Cloud Run Memory: $(fmt_money "$MEM_COST_MONTH")"
echo "- Cloud Run Requests: $(fmt_money "$REQ_COST_MONTH")"
echo "- Gemini Input Tokens: $(fmt_money "$IN_COST_MONTH")"
echo "- Gemini Output Tokens: $(fmt_money "$OUT_COST_MONTH")"
echo "- TOTAL mensal estimado: $(fmt_money "$TOTAL_COST_MONTH")"
