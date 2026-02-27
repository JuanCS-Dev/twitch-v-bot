from __future__ import annotations

import ast
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ROUTE_TABLE_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("GET", "bot/dashboard_server_routes.py", "_GET_ROUTE_HANDLERS"),
    ("PUT", "bot/dashboard_server_routes.py", "_PUT_ROUTE_HANDLERS"),
    ("POST", "bot/dashboard_server_routes_post.py", "_POST_ROUTE_HANDLERS"),
)

DYNAMIC_ROUTE_SOURCES: tuple[tuple[str, str], ...] = (
    ("POST", "/api/action-queue/{action_id}/decision"),
)

API_ROUTE_LITERAL_RE = re.compile(r"\./api/[a-z0-9/_-]+")

ParityStatus = Literal["integrated", "headless_approved"]


@dataclass(frozen=True)
class ParityContractEntry:
    method: str
    backend_route: str
    domain: str
    dashboard_surface: str
    status: ParityStatus
    dashboard_route_prefix: str | None = None
    backend_test_files: tuple[str, ...] = ()
    dashboard_test_files: tuple[str, ...] = ()
    route_snippet: str = ""
    headless_reason: str = ""
    planned_phase: str = ""


PARITY_CONTRACT: tuple[ParityContractEntry, ...] = (
    ParityContractEntry(
        method="GET",
        backend_route="/api/observability",
        domain="observability",
        dashboard_surface="metrics_health + intelligence_panel",
        status="integrated",
        dashboard_route_prefix="/api/observability",
        backend_test_files=(
            "bot/tests/test_dashboard_routes.py",
            "bot/tests/test_dashboard_routes_v3.py",
            "bot/tests/test_observability.py",
        ),
        dashboard_test_files=(
            "dashboard/tests/multi_channel_focus.test.js",
            "dashboard/tests/api_contract_parity.test.js",
        ),
        route_snippet="/api/observability",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/channel-context",
        domain="channel_governance",
        dashboard_surface="agent_context_internals",
        status="integrated",
        dashboard_route_prefix="/api/channel-context",
        backend_test_files=("bot/tests/test_dashboard_routes.py",),
        dashboard_test_files=("dashboard/tests/multi_channel_focus.test.js",),
        route_snippet="/api/channel-context",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/observability/history",
        domain="observability",
        dashboard_surface="agent_context_internals_timeline_comparison",
        status="integrated",
        dashboard_route_prefix="/api/observability/history",
        backend_test_files=(
            "bot/tests/test_dashboard_routes.py",
            "bot/tests/test_dashboard_routes_v3.py",
        ),
        dashboard_test_files=("dashboard/tests/multi_channel_focus.test.js",),
        route_snippet="/api/observability/history",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/control-plane",
        domain="control_plane",
        dashboard_surface="control_plane_panel",
        status="integrated",
        dashboard_route_prefix="/api/control-plane",
        backend_test_files=(
            "bot/tests/test_dashboard_routes.py",
            "bot/tests/test_dashboard_routes_v3.py",
        ),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/control-plane",
    ),
    ParityContractEntry(
        method="PUT",
        backend_route="/api/control-plane",
        domain="control_plane",
        dashboard_surface="control_plane_panel",
        status="integrated",
        dashboard_route_prefix="/api/control-plane",
        backend_test_files=("bot/tests/test_dashboard_routes.py",),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/control-plane",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/channel-config",
        domain="channel_governance",
        dashboard_surface="channel_tuning_card",
        status="integrated",
        dashboard_route_prefix="/api/channel-config",
        backend_test_files=("bot/tests/test_dashboard_routes.py",),
        dashboard_test_files=(
            "dashboard/tests/multi_channel_focus.test.js",
            "dashboard/tests/api_contract_parity.test.js",
        ),
        route_snippet="/api/channel-config",
    ),
    ParityContractEntry(
        method="PUT",
        backend_route="/api/channel-config",
        domain="channel_governance",
        dashboard_surface="channel_tuning_card",
        status="integrated",
        dashboard_route_prefix="/api/channel-config",
        backend_test_files=("bot/tests/test_dashboard_routes.py",),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/channel-config",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/agent-notes",
        domain="prompt_runtime",
        dashboard_surface="channel_directives_card",
        status="integrated",
        dashboard_route_prefix="/api/agent-notes",
        backend_test_files=("bot/tests/test_dashboard_routes.py",),
        dashboard_test_files=(
            "dashboard/tests/multi_channel_focus.test.js",
            "dashboard/tests/api_contract_parity.test.js",
        ),
        route_snippet="/api/agent-notes",
    ),
    ParityContractEntry(
        method="PUT",
        backend_route="/api/agent-notes",
        domain="prompt_runtime",
        dashboard_surface="channel_directives_card",
        status="integrated",
        dashboard_route_prefix="/api/agent-notes",
        backend_test_files=("bot/tests/test_dashboard_routes.py",),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/agent-notes",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/action-queue",
        domain="control_plane",
        dashboard_surface="risk_queue_panel",
        status="integrated",
        dashboard_route_prefix="/api/action-queue",
        backend_test_files=(
            "bot/tests/test_dashboard_routes.py",
            "bot/tests/test_dashboard_routes_v3.py",
        ),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/action-queue",
    ),
    ParityContractEntry(
        method="POST",
        backend_route="/api/action-queue/{action_id}/decision",
        domain="control_plane",
        dashboard_surface="risk_queue_panel",
        status="integrated",
        dashboard_route_prefix="/api/action-queue",
        backend_test_files=(
            "bot/tests/test_dashboard_routes_post.py",
            "bot/tests/test_dashboard_routes_v3.py",
        ),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/action-queue/",
    ),
    ParityContractEntry(
        method="POST",
        backend_route="/api/channel-control",
        domain="channel_governance",
        dashboard_surface="channel_manager_panel",
        status="integrated",
        dashboard_route_prefix="/api/channel-control",
        backend_test_files=(
            "bot/tests/test_dashboard_routes_post.py",
            "bot/tests/test_dashboard_routes_v2.py",
        ),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/channel-control",
    ),
    ParityContractEntry(
        method="POST",
        backend_route="/api/autonomy/tick",
        domain="control_plane",
        dashboard_surface="control_plane_panel",
        status="integrated",
        dashboard_route_prefix="/api/autonomy/tick",
        backend_test_files=(
            "bot/tests/test_dashboard_routes_post.py",
            "bot/tests/test_dashboard_routes_v2.py",
        ),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/autonomy/tick",
    ),
    ParityContractEntry(
        method="POST",
        backend_route="/api/agent/suspend",
        domain="control_plane",
        dashboard_surface="control_plane_panel",
        status="integrated",
        dashboard_route_prefix="/api/agent/suspend",
        backend_test_files=("bot/tests/test_dashboard_routes_post.py",),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/agent/suspend",
    ),
    ParityContractEntry(
        method="POST",
        backend_route="/api/agent/resume",
        domain="control_plane",
        dashboard_surface="control_plane_panel",
        status="integrated",
        dashboard_route_prefix="/api/agent/resume",
        backend_test_files=("bot/tests/test_dashboard_routes_post.py",),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/agent/resume",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/clip-jobs",
        domain="clips",
        dashboard_surface="clips_section_panel",
        status="integrated",
        dashboard_route_prefix="/api/clip-jobs",
        backend_test_files=(
            "bot/tests/test_dashboard_routes.py",
            "bot/tests/test_dashboard_routes_v3.py",
        ),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/clip-jobs",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/hud/messages",
        domain="observability",
        dashboard_surface="hud_overlay_panel",
        status="integrated",
        dashboard_route_prefix="/api/hud/messages",
        backend_test_files=(
            "bot/tests/test_dashboard_routes_v2.py",
            "bot/tests/test_dashboard_routes_v3.py",
        ),
        dashboard_test_files=("dashboard/tests/api_contract_parity.test.js",),
        route_snippet="/api/hud/messages",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/sentiment/scores",
        domain="observability",
        dashboard_surface="planned_stream_health_widget",
        status="headless_approved",
        backend_test_files=("bot/tests/test_dashboard_routes_v3.py",),
        route_snippet="/api/sentiment/scores",
        headless_reason="Endpoint pronto para score consolidado da Fase 11.",
        planned_phase="Fase 11",
    ),
    ParityContractEntry(
        method="GET",
        backend_route="/api/vision/status",
        domain="clips",
        dashboard_surface="planned_visual_clip_widget",
        status="headless_approved",
        backend_test_files=("bot/tests/test_dashboard_routes_v3.py",),
        route_snippet="/api/vision/status",
        headless_reason="Status de vision runtime sera exposto na trilha de clips da Fase 19.",
        planned_phase="Fase 19",
    ),
    ParityContractEntry(
        method="POST",
        backend_route="/api/vision/ingest",
        domain="clips",
        dashboard_surface="planned_visual_clip_widget",
        status="headless_approved",
        backend_test_files=(
            "bot/tests/test_dashboard_routes_post.py",
            "bot/tests/test_dashboard_routes_v2.py",
        ),
        route_snippet="/api/vision/ingest",
        headless_reason="Ingest visual segue interno ate finalizar UX de operacao ao vivo na Fase 19.",
        planned_phase="Fase 19",
    ),
)


