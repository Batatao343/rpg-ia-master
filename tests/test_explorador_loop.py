"""Suíte da spec fix-explorador-loop-navegacao — perfil não oscila cidade↔interior.

Offline/determinístico. Grafo sintético via monkeypatch dos acessores do módulo.
"""
import random
import gamedata
import playtest.profiles as pf


def _mk(monkeypatch, graph, interiors=None):
    interiors = interiors or {}
    monkeypatch.setattr(pf, "_connections", lambda lid: [dict(c) for c in graph.get(lid, [])])
    monkeypatch.setattr(gamedata, "interiors_of", lambda lid: [dict(c) for c in interiors.get(lid, [])])


def test_reset_zera_memoria():
    prof = pf.Explorador()
    prof._recent = ["a", "b"]
    prof.reset()
    assert prof._recent == []


def test_explorador_evita_backtrack_imediato(monkeypatch):
    # cidade conecta a interior + vizinho; tudo já visitado
    _mk(monkeypatch, {"cidade": [{"id": "interior", "name": "Interior"},
                                 {"id": "vizinho", "name": "Vizinho"}]},
        interiors={"cidade": []})
    prof = pf.Explorador(); prof.reset()
    rng = random.Random(0)
    st = {"world": {"current_location_id": "interior",
                    "visited": ["cidade", "interior", "vizinho"]}}
    prof.next_action(st, rng)                     # registra 'interior'
    st["world"]["current_location_id"] = "cidade"  # veio do interior
    act = prof.next_action(st, rng)               # prev = interior
    assert "Interior" not in act                  # não volta de onde veio
    assert "Vizinho" in act


def test_explorador_prioriza_fronteira(monkeypatch):
    # há um nó NÃO visitado -> deve ir pra ele, não pro já-visitado
    _mk(monkeypatch, {"cidade": [{"id": "visto", "name": "Visto"},
                                 {"id": "novo", "name": "Novo"}]},
        interiors={"cidade": []})
    prof = pf.Explorador(); prof.reset()
    st = {"world": {"current_location_id": "cidade", "visited": ["cidade", "visto"]}}
    act = prof.next_action(st, random.Random(1))
    assert "Novo" in act


def test_explorador_entra_interior_nao_visitado(monkeypatch):
    _mk(monkeypatch, {"cidade": [{"id": "vizinho", "name": "Vizinho"}]},
        interiors={"cidade": [{"id": "salao", "name": "Salão"}]})
    prof = pf.Explorador(); prof.reset()
    st = {"world": {"current_location_id": "cidade", "visited": ["cidade"]}}
    act = prof.next_action(st, random.Random(0))
    assert act == "Entro em Salão."


def test_explorador_nao_fixa_numa_folha(monkeypatch):
    # Estrela: cidade<->interior (dead-end) + cidade<->vizinho (dead-end). Passar
    # pelo hub é inevitável; o BUG real era fixar SÓ no interior. O fix rotaciona
    # entre TODAS as folhas -> a trilha visita interior E vizinho (não fixa numa).
    graph = {"cidade": [{"id": "interior", "name": "Interior"},
                        {"id": "vizinho", "name": "Vizinho"}],
             "interior": [{"id": "cidade", "name": "Cidade"}],
             "vizinho": [{"id": "cidade", "name": "Cidade"}]}
    names = {"Interior": "interior", "Vizinho": "vizinho", "Cidade": "cidade"}
    _mk(monkeypatch, graph, interiors={})
    prof = pf.Explorador(); prof.reset()
    rng = random.Random(0)
    cur = "cidade"
    trail = [cur]
    for _ in range(6):
        st = {"world": {"current_location_id": cur,
                        "visited": ["cidade", "interior", "vizinho"]}}
        dest = next((nid for nm, nid in names.items() if nm in prof.next_action(st, rng)), cur)
        cur = dest
        trail.append(cur)
    assert {"interior", "vizinho"} <= set(trail), f"fixou numa folha: {trail}"


def test_explorador_alterna_com_terceiro_no_hub(monkeypatch):
    # hub com folha-dead-end + 2 vizinhos NÃO-dead-end: nunca faz A->B->A.
    graph = {"hub": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
             "a": [{"id": "hub", "name": "Hub"}, {"id": "b", "name": "B"}],
             "b": [{"id": "hub", "name": "Hub"}, {"id": "a", "name": "A"}]}
    names = {"A": "a", "B": "b", "Hub": "hub"}
    _mk(monkeypatch, graph, interiors={})
    prof = pf.Explorador(); prof.reset()
    rng = random.Random(0)
    cur = "hub"; trail = [cur]
    for _ in range(6):
        st = {"world": {"current_location_id": cur, "visited": ["hub", "a", "b"]}}
        cur = next((nid for nm, nid in names.items() if nm in prof.next_action(st, rng)), cur)
        trail.append(cur)
    osc = sum(1 for i in range(2, len(trail)) if trail[i] == trail[i-2] and trail[i] != trail[i-1])
    assert osc == 0, f"oscilou com alternativa disponível: {trail}"
