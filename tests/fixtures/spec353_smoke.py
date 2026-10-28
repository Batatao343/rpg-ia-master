"""SPEC-353 R11: os parágrafos de resumo do smoke 2, VERBATIM (docs/spec353/smoke/state-*.json)."""

D5 = (
    "O Sussurro Faminto rasga o escuro e encontra teu torso antes que a espada gasta termine o arco — "
    "o impacto te arranca o chão, e o gosto de ferro sobe pela garganta. Tua cabeça bate na pedra "
    "fria, o braço cede sob o peso do corpo, e a perna dobra sem força enquanto a Noite Sem Estrelas "
    "engole tudo ao redor. O Anão-Eco cambaleia à beira do colapso, o brilho dele tremendo na "
    "escuridão, e ainda assim não cai. Só resta o som da tua respiração quebrada e o silêncio pesado "
    "do céu sem estrelas."
)

K4 = (
    "Sob o céu de chumbo da Noite Sem Estrelas, sua espada gasta desce duas vezes no mesmo movimento "
    "de penitência, e a criatura além das estacas desmorona sem som que valha a pena guardar. Você "
    "permanece de pé, ileso, o fôlego ainda quente no peito enquanto o silêncio se fecha sobre o que "
    "restou dela. O ermo respira com você — e desta vez, nada respira de volta."
)

R6 = (
    "A adaga de ferro escapa de sua mão enquanto o Couro Encharcado cede sob o peso do seu corpo "
    "exausto — o Corte de Troca não encontra alvo, e é o próprio chão que o recebe. O Minotauro "
    "Esqueleto cambaleia à beira do colapso, seu último golpe cortando apenas o ar vazio, enquanto o "
    "sangue que escorre de você mancha a terra fria do amanhecer. Seus ferimentos — o torso rasgado, "
    "a perna cedendo, o fio de sangue na cabeça — pesam mais que qualquer inimigo, e a consciência se "
    "esvai devagar entre as nuvens rasgadas. Você tomba, e o silêncio do campo de batalha se fecha "
    "sobre você."
)


def _hit(card_id, *, actor="player", target="e1", label=None, acerto=True):
    return {
        "actor_id": actor,
        "target_id": target,
        "card_id": card_id,
        "label": label,
        "acerto": acerto,
        "resultado": "critico" if acerto else "erro",
    }


# last_out como o motor registra (attacks / ticks / final_blows)
LAST_OUT_D5 = {
    "attacks": [
        _hit(None, actor="e1", target="player"),
        _hit("sus_sussurro_abismo", label="Última Ação"),
    ],
    "final_blows": [],
}
LAST_OUT_K4 = {
    "attacks": [
        _hit("bas_dev_golpe", acerto=False),
        _hit(None, actor="npc_ketil"),
    ],
    "ticks": [{"actor_id": "e1", "condition": "Sangramento", "dano_final": 1}],
    "final_blows": [
        {"target_id": "e1", "kind": "dano_continuo", "by_actor_id": None, "condition": "Sangramento"}
    ],
}
LAST_OUT_R6 = {
    "attacks": [
        _hit(None, actor="e1", target="player", acerto=False),
        _hit("san_corte_troca", label="Última Ação"),
    ],
    "final_blows": [],
}
NAMES = {"e1": "Criatura", "npc_ketil": "Ketil"}