def _extract_route_keys(source_path: Path, variable_name: str) -> tuple[str, ...]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            has_target = any(
                isinstance(target, ast.Name) and target.id == variable_name
                for target in node.targets
            )
            if has_target:
                value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == variable_name:
                value = node.value
        if value is None:
            continue
        if not isinstance(value, ast.Dict):
            raise ValueError(f"{variable_name} em {source_path} nao e dict literal.")
        keys = []
        for key in value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.append(key.value)
        return tuple(keys)
    raise ValueError(f"{variable_name} nao encontrado em {source_path}.")


def collect_backend_operational_routes(
    project_root: Path = PROJECT_ROOT,
) -> tuple[tuple[str, str], ...]:
    routes: set[tuple[str, str]] = set()
    for method, relative_path, table_name in ROUTE_TABLE_SOURCES:
        source_path = project_root / relative_path
        for route in _extract_route_keys(source_path, table_name):
            if route.startswith("/api/"):
                routes.add((method, route))
    routes.update(DYNAMIC_ROUTE_SOURCES)
    return tuple(sorted(routes))


def _normalize_dashboard_route(route_literal: str) -> str:
    route = route_literal.strip()
    if route.startswith("./"):
        route = route[1:]
    if not route.startswith("/"):
        route = f"/{route}"
    return route


