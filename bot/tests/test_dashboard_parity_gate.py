from pathlib import Path

from bot.dashboard_parity_gate import (
    ParityContractEntry,
    collect_backend_operational_routes,
    collect_dashboard_api_routes,
    validate_parity_contract,
)


def test_collect_backend_operational_routes_contains_dispatch_and_dynamic_routes():
    routes = set(collect_backend_operational_routes())
    assert ("GET", "/api/observability") in routes
    assert ("PUT", "/api/control-plane") in routes
    assert ("POST", "/api/action-queue/{action_id}/decision") in routes


def test_collect_dashboard_api_routes_contains_core_routes():
    routes = set(collect_dashboard_api_routes())
    expected = {
        "/api/observability",
        "/api/control-plane",
        "/api/channel-control",
        "/api/action-queue",
        "/api/autonomy/tick",
    }
    assert expected.issubset(routes)


def test_validate_parity_contract_current_contract_is_clean():
    issues = validate_parity_contract(
        backend_routes=collect_backend_operational_routes(),
        dashboard_routes=collect_dashboard_api_routes(),
    )
    assert issues == ()


def test_validate_parity_contract_reports_missing_backend_contract_entry():
    issues = validate_parity_contract(
        contract=(),
        backend_routes=(("GET", "/api/observability"),),
        dashboard_routes=(),
    )
    assert "missing_contract_entry_for_backend_route: GET /api/observability" in issues


def test_validate_parity_contract_reports_missing_dashboard_mapping_for_integrated_route(
    tmp_path: Path,
):
    backend_test = tmp_path / "bot/tests/test_backend_route.py"
    backend_test.parent.mkdir(parents=True, exist_ok=True)
    backend_test.write_text('handler.path = "/api/observability"\n', encoding="utf-8")

    dashboard_test = tmp_path / "dashboard/tests/test_dashboard_route.js"
    dashboard_test.parent.mkdir(parents=True, exist_ok=True)
    dashboard_test.write_text('url.includes("/api/observability")\n', encoding="utf-8")

    contract = (
        ParityContractEntry(
            method="GET",
            backend_route="/api/observability",
            domain="observability",
            dashboard_surface="metrics",
            status="integrated",
            dashboard_route_prefix="/api/does-not-exist",
            backend_test_files=("bot/tests/test_backend_route.py",),
            dashboard_test_files=("dashboard/tests/test_dashboard_route.js",),
            route_snippet="/api/observability",
        ),
    )
    issues = validate_parity_contract(
        contract=contract,
        backend_routes=(("GET", "/api/observability"),),
        dashboard_routes=("/api/observability",),
        project_root=tmp_path,
    )

    assert "dashboard_mapping_not_found: GET /api/observability -> /api/does-not-exist" in issues
