"""SPEC-368 R13 - cenarios deterministicos (estado montado, SEM LLM) para o smoke real do §6.

Para o JOGO REAL (save/API/UI) use `tests/fixtures/spec368_seed.py::seed_save` (P1-1 da revisão Sol); este módulo prova a situação no motor.

Cada item do §6 da spec tem um construtor `s6_NN_*` que devolve um `Scenario`: o estado/objetos que
colocam o jogo na situacao pedida, as variaveis de ambiente que o smoke precisa e `check()`, que
devolve os problemas encontrados (lista vazia = a situacao foi alcancada). O smoke do coordenador
chama `build_all()`/`get(item)` para chegar a cada cena sem depender de sorte de LLM; os testes
offline (`tests/test_spec368_scenarios.py`) provam que cada cena e alcancavel.

Cenas de combate usam a mesma arena dos sims (`docs/spec285` via `scripts/cards/sim.py`): heroi,
criatura real do bestiario, pilhas do Baralho e `run_round` reais.
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import random
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARDS_ON = {
    "RPG_CARD_DECK": "on",
    "RPG_ENEMY_INTENT": "on",
    "RPG_ENEMY_DECKS": "on",
    "RPG_SCENE_CARDS": "on",
    "RPG_CARD_REWARDS": "on",
}


@contextlib.contextmanager
def env(values: dict[str, str]) -> Iterator[None]:
    old = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@dataclass
class Scenario:
    item: int  # numero do item no §6 da SPEC-368
    spec: str  # specs que o item fecha
    descricao: str
    env: dict[str, str] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    check: Callable[[Scenario], list[str]] = lambda sc: []
    passos: list[str] = field(default_factory=list)  # o que o coordenador faz na cena

    def problems(self) -> list[str]:
        with env(self.env):
            return self.check(self)


# --------------------------------------------------------------------------
# Arena (mesma da sim.py): heroi + criatura + pilhas
# --------------------------------------------------------------------------
_SIM: Any = None


def _sim():
    global _SIM
    if _SIM is None:
        os.environ.setdefault("RPG_FORCE_MOCK", "1")
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        spec = importlib.util.spec_from_file_location(
            "cards_sim_368_scenarios", os.path.join(ROOT, "scripts", "cards", "sim.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _SIM = mod
    return _SIM


def combat(
    class_name: str,
    level: int,
    creature_id: str,
    *,
    n: int = 1,
    seed: int = 7,
    hand: list[str] | None = None,
    folego: int | None = None,
    enemy_vitality: int | None = None,
    hero_vitality: int | None = None,
    subclass: str = "",
) -> dict[str, Any]:
    """Conflito montado (cena, atores, pilhas) pronto para `orch.run_round`."""
    from services import card_piles
    from services import conflict_scene as cs

    sim = _sim()
    A = sim.A
    with env(CARDS_ON):
        player = A.hero(class_name, level)
        deck = sorted(sim.full_deck(class_name, level, subclass))
        player["deck"] = list(deck)
        player["prepared_cards"] = list(
            dict.fromkeys(list(deck) + (player.get("prepared_cards") or []))
        )
        enemies = A._instances(
            A.template_by_id(creature_id, encounter_level=A.DANGER_BY_LEVEL.get(level, 4)), n
        )
        if enemy_vitality is not None:
            for e in enemies:
                e["vitalidade"] = enemy_vitality
        if hero_vitality is not None:
            player["vitalidade"] = hero_vitality
        actors = {"player": player, **{e["id"]: e for e in enemies}}
        sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
        scene = cs.new_scene()
        for aid in actors:
            cs.place(scene, aid)
        cs.freeze(scene)
        piles = card_piles.start_piles(player, seed)
        if hand is not None:
            piles["mao"] = list(hand)
            piles["compra"] = [c for c in piles["compra"] if c not in hand]
        if folego is not None:
            piles["folego"] = folego
    return {
        "player": player,
        "enemies": enemies,
        "actors": actors,
        "sides": sides,
        "scene": scene,
        "piles": piles,
        "state": {"player": player, "_piles": piles, "_deck_mode": "on"},
        "rng": random.Random(seed),
    }


def _hand_has(sc: Scenario, key: str, ids: list[str]) -> list[str]:
    mao = sc.data[key]["piles"]["mao"]
    return [f"{key}: '{i}' fora da mao" for i in ids if i not in mao]


# --------------------------------------------------------------------------
# Itens do §6
# --------------------------------------------------------------------------
def s6_01_pacto_e_rollback() -> Scenario:
    """328 §6.2 + R1-R3: Pacto do Abismo (Folego curto) e baralho ativo para desligar a flag fora de combate."""
    from services import card_piles, cards

    c = combat("Sangromante", 3, "enemy_goblin", folego=1, hand=["bas_san_golpe", "bas_san_golpe"])
    p = {
        "class_name": "Sangromante",
        "level": 1,
        "known_cards": [x["id"] for x in cards.cards_for_class("Sangromante")][:6],
        "prepared_cards": [x["id"] for x in cards.cards_for_class("Sangromante")][:2],
        "entropy": 6,
        "max_entropy": 10,
    }
    original = list(p["prepared_cards"])
    with env({"RPG_CARD_DECK": "on"}):
        card_piles.activate_deck(p)

    def check(sc: Scenario) -> list[str]:
        out: list[str] = []
        steps = [
            _step("bas_san_golpe", "player") for _ in range(2)
        ]  # 2 jogadas de 1 Folego com 1 so
        plan = card_piles.plan_plays(sc.data["pacto"]["piles"], sc.data["pacto"]["player"], steps)
        if not plan["ok"] or plan["emprestado"] < 1:
            out.append(f"Pacto nao exigido: {plan}")
        if "prepared_cards_pre_deck" not in sc.data["rollback_player"]:
            out.append("baralho nao esta ativo")
        probe = dict(sc.data["rollback_player"])
        with env({"RPG_CARD_DECK": "off"}):
            card_piles.sync_deck_mode(probe)
        if probe["prepared_cards"] != sc.data["preparadas_antes"]:
            out.append("rollback fora de combate nao restaurou as Preparadas")
        return out

    return Scenario(
        1,
        "328 §6.2 · R1-R3",
        "Heroi com 1 de Folego e 2 jogadas na mao; ficha com baralho ativo para o rollback.",
        env=dict(CARDS_ON),
        data={
            "pacto": c,
            "rollback_player": p,
            "preparadas_antes": original,
        },
        check=check,
        passos=[
            "Jogar as 2 cartas: aceitar o Pacto (debita Entropia, +1 Carga 1x/rodada).",
            "Recusar o Pacto: o Pressagio da rodada nao e rerrolado.",
            "Fora de combate, desligar RPG_CARD_DECK: as Preparadas voltam as de antes.",
        ],
    )


def _step(card_id: str, target: str):
    from services import conflict_turn as ct

    return ct.TurnStep(kind="card", card_id=card_id, target_id=target)


def s6_02_familia_estudada_e_pressagio_frustrado() -> Scenario:
    """329 §6.2/§6.3: familia estudada (faixa e nome) e Pressagio frustrado."""
    from services import enemy_intent

    c = combat("Devoto do Abismo", 3, "enemy_goblin")
    enemy = c["enemies"][0]
    with env(CARDS_ON):
        forecast = enemy_intent.forecast_round(c["scene"], c["actors"], c["sides"], c["rng"])
    intent = (forecast.get(enemy["id"]) or [{}])[0]
    carta = intent.get("carta_id")
    if carta:
        enemy["revealed_cards"] = [carta]

    def check(sc: Scenario) -> list[str]:
        out: list[str] = []
        e = sc.data["combat"]["enemies"][0]
        it = sc.data["intent"]
        if not it:
            return ["sem presságio"]
        if it.get("carta_id") and enemy_intent.knowledge_level(e, it["carta_id"]) != "estudada":
            out.append("familia nao ficou 'estudada'")
        actors = dict(sc.data["combat"]["actors"])
        dead = dict(actors[it["actor_id"]], dead=True, status="morto")
        actors[it["actor_id"]] = dead
        if enemy_intent.still_possible(it, actors, sc.data["combat"]["scene"]):
            out.append("presságio nao ficou frustrado")
        return out

    return Scenario(
        2,
        "329 §6.2/§6.3",
        "Goblin com Carta do presságio ja estudada; o executor pode ser incapacitado para frustrar.",
        env=dict(CARDS_ON),
        data={"combat": c, "intent": intent},
        check=check,
        passos=[
            "Ler faixa e nome no chip.",
            "Incapacitar o executor antes da jogada: linha de frustrado.",
        ],
    )


def s6_03_eco_e_rachadura() -> Scenario:
    """330 §6: combo Eco; Rachadura + golpe com numero igual ao texto."""
    eco = combat("Sangromante", 5, "enemy_goblin", hand=["san1_exp_segundo_ato", "bas_san_golpe"])
    rach = combat(
        "Corruptor", 5, "enemy_goblin", hand=["cor1_ino_junta_emperrada", "bas_cor_golpe"]
    )

    def check(sc: Scenario) -> list[str]:
        from services import card_effects as fx
        from services import cards

        out = _hand_has(sc, "eco", ["san1_exp_segundo_ato"]) + _hand_has(
            sc, "rachadura", ["cor1_ino_junta_emperrada"]
        )
        if not fx.keywords(cards.get_card("san1_exp_segundo_ato")).get("eco"):
            out.append("segundo_ato sem Eco")
        if (cards.get_card("cor1_ino_junta_emperrada").get("efeito") or {}).get(
            "kind"
        ) != "rachadura":
            out.append("junta_emperrada sem Rachadura")
        return out

    return Scenario(
        3,
        "330 §6",
        "Sangromante com carta de Eco na mao; Corruptor com Rachadura + golpe.",
        env=dict(CARDS_ON),
        data={"eco": eco, "rachadura": rach},
        check=check,
        passos=[
            "Jogar a de Eco duas vezes na cena.",
            "Rachadura e depois golpe: dano = numero do texto.",
        ],
    )


def s6_04_escolta_proteger() -> Scenario:
    """331 §6.2: cena de escolta com objetivo `proteger`."""
    from services import scene_cards

    c = combat("Devoto do Abismo", 3, "enemy_goblin", n=2)
    with env(CARDS_ON):
        scene_cards.attach(
            c["scene"], [], {"tipo": "proteger", "alvo": "escoltado"}, None, allies=["escoltado"]
        )

    def check(sc: Scenario) -> list[str]:
        obj = sc.data["combat"]["scene"].get("objetivo") or {}
        if obj.get("tipo") != "proteger":
            return [f"objetivo nao e proteger: {obj}"]
        return []

    return Scenario(
        4,
        "331 §6.2",
        "Duas ameacas e um escoltado; o objetivo da cena e proteger.",
        env=dict(CARDS_ON),
        data={"combat": c},
        check=check,
        passos=["Proteger o escoltado ate o fim: cumprido; deixa-lo cair: falhou."],
    )


def s6_05_legiao_chefe_faccao_nova() -> Scenario:
    """332 §6: assinatura da Legiao, padrao visivel, fase do chefe, 1 combate com facao do R4."""
    from services import enemy_decks as edk

    legiao = combat("Devoto do Abismo", 5, "enemy_soldado_legiao_ferro", n=2)
    chefe = combat("Devoto do Abismo", 5, "enemy_boss_valerius")
    nova = combat("Sangromante", 3, "mon_costurado_de_lentes")
    with env(CARDS_ON):
        for c in (legiao, chefe, nova):
            for e in c["enemies"]:
                edk.apply_deck(e, 7)

    def check(sc: Scenario) -> list[str]:
        out: list[str] = []
        from services import enemy_decks as edk2

        if not edk2.pattern_of(sc.data["legiao"]["enemies"][0]):
            out.append("Legiao sem padrao")
        if "enemy_boss_valerius" not in edk2._meta().get("fases", {}):
            out.append("Valerius sem fases autoradas")
        deck = sc.data["nova_faccao"]["enemies"][0].get("cartas") or []
        if not deck:
            out.append("facção nova sem baralho de inimigo")
        return out

    return Scenario(
        5,
        "332 §6 · R4",
        "Legiao de Ferro, Valerius (fases) e um Devorador de Sol (facção nova) com baralho de inimigo.",
        env=dict(CARDS_ON),
        data={"legiao": legiao, "chefe": chefe, "nova_faccao": nova},
        check=check,
        passos=[
            "Ver a assinatura da Legiao e o padrao visivel.",
            "Derrubar Valerius ate trocar de fase.",
            "Combate com o Costurado de Lentes: baralho da facção tribos_devoradores_sol.",
        ],
    )


def s6_06_espolio_descanso_dor_surda() -> Scenario:
    """333 §6.1/§6.3: espolio com Carta da facção, descanso longo (Esquecer) e Dor Surda descartada (R6)."""
    from services import card_piles, card_rewards
    from services import conflict_turn as ct
    from services import enemy_decks as edk

    c = combat(
        "Sangromante",
        3,
        "enemy_degolador_mao_sombria",
        n=2,
        hand=["sts_dor_surda", "bas_san_golpe"],
    )
    player = c["player"]
    with env(CARDS_ON):
        for e in c["enemies"]:
            edk.apply_deck(e, 7)
        player.setdefault("known_cards", [])
        state = {"player": player, "world": {"current_location_id": "skallgard"}}
        seed_hit = None
        for seed in range(400):
            offered = card_rewards.roll_rewards(state, None, seed, defeated=c["enemies"])
            if any(cid.startswith("inf_fac_mao_sombria") for cid in offered):
                seed_hit = seed
                break
    rest = {"forja_esquecer": 0}
    with env(CARDS_ON):
        card_rewards.on_long_rest(rest)

    def check(sc: Scenario) -> list[str]:
        out: list[str] = []
        if sc.data["seed_com_carta_da_faccao"] is None:
            out.append("nenhum espólio ofereceu Carta da facção Mão Sombria")
        if sc.data["descanso"].get("forja_esquecer") != 1:
            out.append("descanso longo nao deu a carga de Esquecer")
        piles = sc.data["combat"]["piles"]
        plan = card_piles.plan_plays(
            piles,
            sc.data["combat"]["player"],
            [ct.TurnStep(kind="discard", card_id="sts_dor_surda")],
        )
        if not plan["ok"]:
            out.append(f"Dor Surda nao descartavel: {plan['motivo']}")
        return out

    return Scenario(
        6,
        "333 §6.1/§6.3 · R6",
        "Mao Sombria derrotada (espolio com Carta da facção), descanso longo e Dor Surda na mao.",
        env=dict(CARDS_ON),
        data={"combat": c, "seed_com_carta_da_faccao": seed_hit, "descanso": rest},
        check=check,
        passos=[
            "Vencer a Mao Sombria: o espólio traz Carta da facção (semente indicada).",
            "Descansar (longo): Esquecer disponivel.",
            "Com Dor Surda na mao: botao 'Descartar (1 Folego)'.",
        ],
    )


def s6_07_corruptor_e_medico() -> Scenario:
    """335 §6: 1 conflito com Corruptor e 1 com Medico."""
    corr = combat("Corruptor", 3, "enemy_goblin", n=2)
    med = combat("Médico de Campo", 3, "enemy_goblin", n=2)

    def check(sc: Scenario) -> list[str]:
        return [
            f"{k}: classe errada"
            for k, cls in (("corruptor", "Corruptor"), ("medico", "Médico de Campo"))
            if sc.data[k]["player"].get("class_name") != cls
        ] + [f"{k}: mao vazia" for k in ("corruptor", "medico") if not sc.data[k]["piles"]["mao"]]

    return Scenario(
        7,
        "335 §6",
        "Dois heróis (Corruptor e Médico de Campo) contra dois goblins.",
        env=dict(CARDS_ON),
        data={"corruptor": corr, "medico": med},
        check=check,
        passos=["Jogar 1 conflito com cada Postura e anotar o que a mão oferece."],
    )


def s6_08_draft_promover() -> Scenario:
    """336 §6: draft.py (chave real) -> lint -> sim -> promover -> jogar 1 Carta."""
    from services import cards

    postura, sub = "Médico de Campo", "boticario"
    cmd = [
        'bash scripts/dev/py.sh scripts/cards/draft.py --postura "Médico de Campo" --subclasse boticario --n 4'
        " --raridades comum --onda 368",
        "bash scripts/dev/py.sh scripts/cards/lint.py --lote data/cards/_rascunhos/<arquivo>.json",
        "bash scripts/dev/py.sh scripts/cards/sim.py --lote data/cards/_rascunhos/<arquivo>.json --json",
        "bash scripts/dev/py.sh scripts/cards/promote.py --lote data/cards/_rascunhos/<arquivo>.json",
    ]

    def check(sc: Scenario) -> list[str]:
        out: list[str] = []
        if not cards.cards_for_class(postura, sub):
            out.append("Postura/subclasse sem Cartas no catalogo")
        for name in ("draft.py", "lint.py", "sim.py", "promote.py"):
            if not os.path.isfile(os.path.join(ROOT, "scripts", "cards", name)):
                out.append(f"scripts/cards/{name} ausente")
        if not os.path.isdir(
            os.path.join(ROOT, "data", "cards", "_rascunhos")
        ) and not os.path.isdir(os.path.join(ROOT, "data", "cards")):
            out.append("pasta de cartas ausente")
        return out

    return Scenario(
        8,
        "336 §6",
        "Postura/subclasse alvo do rascunho e os 4 comandos do fluxo (custo: 1 chamada SMART).",
        env={"RPG_FORCE_MOCK": "0"},
        data={"comandos": cmd, "postura": postura, "subclasse": sub},
        check=check,
        passos=["Rodar os comandos na ordem; jogar a Carta promovida 1x; registrar o custo."],
    )


def s6_09_modo_off() -> Scenario:
    """345 §6.1 (D-368-2): modo `off` local com o preset do staging."""
    import json

    import yaml

    off = {k: "off" for k in CARDS_ON}

    def check(sc: Scenario) -> list[str]:
        out: list[str] = []
        with open(os.path.join(ROOT, "config", "flags.yaml"), encoding="utf-8") as fh:
            registered = set((yaml.safe_load(fh) or {}).get("flags", {}) or {})
        known = registered or set()
        for flag in sc.env:
            if known and flag not in known:
                out.append(f"{flag} fora de config/flags.yaml")
        with env(sc.env):
            from services import card_piles

            if card_piles.mode() != "off":
                out.append("RPG_CARD_DECK nao ficou off")
        with open(
            os.path.join(ROOT, "scripts", "staging", "staging_flags.json"), encoding="utf-8"
        ) as fh:
            staging = json.load(fh)["flags"]
        for flag in sc.env:
            if flag not in staging:
                out.append(f"{flag} ausente do preset do staging")
        return out

    return Scenario(
        9,
        "345 §6.1",
        "Preset local com todas as flags de cartas `off`.",
        env=off,
        check=check,
        passos=[
            "Subir a API local com este env, jogar 1 conflito e conferir o combate sem Baralho."
        ],
    )


def s6_10_router_esgotado() -> Scenario:
    """346 §6.5/6.6/6.7: router esgotado, CLASSIFY so no Groq, rodada `off`, morte real."""
    import json

    routes = json.dumps(
        {
            "classify": [["groq", "openai/gpt-oss-20b"]],
            "fast": [["groq", "openai/gpt-oss-120b"]],
            "smart": [["groq", "openai/gpt-oss-120b"]],
        }
    )
    c = combat("Sangromante", 1, "enemy_goblin", n=3, hero_vitality=1)

    def check(sc: Scenario) -> list[str]:
        out: list[str] = []
        parsed = json.loads(sc.env["RPG_ROUTES"])
        if set(parsed) != {"classify", "fast", "smart"}:
            out.append("RPG_ROUTES sem os 3 tiers")
        hero = sc.data["morte"]["player"]
        if int(hero.get("vitalidade", 99)) != 1:
            out.append("heroi nao esta com 1 de Vitalidade")
        return out

    return Scenario(
        10,
        "346 §6.5/§6.6/§6.7",
        "RPG_ROUTES so com Groq; heroi com 1 de Vitalidade contra 3 goblins para a morte real.",
        env={"RPG_ROUTES": routes, "RPG_CARD_DECK": "off"},
        data={"morte": c},
        check=check,
        passos=[
            "Forcar falha dos candidatos (chave invalida do Groq) e ver o router esgotado.",
            "Rodada com RPG_CARD_DECK=off e a morte vista ao vivo.",
        ],
    )


def s6_11_arte_unico_concorrencia() -> Scenario:
    """347 §6.5 / 352 §6.1/6.4/6.5: importar imagem, chefe `unico:{game}`, confirmacoes concorrentes."""
    import tempfile
    import uuid

    from PIL import Image

    from services import creature_art

    folder = tempfile.mkdtemp(prefix="spec368_arte_")
    os.makedirs(os.path.join(folder, "criaturas"), exist_ok=True)
    path = os.path.join(folder, "criaturas", "enemy_goblin.png")
    Image.new("RGB", (512, 512), (40, 30, 30)).save(path)
    boss = {"id": "enemy_boss_valerius", "name": "Valerius", "categoria": "chefe"}
    keys = {
        g: creature_art.portrait_key(boss, None, game_id=g) for g in ("jogo-a-0000", "jogo-b-0000")
    }
    action_ids = [str(uuid.UUID(int=i + 1)) for i in range(2)]

    def check(sc: Scenario) -> list[str]:
        out: list[str] = []
        with Image.open(sc.data["png"]) as im:
            if im.size != (512, 512):
                out.append("PNG de teste invalido")
        k = list(sc.data["chaves"].values())
        if len(set(k)) != 2 or not all(x.startswith("unico:") for x in k):
            out.append(f"chefe nao isolado por jogo: {k}")
        if len(set(sc.data["action_ids"])) != 2:
            out.append("action_ids concorrentes iguais")
        return out

    return Scenario(
        11,
        "347 §6.5 · 352 §6.1/§6.4/§6.5",
        "PNG de teste para o import, chaves de retrato do chefe por jogo e 2 action_ids para confirmar em paralelo.",
        env={},
        data={"pasta": folder, "png": path, "chaves": keys, "action_ids": action_ids},
        check=check,
        passos=[
            "scripts/import_bestiary_art.py <pasta>; 'Agora nao' sem cotacao nem request.",
            "Duas contas: o chefe unico:{game} nao vaza.",
            "Duas confirmacoes concorrentes: so uma cobra. image_generation on so durante o item.",
        ],
    )


def s6_12_toast_na_vitoria() -> Scenario:
    """354: toast a 1440 no instante da vitoria."""
    c = combat(
        "Sangromante", 3, "enemy_goblin", enemy_vitality=1, hand=["bas_san_golpe", "bas_san_guarda"]
    )

    def check(sc: Scenario) -> list[str]:
        e = sc.data["combat"]["enemies"][0]
        if int(e.get("vitalidade", 99)) != 1:
            return ["inimigo nao esta a 1 golpe da vitoria"]
        return _hand_has(sc, "combat", ["bas_san_golpe"])

    return Scenario(
        12,
        "354",
        "Um goblin com 1 de Vitalidade e um golpe na mao: a proxima rodada e a vitoria.",
        env=dict(CARDS_ON),
        data={"combat": c},
        check=check,
        passos=[
            "Viewport 1440: encerrar a rodada com o golpe e ver o toast no instante da vitoria."
        ],
    )


def s6_13_cartas_355() -> Scenario:
    """355 §6: Voto em Ketil, Leitura de Pressao, Armadura Comprometida, Renegado, vitoria com Reacao."""
    from services import enemy_decks as edk

    voto = combat(
        "Devoto do Abismo", 3, "enemy_goblin", n=2, hand=["bas_dev_voto", "bas_dev_golpe"]
    )
    leitura = combat(
        "Arcanista Cinzento",
        3,
        "enemy_goblin",
        hand=["arc1_cal_leitura", "bas_arc_golpe"],
        subclass="calibrado",
    )
    armadura = combat("Corruptor", 3, "enemy_goblin", hand=["cor_ino_fadiga", "bas_cor_golpe"])
    renegado = combat("Sangromante", 3, "enemy_renegado_ermo")
    with env(CARDS_ON):
        edk.apply_deck(renegado["enemies"][0], 7)
    reacao = combat(
        "Devoto do Abismo",
        3,
        "enemy_goblin",
        enemy_vitality=1,
        hand=["dev_encaixe", "bas_dev_golpe"],
    )

    def check(sc: Scenario) -> list[str]:
        from services import cards

        out = _hand_has(sc, "voto", ["bas_dev_voto"]) + _hand_has(
            sc, "leitura", ["arc1_cal_leitura"]
        )
        out += _hand_has(sc, "armadura", ["cor_ino_fadiga"]) + _hand_has(
            sc, "reacao", ["dev_encaixe"]
        )
        if any(
            "aguentar" in str(cards.get_card(c) or {}).lower()
            for c in sc.data["voto"]["piles"]["mao"]
        ):
            out.append("mao do Voto tem Aguentar")
        names = " ".join(
            str((cards.get_card(i["id"] if isinstance(i, dict) else i) or {}).get("name", ""))
            for i in sc.data["renegado"]["enemies"][0].get("cartas") or []
        ).lower()
        if "descarga arcana" in names:
            out.append("Renegado ainda com Descarga Arcana")
        return out

    return Scenario(
        13,
        "355 §6",
        "Cinco cenas: Voto (Devoto), Leitura (Arcanista calibrado), Armadura Comprometida, Renegado do Ermo, vitoria com Reacao.",
        env=dict(CARDS_ON),
        data={
            "voto": voto,
            "leitura": leitura,
            "armadura": armadura,
            "renegado": renegado,
            "reacao": reacao,
        },
        check=check,
        passos=[
            "Voto com presságio mirando Ketil: 'muda de alvo' ou 'resiste'.",
            "Leitura de Pressao: o presságio seguinte mostra o nome da Carta.",
            "Armadura Comprometida em chip e registro (nunca o id).",
            "Skallgard, Renegado: sem Descarga Arcana.",
            "Vitoria com Reacao: o resumo cita o autor.",
        ],
    )


def s6_14_quest_justa_tecnica() -> Scenario:
    """357 §6.5: quest de lore `justa` entregando tecnica."""
    from services import card_rewards

    quest = {
        "id": "q368",
        "title": "Caca",
        "status": "active",
        "location_id": "brekmar",
        "reward_card_planned": True,
        "reward_card_label": "justa",
        "reward_hint": "justa · uma técnica",
    }
    player = {
        "level": 6,
        "class_name": "Sangromante",
        "known_cards": [],
        "deck": [],
        "prepared_cards": [],
    }
    with env({"RPG_CARD_REWARDS": "on"}):
        granted = card_rewards.grant_for_quest({"game_id": "g"}, player, quest, 5)

    def check(sc: Scenario) -> list[str]:
        if not sc.data["tecnica"]:
            return ["a quest `justa` nao entregou tecnica"]
        if sc.data["tecnica"] not in sc.data["player"]["known_cards"]:
            return ["a tecnica nao entrou no Acervo"]
        return []

    return Scenario(
        14,
        "357 §6.5",
        "Quest de lore `justa` com tecnica prometida; a conclusao entrega uma Carta neutra.",
        env={"RPG_CARD_REWARDS": "on"},
        data={"quest": quest, "player": player, "tecnica": granted},
        check=check,
        passos=[
            "Concluir a quest pelo jogo e conferir a Carta no Acervo (so o nome aparece na UI)."
        ],
    )


BUILDERS: dict[int, Callable[[], Scenario]] = {
    1: s6_01_pacto_e_rollback,
    2: s6_02_familia_estudada_e_pressagio_frustrado,
    3: s6_03_eco_e_rachadura,
    4: s6_04_escolta_proteger,
    5: s6_05_legiao_chefe_faccao_nova,
    6: s6_06_espolio_descanso_dor_surda,
    7: s6_07_corruptor_e_medico,
    8: s6_08_draft_promover,
    9: s6_09_modo_off,
    10: s6_10_router_esgotado,
    11: s6_11_arte_unico_concorrencia,
    12: s6_12_toast_na_vitoria,
    13: s6_13_cartas_355,
    14: s6_14_quest_justa_tecnica,
}


def get(item: int) -> Scenario:
    return BUILDERS[item]()


def build_all() -> dict[int, Scenario]:
    return {i: b() for i, b in BUILDERS.items()}