def collect_dashboard_api_routes(project_root: Path = PROJECT_ROOT) -> tuple[str, ...]:
    routes: set[str] = set()
    for api_file in sorted((project_root / "dashboard/features").glob("*/api.js")):
        content = api_file.read_text(encoding="utf-8")
        matches = API_ROUTE_LITERAL_RE.findall(content)
        routes.update(_normalize_dashboard_route(match) for match in matches)
    return tuple(sorted(routes))


def _build_contract_index(
    contract: Sequence[ParityContractEntry],
) -> tuple[dict[tuple[str, str], ParityContractEntry], list[str]]:
    index: dict[tuple[str, str], ParityContractEntry] = {}
    issues: list[str] = []
    for entry in contract:
        key = (entry.method.upper(), entry.backend_route)
        if key in index:
            issues.append(f"duplicated_contract_entry: {key[0]} {key[1]}")
            continue
        index[key] = entry
    return index, issues


def _route_has_dashboard_mapping(route_prefix: str, dashboard_routes: set[str]) -> bool:
    return any(
        route == route_prefix or route.startswith(f"{route_prefix}/") for route in dashboard_routes
    )


def _read_file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _files_contain_snippet(paths: Sequence[Path], snippet: str) -> bool:
    return any(snippet in _read_file_text(path) for path in paths)


def _validate_entry_files_exist(
    entry: ParityContractEntry,
    project_root: Path,
    *,
    kind: str,
    issues: list[str],
) -> list[Path]:
    existing: list[Path] = []
    for relative_path in (
        entry.backend_test_files if kind == "backend" else entry.dashboard_test_files
    ):
        absolute_path = project_root / relative_path
        if not absolute_path.exists():
            issues.append(
                f"missing_{kind}_test_file: {entry.method} {entry.backend_route} -> {relative_path}"
            )
            continue
        existing.append(absolute_path)
    return existing


