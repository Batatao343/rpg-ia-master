import json
import logging
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image, ImageOps

import workers.dynamic_art_jobs as art_jobs
from infrastructure.file_blob import FileBlobStore
from infrastructure.ports import GeneratedImage
from services.art_brief import (
    build_epic_art_brief,
    build_npc_art_brief,
    build_player_art_brief,
    render_image_prompt,
)
from tests.fakes.fake_image_generator import FakeImageGenerator
from workers.dynamic_art_jobs import generate_dynamic_art_job


def test_worker_fake_gera_duas_variantes_privadas_sem_provider_real(tmp_path):
    generator = FakeImageGenerator()
    owner, game, asset = uuid4(), uuid4(), uuid4()
    generation = {
        "private_brief": {
            "subject": "Iria",
            "canon": ["Valoria"],
            "player_description": "adulta",
            "composition": ["natural spine"],
            "exclusions": ["no text"],
            "reference_asset_ids": [],
            "profile_version": "v1",
            "size": "1024x1536",
        },
        "model": "gpt-image-2-2026-04-21",
        "subject_type": "player",
        "subject_id": "player",
        "trigger_kind": "player_portrait",
    }
    result = generate_dynamic_art_job(
        generator=generator,
        blob_store=FileBlobStore(tmp_path),
        generation=generation,
        owner_id=owner,
        game_id=game,
        asset_id=asset,
        admission=lambda: generation,
    )
    assert generator.calls == 1 and result["status"] == "ready"
    assert len(result["variants"]) == 2
    assert all((tmp_path / row["key"]).exists() for row in result["variants"])


def test_usage_is_published_before_image_processing_can_fail(tmp_path, monkeypatch):
    published = []

    def fail_processing(_payload):
        raise RuntimeError("failed after provider response")

    monkeypatch.setattr(art_jobs, "process_image", fail_processing)
    generation = {
        "private_brief": {
            "subject": "Iria",
            "canon": ["Valoria"],
            "player_description": "adulta",
            "composition": ["natural spine"],
            "exclusions": ["no text"],
            "reference_asset_ids": [],
            "profile_version": "v1",
            "size": "1024x1536",
        },
        "model": "gpt-image-2-2026-04-21",
        "subject_type": "player",
        "subject_id": "player",
        "trigger_kind": "player_portrait",
    }
    with pytest.raises(RuntimeError, match="failed after provider"):
        generate_dynamic_art_job(
            generator=FakeImageGenerator(),
            blob_store=FileBlobStore(tmp_path),
            generation=generation,
            owner_id=uuid4(),
            game_id=uuid4(),
            asset_id=uuid4(),
            admission=lambda: generation,
            usage_sink=lambda model, usage: published.append((model, usage)),
        )
    assert published == [
        (
            "gpt-image-2-2026-04-21",
            {
                "image_units": 1,
                "provider_cost_usd": "0",
            },
        )
    ]


# --------------------------------------------------------------------------- #
# SPEC-326: referências, preâmbulos, guard anti-cópia
# --------------------------------------------------------------------------- #
class RecordingGenerator:
    """Registra o ImageGenerationInput; ``reply`` decide os bytes devolvidos."""

    def __init__(self, reply=None):
        self.requests = []
        self.reply = reply

    def generate(self, request):
        self.requests.append(request)
        if self.reply is not None:
            payload = self.reply(request)
        else:
            out = BytesIO()
            Image.new("RGB", (320, 480), (42, 23, 29)).save(out, "PNG")
            payload = out.getvalue()
        return GeneratedImage(payload, "image/png", "rec", request.model, {"images": 1})


def _run(brief, tmp_path, generator=None, *, portrait_key=None, subject="player"):
    generator = generator or RecordingGenerator()
    generation = {
        "private_brief": brief,
        "model": "gpt-image-2-2026-04-21",
        "subject_type": subject,
        "subject_id": "player",
        "trigger_kind": "player_portrait",
    }
    result = generate_dynamic_art_job(
        generator=generator,
        blob_store=FileBlobStore(tmp_path),
        generation=generation,
        owner_id=uuid4(),
        game_id=uuid4(),
        asset_id=uuid4(),
        admission=lambda: generation,
        approved_portrait_key=portrait_key,
    )
    return generator, result


