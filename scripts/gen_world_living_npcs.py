"""Gera o lote curado de NPCs regionais da spec conflito-17.

Os textos são fonte autoral declarativa; a escrita é idempotente e mantém os
demais nós/arestas do grafo. Cada NPC público traz apenas informação segura para
o jogador. Segredos futuros devem morar em `npcs/segredos/`.
"""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from pathlib import Path

import yaml


ROOT = Path(os.environ.get("RPG_ROOT", Path(__file__).resolve().parents[1]))
NPC_DIR = ROOT / "data" / "codex" / "npcs" / "mundo_vivo"
GRAPH_DIR = ROOT / "data" / "graph"


# região: (nome, papel, facção declarada, gancho público)
NPCS = {
    "nova_arcadia": [
        ("Irena Prego-Frio", "fiscal de rebites do Anel de Ferro", "legiao_ferro", "Encontrar a remessa de rebites ocos que faz caldeiras explodirem."),
        ("Téo Chaminé", "mensageiro pelos telhados fabris", "resistencia_operaria_martelos_partidos", "Levar uma lista de operários presos sem cruzar uma patrulha da Legião."),
        ("Mara do Sétimo Sino", "relojoeira e informante de turnos", "guilda_corvos", "Descobrir por que um sino toca sozinho antes de cada desaparecimento."),
    ],
    "pantano_melancolia": [
        ("Ume Lodo-Claro", "barqueira dos canais rasos", "druidas_ciclo_cinzento", "Guiar uma coleta de água que ainda não aprendeu a lembrar dos mortos."),
        ("Padre Junco", "guardião de túmulos flutuantes", "druidas_ciclo_cinzento", "Reatar três âncoras funerárias antes da próxima cheia de Éter."),
        ("Sira Candeia", "caçadora de luzes-fátuas", "independente", "Capturar uma chama que repete a voz de uma criança desaparecida."),
    ],
    "deserto_zhur": [
        ("Nahir Vidro-Manso", "lapidador de vidro solar", "tribos_devoradores_sol", "Recuperar uma lente roubada capaz de revelar água sob as dunas."),
        ("Kessa Três-Sombras", "batedora de caravanas", "tribos_devoradores_sol", "Mapear a sombra extra que acompanha uma caravana sem possuir dono."),
        ("Orun Sal-Negro", "negociador de poços", "independente", "Impedir que dois clãs sangrem pelo mesmo poço envenenado."),
    ],
    "floresta_sussurros": [
        ("Eilin Folha-Oca", "intérprete dos sussurros de trilha", "independente", "Traduzir o aviso que árvores diferentes repetem com a mesma voz."),
        ("Tomir Musgo", "curador de cascas feridas", "guardiões_de_thessavar", "Descobrir quem grava símbolos de Nova Arcádia em árvores antigas."),
        ("Vaela do Ninho", "guia de copas baixas", "independente", "Resgatar ovos de mariposa antes que o sussurro dentro deles desperte."),
    ],
    "selva_xylos": [
        ("Jori Sete-Esporos", "mediador entre hospedeiros", "colmeia_hospedeiros", "Separar uma memória coletiva que começou a acusar o corpo errado."),
        ("Mãe Aru", "parteira das cidades de copa", "colmeia_hospedeiros", "Buscar uma planta que permita a um recém-hospedado conservar o próprio nome."),
        ("Pel Sem-Rosto", "cartógrafo de trilhas migratórias", "independente", "Marcar uma rota que muda quando ninguém está olhando para ela."),
    ],
    "skallgard": [
        ("Runa Brasa-Branca", "mecânica de aquecedores de clã", "clas_tecnologicos", "Reativar um forno soterrado antes que a noite congele o abrigo."),
        ("Eirik Sem-Pegadas", "caçador da borda noturna", "clas_combate", "Seguir um lobo que deixa pegadas apontando na direção contrária."),
        ("Solvi Cabo-Cobre", "operadora de rádio antigo", "independente", "Localizar a estação que responde com notícias de amanhã."),
    ],
    "aethelgard": [
        ("Maeril Caco-Azul", "zelador de cristal de contenção", "independente", "Substituir um cristal rachado sem repetir a falha da Destilação."),
        ("Oren Último-Mapa", "copista das galerias élficas", "independente", "Conferir uma sala que apareceu apenas na cópia mais recente do mapa."),
        ("Tessa Ampola", "alquimista arrependida", "cultistas_destilacao", "Interceptar reagentes antes que cheguem a um novo laboratório clandestino."),
    ],
    "ophidia": [
        ("Nami Cinza-Sal", "pilota de canais vulcânicos", "navegadores_ophidia", "Atravessar uma caldeira marítima durante a breve maré de cinzas."),
        ("Koro Remo-Curto", "pescador de tubos de lava", "independente", "Retirar uma rede presa a algo grande demais para ser peixe."),
        ("Iria Coral-Cego", "oraculista de recife", "guardiões_do_recife", "Interpretar uma resposta de coral que cita alguém ainda não nascido."),
    ],
    "costa_negra": [
        ("Daro Osso-Cantante", "afinador de ossadas titânicas", "mercadores_curiosidades", "Silenciar uma costela gigante que chama predadores a cada vento."),
        ("Mãe Neris", "capitã de coleta de marfim", "osshari", "Encontrar três coletores antes que a maré exponha o caminho até eles."),
        ("Ulk Marfim", "avaliador de relíquias costeiras", "independente", "Provar que um dente vendido em Brekmar pertence a uma criatura viva."),
    ],
    "montanhas_afiadas": [
        ("Brunna Ponte-Alta", "engenheira das passagens anãs", "ultimos_anoes_reino", "Firmar uma ponte que o eco insiste em desmontar durante a noite."),
        ("Skek Eco-Curto", "prospector goblin", "goblins_mineiros", "Seguir um veio que responde às picaretas com batidas codificadas."),
        ("Odrin Calcário", "mediador das saídas baixas", "bandos_orc_saidas_baixas", "Negociar passagem antes que dois túneis rivais se encontrem à força."),
    ],
    "pradaria_ruinas": [
        ("Lio Bandeira-Vazia", "arqueólogo de brasões apagados", "cidades_estado_sobreviventes_vaelorn_solvhen", "Identificar a cidade de uma bandeira que ninguém consegue recordar."),
        ("Hana Estribo", "correio dos bandos nômades", "bandos_nomades", "Entregar um tratado entre acampamentos que mudam de lugar a cada aurora."),
        ("Korso Pedra-Móvel", "pastor de auroques", "independente", "Desviar um rebanho antes que derrube a última torre de uma ruína habitada."),
    ],
    "brekmar": [
        ("Mina Sete-Taxas", "escrivã dos sindicatos", "tres_sindicatos_comercio", "Encontrar o livro-caixa que cobra a mesma dívida de sete pessoas."),
        ("Jax Corda-Seca", "salvador de tripulações", "grupos_piratas_rivais", "Resgatar marinheiros presos num navio que continua afundando fora d'água."),
        ("Varo Dois-Portos", "corretor de rotas clandestinas", "poder_kahen", "Descobrir qual dos dois portos desenhados em seu mapa passou a existir."),
    ],
}


