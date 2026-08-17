"""playtest/telemetry.py — rastro estruturado por campanha (Fase 5.3).

Grava, por campanha de playtest, 1 JSONL (uma linha por turno, shape do logger
`rpg.turn` da Fase 10 + campos de playtest e de roteamento) e um `summary.json`
com métricas agregadas. Tudo em `playtest_runs/{run_id}/` (gitignored). Funções
puras sobre `CampaignResult` + `TurnRecord`; zero dependência nova.
"""
from __future__ import annotations

import json
import os
import glob
import socket
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from playtest import pricing
from playtest.runner import CampaignResult, TurnRecord

PLAYTEST_RUNS_DIR = os.getenv("RPG_PLAYTEST_RUNS_DIR", "playtest_runs")
RUN_META_FILENAME = "run.meta.json"


def new_run_id() -> str:
    """Id de run = timestamp que ordena sozinho."""
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def run_dir(run_id: str) -> str:
    return os.path.join(PLAYTEST_RUNS_DIR, run_id)


def report_path(run_id: str) -> str:
    return os.path.join(run_dir(run_id), "report.md")


def _meta_path(run_id: str) -> str:
    return os.path.join(run_dir(run_id), RUN_META_FILENAME)


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)


def _owner() -> dict:
    return {"pid": os.getpid(), "host": socket.gethostname()}