def _player_brief(race="Elfo", **extra):
    return build_player_art_brief(
        {"name": "Iria", "race": race, "class_name": "Sangromante", **extra}
    )


def _approved_portrait_key(tmp_path):
    _, result = _run(_player_brief(), tmp_path)
    return next(row["key"] for row in result["variants"] if row["variant"] == "full")


def _epic_state():
    return {
        "player": {"name": "Iria", "race": "Elfo", "class_name": "Sangromante"},
        "world": {"current_location": "Brekmar", "current_location_id": "brekmar"},
        "enemies": [{"name": "Vorr", "type": "boss"}],
    }


def test_worker_envia_ref_da_raca_no_retrato(tmp_path):
    generator, result = _run(_player_brief("Vrel"), tmp_path)
    request = generator.requests[0]
    assert len(request.reference_payloads) == 1
    assert request.reference_payloads[0].startswith(b"\x89PNG")
    assert request.quality == "medium"
    assert "REFERENCE IMAGE 1" in request.prompt and "NEW individual" in request.prompt
    assert result["status"] == "ready"
    npc = build_npc_art_brief({"npcs": {"k": {"name": "Kahen", "race_id": "race_cinzeus"}}}, "k")
    generator, _ = _run(npc, tmp_path)
    assert len(generator.requests[0].reference_payloads) == 1


def test_epico_envia_retrato_aprovado_e_local(tmp_path):
    key = _approved_portrait_key(tmp_path)
    asked = []
    generator, _ = _run(
        build_epic_art_brief(_epic_state(), {}),
        tmp_path,
        portrait_key=lambda: asked.append(1) or key,
        subject="scene",
    )
    request = generator.requests[0]
    assert asked and len(request.reference_payloads) == 2
    assert "SAME person" in request.prompt and "NEW scene" in request.prompt
    assert request.size == "1536x1024"


def test_reformulacao_usa_retrato_aprovado_e_raca(tmp_path):
    key = _approved_portrait_key(tmp_path)
    brief = build_player_art_brief(
        {
            "name": "Iria",
            "race": "Elfo",
            "class_name": "Devoto do Abismo",
            "subclass": "consagrado",
        },
        reformulation=True,
    )
    generator, _ = _run(brief, tmp_path, portrait_key=lambda: key)
    assert len(generator.requests[0].reference_payloads) == 2


def test_aprovado_exige_status_ready_e_sem_retrato_segue_texto(tmp_path):
    """O worker só pede a chave ao repositório, que filtra ``status='ready'`` (rejeitadas ficam fora)."""
    import inspect

    from services.dynamic_art import DynamicArtRepository

    sql = inspect.getsource(DynamicArtRepository.approved_portrait_key)
    assert "g.status='ready'" in sql and "rejected_quality" not in sql
    brief = build_epic_art_brief({"player": {"race": "Elfo"}}, {})
    generator, _ = _run(brief, tmp_path, portrait_key=lambda: None)
    assert generator.requests[0].reference_payloads == ()


def test_max_duas_refs(tmp_path):
    brief = _player_brief()
    brief["reference_asset_ids"] = ["race:race_elfos", "race:race_vrel", "race:race_cinzeus"]
    generator, _ = _run(brief, tmp_path)
    assert len(generator.requests[0].reference_payloads) == 2


def test_ref_ausente_segue_texto_e_loga(tmp_path, caplog):
    brief = _player_brief()
    brief["reference_asset_ids"] = ["race:race_inexistente", "player:approved_portrait"]
    with caplog.at_level(logging.WARNING, logger="rpg.art"):
        generator, result = _run(brief, tmp_path, portrait_key=lambda: "users/x/missing.webp")
    request = generator.requests[0]
    assert request.reference_payloads == () and result["status"] == "ready"
    assert "REFERENCE IMAGE" not in request.prompt  # sem preâmbulo de ref que não existe
    assert caplog.text.count("art.reference_missing") == 2
    assert "race_inexistente" not in caplog.text  # só o tipo, nunca o conteúdo