def _validate_integrated_entry(
    entry: ParityContractEntry,
    dashboard_routes: set[str],
    issues: list[str],
) -> None:
    if not entry.dashboard_route_prefix:
        issues.append(f"missing_dashboard_route_prefix: {entry.method} {entry.backend_route}")
        return
    if not _route_has_dashboard_mapping(entry.dashboard_route_prefix, dashboard_routes):
        issues.append(
            f"dashboard_mapping_not_found: {entry.method} {entry.backend_route}"
            f" -> {entry.dashboard_route_prefix}"
        )
    if not entry.dashboard_test_files:
        issues.append(f"missing_dashboard_tests: {entry.method} {entry.backend_route}")


def _validate_headless_entry(entry: ParityContractEntry, issues: list[str]) -> None:
    if not entry.headless_reason.strip():
        issues.append(f"missing_headless_reason: {entry.method} {entry.backend_route}")
    if not entry.planned_phase.strip():
        issues.append(f"missing_headless_planned_phase: {entry.method} {entry.backend_route}")


def _validate_test_evidence(
    entry: ParityContractEntry,
    backend_files: Sequence[Path],
    dashboard_files: Sequence[Path],
    issues: list[str],
) -> None:
    snippet = entry.route_snippet.strip() or entry.backend_route
    if not backend_files:
        issues.append(f"missing_backend_tests: {entry.method} {entry.backend_route}")
    elif not _files_contain_snippet(backend_files, snippet):
        issues.append(f"backend_test_missing_route_snippet: {entry.method} {entry.backend_route}")

    if entry.status == "integrated":
        if not dashboard_files:
            issues.append(f"missing_dashboard_tests: {entry.method} {entry.backend_route}")
        elif not _files_contain_snippet(dashboard_files, snippet):
            issues.append(
                f"dashboard_test_missing_route_snippet: {entry.method} {entry.backend_route}"
            )


def validate_parity_contract(
    *,
    contract: Sequence[ParityContractEntry] = PARITY_CONTRACT,
    backend_routes: Sequence[tuple[str, str]],
    dashboard_routes: Sequence[str],
    project_root: Path = PROJECT_ROOT,
) -> tuple[str, ...]:
    backend_route_set = {(method.upper(), route) for method, route in backend_routes}
    dashboard_route_set = set(dashboard_routes)
    contract_index, issues = _build_contract_index(contract)

    for method, route in sorted(backend_route_set):
        if (method, route) not in contract_index:
            issues.append(f"missing_contract_entry_for_backend_route: {method} {route}")

    for method, route in sorted(contract_index):
        if (method, route) not in backend_route_set:
            issues.append(f"stale_contract_entry_without_backend_route: {method} {route}")

    for entry in contract:
        if entry.status == "integrated":
            _validate_integrated_entry(entry, dashboard_route_set, issues)
        else:
            _validate_headless_entry(entry, issues)

        backend_files = _validate_entry_files_exist(
            entry,
            project_root,
            kind="backend",
            issues=issues,
        )
        dashboard_files = _validate_entry_files_exist(
            entry,
            project_root,
            kind="dashboard",
            issues=issues,
        )
        _validate_test_evidence(entry, backend_files, dashboard_files, issues)

    return tuple(issues)


def run_parity_gate(project_root: Path = PROJECT_ROOT) -> int:
    backend_routes = collect_backend_operational_routes(project_root)
    dashboard_routes = collect_dashboard_api_routes(project_root)
    issues = validate_parity_contract(
        backend_routes=backend_routes,
        dashboard_routes=dashboard_routes,
        project_root=project_root,
    )

    print(f"[parity-gate] backend_routes={len(backend_routes)}")
    print(f"[parity-gate] dashboard_api_routes={len(dashboard_routes)}")
    if issues:
        print(f"[parity-gate] failed ({len(issues)} issue(s))")
        for issue in issues:
            print(f"[parity-gate] - {issue}")
        return 1

    integrated = sum(1 for entry in PARITY_CONTRACT if entry.status == "integrated")
    headless = sum(1 for entry in PARITY_CONTRACT if entry.status == "headless_approved")
    print(f"[parity-gate] ok integrated={integrated} headless_approved={headless}")
    return 0


def main() -> int:
    return run_parity_gate()


if __name__ == "__main__":
    raise SystemExit(main())