def _slug(text: str) -> str:
    ascii_text = "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    return "".join(char if char.isalnum() else "_" for char in ascii_text.lower()).strip("_").replace("__", "_")


def _write_codex(npc_id: str, name: str, region: str, role: str,
                 faction: str, hook: str) -> None:
    frontmatter = {
        "id": npc_id,
        "type": "npc",
        "name": name,
        "aliases": [],
        "tags": [region, "mundo_vivo", faction],
        "visibility": "public",
        "related_entities": [region],
        "curated": True,
        "home_location_id": region,
        "role": role,
        "faction": faction,
        "origin": "conflito-17",
    }
    body = (
        f"# {name}\n\n"
        f"Papel: {role}.\n\n"
        f"Facção declarada: {faction}.\n\n"
        f"Gancho: {hook}\n\n"
        "Traços de cena: fala por imagens concretas, deseja algo verificável e "
        "reage às mudanças persistentes da região. Seus traços de personalidade "
        "são derivados deterministicamente por `npc_layers` a partir do ID.\n"
    )
    text = "---\n" + yaml.safe_dump(
        frontmatter, allow_unicode=True, sort_keys=False
    ).strip() + "\n---\n\n" + body
    (NPC_DIR / f"{npc_id}.md").write_text(text, encoding="utf-8")


def main() -> int:
    NPC_DIR.mkdir(parents=True, exist_ok=True)
    entities_path = GRAPH_DIR / "entities.json"
    extra_path = GRAPH_DIR / "entities_extra.json"
    edges_path = GRAPH_DIR / "edges.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    extra = json.loads(extra_path.read_text(encoding="utf-8"))
    edges = json.loads(edges_path.read_text(encoding="utf-8"))
    edge_by_id = {edge["id"]: edge for edge in edges}

    count = 0
    for region, entries in NPCS.items():
        for name, role, faction, hook in entries:
            npc_id = f"npc_mv_{_slug(name)}"
            _write_codex(npc_id, name, region, role, faction, hook)
            entities[npc_id] = {
                "id": npc_id,
                "type": "npc",
                "name": name,
                "aliases": [],
                "tags": [region, "mundo_vivo", faction],
                "visibility": "public",
                "components": {
                    "home_location_id": region,
                    "role": role,
                    "faction": faction,
                },
            }
            # Versões anteriores do gerador colocavam o lote no overlay extra;
            # o Codex e os contratos legados exigem entidades autorais no grafo
            # canônico. A migração idempotente remove somente esses mesmos IDs.
            extra.pop(npc_id, None)
            edge_id = f"e_{npc_id}_em_{region}"
            edge_by_id[edge_id] = {
                "id": edge_id,
                "source": npc_id,
                "type": "located_in",
                "target": region,
                "visibility": "public",
            }
            count += 1

    entities_path.write_text(
        json.dumps(entities, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    extra_path.write_text(
        json.dumps(extra, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    edges_path.write_text(
        json.dumps(list(edge_by_id.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"NPCs mundo vivo: {count}; entidades={len(entities)}; arestas={len(edge_by_id)}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
