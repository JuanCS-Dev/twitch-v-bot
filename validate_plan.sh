#!/bin/bash
echo "Iniciando auditoria completa do plano contra o código..."
errors=0

check_file() {
    if [ -f "$1" ]; then
        echo "[OK] Arquivo $1 existe."
    else
        echo "[ERRO] Arquivo $1 NÃO encontrado."
        errors=$((errors + 1))
    fi
}

check_grep() {
    if grep -q "$1" "$2"; then
        echo "[OK] String '$1' encontrada em $2."
    else
        echo "[ERRO] String '$1' NÃO encontrada em $2."
        errors=$((errors + 1))
    fi
}

echo "=== Fases 1-3: Persistência base ==="
check_file "bot/persistence_layer.py"
check_file "bot/logic_context.py"
check_grep "def load_channel_config_sync" "bot/persistence_layer.py"
check_grep "def _trigger_lazy_load" "bot/logic_context.py"

echo "=== Fase 4: Canais dinâmicos ==="
check_file "bot/bootstrap_runtime.py"
check_grep "def resolve_irc_channel_logins" "bot/bootstrap_runtime.py"

echo "=== Fase 5: Observabilidade stateful ==="
check_file "bot/observability_state.py"
check_file "bot/observability_snapshot.py"
check_grep "observability_rollups" "bot/persistence_layer.py"

echo "=== Fase 6: Dashboard multi-canal ==="
check_grep "/api/channel-context" "bot/dashboard_server_routes.py"
check_grep "/api/observability/history" "bot/dashboard_server_routes.py"

echo "=== Fase 7: Soberania ==="
check_grep "/api/autonomy/tick" "bot/dashboard_server_routes_post.py"
check_grep "/api/agent/suspend" "bot/dashboard_server_routes_post.py"
check_grep "/api/agent/resume" "bot/dashboard_server_routes_post.py"
check_grep "def save_agent_notes" "bot/persistence_layer.py"

echo "=== Fase 8: Memória semântica ==="
check_file "bot/semantic_memory.py"
check_file "bot/persistence_semantic_memory_repository.py"
check_grep "/api/semantic-memory" "bot/dashboard_server_routes.py"

echo "=== Fase 9: Paridade formal ==="
check_file "bot/dashboard_parity_gate.py"
check_file "dashboard/tests/api_contract_parity.test.js"
check_file ".github/workflows/ci.yml"

echo "=== Fase 10: Saneamento estrutural ==="
check_file "bot/dashboard_http_helpers.py"
check_file "bot/structural_health_gate.py"

echo "=== Fase 11: Stream Health Score ==="
check_file "bot/stream_health_score.py"
check_grep "/api/sentiment/scores" "bot/dashboard_server_routes.py"

echo "=== Fase 12: Post-Stream Report ==="
check_file "bot/post_stream_report.py"
check_file "bot/persistence_post_stream_report_repository.py"
check_grep "/api/observability/post-stream-report" "bot/dashboard_server_routes.py"

echo "=== Fase 13: Goal-Driven Autonomy ==="
check_file "bot/control_plane_constants.py"
check_file "bot/control_plane_config.py"
check_file "bot/autonomy_runtime.py"

echo "=== Fase 14: Ops Playbooks ==="
check_file "bot/ops_playbooks.py"
check_grep "/api/ops-playbooks" "bot/dashboard_server_routes.py"
check_grep "/api/ops-playbooks/trigger" "bot/dashboard_server_routes_post.py"

echo "=== Fase 15: Per-Channel Identity ==="
check_file "bot/persistence_channel_identity_repository.py"
check_grep "/api/channel-config" "bot/dashboard_server_routes.py"

echo "=== Fase 16: Coaching ==="
check_file "bot/coaching_churn_risk.py"
check_file "bot/coaching_runtime.py"

echo "=== Fase 17: Revenue Attribution ==="
check_file "bot/revenue_attribution_engine.py"
check_file "bot/persistence_revenue_attribution_repository.py"
check_grep "/api/observability/conversions" "bot/dashboard_server_routes.py"
check_grep "/api/observability/conversion" "bot/dashboard_server_routes_post.py"

echo "=== Testes e UI ==="
check_file "dashboard/partials/intelligence_panel.html"
check_file "dashboard/partials/control_plane.html"
check_file "dashboard/partials/risk_queue.html"
check_file "bot/tests/test_coaching_churn_risk.py"
check_file "dashboard/tests/multi_channel_focus.test.js"

if [ "$errors" -gt 0 ]; then
    echo "Auditoria concluída com $errors erro(s)."
    exit 1
fi

echo "Auditoria concluída sem inconsistências."
