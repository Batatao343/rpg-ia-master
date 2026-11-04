"""SPEC-361 Etapa 5 — integração no combate, no bestiário e no brief de arte (R18, R28-R30)."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

import agents.bestiary as bst
import agents.combat as combat
from services import creature_gen as cg
from tests.test_encounter_identity_repro import _install_llm, _scan, _start_state

ZHUR = {
    "current_location": "Deserto de Zhur",
    "current_location_id": "deserto_zhur",
    "turn_count": 40,
    "danger_level": 1,
    "visited": ["deserto_zhur"],
}


@pytest.fixture
def gen_on(monkeypatch):
    monkeypatch.setenv("RPG_CREATURE_GEN", "on")
    monkeypatch.setenv("RPG_SHARED_POOL", "off")
    token = cg.CONTADOR_ATUALIZADO.set(None)
    yield
    cg.CONTADOR_ATUALIZADO.reset(token)


def _overlay() -> dict:
    from infrastructure.runtime import get_runtime

    return get_runtime().runtime_catalog.list("bestiary_template", owner_id=None, game_id=None)


def test_flag_legacy_identico(monkeypatch):
    monkeypatch.delenv("RPG_CREATURE_GEN", raising=False)
    assert cg.mode() == "legacy"

    def boom(*a, **k):
        raise AssertionError("legacy não passa pelo gerador da SPEC-361")

    monkeypatch.setattr(cg, "gerar", boom)
    t = bst.generate_new_enemy("Verme das Cinzas Profundas", "teste")
    assert t["name"] and "geracao" not in t and "ficha" not in t


def test_grounded_aceita_geracao_pedido(gen_on, monkeypatch):
    def fake(name, context="", **kw):
        assert "state" in kw  # R30: o estado vai ao gerador
        return {
            "id": "mon_coro_de_quitina_rt_abcdef",
            "name": "Coro de Quitina",
            "categoria": "lacaio",
            "geracao": {"caminho": "nova", "nome": name},
        }

    monkeypatch.setattr(combat, "generate_new_enemy", fake)
    t = combat._grounded_template("Lacaio mente-colmeia", "ctx", 1, {"world": ZHUR})
    assert t["name"] == "Coro de Quitina"
    # sem a marca da geração, a trava de identidade continua valendo
    monkeypatch.setattr(
        combat,
        "generate_new_enemy",
        lambda name, context="", **kw: {"id": "x", "name": "Outra Coisa", "categoria": "lacaio"},
    )
    t2 = combat._grounded_template("Lacaio mente-colmeia", "ctx", 1, {"world": ZHUR})
    assert t2["name"] != "Outra Coisa"


def test_spawn_colmeia_zhur_variante(gen_on, monkeypatch):
    hint = "lacaio mente-colmeia"
    _install_llm(monkeypatch, scan=_scan(("Lacaio mente-colmeia", 1)))
    # o piso do grupo vale no spawn; o orçamento do encontro (SPEC-203/287) segue com a última
    # palavra, então o teste usa um perigo em que três lacaios cabem.
    state = _start_state(hint=hint, world={**ZHUR, "danger_level": 3})
    enemies, _ = combat._spawn_v4_enemies(state["messages"], hint, state, {})
    variantes = [e for e in enemies if e.get("variant_of") == "mon_saltador_de_palafita"]
    assert len(variantes) >= 3
    assert all(e["name"].startswith("Saltador de Palafita da Mente Única") for e in variantes)
    assert variantes[0]["tactical_profile"]["padrao"] == ["reforco_proprio", "ataque_multiplo"]
    # a variante fica no overlay do dono, nunca no pool
    assert "mon_saltador_de_palafita__v_mente_unica" in _overlay()


ODRES = "algo que vive dentro dos odres de água estragada"


def test_spawn_substituta_agenda_e_job_salva_overlay(gen_on):
    from services import creature_gen_jobs as cgj

    state = {"game_id": "g-int", "world": dict(ZHUR)}
    t = bst.generate_new_enemy("Bebedor de Odres", ODRES, state=state)
    # decisão do dono: na hora, a existente mais próxima; a nova fica agendada
    assert t["geracao"]["caminho"] == "substituta" and t["geracao"]["agendada"] is True
    assert "ficha" not in t and t["id"] in __import__("gamedata").BESTIARY
    assert cg.CONTADOR_ATUALIZADO.get() == (1, 40)  # P1-2: o teto conta a tentativa
    assert cgj.drenar_local(5) == 1
    geradas = [v for v in _overlay().values() if (v.get("geracao") or {}).get("caminho") == "nova"]
    assert len(geradas) == 1
    saved = geradas[0]
    assert saved["ficha"]["revisao"] == "pendente" and saved["appearance"]
    assert saved["geracao"]["estado"] == "local" and saved["geracao"]["pedido"] == ODRES
    # o próximo encontro com o mesmo pedido usa a ficha nova (sem agendar outra)
    t2 = bst.generate_new_enemy("Bebedor de Odres", ODRES, state={**state, "world": dict(ZHUR)})
    assert t2["id"] == saved["id"] and "agendada" not in t2["geracao"]
    assert cgj.drenar_local(5) == 0


def test_turno_nao_chama_llm_de_geracao(gen_on, monkeypatch):
    """O turno com spawn desconhecido não espera o LLM de geração: zero chamada de ficha."""
    import time

    import llm_setup

    chamadas: list[str] = []

    class _Lento:
        def with_structured_output(self, schema, **_k):
            class _B:
                def invoke(self, messages):
                    chamadas.append(schema.__name__)
                    if schema.__name__ in ("FichaCriaturaGerada", "EnemySchema"):
                        time.sleep(0.4)  # o LLM de geração é lento
                    from mock_llm import MockLLM

                    return MockLLM().with_structured_output(schema).invoke(messages)

            return _B()

    monkeypatch.setattr(llm_setup, "get_llm", lambda *a, **k: _Lento())
    monkeypatch.setattr(bst, "get_llm", lambda *a, **k: _Lento())
    state = {"game_id": "g-lat", "world": dict(ZHUR)}
    t0 = time.perf_counter()
    bst.generate_new_enemy("Bebedor de Odres", ODRES, state=state)
    on_s = time.perf_counter() - t0
    assert "FichaCriaturaGerada" not in chamadas
    monkeypatch.setenv("RPG_CREATURE_GEN", "legacy")
    t0 = time.perf_counter()
    bst.generate_new_enemy("Bebedor de Odres Outro", ODRES)
    legacy_s = time.perf_counter() - t0
    assert "EnemySchema" in chamadas
    assert on_s < legacy_s  # o caminho novo não é mais lento que o legado


def test_teto_conta_tentativa_que_falhou(gen_on, monkeypatch):
    """P1-2: geração que caiu em fallback no job ainda consome o intervalo do teto."""
    from services import creature_gen_jobs as cgj

    monkeypatch.setattr(cg, "gerar_nova", lambda *a, **k: (None, {"codigos": ["PRAZO"]}))
    state = {"game_id": "g-teto", "world": dict(ZHUR)}
    bst.generate_new_enemy("Bebedor de Odres", ODRES, state=state)
    assert cg.CONTADOR_ATUALIZADO.get() == (1, 40)
    assert cgj.drenar_local(5) == 1  # o job roda e falha: fica a substituta
    world = {**ZHUR, "turn_count": 45, "creature_gen": {"novas": 1, "ultimo_turno": 40}}
    cg.CONTADOR_ATUALIZADO.set(None)
    t = bst.generate_new_enemy(
        "Roedor de Cântaro", "um roedor de cântaro", state={"game_id": "g-teto", "world": world}
    )
    assert t["geracao"]["caminho"] == "fallback" and "agendada" not in t["geracao"]
    assert cg.CONTADOR_ATUALIZADO.get() is None
    assert cgj.drenar_local(5) == 0


def test_contador_vai_ao_estado(gen_on, monkeypatch):
    def fake_node(state):
        cg.CONTADOR_ATUALIZADO.set((2, 41))
        return {"messages": [AIMessage(content="x")]}

    monkeypatch.setattr(combat, "_combat_node", fake_node)
    out = combat.combat_node({"world": dict(ZHUR)})
    assert out["world"]["creature_gen"] == {"novas": 2, "ultimo_turno": 41}
    assert out["world"]["current_location_id"] == "deserto_zhur"
    assert cg.CONTADOR_ATUALIZADO.get() is None


def test_art_brief_criatura_gerada(gen_on):
    from services import creature_gen_jobs as cgj
    from services.art_brief import build_creature_art_brief

    state = {"game_id": "g-art", "world": dict(ZHUR)}
    bst.generate_new_enemy("Bebedor de Odres", ODRES, state=state)
    cgj.drenar_local(1)
    t = bst.generate_new_enemy("Bebedor de Odres", ODRES, state=state)
    assert t["geracao"]["caminho"] == "existente" and "ficha" in t  # a ficha gerada pelo job
    inst = combat._instances(t, 1, {}, None)[0]
    brief = build_creature_art_brief(inst, important=False)
    assert brief["player_description"] and brief["player_description"] in t["appearance"]
    var = combat._grounded_template(
        "lacaio mente-colmeia", "lacaio mente-colmeia", 1, {"world": dict(ZHUR)}
    )
    vb = build_creature_art_brief(combat._instances(var, 1, {}, None)[0], important=False)
    assert "mesma pose" in vb["player_description"]


def test_save_antigo_carrega(gen_on):
    """Inimigo e overlay do gerador antigo (EnemySchema) seguem válidos com a flag `on`."""
    import persistence
    from services import conflict_orchestrator as orch

    antigo = bst.materialize_enemy_concept(
        {"name": "Verme das Cinzas", "categoria": "padrao", "arquetipo": "bruto"}
    )
    bst.save_enemy(dict(antigo))
    inst = orch.ensure_combat_sheet({**antigo, "id": "enemy_verme_das_cinzas_1"})
    assert inst["max_vitalidade"] >= 1
    state = _start_state(hint="Verme das Cinzas", enemies=[inst], world=dict(ZHUR))
    state["game_id"] = "36136136-1361-4361-8361-361361361361"
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(
        persistence.save_path("36136136-1361-4361-8361-361361361361")
    )
    assert loaded["enemies"][0]["name"] == "Verme das Cinzas"
    assert "creature_gen" not in (loaded.get("world") or {})
    p = cg.PedidoCriatura.from_spawn(
        "x", "", state=loaded, encounter_level=1, location_id="deserto_zhur"
    )
    assert p.contador == (0, 0)
    # o overlay antigo (sem ficha) é achado de novo e não volta a gerar
    t = bst.generate_new_enemy("Verme das Cinzas", "", state=loaded)
    assert t["name"] == "Verme das Cinzas" and "ficha" not in t


def test_variante_telegrafa_antes_da_assinatura(gen_on, monkeypatch):
    """§6 passo 2 (offline): com baralhos e intenção ligados, o telegrafo da variante sai uma
    rodada antes da assinatura."""
    from services import enemy_decks

    monkeypatch.setenv("RPG_ENEMY_DECKS", "on")
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    var = combat._grounded_template(
        "lacaio mente-colmeia", "lacaio mente-colmeia", 1, {"world": dict(ZHUR)}
    )
    inst = combat._instances(var, 3, {}, 7)[0]
    sig = enemy_decks.assinatura_of(inst)
    assert sig and "congela no meio do passo" in sig["telegrafo"]
    rodadas = [r for r in range(1, 8) if enemy_decks.prenuncio(inst, r)]
    assert rodadas, "o telegrafo nunca apareceu"
    texto = enemy_decks.prenuncio(inst, rodadas[0])
    assert texto.startswith(inst["name"]) and "congela" in texto
    assert enemy_decks.plan(inst, rodadas[0] + 1)["assinatura"] == sig["carta"]


def test_trava_identidade_nome_sanitizado(gen_on, monkeypatch):
    """P2-4: nome que o sanitizador altera não derruba a trava de identidade."""
    from services import creature_gen_jobs as cgj

    monkeypatch.setattr(cgj, "agendar", lambda *a, **k: True)
    nome = "Coisa <dos> Odres!!"
    t = combat._grounded_template(nome, ODRES, 1, {"game_id": "g-san", "world": dict(ZHUR)})
    assert t["geracao"]["caminho"] == "substituta"  # não virou o genérico da trava


def test_round_trip_creature_gen_preenchido(gen_on):
    """P2-5: o writer novo (`world.creature_gen`) sobrevive a save/load."""
    import persistence

    gid = "36136136-1361-4361-8361-361361361362"
    state = _start_state(hint="x", world={**ZHUR, "creature_gen": {"novas": 2, "ultimo_turno": 41}})
    state["game_id"] = gid
    assert persistence.save_game_state(state)
    loaded = persistence.load_game_state(persistence.save_path(gid))
    assert loaded["world"]["creature_gen"] == {"novas": 2, "ultimo_turno": 41}
    p = cg.PedidoCriatura.from_spawn("x", "", state=loaded, encounter_level=1, location_id="")
    assert p.contador == (2, 41)


def test_gatilho_so_da_acao_do_jogador(gen_on):
    """P2-6: "veterano" na narração (motivo de trama) não vira variante; na fala do jogador vira."""
    from agents.bestiary import load_bestiary

    base = dict(
        regiao="deserto_zhur",
        location_id="deserto_zhur",
        categoria_sugerida=None,
        encounter_level=1,
        game_id="g-gat",
        turn=40,
    )
    narrado = cg.PedidoCriatura(
        pedido="bicho da duna",
        motivo_trama="Última cena: …o veterano da caravana conta do covil e do ninho.",
        **base,
    )
    assert cg.decidir_caminho(narrado, bestiary=load_bestiary()).caminho != "variante"
    falado = cg.PedidoCriatura(
        pedido="bicho da duna",
        motivo_trama="",
        player_inputs=("ataco o bicho veterano cheio de cicatrizes",),
        **base,
    )
    assert cg.texto_do_jogador(falado).endswith("cicatrizes")
    assert "veterano" not in cg.texto_do_jogador(narrado)


def test_drenagem_fora_do_lock_do_jogo(gen_on, monkeypatch):
    """R2-P1-2: a geração (lenta) roda numa thread daemon fora do lock; a próxima ação do mesmo
    jogo pega o lock na hora. `_execute_action` não drena mais nada sob o lock."""
    import inspect
    import time

    import api
    import api_core
    import routes.turn
    from services import creature_gen_jobs as cgj

    rodou = []

    def lento(payload):
        time.sleep(0.5)
        rodou.append(payload["pedido"])
        return {"status": "fallback"}

    monkeypatch.setattr(cgj, "handler", lento)
    state = {"game_id": "g-lock", "world": dict(ZHUR)}
    bst.generate_new_enemy("Bebedor de Odres", ODRES, state=state)
    t0 = time.perf_counter()
    api._drain_creature_gen()
    assert time.perf_counter() - t0 < 0.2  # devolve na hora
    lock = api_core._game_lock("g-lock")
    assert lock.acquire(timeout=0.1)  # a próxima ação do jogo não espera o job
    lock.release()
    cgj.aguardar_drenagem(5)
    assert rodou == [ODRES]
    assert "creature_gen" not in inspect.getsource(routes.turn._execute_action)


def test_payload_sem_fala_crua_do_jogador():
    """R2-P2-4: o payload do job guarda hashes, nunca as falas do jogador."""
    import json

    from services import creature_gen_jobs as cgj

    p = cg.PedidoCriatura(
        pedido="bicho do poço",
        regiao="deserto_zhur",
        location_id="deserto_zhur",
        categoria_sugerida=None,
        motivo_trama="",
        encounter_level=1,
        game_id="g",
        turn=1,
        player_inputs=("meu email é fulano@exemplo.com e ataco o Rastejador Pardo",),
    )
    payload = cgj.payload_de(p)
    texto = json.dumps(payload, ensure_ascii=False)
    assert "fulano" not in texto and "exemplo" not in texto and "Rastejador" not in texto
    assert cgj.nome_digitado("Rastejador de Cinza", payload["player_token_hashes"])
    assert not cgj.nome_digitado("Coro de Quitina", payload["player_token_hashes"])
    assert cgj.pedido_de(payload).player_inputs == ()


def test_build_handlers_registra_creature_gen(monkeypatch):
    """R2-P2-3: o worker durável (perfil DB) conhece o kind `creature_gen`."""
    import types

    from infrastructure.pgvector_memory import PgVectorMemoryStore
    from services import creature_gen_jobs as cgj
    from workers import run_worker

    fake = types.SimpleNamespace(
        resources=[object()],
        memory_store=object.__new__(PgVectorMemoryStore),
        blob_store=None,
        shared_blob_store=None,
    )
    monkeypatch.setattr(run_worker, "get_runtime", lambda: fake)
    handlers = run_worker.build_handlers()
    assert "creature_gen" in handlers
    chamado = []
    monkeypatch.setattr(cgj, "handler", lambda payload: chamado.append(payload) or {"ok": 1})
    assert handlers["creature_gen"]({"pedido": "x"}) == {"ok": 1} and chamado
