"""SPEC-350 — fixtures sintéticas do catálogo de tramas (sem tocar nos dados reais)."""

from __future__ import annotations

import copy

from services.plot_threads_lint import PlotRefs

TID = "tr_na_teste"


def _sheet(
    tier, papel, desejo, medo, topico, registro, fala, loc, doc="", fonte="lore_nova/x.txt:1-2"
):
    return {
        "tier": tier,
        "threads": [{"thread_id": TID, "papel": papel}],
        "desejo": desejo,
        "medo": medo,
        "segredo_topico": topico,
        "segredo_doc_id": doc,
        "voz": {"registro": registro, "fala": fala},
        "home_location_id": loc,
        "archetype": "sedentario",
        "fonte": fonte,
    }


def good_data() -> dict:
    return copy.deepcopy(
        {
            "version": 1,
            "waves": [{"order": 1, "regions": ["nova_arcadia"], "status": "in_progress"}],
            "threads": [
                {
                    "id": TID,
                    "region_id": "nova_arcadia",
                    "title": "A trama de teste",
                    "pergunta": "Quem fica com os barris quando a adega fecha?",
                    "resumo_publico": "A adega foi revistada duas vezes e ninguém diz por quê.",
                    "core": ["npc_chefe", "npc_vilao"],
                    "borda": ["npc_a", "npc_b"],
                    "portas": [
                        {
                            "id": f"{TID}__p1",
                            "anchor_npc_id": "npc_a",
                            "location_id": "loc_1",
                            "link_kind": "emprego",
                            "hook_public": "A ajudante da adega paga uma moeda por noite a quem rolar barris.",
                        },
                        {
                            "id": f"{TID}__p2",
                            "anchor_npc_id": "npc_b",
                            "location_id": "loc_2",
                            "link_kind": "testemunha",
                            "hook_public": "Um cabo confisca papéis na rua e não sabe dizer o quê.",
                            "quest_hint": {"kind": "escoltar", "anchor_id": "npc_b"},
                        },
                        {
                            "id": f"{TID}__p3",
                            "anchor_npc_id": "npc_c",
                            "location_id": "loc_1",
                            "link_kind": "encomenda",
                            "hook_public": "A remendeira precisa de um recado levado à velha dos espetinhos.",
                            "rumor_ids": ["rumor_x"],
                            "quest_hint": {"kind": "entregar_material", "anchor_id": "rota_1"},
                        },
                    ],
                    "factions": ["fac_a"],
                    "locations": ["loc_1", "loc_2"],
                    "rumor_ids": ["rumor_x"],
                    "secret_ids": ["sec_a"],
                    "lore_refs": ["lore_nova/teste.txt:1-2"],
                    "lore_keyword": "barril",
                    "postura_afinidade": ["Sangromante"],
                }
            ],
            "cast": {
                "npc_a": _sheet(
                    "borda",
                    "ajudante de adega que rola barris",
                    "pagar a fiança do irmão preso",
                    "voltar ao fosso depois da taverna fechar",
                    "o que o sargento procura",
                    "contadora nos dedos",
                    "Três barris, duas mentiras e um sargento.",
                    "loc_1",
                    doc="npc_a_segredo",
                    fonte="spec350",
                ),
                "npc_b": _sheet(
                    "borda",
                    "cabo de patrulha que confisca papéis",
                    "transferência antes do inverno",
                    "virar exemplo como o desertor",
                    "o que não consegue ler",
                    "regulamento pela metade",
                    "Artigo, o artigo diz que é pra entregar.",
                    "loc_2",
                    doc="npc_b_segredo",
                    fonte="spec350",
                ),
                "npc_c": _sheet(
                    "ponte",
                    "remendeira de redes com recados",
                    "uma rede nova para o inverno",
                    "perder o ponto na ponte",
                    "para quem remenda de noite",
                    "miúda e desconfiada",
                    "Linha curta, nó firme. Não pergunto.",
                    "loc_1",
                ),
            },
            "excluded": {},
        }
    )


def good_refs() -> PlotRefs:
    return PlotRefs(
        npc_ids={"npc_chefe", "npc_vilao", "npc_a", "npc_b", "npc_c"},
        leader_ids={"npc_chefe"},
        location_ids={"loc_1", "loc_2"},
        faction_ids={"fac_a"},
        rumor_ids={"rumor_x"},
        route_ids={"rota_1"},
        secret_ids={"sec_a"},
        archetypes={"sedentario", "patrulheiro"},
        region_ids={"nova_arcadia", "brekmar"},
        posturas={"Sangromante", "Corruptor"},
        banned_words={"mana", "boss", "loot"},
        secret_signatures={"sec_a": ["testamento do antigo rei"]},
        leak_phrases=["herdeiro de ostmar"],
        secret_doc_visibility={"npc_a_segredo": "hidden", "npc_b_segredo": "hidden"},
        secret_doc_text={
            "npc_a_segredo": "Dalva entrega a chave da adega ao sargento todas as noites.",
            "npc_b_segredo": "O cabo analfabeto deixou passar o documento procurado.",
        },
        public_doc_text={
            "npc_a": "Ajudante da adega. Rola barris, conta nos dedos e fala do sargento.",
            "npc_b": "Cabo da patrulha. Recita regulamento pela metade.",
        },
        name_owners={},
        npc_names={"npc_a": ["Dalva Torneira"], "npc_b": ["Anselmo Tiza"]},
        role_radicals=["ajudante", "cabo", "remendeira"],
        lore_reader=lambda path, a, b: (
            "Um barril de cerveja azeda na adega." if "teste" in path else None
        ),
    )
