"""SPEC-207 Etapas 2–3: trilha por turno (ring buffer) + builder ZIP determinístico."""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import persistence
from services import audit_trace
from services.audit_export import (
    FIXED_FILES,
    AuditLimits,
    AuditSource,
    build_audit_bundle,
    bundle_zip,
    verify_audit_zip,
    write_zip,
)
from services.audit_redaction import PRIVATE_LABEL

GEN_AT = "2026-10-16T00:00:00Z"
REF_KEYS = {
    "source_id",
    "section",
    "visibility",
    "purpose",
    "npc_id",
    "knowledge_kind",
    "certainty",
    "source_kind",
}


@pytest.fixture()
def client(monkeypatch):
    import api

    monkeypatch.setenv("RPG_RATE_LIMIT", "0")
    api._rate_hits.clear()
    return TestClient(api.app)


def _new_game(client) -> str:
    r = client.post(
        "/game/new",
        json={
            "name": "Auditada",
            "race": "Humano",
            "class_name": "Sangromante",
            "region": "Nova Arcádia",
            "level": 1,
            "backstory": "",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["game_id"]


@pytest.fixture()
def played(client):
    gid = _new_game(client)
    for text in (
        "Olho ao redor da praça.",
        "Falo com o taverneiro sobre boatos.",
        "Meu email é jogador.real@example.com, me chame em (11) 98765-4321.",
    ):
        r = client.post(
            "/game/action",
            json={"input_text": text, "game_id": gid, "action_id": str(uuid.uuid4())},
        )
        assert r.status_code == 200, r.text
    state = persistence.load_game_state(persistence.save_path(gid))
    assert state is not None
    return gid, state


def _source(state, **kw) -> AuditSource:
    return AuditSource(game_id=str(state["game_id"]), state=state, **kw)


def _zip_files(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {n: archive.read(n) for n in archive.namelist()}


# --------------------------------------------------------------------------- #
# Etapa 2 — trilha
# --------------------------------------------------------------------------- #
def test_real_turns_write_trace(played):
    _gid, state = played
    trace = state["audit_trace"]
    assert len(trace) == 3
    assert all(row["action_ref"] for row in trace)
    assert all(isinstance(row["delta"], dict) for row in trace)


def test_trace_ring_buffer_caps_at_limit(monkeypatch):
    monkeypatch.setenv("RPG_AUDIT_TRACE_MAX", "3")
    state = {"game_id": "g", "world": {"turn_count": 0}, "player": {}}
    for i in range(5):
        state["world"]["turn_count"] = i
        audit_trace.record_turn_trace(
            state, previous_state=dict(state), action_id=f"a{i}", context_refs=[]
        )
    assert [row["turn"] for row in state["audit_trace"]] == [2, 3, 4]
    # cabe no orçamento de tamanho por turno (estimativa da spec: 0,5–2 KB)
    monkeypatch.delenv("RPG_AUDIT_TRACE_MAX")
    assert audit_trace.trace_limit() == 200
    size = len(json.dumps(state["audit_trace"][-1]))
    assert size < 2048


def test_real_turn_trace_fits_size_budget(played, monkeypatch):
    """Revisão Astra: ring de 200 turnos reais (MockLLM, ~94 refs/turno alternando
    narrador↔NPC) cabe em 400 KB no save (antes: ~19 KB por linha, ≈4 MB)."""
    _gid, state = played
    real = audit_trace.expand_trace(state["audit_trace"])
    assert all(len(list(audit_trace.iter_context_refs(r))) > 50 for r in real)
    monkeypatch.delenv("RPG_AUDIT_TRACE_MAX", raising=False)
    rows = [dict(real[i % len(real)], turn=i + 1, action_ref=f"a{i:014d}") for i in range(200)]
    ring = audit_trace.normalize_audit_trace(rows)
    assert len(ring) == 200
    assert len(json.dumps(ring, ensure_ascii=False)) <= 400 * 1024
    # codificação sem perda: expandir devolve exatamente as refs e o timing originais
    back = audit_trace.expand_trace(ring)
    for orig, got in zip(rows, back):
        assert list(audit_trace.iter_context_refs(orig)) == list(audit_trace.iter_context_refs(got))
        assert got["timing"] == orig["timing"]
    assert audit_trace.normalize_audit_trace(ring) == ring  # idempotente
    # corte do ring re-materializa a nova 1ª linha (sem depender da linha descartada)
    monkeypatch.setenv("RPG_AUDIT_TRACE_MAX", "5")
    tail = audit_trace.normalize_audit_trace(ring)
    assert len(tail) == 5 and "ids_prev" not in json.dumps(tail[0])
    assert list(audit_trace.iter_context_refs(audit_trace.expand_trace(tail)[0])) == list(
        audit_trace.iter_context_refs(back[-5])
    )


def test_context_refs_have_no_text(played):
    _gid, state = played
    refs = [
        ref
        for row in audit_trace.expand_trace(state["audit_trace"])
        for ref in audit_trace.iter_context_refs(row)
    ]
    assert refs, "turnos reais devem registrar refs do ContextPack"
    for ref in refs:
        assert set(ref) <= REF_KEYS
        for value in ref.values():
            assert value is None or len(str(value)) <= 80


def test_context_pack_exposes_refs_without_text():
    from services.context_builder import ContextBudget, ScoredFact, assemble_pack

    pack = assemble_pack(
        [ScoredFact("O porto arde.", 1.0, "current_state", "ev1")],
        ContextBudget(),
        lore_text="Lore canônico longo.",
        memory_text="[RELATO | npc_claim | turno 2] Magda diz algo.",
    )
    sections = {ref["section"]: ref for ref in pack.context_refs}
    assert set(sections) == {"current_state", "lore", "session_memory"}
    assert sections["session_memory"]["source_kind"] == "npc_claim"
    assert sections["session_memory"]["certainty"] == "reported"
    assert sections["current_state"]["knowledge_kind"] == "fact"
    assert all("text" not in ref for ref in pack.context_refs)


def test_save_v8_loads_with_empty_audit_trace(played):
    _gid, state = played
    from services.game_serialization import serialize_game_state

    raw = serialize_game_state(state)
    assert raw["schema_version"] == 8 == persistence.SCHEMA_VERSION
    legacy = json.loads(json.dumps(raw))
    legacy.pop("audit_trace")
    loaded = persistence._raw_to_state(legacy)
    assert loaded["audit_trace"] == []
    again = persistence._raw_to_state(json.loads(json.dumps(raw)))
    assert again["audit_trace"] == state["audit_trace"]


def test_trace_written_once_per_action_id(client):
    gid = _new_game(client)
    action = str(uuid.uuid4())
    for _ in range(2):
        r = client.post(
            "/game/action",
            json={"input_text": "Descanso um pouco.", "game_id": gid, "action_id": action},
        )
        assert r.status_code == 200
    state = persistence.load_game_state(persistence.save_path(gid))
    assert len(state["audit_trace"]) == 1
    same = {"game_id": "g", "world": {"turn_count": 1}}
    audit_trace.record_turn_trace(same, previous_state={}, action_id="x", context_refs=[])
    audit_trace.record_turn_trace(same, previous_state={}, action_id="x", context_refs=[])
    assert len(same["audit_trace"]) == 1


def test_trace_timing_uses_spec200_field_names():
    from observability.latency import FakeClock, TurnPhase, TurnTimeline

    clock = FakeClock()
    timeline = TurnTimeline(clock, transport="stream")
    timeline.mark("accepted")
    with timeline.phase(TurnPhase.ROUTER):
        clock.advance(0.3)
    with timeline.phase(TurnPhase.PERSISTENCE):
        snap = audit_trace.timing_snapshot(timeline)
    assert list(snap) == [
        "transport",
        "execution_mode",
        "ack_server_ms",
        "ttfmc_server_ms",
        "ttlt_server_ms",
        "phase_ms",
        "lock_wait_ms",
        "llm_attempts",
        "llm_fallbacks",
        "llm_failed_attempts",
        "providers_used",
        "cost_basis",
        "input_size",
    ]
    assert set(snap["phase_ms"]) == {
        "router",
        "context",
        "narrator",
        "archivist",
        "persistence",
        "other",
    }
    assert snap["phase_ms"]["persistence"] is None and snap["phase_ms"]["router"] == 300
    assert snap["transport"] == "stream"
    assert audit_trace.timing_snapshot(None) is None


def _crafted_state():
    return {
        "game_id": str(uuid.uuid4()),
        "world": {"turn_count": 2, "current_location_id": "nova_arcadia"},
        "player": {"gold": 10},
        "campaign_plan": {
            "arc_title": "Arco",
            "climax": "O pacto é revelado",
            "beats": [{"description": "Beat secreto", "status": "pending"}],
        },
        "presentation_history": [
            {"id": "p1", "turn": 1, "epoch": 0, "role": "player", "text": "oi"},
            {
                "id": "n1",
                "turn": 1,
                "epoch": 0,
                "role": "narrator",
                "text": "Olá.",
                "speaker_kind": "npc",
                "speaker_id": "npc_magda",
            },
            {"id": "p2", "turn": 2, "epoch": 0, "role": "player", "text": "e aí"},
            {"id": "n2", "turn": 2, "epoch": 0, "role": "narrator", "text": "Silêncio."},
        ],
        "audit_trace": [
            {
                "turn": 1,
                "epoch": 0,
                "action_ref": "aaaa",
                "speaker": "npc:npc_magda",
                "context_refs": [
                    {
                        "source_id": "memory_content_x",
                        "section": "session_memory",
                        "visibility": "public",
                        "purpose": "npc",
                        "knowledge_kind": "report",
                        "certainty": "reported",
                        "source_kind": "npc_claim",
                    },
                    {
                        "source_id": "lore_content_y",
                        "section": "lore",
                        "visibility": "hidden",
                        "purpose": "story",
                        "knowledge_kind": "fact",
                        "certainty": "confirmed",
                        "source_kind": "canonical_event",
                    },
                    {
                        "source_id": "plan_z",
                        "section": "lore",
                        "visibility": "public",
                        "purpose": "story",
                        "knowledge_kind": "invented",
                        "certainty": "sure",
                        "source_kind": "llm",
                    },
                ],
                "delta": {"player.gold": {"before": 5, "after": 10}},
                "errors": [
                    {
                        "code": "structured_output_invalid",
                        "node": None,
                        "tier": "fast",
                        "recovered": True,
                        "fallback": "provider_next",
                        "error_class": None,
                        "message": "Traceback com segredo",
                    }
                ],
                "timing": None,
                "timing_partial": False,
                "revealed_secret_ids": [],
                "reveal_criteria_diverge": False,
            }
        ],
    }


def _lines(files, name):
    return [json.loads(line) for line in files[name].decode().splitlines() if line]


def test_knowledge_visibility_values_match_spec206():
    bundle = build_audit_bundle(_source(_crafted_state()), generated_at=GEN_AT)
    rows = _lines(bundle.files, "knowledge_visibility.jsonl")
    first = rows[0]
    assert first["speaker"] == "npc:npc_magda"
    public, private, invalid = first["items"]
    assert (public["knowledge_kind"], public["certainty"], public["source_kind"]) == (
        "report",
        "reported",
        "npc_claim",
    )
    assert private["visibility"] == "hidden"
    assert private["knowledge_kind"] is None and private["certainty"] is None
    assert private["source_kind"] is None and private["private_label"] == PRIVATE_LABEL
    assert invalid["knowledge_kind"] is None  # fora do enum nunca sai
    assert "private_label" not in public
    assert rows[1] == {
        "turn_ref": "t:0:2",
        "speaker": "narrator",
        "items": None,
        "context_refs_unavailable": True,
    }


def test_revealed_ids_use_accepted_secret_ids():
    state = {
        "player": {"known_secrets": ["pacto_valerius"]},
        "narrative_summary": "Magda contou do pacto com Valerius.",
        "event_log": [],
    }
    status = audit_trace.reveal_status(state)
    assert status["revealed_secret_ids"] == []
    assert status["reveal_criteria_diverge"] is True
    state["event_log"] = [
        {"type": "secret_revealed", "target_id": "pacto_valerius", "event_id": "e1"}
    ]
    status = audit_trace.reveal_status(state)
    assert "pacto_valerius" in status["revealed_secret_ids"]


# --------------------------------------------------------------------------- #
# Etapa 3 — builder/ZIP
# --------------------------------------------------------------------------- #
def test_zip_has_required_files(played):
    _gid, state = played
    data = bundle_zip(_source(state), generated_at=GEN_AT)
    files = _zip_files(data)
    for name in FIXED_FILES:
        assert name in files
    assert any(n.startswith("sessions/") for n in files)
    assert len([n for n in files if not n.startswith("sessions/")]) + 1 >= 10
    assert verify_audit_zip(data) == []


def test_manifest_hashes_match(played):
    _gid, state = played
    files = _zip_files(bundle_zip(_source(state), generated_at=GEN_AT))
    manifest = json.loads(files["manifest.json"])
    assert manifest["format"] == "valoria-audit-export-v1"
    assert manifest["save_schema_version"] == 8
    assert str(state["game_id"]) not in files["manifest.json"].decode()
    for name, digest in manifest["files"].items():
        assert hashlib.sha256(files[name]).hexdigest() == digest
    tampered = dict(files)
    tampered["errors.jsonl"] = b'{"x":1}\n'
    assert "hash:errors.jsonl" in verify_audit_zip(write_zip(tampered))


def test_same_input_same_bytes(played):
    _gid, state = played
    assert bundle_zip(_source(state), generated_at=GEN_AT) == bundle_zip(
        _source(state), generated_at=GEN_AT
    )


def test_sessions_ordered_by_sequence():
    state = _crafted_state()
    turns = [
        {
            "operation_id": str(uuid.uuid4()),
            "sequence": 9,
            "presentation_entry_id": "n1",
            "route": "npc_actor",
            "latency_ms": 10,
            "llm_cost_usd": None,
        },
        {
            "operation_id": str(uuid.uuid4()),
            "sequence": 4,
            "presentation_entry_id": "n2",
            "route": "storyteller",
            "latency_ms": 20,
            "llm_cost_usd": None,
        },
    ]
    cost = {turns[0]["operation_id"]: "0.00002", turns[1]["operation_id"]: "0.00001"}
    files = build_audit_bundle(
        _source(state, turns=turns, usage_cost=cost), generated_at=GEN_AT
    ).files
    rows = _lines(files, "sessions/0.jsonl")
    assert [r["sequence"] for r in rows] == [4, 9]
    assert rows[0]["cost_usd"] == "0.00001" and rows[1]["cost_usd"] == "0.00002"
    assert all(turns[0]["operation_id"] not in f.decode(errors="ignore") for f in files.values())


def test_private_items_only_with_label(played):
    _gid, state = played
    state = dict(state)
    state["campaign_plan"] = {
        "arc_title": "A",
        "climax": "pacto com valerius",
        "beats": [{"description": "segredo", "status": "pending"}],
    }
    files = build_audit_bundle(_source(state), generated_at=GEN_AT).files
    final = json.loads(files["state/final_snapshot.json"])
    assert final["private_reference"]["label"] == PRIVATE_LABEL
    assert final["private_reference"]["climax"] == "pacto com valerius"
    for name, data in files.items():
        if name in ("state/final_snapshot.json",) or name.endswith(".md"):
            continue
        text = data.decode()
        assert "pacto com valerius" not in text, name
        if '"visibility":"hidden"' in text or '"visibility":"engine"' in text:
            assert PRIVATE_LABEL in text


def test_truncation_marks_manifest():
    state = _crafted_state()
    bundle = build_audit_bundle(
        _source(state), limits=AuditLimits(max_turns=1), generated_at=GEN_AT
    )
    assert bundle.manifest["truncated"] is True
    assert bundle.manifest["truncation_reason"] == "max_turns"
    assert bundle.manifest["turn_count"] == 1
    assert bundle.manifest["range"]["first_turn_ref"] == "t:0:2"
    full = len(write_zip(build_audit_bundle(_source(state), generated_at=GEN_AT).files))
    small = build_audit_bundle(
        _source(state), limits=AuditLimits(max_bytes=full - 1), generated_at=GEN_AT
    )
    assert small.manifest["truncated"] is True
    assert small.manifest["truncation_reason"] == "max_bytes"
    assert len(write_zip(small.files)) <= full - 1
    assert small.manifest["turn_count"] < 2


def test_zip_pii_scan_clean(played):
    _gid, state = played
    owner = uuid.uuid4()
    email = "dono.conta@example.net"
    state = json.loads(json.dumps(state, default=str))
    state["presentation_history"].append(
        {
            "id": "nx",
            "turn": 99,
            "epoch": 0,
            "role": "narrator",
            "text": f"Conta {owner} de {email} via 192.168.0.10 Bearer tok.en.x "
            "https://x.supabase.co/storage/v1/object/sign/a?token=t",
        }
    )
    source = _source(state, owner_values={str(owner), email})
    data = bundle_zip(source, generated_at=GEN_AT)
    assert verify_audit_zip(data, owner_values={str(owner), email}) == []
    blob = b"".join(_zip_files(data).values()).decode(errors="ignore")
    for needle in (
        str(owner),
        owner.hex,
        email,
        "jogador.real@example.com",
        "98765-4321",
        "192.168.0.10",
        "token=t",
    ):
        assert needle not in blob


def test_redaction_failure_fails_closed(monkeypatch):
    import services.audit_export as ae
    from services.audit_redaction import AuditRedactionError

    monkeypatch.setattr(ae, "scan_pii", lambda *_a, **_k: ["email"])
    with pytest.raises(AuditRedactionError):
        build_audit_bundle(_source(_crafted_state()), generated_at=GEN_AT)


def test_errors_have_no_raw_exception_message():
    files = build_audit_bundle(_source(_crafted_state()), generated_at=GEN_AT).files
    rows = _lines(files, "errors.jsonl")
    assert rows and rows[0]["code"] == "structured_output_invalid"
    assert "message" not in rows[0] and "Traceback" not in files["errors.jsonl"].decode()
    timing = _lines(files, "timings.jsonl")[0]
    assert timing["timing"] is None and timing["client_timing"] == "not_exported"


def test_no_llm_called(played, monkeypatch):
    _gid, state = played
    import llm_setup
    import rag

    def boom(*_a, **_k):
        raise AssertionError("export não pode chamar LLM/embedding")

    monkeypatch.setattr(llm_setup, "get_llm", boom)
    monkeypatch.setattr(rag, "query_rag", boom, raising=False)
    monkeypatch.setattr(rag, "get_embeddings", boom, raising=False)
    calls = []
    llm_setup.set_llm_telemetry_hook(lambda *a: calls.append(a))
    try:
        bundle_zip(_source(state), generated_at=GEN_AT)
    finally:
        llm_setup.set_llm_telemetry_hook(None)
    assert calls == []


def test_audit_docs_runtime_copy_matches_repo():
    root = Path(__file__).resolve().parent.parent
    for name in ("AUDITOR_PROMPT.md", "README_SCHEMA.md"):
        assert (root / "docs/auditoria" / name).read_bytes() == (
            root / "data/auditoria" / name
        ).read_bytes()


def test_readme_schema_documents_real_fields(played):
    _gid, state = played
    files = build_audit_bundle(_source(state), generated_at=GEN_AT).files
    readme = files["README_SCHEMA.md"].decode()
    keys = set()
    for name in ("sessions/0.jsonl", "knowledge_visibility.jsonl", "timings.jsonl"):
        for row in _lines(files, name) if name in files else []:
            keys |= set(row)
    keys |= set(json.loads(files["manifest.json"]))
    for key in keys:
        assert f"`{key}`" in readme, key
    prompt = files["AUDITOR_PROMPT.md"].decode()
    for key in (
        "severity",
        "category",
        "session_ref",
        "turn_ref",
        "expected",
        "observed",
        "evidence_refs",
        "hypothesis",
        "confidence",
        "eval_proposal",
        "cluster_id",
    ):
        assert f'"{key}"' in prompt


def test_legacy_profile_404(client):
    r = client.post(f"/game/{uuid.uuid4()}/audit-export")
    assert r.status_code == 404
    assert r.json()["detail"] == "audit_export_unavailable_in_legacy"


def test_cli_exports_local_save(played, tmp_path):
    gid, state = played
    from scripts.export_game_audit import main

    save = Path(persistence.save_path(gid))
    out = tmp_path / "audit.zip"
    assert main(["--save", str(save), "--output", str(out), "--generated-at", GEN_AT]) == 0
    assert verify_audit_zip(out.read_bytes()) == []


def test_adversarial_player_text_and_raw_game_id_never_in_zip():
    """Revisão Astra: PII BR/chaves no texto do jogador e game_id cru (hex) somem do ZIP."""
    state = _crafted_state()
    gid = uuid.UUID(state["game_id"])
    state["presentation_history"][0]["text"] = (
        f"cpf 123.456.789-09, zap 11987654321, AKIAIOSFODNN7EXAMPLE, fe80::1ff:fe23:4567:890a, "
        f"senha: hunter22, ghp_abcdefghijklmnopqrstuvwxyz0123456789, jogo {gid.hex}"
    )
    data = bundle_zip(_source(state), generated_at=GEN_AT)
    assert verify_audit_zip(data) == []
    blob = b"".join(_zip_files(data).values()).decode(errors="ignore")
    for needle in (
        "123.456.789-09",
        "11987654321",
        "AKIAIOSFODNN7",
        "fe80::1ff",
        "hunter22",
        "ghp_abcdef",
        gid.hex,
        str(gid),
    ):
        assert needle not in blob, needle