def test_ref_de_raca_vive_no_pacote_do_worker():
    """Bundle: web/public/** é excluído da Vercel; as refs vêm de data/art_refs."""
    from services.reputation import VALID_RACES

    for rid in VALID_RACES:
        assert (art_jobs.ART_REFS_DIR / "race" / f"{rid}.webp").is_file()
    assert (art_jobs.ART_REFS_DIR / "location" / "brekmar.webp").is_file()
    root = Path(art_jobs.__file__).resolve().parents[1]
    config = json.loads((root / "vercel.json").read_text(encoding="utf-8"))
    excluded = config["functions"]["vercel_app.py"]["excludeFiles"].strip("{}").split(",")
    assert "web/public/**" in excluded
    assert not any(pattern.startswith("data") or pattern == "**" for pattern in excluded)
    ignored = (root / ".vercelignore").read_text(encoding="utf-8").splitlines()
    for line in (row.strip().rstrip("/") for row in ignored):
        assert line not in {"data", "data/art_refs", "*.webp", "data/art_refs/**"}


def test_local_interior_cai_para_a_regiao(tmp_path):
    state = {"player": {"race": "Elfo"}, "world": {"current_location_id": "bk_docas_velhas"}}
    used, payloads = art_jobs.resolve_reference_payloads(
        build_epic_art_brief(state, {}), blob_store=FileBlobStore(tmp_path), generation={}
    )
    assert used == ("location:bk_docas_velhas",) and len(payloads) == 1


def test_preambulo_por_tipo_de_ref(tmp_path):
    generator, _ = _run(_player_brief(), tmp_path)
    canon_prompt = generator.requests[0].prompt
    assert "match technique, palette and racial anatomy" in canon_prompt
    assert "SAME person" not in canon_prompt
    identity = render_image_prompt(_player_brief(), ["player:approved_portrait"])
    assert "SAME person: identical face" in identity and "racial anatomy" not in identity
    assert "NEW scene" in render_image_prompt(_player_brief(), ["location:brekmar"])


def test_similaridade_canonica_sinaliza(tmp_path, caplog):
    copy = RecordingGenerator(reply=lambda request: request.reference_payloads[0])
    with caplog.at_level(logging.WARNING, logger="rpg.art"):
        _, result = _run(_player_brief(), tmp_path, copy)
    assert result["similar_to_canon"] is True and result["canon_min_hamming"] == 0
    assert "art.canon_similarity" in caplog.text

    def inverted(request):
        with Image.open(BytesIO(request.reference_payloads[0])) as source:
            out = BytesIO()
            ImageOps.invert(source.convert("RGB")).save(out, "PNG")
            return out.getvalue()

    _, other = _run(_player_brief(), tmp_path, RecordingGenerator(reply=inverted))
    assert other["similar_to_canon"] is False and other["canon_min_hamming"] > 10


def test_retrato_proprio_fora_do_guard(tmp_path):
    key = _approved_portrait_key(tmp_path)
    copy = RecordingGenerator(reply=lambda request: request.reference_payloads[0])
    brief = build_epic_art_brief({"player": {"race": "Elfo"}}, {})  # só o retrato (sem local)
    _, result = _run(brief, tmp_path, copy, portrait_key=lambda: key, subject="scene")
    assert result["similar_to_canon"] is False and result["canon_min_hamming"] is None


def test_guard_pega_copia_espelhada(tmp_path):
    def mirrored(request):
        with Image.open(BytesIO(request.reference_payloads[0])) as source:
            out = BytesIO()
            ImageOps.mirror(source.convert("RGB")).save(out, "PNG")
            return out.getvalue()

    _, result = _run(_player_brief(), tmp_path, RecordingGenerator(reply=mirrored))
    assert result["similar_to_canon"] is True and result["canon_min_hamming"] < 14