def _pid_is_alive(pid: int) -> bool:
    """Best-effort local e read-only; outro host é tratado via heartbeat."""
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return False
    if value <= 0:
        return False
    if value == os.getpid():
        return True
    if os.name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, value,
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            # Access denied still proves that a process owns this PID.
            return int(ctypes.windll.kernel32.GetLastError()) == 5
        except Exception:
            return False
    try:
        os.kill(value, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def begin_run(
    run_id: str,
    *,
    profiles: List[str],
    turns: int,
    seed: int,
    real: bool,
    class_name: Optional[str] = None,
    invariants_enabled: bool = True,
    scenario: Optional[str] = None,
) -> dict:
    """Cria o manifesto antes da primeira campanha.

    Assim uma interrupção entre perfis deixa evidência explícita do que faltou,
    em vez de um diretório parcial indistinguível de uma run curta válida.
    """
    stale_seconds = int(os.getenv("RPG_PLAYTEST_STALE_SECONDS", "21600") or 21600)
    recover_stale_runs(max_age_seconds=stale_seconds)
    created = datetime.now()
    meta = {
        "schema_version": 3,
        "run_id": run_id,
        "created_at": created.isoformat(timespec="seconds"),
        "heartbeat_at": created.isoformat(timespec="seconds"),
        "owner": _owner(),
        "status": "running",
        "complete": False,
        "expected": {
            "profiles": list(profiles),
            "turns_per_campaign": int(turns),
            "seed": int(seed),
            "real": bool(real),
            "class_name": class_name,
            "invariants_enabled": bool(invariants_enabled),
            "scenario": scenario,
        },
        "campaigns": {},
    }
    _write_json(_meta_path(run_id), meta)
    return meta


def recover_stale_runs(*, max_age_seconds: int = 21600,
                       now: Optional[datetime] = None) -> List[str]:
    """Fecha manifestos ``running`` antigos deixados por processo interrompido.

    Runs recentes são preservadas para não interferir em outro playtest ativo.
    """
    current = now or datetime.now()
    recovered: List[str] = []
    pattern = os.path.join(PLAYTEST_RUNS_DIR, "*", RUN_META_FILENAME)
    for path in sorted(glob.glob(pattern)):
        meta = _read_json(path)
        if not meta or str(meta.get("status")) != "running" or meta.get("complete"):
            continue
        owner = meta.get("owner") or {}
        same_host = str(owner.get("host") or "") == socket.gethostname()
        if same_host and _pid_is_alive(owner.get("pid", 0)):
            continue
        try:
            last_seen = datetime.fromisoformat(str(
                meta.get("heartbeat_at") or meta.get("created_at") or ""
            ))
            age = (current - last_seen).total_seconds()
        except (TypeError, ValueError):
            try:
                age = current.timestamp() - os.path.getmtime(path)
            except OSError:
                continue
        if age < max(1, int(max_age_seconds)):
            continue
        run_id = str(meta.get("run_id") or os.path.basename(os.path.dirname(path)))
        meta["status"] = "aborted"
        meta["complete"] = False
        meta["abort_reason"] = "stale_running_manifest"
        meta["finished_at"] = current.isoformat(timespec="seconds")
        _write_json(path, meta)
        recovered.append(run_id)
    return recovered


def touch_run(run_id: str, *, now: Optional[datetime] = None) -> bool:
    """Atualiza prova de vida de manifesto em execução; False se não aplicável."""
    path = _meta_path(run_id)
    meta = _read_json(path)
    if not meta or str(meta.get("status")) != "running" or meta.get("complete"):
        return False
    current = now or datetime.now()
    meta["heartbeat_at"] = current.isoformat(timespec="seconds")
    meta["owner"] = _owner()
    _write_json(path, meta)
    return True


def _manifest_completeness(meta: dict, directory: str) -> dict:
    expected = meta.get("expected") or {}
    expected_profiles = [str(p) for p in expected.get("profiles") or []]
    expected_turns = int(expected.get("turns_per_campaign", 0) or 0)
    expected_seed = int(expected.get("seed", 0) or 0)
    expected_real = bool(expected.get("real"))
    expected_invariants = bool(expected.get("invariants_enabled", True))
    campaigns = [
        value for value in (meta.get("campaigns") or {}).values()
        if isinstance(value, dict)
    ]
    by_profile: Dict[str, List[dict]] = {}
    for campaign in campaigns:
        by_profile.setdefault(str(campaign.get("profile") or ""), []).append(campaign)

    missing_profiles = [
        profile for profile in expected_profiles if not by_profile.get(profile)
    ]
    duplicate_profiles = sorted(
        profile for profile in expected_profiles
        if len(by_profile.get(profile, [])) > 1
    )
    unexpected_profiles = sorted(
        profile for profile in by_profile
        if profile not in set(expected_profiles)
    )
    incomplete_campaigns: List[dict] = []
    missing_summaries: List[str] = []
    invalid_summaries: List[dict] = []
    missing_jsonls: List[str] = []
    invalid_jsonls: List[dict] = []
    missing_saves: List[str] = []
    invalid_saves: List[dict] = []
    artifact_mismatches: List[dict] = []
    configuration_errors: List[str] = []

    if not expected_profiles:
        configuration_errors.append("manifesto não declara perfis esperados")
    if expected_turns <= 0:
        configuration_errors.append("turnos esperados devem ser positivos")
    if not expected_invariants:
        configuration_errors.append(
            "invariantes desabilitadas: run formal não pode ser aceita"
        )

    def mismatch(profile: str, field: str, expected_value, actual_value) -> None:
        artifact_mismatches.append({
            "profile": profile,
            "field": field,
            "expected": expected_value,
            "actual": actual_value,
        })

    def load_json_artifact(path: str) -> tuple[Optional[dict], Optional[str]]:
        try:
            with open(path, encoding="utf-8") as fp:
                value = json.load(fp)
        except Exception as exc:
            return None, f"{type(exc).__name__}: {str(exc)[:180]}"
        if not isinstance(value, dict):
            return None, f"raiz {type(value).__name__}, esperado objeto"
        return value, None

    def load_jsonl_artifact(path: str) -> tuple[List[dict], Optional[str]]:
        rows: List[dict] = []
        try:
            with open(path, encoding="utf-8") as fp:
                lines = fp.readlines()
        except Exception as exc:
            return rows, f"{type(exc).__name__}: {str(exc)[:180]}"
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                return rows, f"linha {line_number} vazia"
            try:
                value = json.loads(line)
            except Exception as exc:
                return rows, (
                    f"linha {line_number}: {type(exc).__name__}: "
                    f"{str(exc)[:160]}"
                )
            if not isinstance(value, dict):
                return rows, (
                    f"linha {line_number}: raiz {type(value).__name__}, "
                    "esperado objeto"
                )
            rows.append(value)
        return rows, None

    for profile in expected_profiles:
        for campaign in by_profile.get(profile, []):
            reasons: List[str] = []
            summary_name = str(campaign.get("summary_file") or "")
            summary_path = os.path.join(directory, summary_name)
            summary: Optional[dict] = None
            if not summary_name or not os.path.isfile(summary_path):
                missing_summaries.append(summary_name or f"{profile}:<summary>")
                reasons.append("summary ausente")
            else:
                summary, summary_error = load_json_artifact(summary_path)
                if summary_error:
                    invalid_summaries.append({
                        "profile": profile,
                        "file": summary_name,
                        "error": summary_error,
                    })
                    reasons.append("summary inválido")

            jsonl_name = str(campaign.get("jsonl_file") or "")
            jsonl_path = os.path.join(directory, jsonl_name)
            rows: List[dict] = []
            if not jsonl_name or not os.path.isfile(jsonl_path):
                missing_jsonls.append(jsonl_name or f"{profile}:<jsonl>")
                reasons.append("JSONL ausente")
            else:
                rows, jsonl_error = load_jsonl_artifact(jsonl_path)
                if jsonl_error:
                    invalid_jsonls.append({
                        "profile": profile,
                        "file": jsonl_name,
                        "error": jsonl_error,
                    })
                    reasons.append("JSONL inválido")

            completed = int(campaign.get("turns_completed", 0) or 0)
            requested = int(
                campaign.get("turns_requested", expected_turns) or expected_turns
            )
            campaign_errors = int(campaign.get("errors", 0) or 0)
            campaign_error_violations = int(
                campaign.get("error_violations", 0) or 0
            )
            campaign_observability_errors = int(
                campaign.get("observability_errors", 0) or 0
            )
            campaign_aborted = bool(campaign.get("aborted_reason"))

            if completed != requested or (
                expected_turns and completed != expected_turns
            ):
                reasons.append("contagem de turnos da campanha diverge")
            if campaign_errors:
                reasons.append("campanha contém erros")
            if campaign.get("aborted_reason"):
                reasons.append("campanha abortada")
            if campaign_error_violations:
                reasons.append("campanha contém invariantes error")
            if campaign_observability_errors:
                reasons.append("campanha contém erros de observabilidade")
            if campaign.get("status") != "complete":
                reasons.append("status da campanha não é complete")

            if summary is not None:
                scalar_contract = {
                    "profile": profile,
                    "seed": expected_seed,
                    "turns_requested": expected_turns,
                    "turns_completed": (
                        completed if campaign_aborted else expected_turns
                    ),
                    "errors": campaign_errors,
                    "error_violations": campaign_error_violations,
                    "observability_errors": campaign_observability_errors,
                    "aborted_reason": campaign.get("aborted_reason"),
                    "invariants_enabled": True,
                }
                for field, expected_value in scalar_contract.items():
                    actual_value = summary.get(field)
                    if actual_value != expected_value:
                        mismatch(profile, f"summary.{field}",
                                 expected_value, actual_value)
                        reasons.append(f"summary.{field} diverge")
                if expected_real:
                    if summary.get("mock") is not False:
                        mismatch(profile, "summary.mock", False,
                                 summary.get("mock"))
                        reasons.append("summary não comprova modo real")
                    if int(summary.get("llm_network_successes", 0) or 0) < 1:
                        configuration_errors.append(
                            f"{profile}: run real sem sucesso de rede LLM"
                        )
                        reasons.append("nenhum sucesso de rede LLM")
                    if int(
                        summary.get("startup_llm_network_successes", 0) or 0
                    ) < 1:
                        configuration_errors.append(
                            f"{profile}: startup real sem sucesso de rede LLM"
                        )
                        reasons.append("startup sem sucesso de rede LLM")

                expected_jsonl_rows = completed if campaign_aborted else expected_turns
                if len(rows) != expected_jsonl_rows:
                    invalid_jsonls.append({
                        "profile": profile,
                        "file": jsonl_name,
                        "error": (
                            f"{len(rows)} linhas/turnos, "
                            f"esperado {expected_jsonl_rows}"
                        ),
                    })
                    reasons.append("contagem de linhas do JSONL diverge")
                if rows:
                    turns_seen = [row.get("turn") for row in rows]
                    expected_sequence = list(range(1, len(rows) + 1))
                    if turns_seen != expected_sequence:
                        invalid_jsonls.append({
                            "profile": profile,
                            "file": jsonl_name,
                            "error": (
                                f"sequência de turnos {turns_seen!r}, "
                                f"esperado {expected_sequence!r}"
                            ),
                        })
                        reasons.append("sequência de turnos do JSONL diverge")
                    required_row_fields = {
                        "turn", "game_id", "save_path", "route",
                        "nodes_executed", "decision",
                        "resolved_action", "error", "violations",
                        "violation_details", "llm_events", "rag_events",
                        "player_vitality", "player_max_vitality",
                        "player_wounds", "enemy_wounds",
                        "conflict_wounds", "reactions",
                    }
                    for row_index, row in enumerate(rows, start=1):
                        absent = sorted(required_row_fields - set(row))
                        if absent:
                            invalid_jsonls.append({
                                "profile": profile,
                                "file": jsonl_name,
                                "error": (
                                    f"linha {row_index}: campos ausentes "
                                    f"{', '.join(absent)}"
                                ),
                            })
                            reasons.append("JSONL sem campos obrigatórios")
                            break
                        row_contract_errors: List[str] = []
                        if row.get("route") not in {
                            "storyteller", "combat_agent", "npc_actor", "loot",
                            "timeout",
                        }:
                            row_contract_errors.append(
                                f"route inválida {row.get('route')!r}"
                            )
                        nodes = row.get("nodes_executed")
                        if not isinstance(nodes, list):
                            row_contract_errors.append(
                                "nodes_executed inválido"
                            )
                        elif row.get("route") != "timeout" and not nodes:
                            row_contract_errors.append("nodes_executed vazio")
                        elif row.get("route") != "timeout" and "archivist" not in nodes:
                            row_contract_errors.append(
                                "archivist ausente de nodes_executed"
                            )
                        decision = row.get("decision")
                        if not isinstance(decision, dict):
                            row_contract_errors.append("decision não é objeto")
                        elif row.get("action") != decision.get("text"):
                            row_contract_errors.append(
                                "action diverge de decision.text"
                            )
                        for list_field in (
                            "llm_events", "rag_events", "reactions",
                            "violations", "violation_details",
                        ):
                            if not isinstance(row.get(list_field), list):
                                row_contract_errors.append(
                                    f"{list_field} não é lista"
                                )
                        for dict_field in (
                            "resolved_action", "player_wounds",
                            "enemy_wounds", "conflict_wounds",
                        ):
                            if not isinstance(row.get(dict_field), dict):
                                row_contract_errors.append(
                                    f"{dict_field} não é objeto"
                                )
                        if row_contract_errors:
                            invalid_jsonls.append({
                                "profile": profile,
                                "file": jsonl_name,
                                "error": (
                                    f"linha {row_index}: "
                                    + "; ".join(row_contract_errors)
                                ),
                            })
                            reasons.append("contrato de linha JSONL inválido")
                        if row.get("game_id") != summary.get("game_id"):
                            mismatch(
                                profile,
                                f"jsonl[{row_index}].game_id",
                                summary.get("game_id"),
                                row.get("game_id"),
                            )
                            reasons.append("game_id do JSONL diverge")
                        if row.get("save_path") != summary.get("save_path"):
                            mismatch(
                                profile,
                                f"jsonl[{row_index}].save_path",
                                summary.get("save_path"),
                                row.get("save_path"),
                            )
                            reasons.append("save_path do JSONL diverge")
                    row_errors = len([row for row in rows if row.get("error")])
                    if row_errors != int(summary.get("errors", 0) or 0):
                        mismatch(profile, "jsonl.errors",
                                 int(summary.get("errors", 0) or 0), row_errors)
                        reasons.append("erros JSONL divergem do summary")
                    row_error_violations = len([
                        detail
                        for row in rows
                        for detail in (row.get("violation_details") or [])
                        if isinstance(detail, dict)
                        and detail.get("severity") == "error"
                    ])
                    if row_error_violations != int(
                        summary.get("error_violations", 0) or 0
                    ):
                        mismatch(
                            profile,
                            "jsonl.error_violations",
                            int(summary.get("error_violations", 0) or 0),
                            row_error_violations,
                        )
                        reasons.append(
                            "invariantes error do JSONL divergem do summary"
                        )
                    row_routes = Counter(
                        str(row.get("route") or "")
                        for row in rows if row.get("route")
                    )
                    if dict(row_routes) != dict(summary.get("routes") or {}):
                        mismatch(profile, "jsonl.routes",
                                 summary.get("routes") or {}, dict(row_routes))
                        reasons.append("rotas JSONL divergem do summary")
                    row_violations = Counter(
                        str(check_id)
                        for row in rows
                        for check_id in (row.get("violations") or [])
                    )
                    if dict(row_violations) != dict(
                        summary.get("violations") or {}
                    ):
                        mismatch(
                            profile,
                            "jsonl.violations",
                            summary.get("violations") or {},
                            dict(row_violations),
                        )
                        reasons.append("violações JSONL divergem do summary")

                summary_save = str(summary.get("save_path") or "")
                campaign_save = str(campaign.get("save_path") or "")
                summary_game_id = str(summary.get("game_id") or "")
                campaign_game_id = str(campaign.get("game_id") or "")
                if summary_save != campaign_save:
                    mismatch(profile, "save_path",
                             campaign_save, summary_save)
                    reasons.append("vínculo de save diverge")
                if summary_game_id != campaign_game_id:
                    mismatch(profile, "game_id",
                             campaign_game_id, summary_game_id)
                    reasons.append("game_id diverge")

            save_path = str(campaign.get("save_path") or "")
            if not save_path or not os.path.isfile(save_path):
                missing_saves.append(save_path or f"{profile}:<save>")
                reasons.append("save final ausente")
            else:
                save_data, save_error = load_json_artifact(save_path)
                if save_error:
                    invalid_saves.append({
                        "profile": profile,
                        "file": save_path,
                        "error": save_error,
                    })
                    reasons.append("save final inválido")
                elif str(save_data.get("game_id") or "") != str(
                    campaign.get("game_id") or ""
                ):
                    mismatch(
                        profile,
                        "save.game_id",
                        campaign.get("game_id"),
                        save_data.get("game_id"),
                    )
                    reasons.append("game_id do save diverge")

            if (
                reasons
            ):
                incomplete_campaigns.append({
                    "profile": profile,
                    "turns_completed": completed,
                    "turns_expected": expected_turns or requested,
                    "errors": campaign_errors,
                    "aborted_reason": campaign.get("aborted_reason"),
                    "error_violations": campaign_error_violations,
                    "observability_errors": campaign_observability_errors,
                    "reasons": list(dict.fromkeys(reasons)),
                })

    declared_summaries = {
        str(campaign.get("summary_file") or "")
        for campaign in campaigns
        if campaign.get("summary_file")
    }
    declared_jsonls = {
        str(campaign.get("jsonl_file") or "")
        for campaign in campaigns
        if campaign.get("jsonl_file")
    }
    actual_summaries = {
        os.path.basename(path)
        for path in glob.glob(os.path.join(directory, "*.summary.json"))
    }
    actual_jsonls = {
        os.path.basename(path)
        for path in glob.glob(os.path.join(directory, "*.jsonl"))
    }
    unexpected_summaries = sorted(actual_summaries - declared_summaries)
    unexpected_jsonls = sorted(actual_jsonls - declared_jsonls)

    data_complete = bool(expected_profiles) and expected_turns > 0 and not (
        missing_profiles
        or duplicate_profiles
        or unexpected_profiles
        or len(campaigns) != len(expected_profiles)
        or incomplete_campaigns
        or missing_summaries
        or invalid_summaries
        or missing_jsonls
        or invalid_jsonls
        or missing_saves
        or invalid_saves
        or artifact_mismatches
        or configuration_errors
        or unexpected_summaries
        or unexpected_jsonls
    )
    return {
        "data_complete": data_complete,
        "expected_campaigns": len(expected_profiles),
        "persisted_campaigns": len(campaigns),
        "expected_turns_per_campaign": expected_turns,
        "missing_profiles": missing_profiles,
        "duplicate_profiles": duplicate_profiles,
        "unexpected_profiles": unexpected_profiles,
        "incomplete_campaigns": incomplete_campaigns,
        "missing_summaries": missing_summaries,
        "invalid_summaries": invalid_summaries,
        "missing_jsonls": missing_jsonls,
        "invalid_jsonls": invalid_jsonls,
        "missing_saves": missing_saves,
        "invalid_saves": invalid_saves,
        "artifact_mismatches": artifact_mismatches,
        "configuration_errors": configuration_errors,
        "unexpected_summaries": unexpected_summaries,
        "unexpected_jsonls": unexpected_jsonls,
    }


def inspect_run(run_id_or_dir: str) -> dict:
    """Inspeciona o manifesto sem confiar apenas no campo `status` gravado."""
    directory = (
        run_id_or_dir
        if os.path.isdir(run_id_or_dir)
        else run_dir(run_id_or_dir)
    )
    meta = _read_json(os.path.join(directory, RUN_META_FILENAME))
    if not meta:
        return {
            "manifest": False,
            "status": "legacy",
            # Diretórios anteriores ao manifesto continuam legíveis no report,
            # mas nunca constituem evidência de aceite formal.
            "complete": False,
            "data_complete": False,
            "expected_campaigns": None,
            "persisted_campaigns": None,
            "expected_turns_per_campaign": None,
            "missing_profiles": [],
            "duplicate_profiles": [],
            "unexpected_profiles": [],
            "incomplete_campaigns": [],
            "missing_summaries": [],
            "invalid_summaries": [],
            "missing_jsonls": [],
            "invalid_jsonls": [],
            "missing_saves": [],
            "invalid_saves": [],
            "artifact_mismatches": [],
            "configuration_errors": [
                "manifesto ausente: run legado não é aceite formal",
            ],
            "unexpected_summaries": [],
            "unexpected_jsonls": [],
        }
    details = _manifest_completeness(meta, directory)
    status = str(meta.get("status") or "running")
    return {
        "manifest": True,
        "status": status,
        "complete": bool(details["data_complete"] and status == "complete"),
        **details,
    }


def finish_run(run_id: str, *, status: str = "complete",
               reason: Optional[str] = None) -> dict:
    """Fecha o manifesto; `complete` só é verdadeiro se os artefatos provarem."""
    path = _meta_path(run_id)
    meta = _read_json(path)
    if not meta:
        raise FileNotFoundError(f"manifesto ausente: {path}")
    details = _manifest_completeness(meta, run_dir(run_id))
    requested_success = status in ("complete", "completed", "success")
    if requested_success:
        meta["status"] = "complete" if details["data_complete"] else "failed"
    else:
        meta["status"] = status if status in ("failed", "aborted") else "failed"
    meta["complete"] = meta["status"] == "complete"
    if reason:
        meta["abort_reason"] = str(reason)[:500]
    meta["finished_at"] = datetime.now().isoformat(timespec="seconds")
    meta["heartbeat_at"] = meta["finished_at"]
    meta["completeness"] = details
    _write_json(path, meta)
    return inspect_run(run_id)


# --- registros por turno ----------------------------------------------------

def turn_to_record(rec: TurnRecord) -> dict:
    """TurnRecord -> dict serializável (1 linha do JSONL)."""
    return {
        "turn": rec.turn,
        "game_id": rec.game_id,
        "save_path": rec.save_path,
        "action": rec.action,
        "narrative": rec.narrative,
        "progression_choices": list(rec.progression_choices),
        "quest_requested": rec.quest_requested,
        "quests_before": rec.quests_before,
        "quests_after": rec.quests_after,
        "combat_origin": rec.combat_origin,
        "conflict_instance_id": rec.conflict_instance_id,
        "session_action_count": rec.session_action_count,
        "canonical_turn": rec.canonical_turn,
        "timeline_epoch": rec.timeline_epoch,
        "route": rec.route,
        "nodes_executed": list(rec.nodes_executed),
        "node_latency_ms": dict(rec.node_latency_ms),
        "combat_executed": rec.combat_executed,
        "combat_active_before": rec.combat_active_before,
        "combat_round_before": rec.combat_round_before,
        "combat_round_after": rec.combat_round_after,
        "combat_started": rec.combat_started,
        "combat_ended": rec.combat_ended,
        "decision": dict(rec.decision),
        "resolved_action": dict(rec.resolved_action),
        "latency_ms": rec.latency_ms,
        "events_applied": rec.events_applied,
        "events_rejected": rec.events_rejected,
        "error": rec.error,
        "location_id": rec.location_id,
        "player_hp": rec.player_hp,
        "player_max_hp": rec.player_max_hp,
        "player_vitality": rec.player_vitality,
        "player_max_vitality": rec.player_max_vitality,
        "player_level": rec.player_level,
        "gold": rec.gold,
        "combat_active": rec.combat_active,
        "replanned": rec.replanned,
        # spec balanceamento-classes-pos-playtest (R2)
        "entropy": rec.entropy,
        "max_entropy": rec.max_entropy,
        "abyss_charge": rec.abyss_charge,
        "abyss_tier": rec.abyss_tier,
        # spec playtest-agente-curioso-entropia (R3): gasto real de Entropia
        "entropy_spent": rec.entropy_spent,
        "used_active_ability": rec.used_active_ability,
        "ability_id": rec.ability_id,
        "class_mechanics": list(rec.class_mechanics),
        "reactions": list(rec.reactions),
        "last_tactics": list(rec.last_tactics),
        "player_wounds": dict(rec.player_wounds),
        "enemy_wounds": dict(rec.enemy_wounds),
        "conflict_wounds": dict(rec.conflict_wounds),
        "memory_by_provenance": dict(rec.memory_by_provenance),
        "memory_by_confidence": dict(rec.memory_by_confidence),
        "stale_speculative_memories": rec.stale_speculative_memories,
        "memory_writes_by_provenance": dict(rec.memory_writes_by_provenance),
        "memory_rejections": rec.memory_rejections,
        "memory_promotions": rec.memory_promotions,
        "violations": list(rec.violations),
        "violation_details": list(rec.violation_details),
        "death": rec.death,
        "death_pending": rec.death_pending,
        "game_over": rec.game_over,
        "llm_events": list(rec.llm_events),
        "rag_events": list(rec.rag_events),
        "provider": rec.provider,
        "model": rec.model,
        "tier": rec.tier,
        "fell_back": rec.fell_back,
        "cost_usd": round(pricing.turn_cost([
            event for event in rec.llm_events
            if event.get("network_attempted", True)
        ]), 6),
    }


def write_turn(fp, record: dict) -> None:
    fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def _percentile(values: List[int], pct: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = min(len(s) - 1, int(round((pct / 100.0) * (len(s) - 1))))
    return int(s[idx])


def _min_active_entropy_cost(player: dict) -> int:
    """Menor custo de Entropia entre as Cartas ATIVAS preparadas do jogador
    (spec playtest-agente-curioso-entropia R4). 0 se a classe não tem ativa de
    Entropia (starvation não se aplica)."""
    try:
        from services import cards
    except Exception:
        return 0
    costs: List[int] = []
    for aid in (player.get("prepared_cards") or []):
        ab = cards.get_card(str(aid))
        if not isinstance(ab, dict):
            continue
        if ab.get("tipo") != "ativa":
            continue
        cost = int(ab.get("custo_entropia", 0) or 0)
        if cost > 0:
            costs.append(cost)
    return min(costs) if costs else 0


def build_summary(result: CampaignResult, turn_records: List[dict]) -> dict:
    """Métricas agregadas da campanha (spec 5.3 R2)."""
    routes: dict = {}
    violations: dict = {}
    violation_samples: dict = {}
    providers: dict = {}
    cost_by_tier: dict = {}
    latencies: List[int] = []
    fell_back_turns = 0
    action_kinds: Counter = Counter()

    for r in turn_records:
        if r.get("route"):
            routes[r["route"]] = routes.get(r["route"], 0) + 1
        for cid in r.get("violations", []):
            violations[cid] = violations.get(cid, 0) + 1
        for detail in r.get("violation_details", []) or []:
            if not isinstance(detail, dict):
                continue
            cid = str(detail.get("check_id") or "")
            if cid and cid not in violation_samples:
                violation_samples[cid] = detail
        latencies.append(int(r.get("latency_ms", 0)))
        action_kinds[str((r.get("decision") or {}).get("kind") or "unknown")] += 1
        if r.get("fell_back"):
            fell_back_turns += 1

    # Inclui criação/abertura e CADA candidato. Build skip é tentativa, mas não
    # request nem custo; falha que chegou à rede entra no lower bound.
    startup_llm_events = list(
        getattr(result, "startup_llm_events", []) or []
    )
    all_llm_events = startup_llm_events + [
        event
        for rec in result.history
        for event in (rec.llm_events or [])
        if isinstance(event, dict)
    ]
    network_llm_events = [
        event for event in all_llm_events
        if event.get("network_attempted", True)
    ]
    for event in network_llm_events:
        provider = event.get("provider") or "?"
        providers[provider] = providers.get(provider, 0) + 1
        tier = event.get("tier") or "?"
        cost_by_tier[tier] = round(
            cost_by_tier.get(tier, 0.0)
            + pricing.estimate_cost(event.get("model", "")),
            6,
        )
    llm_successes = len([
        event for event in all_llm_events
        if event.get("status", "success") == "success"
    ])
    llm_skipped = len([
        event for event in all_llm_events
        if event.get("status") == "circuit_open"
    ])
    llm_attempts = len(all_llm_events)
    llm_failures = llm_attempts - llm_successes - llm_skipped
    llm_network_successes = len([
        event for event in network_llm_events
        if event.get("status", "success") == "success"
    ])
    startup_llm_network_successes = len([
        event for event in startup_llm_events
        if event.get("network_attempted", True)
        and event.get("status", "success") == "success"
    ])
    cost_total = pricing.turn_cost(network_llm_events)

    memory_writes_by_provenance: Counter = Counter()
    startup_rag_events = list(
        getattr(result, "startup_rag_events", []) or []
    )
    all_rag_events = startup_rag_events + [
        event
        for rec in result.history
        for event in (rec.rag_events or [])
        if isinstance(event, dict)
    ]
    for event in startup_rag_events:
        if not event.get("success"):
            continue
        memory_writes_by_provenance.update({
            str(key): int(value or 0)
            for key, value in dict(
                event.get("provenance_counts") or {}
            ).items()
        })
    rag_operations: Dict[str, int] = {}
    for event in all_rag_events:
        operation = str(event.get("operation") or "?")
        rag_operations[operation] = rag_operations.get(operation, 0) + 1
    rag_failures = len([
        event for event in all_rag_events if not event.get("success", False)
    ])
    startup_missing = bool(not result.mock and not startup_llm_events)
    observability_errors = rag_failures + int(startup_missing)

    final = result.final_state or {}
    world = final.get("world", {}) or {}
    player = final.get("player", {}) or {}
    quests = [q for q in (final.get("quests") or []) if isinstance(q, dict)]
    final_memory_by_provenance = dict(
        turn_records[-1].get("memory_by_provenance") or {}
    ) if turn_records else {}
    final_memory_by_confidence = dict(
        turn_records[-1].get("memory_by_confidence") or {}
    ) if turn_records else {}
    final_memory_rejections = int(
        turn_records[-1].get("memory_rejections", 0) or 0
    ) if turn_records else 0
    final_memory_promotions = int(
        turn_records[-1].get("memory_promotions", 0) or 0
    ) if turn_records else 0
    for record in turn_records:
        memory_writes_by_provenance.update({
            str(key): int(value or 0)
            for key, value in dict(
                record.get("memory_writes_by_provenance") or {}
            ).items()
        })

    # Morte canônica: log do runner; para saves antigos, somente marcadores
    # terminais explícitos permitem inferência. HP/Vitalidade zero isolados não.
    continuity_deaths = [
        row for row in ((final.get("continuity") or {}).get("death_history") or [])
        if isinstance(row, dict)
    ]
    deaths_log = list(getattr(result, "deaths_log", []) or [])
    if not deaths_log and continuity_deaths:
        deaths_log = [{
            "turn": row.get("session_action"),
            "session_action": row.get("session_action"),
            "canonical_turn": row.get("death_turn"),
            "timeline_epoch": row.get("epoch"),
            "location": row.get("location"),
            "cause": row.get("cause"),
        } for row in continuity_deaths]
    if not deaths_log and (final.get("death_pending") or final.get("game_over")):
        death_ev = next(
            (ev for ev in reversed(final.get("event_log") or [])
             if isinstance(ev, dict) and ev.get("type") in ("player_died", "player_downed")), None)
        death_payload = (death_ev or {}).get("payload", {}) or {}
        deaths_log = [{
            "turn": (
                (death_ev or {}).get("turn")
                or (turn_records[-1].get("turn") if turn_records else None)
            ),
            "location": death_payload.get("location"),
            "cause": death_payload.get("killer"),
        }]

    # spec balanceamento-early-game (R5): métricas de balanço da campanha.
    first_death = deaths_log[0] if deaths_log else {}
    last_death = deaths_log[-1] if deaths_log else {}
    first_death_turn = first_death.get("turn")
    death_location = first_death.get("location") or None
    death_cause = first_death.get("cause") or None
    downed_count = (
        len(continuity_deaths) if continuity_deaths else len(deaths_log)
    )
    replan_count = len([r for r in turn_records if r.get("replanned")])
    combat_turns = len([
        r for r in turn_records
        if r.get("combat_executed") or r.get("route") == "combat_agent"
    ])
    quest_requests = len([r for r in turn_records if r.get("quest_requested")])
    from playtest.metrics import quest_request_conversion_count
    quest_request_conversions = quest_request_conversion_count(
        turn_records, window=3,
    )
    experience_balance = {
        "combat_turns": combat_turns,
        "combat_turn_pct": (
            round(100.0 * combat_turns / len(turn_records), 1)
            if turn_records else None
        ),
        "quest_requests": quest_requests,
        "quest_request_conversions": quest_request_conversions,
        "quest_conversion_pct": (
            round(100.0 * quest_request_conversions / quest_requests, 1)
            if quest_requests else None
        ),
    }
    node_samples: Dict[str, List[int]] = {}
    for row in turn_records:
        for node, value in dict(row.get("node_latency_ms") or {}).items():
            node_samples.setdefault(str(node), []).append(int(value or 0))
    node_latency = {
        node: {
            "count": len(values),
            "mean": round(sum(values) / len(values), 1) if values else 0,
            "p50": _percentile(values, 50),
            "p95": _percentile(values, 95),
            "max": max(values, default=0),
        }
        for node, values in sorted(node_samples.items())
    }
    combat_origins = Counter(
        str(row.get("combat_origin") or "unknown") for row in turn_records
        if row.get("combat_started")
    )
    started_conflicts = [
        (
            str(row.get("conflict_instance_id") or f"legacy:{row.get('turn')}"),
            int(row.get("timeline_epoch", 0) or 0),
        )
        for row in turn_records if row.get("combat_started")
    ]
    ended_conflicts = [
        (
            str(row.get("conflict_instance_id") or f"legacy:{row.get('turn')}"),
            int(row.get("timeline_epoch", 0) or 0),
        )
        for row in turn_records if row.get("combat_ended")
    ]
    combat_end_hp_pcts: List[float] = []
    prev_combat = False
    for r in turn_records:
        now_combat = bool(r.get("combat_active"))
        ended = bool(r.get("combat_ended")) or (
            (not now_combat)
            and (
                prev_combat
                or r.get("combat_executed")
                or r.get("route") == "combat_agent"
            )
        )
        mx = int(
            r.get("player_max_vitality", r.get("player_max_hp", 0)) or 0
        )
        if ended and mx > 0:
            current = int(
                r.get("player_vitality", r.get("player_hp", 0)) or 0
            )
            combat_end_hp_pcts.append(100.0 * current / mx)
        prev_combat = now_combat
    avg_hp_pct_after_combat = (
        round(sum(combat_end_hp_pcts) / len(combat_end_hp_pcts), 1)
        if combat_end_hp_pcts else None)

    # spec playtest-agente-curioso-entropia (R4): economia de Entropia medida por
    # GASTO, não por snapshot. Turno de combate = rota combat_agent (o gasto só é
    # fiel aí; ver runner._fill_state_metrics). O snapshot antigo era degenerado
    # (o gatilho reenche ao teto → flooding 100% / starvation 0% sempre).
    combat_rows = [
        r for r in turn_records
        if r.get("combat_executed") or r.get("route") == "combat_agent"
    ]

    def _pct(n: int, d: int):
        return round(100.0 * n / d, 1) if d else None

    n_combat = len(combat_rows)
    ability_turns = [r for r in combat_rows if r.get("used_active_ability")]
    # "Básico" significa ataque básico de fato. A versão anterior tratava
    # poção, fuga, manobra e passe como desperdício de Entropia, inflando
    # flooding justamente quando o agente jogava defensivamente.
    basic_turns = [
        r for r in combat_rows
        if not r.get("used_active_ability")
        and str((r.get("resolved_action") or {}).get("kind") or "") == "attack"
    ]
    spent_total = sum(int(r.get("entropy_spent", 0) or 0) for r in combat_rows)
    spent_per_combat_turn = round(spent_total / n_combat, 2) if n_combat else None
    pct_ability_used = _pct(len(ability_turns), n_combat)
    pct_basic_only = _pct(len(basic_turns), n_combat)
    # starvation REDEFINIDO: turno de combate que NÃO usou ativa E tinha Entropia
    # abaixo do menor custo de ativa conhecida (recurso faltou p/ agir).
    min_active_cost = _min_active_entropy_cost(player)
    starvation = _pct(
        len([r for r in basic_turns
             if int(r.get("max_entropy", 0) or 0) > 0
             and int(r.get("entropy", 0) or 0) < min_active_cost]),
        n_combat) if min_active_cost > 0 else None
    # flooding REDEFINIDO: turno que terminou com ataque básico E Entropia cheia
    # (recurso sobrou e não foi usado — gatilho/pool irrelevante).
    flooding = _pct(
        len([r for r in basic_turns
             if int(r.get("max_entropy", 0) or 0) > 0
             and int(r.get("entropy", 0) or 0) == int(r.get("max_entropy", 0) or 0)]),
        n_combat)
    peak_charge = max((int(r.get("abyss_charge", 0) or 0) for r in turn_records), default=0)
    class_mechanics = Counter(
        str(event.get("kind"))
        for row in turn_records
        for event in (row.get("class_mechanics") or [])
        if isinstance(event, dict) and event.get("kind")
    )
    try:
        from combat_mechanics import abyss_tier
        final_tier = abyss_tier(player)
    except Exception:
        final_tier = ""

    return {
        "game_id": str(final.get("game_id") or ""),
        "save_path": (
            os.path.abspath(result.save_path)
            if getattr(result, "save_path", "") else ""
        ),
        "profile": result.profile,
        "scenario": getattr(result, "scenario", None),
        "seed": result.seed,
        "class_name": player.get("class_name") or None,
        "entropy": {
            "spent_total": spent_total,
            "spent_per_combat_turn": spent_per_combat_turn,
            "pct_combat_turns_ability_used": pct_ability_used,
            "pct_combat_turns_basic_only": pct_basic_only,
            "starvation_pct_combat": starvation,
            "flooding_pct_combat": flooding,
            "peak_abyss_charge": peak_charge,
            "final_abyss_charge": int(player.get("abyss_charge", 0) or 0),
            "final_abyss_tier": final_tier,
            "mechanic_activations": dict(sorted(class_mechanics.items())),
        },
        "turns_completed": result.turns_completed,
        "turns_requested": int(
            getattr(result, "turns_requested", 0) or result.turns_completed
        ),
        "errors": len(result.errors),
        "violations": violations,
        "violation_samples": violation_samples,
        "error_violations": len([
            violation for violation in (result.violations or [])
            if violation.get("severity") == "error"
        ]),
        "warning_violations": len([
            violation for violation in (result.violations or [])
            if violation.get("severity") == "warning"
        ]),
        "routes": routes,
        "latency_ms": {"p50": _percentile(latencies, 50), "p95": _percentile(latencies, 95)},
        "node_latency_ms": node_latency,
        "latency_slo": {
            "warning_ms": 45_000,
            "error_ms": 90_000,
            "over_warning_45s": len([value for value in latencies if value > 45_000]),
            "over_error_90s": len([value for value in latencies if value > 90_000]),
        },
        "diversity": {
            "unique_routes": len(routes),
            "unique_action_kinds": len(action_kinds),
            "action_kinds": dict(sorted(action_kinds.items())),
        },
        "progression_choices": sum(
            len(record.get("progression_choices") or []) for record in turn_records
        ),
        "experience_balance": experience_balance,
        "combat_origins": dict(sorted(combat_origins.items())),
        "continuity": {
            "session_action_count": int((final.get("continuity") or {}).get(
                "session_action_count", len(turn_records)) or 0),
            "canonical_turn": int(world.get("turn_count", 0) or 0),
            "timeline_epoch": int((final.get("continuity") or {}).get("timeline_epoch", 0) or 0),
        },
        # spec checkpoints-morte: conta TODAS as mortes (cada uma dispara restore);
        # game_over só existe pela via voluntária "Aceitar".
        "deaths": len(deaths_log),
        "deaths_log": deaths_log,
        "first_death_turn": first_death_turn,
        "death_location": death_location,
        "death_cause": death_cause,
        "last_death_turn": last_death.get("turn"),
        "last_death_location": last_death.get("location") or None,
        "last_death_cause": last_death.get("cause") or None,
        "downed_count": downed_count,
        "avg_hp_pct_after_combat": avg_hp_pct_after_combat,
        "replan_count": replan_count,
        "final_level": int(player.get("level", 1) or 1),
        "final_gold": int(player.get("gold", 0) or 0),
        "locations_visited": len(world.get("visited", []) or []),
        "quests": {
            "created": len(quests),
            "progressed": len([q for q in quests if len(q.get("progress_log") or []) > 1]),
            "completed": len([q for q in quests if q.get("status") == "completed"]),
            "rewarded": len([q for q in quests if q.get("reward_delivered")]),
            "reward_gold": sum(int(q.get("reward_gold", 0) or 0) for q in quests),
        },
        "memory": {
            "by_provenance": final_memory_by_provenance,
            "by_confidence": final_memory_by_confidence,
            "authority_pct": (
                round(100.0 * (
                    int(final_memory_by_confidence.get("confirmed", 0) or 0)
                    + int(final_memory_by_confidence.get("reported", 0) or 0)
                ) / sum(int(v or 0) for v in final_memory_by_confidence.values()), 1)
                if sum(int(v or 0) for v in final_memory_by_confidence.values()) else None
            ),
            "stale_speculative": int(
                turn_records[-1].get("stale_speculative_memories", 0) or 0
            ) if turn_records else 0,
            "writes_by_provenance": dict(memory_writes_by_provenance),
            "rejections": final_memory_rejections,
            "promotions": final_memory_promotions,
        },
        "llm_requests_by_provider": providers,
        "llm_attempts": llm_attempts,
        "llm_successes": llm_successes,
        "llm_failures": llm_failures,
        "llm_skipped": llm_skipped,
        "llm_network_requests": len(network_llm_events),
        "llm_network_successes": llm_network_successes,
        "startup_llm_attempts": len(startup_llm_events),
        "startup_llm_skipped": len([
            event for event in startup_llm_events
            if event.get("status") == "circuit_open"
        ]),
        "startup_llm_network_successes": startup_llm_network_successes,
        "startup_llm_missing": startup_missing,
        "startup_llm_events": startup_llm_events,
        "cost_usd_total": round(cost_total, 6),
        "cost_usd_by_tier": cost_by_tier,
        "fell_back_turns": fell_back_turns,
        "rag_operations": rag_operations,
        "rag_operation_count": len(all_rag_events),
        "rag_failures": rag_failures,
        "startup_rag_events": startup_rag_events,
        "observability_errors": observability_errors,
        "mock": result.mock,
        "aborted_reason": result.aborted_reason,
        "invariants_enabled": bool(
            getattr(result, "invariants_enabled", True)
        ),
        "combat_coverage": {
            "executed_turns": len([
                record for record in turn_records
                if record.get("combat_executed")
            ]),
            "started": len(set(started_conflicts)),
            "ended": len(set(ended_conflicts)),
            "replayed_starts": len(started_conflicts) - len(set(started_conflicts)),
            "timeline_epochs": len({epoch for _identity, epoch in started_conflicts}),
            "reactions": sum(
                len(record.get("reactions") or [])
                for record in turn_records
            ),
            "tactics": sum(
                len(record.get("last_tactics") or [])
                for record in turn_records
            ),
        },
    }


def persist_campaign(run_id: str, result: CampaignResult,
                     stem: str | None = None) -> dict:
    """Escreve `{stem}.jsonl` + `{stem}.summary.json` no run (default
    `{profile}_{seed}`; runs por CLASSE passam stem próprio p/ não colidir —
    spec balanceamento-classes-pos-playtest). Devolve o summary."""
    d = run_dir(run_id)
    os.makedirs(d, exist_ok=True)
    stem = stem or f"{result.profile}_{result.seed}"
    turn_records = [turn_to_record(r) for r in result.history]
    game_id = str((result.final_state or {}).get("game_id") or "")
    linked_save_path = (
        os.path.abspath(result.save_path)
        if getattr(result, "save_path", "") else ""
    )
    for record in turn_records:
        # A linha deve ser auditável sem depender do nome do arquivo ou de um
        # join implícito pelo profile.
        record["game_id"] = game_id
        record["save_path"] = linked_save_path

    with open(os.path.join(d, f"{stem}.jsonl"), "w", encoding="utf-8") as f:
        for rec in turn_records:
            write_turn(f, rec)

    summary = build_summary(result, turn_records)
    with open(os.path.join(d, f"{stem}.summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    meta_path = os.path.join(d, RUN_META_FILENAME)
    meta = _read_json(meta_path)
    if meta:
        expected = meta.get("expected") or {}
        formal_invariants = bool(expected.get("invariants_enabled", True))
        requires_real = bool(expected.get("real"))
        requested = int(
            getattr(result, "turns_requested", 0) or result.turns_completed
        )
        error_violations = int(summary.get("error_violations", 0) or 0)
        observability_errors = int(
            summary.get("observability_errors", 0) or 0
        )
        campaign_ok = (
            result.turns_completed == requested
            and not result.errors
            and not result.aborted_reason
            and error_violations == 0
            and observability_errors == 0
            and formal_invariants
            and bool(summary.get("invariants_enabled"))
            and (
                not requires_real
                or (
                    summary.get("mock") is False
                    and int(summary.get("llm_network_successes", 0) or 0) > 0
                    and int(
                        summary.get("startup_llm_network_successes", 0) or 0
                    ) > 0
                )
            )
        )
        campaigns = meta.setdefault("campaigns", {})
        campaigns[stem] = {
            "profile": result.profile,
            "seed": result.seed,
            "game_id": summary.get("game_id") or "",
            "save_path": summary.get("save_path") or "",
            "turns_requested": requested,
            "turns_completed": result.turns_completed,
            "summary_file": f"{stem}.summary.json",
            "jsonl_file": f"{stem}.jsonl",
            "errors": len(result.errors),
            "error_violations": error_violations,
            "warning_violations": int(
                summary.get("warning_violations", 0) or 0
            ),
            "observability_errors": observability_errors,
            "aborted_reason": result.aborted_reason,
            "mock": bool(summary.get("mock")),
            "invariants_enabled": bool(summary.get("invariants_enabled")),
            "llm_network_successes": int(
                summary.get("llm_network_successes", 0) or 0
            ),
            "startup_llm_network_successes": int(
                summary.get("startup_llm_network_successes", 0) or 0
            ),
            "status": "complete" if campaign_ok else "failed",
        }
        meta["heartbeat_at"] = datetime.now().isoformat(timespec="seconds")
        _write_json(meta_path, meta)
    return summary
