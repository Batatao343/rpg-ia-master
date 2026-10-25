# SPEC-310 — O NPC sabe de si (fação, patente, agenda, o que ouviu, motivações)

> **Status:** `approved` (dono 24/10, escopo da proposta R3; decisões D1–D6 abaixo seguem a recomendação até o dono dizer o contrário)
> **Criada:** 2026-10-24 · **Atualizada:** 2026-10-24
> **Depende de:** SPEC-215 (ledger de conhecimento por NPC), SPEC-297/306 (semente de NPC),
> SPEC-298 (`<ATITUDE>`, teto de linhas por faixa), SPEC-301 (catálogo de patentes),
> SPEC-302 (`relation_bands`), SPEC-303/307 (calendário, festa como estado de local),
> SPEC-304 (`npc_sim`, `location_of`). Todas na `main`; com flag desligada cada fonte
> simplesmente não gera linha.
> **Coordena com:** SPEC-308 (regra de ouro no pack — não muda nada aqui), SPEC-309
> (`<MUNDO_PERCEBIDO>` do narrador: se pousar antes, reusar o helper de rótulo do local).
> **Desbloqueia:** proposta R7 (parte "NPC membro sabe da guerra da fação") fica coberta;
> N1/N5 (rumor com semente, pistas de segredo) ganham onde aparecer no diálogo.
> **Origem:** `docs/mundo-vivo/REVISAO-ORQUESTRADA-2026-10-24.md` §4.1 R3, achado A6, §2.1
> linha "NPC actor"; regra de ouro em `docs/mundo-vivo/VISAO.md:79-82` e `:220`.

---

## 1. Contexto & Objetivo

O `npc_actor` monta o prompt em `agents/npc.py:1046-1114`. O NPC recebe a própria
ocupação, a persona em texto livre e os traços **já revelados** (`:1048-1060`), a atitude
com o jogador (`:1028`, SPEC-298), a memória, o pack (`:956-964`), o ambiente
(`:1081`), a lei (`:1024-1027`), a lista de **todas** as fações do mundo (`:968-976`) e a
fação **do jogador** (`:1044`, `faction_membership.prompt_block`, `services/faction_membership.py:1232-1254`).
Ele **não** recebe nada sobre si: nem a própria fação ou patente, nem onde passou o dia,
nem de onde veio, nem a festa ou o cerco do lugar onde está, nem as motivações da
semente (revisão §2.1, linha "NPC actor"). O resultado é um NPC que só sabe ser
"Ocupação: Ferreiro" e reage ao jogador, sem vida própria.

Três achados do source explicam o buraco:

1. **`npc_knowledge_block` nunca é chamado** (`services/npc_knowledge.py:850-854`; único uso
   em `tests/test_npc_knowledge.py:410`). Com `RPG_NPC_KNOWLEDGE=on` as linhas
   `[VIU]/[OUVIU]/[BOATO]` já entram, mas **dentro do pack**, competindo pela cota
   `current_state` (`services/context_builder.py:603-619`). O que estoura a cota some do
   prompt sem aviso. Com `off`/`shadow` o NPC não sabe nada do mundo dinâmico.
2. **A semente não chega à ficha de runtime.** `_submit_generated_npc` copia só
   `race_id/origin_region_id/faction_id/profession_id` (`agents/npc.py:581-587`); desejo,
   medo, segredo, contradição e maneirismo (`services/npc_seed.py:33-43`) ficam só na
   entrada do pool (`services/shared_pool_models.py:97`) e "assados" na persona gerada.
   `materialize_npc` também não os copia (`services/shared_pool.py:747-760`).
3. **Fação do NPC tem dois resolvedores que divergem.** `npc_world.npc_faction` lê
   projection → `row["faction"]` → grafo → `leads`/`member_of`
   (`services/npc_world.py:199-219`) e **ignora `faction_id`**, que é o campo que a semente
   grava; `reputation.npc_faction_id` lê `faction_id`/`faction` e o grafo, mas ignora a
   troca de lado da 304 (`services/reputation.py:330-344`). Patente de NPC não existe: a
   301 só modela patente do **jogador** (`services/faction_membership.py:224-233`,
   `data/faction_membership.json:19-25`).

Objetivo: um bloco determinístico `<SOBRE_VOCE>` + `<MOTIVACOES_INTERNAS>` + o
complemento de `<O_QUE_VOCE_SABE>`, montado em Python, sem chamada LLM nova, com
orçamento fixo. **Regra de ouro aplicada ao NPC:** ele só sabe o que viveu (a própria
posição, a própria fação, o lugar onde está) ou ouviu (ledger da 215). Ele nunca recebe
pressões, severidade, tensão, fase do diretor, números de relação, verdade de outros NPCs
nem notícias do **jogador** (`world.news`). O segredo da semente nunca aparece literal:
vira só "há um assunto que você evita: X".

## 2. Requisitos

### Montagem e orçamento

- **R1 — Módulo puro.** `services/npc_self.py` expõe `npc_self_blocks(state, npc_key,
  npc_row, *, pack_evidence_ids=()) -> NpcSelfBlocks` (§3). É puro: sem LLM, rede, RAG,
  escrita em disco nem mutação de `state`/`npc_row`. Mesmo estado → mesmo texto (byte a
  byte).
- **R2 — Injeção no prompt.** `npc_actor_node` insere, logo depois de `</ROLE>` e antes de
  `{atitude_block}` (`agents/npc.py:1060-1061`), os três blocos não vazios na ordem
  `<SOBRE_VOCE>`, `<MOTIVACOES_INTERNAS>`, `<O_QUE_VOCE_SABE>`. Bloco vazio não deixa tag
  nem linha em branco extra.
- **R3 — Nunca derruba o turno.** Qualquer exceção dentro de `npc_self_blocks` vira blocos
  vazios + `log_fallback("npc", "self_block_failed", exc)`, no mesmo padrão do bloco de
  companheiro (`agents/npc.py:1031-1041`).
- **R4 — Orçamento.** `<SOBRE_VOCE>` ≤ `SELF_MAX_CHARS = 700`; `<MOTIVACOES_INTERNAS>` ≤
  `MOTIVES_MAX_CHARS = 450`; `<O_QUE_VOCE_SABE>` ≤ `KNOWS_MAX_CHARS = 800` e ≤ o teto de
  linhas da faixa (R13). Corte por **linha inteira**, do fim para o começo, seguindo a
  prioridade de R6. O total adicionado nunca passa de 1.950 caracteres (~490 tokens por
  `context_builder.estimate_tokens`, `services/context_builder.py:121`).
- **R5 — Kill switch.** `RPG_NPC_SELF=on|off` (default `on`). Com `off`, os três blocos
  são vazios e o prompt fica idêntico ao de antes da spec (teste com spy que compara o
  `SystemMessage` com o flag `off` e com o módulo removido por monkeypatch).

### `<SOBRE_VOCE>` — quem eu sou, onde estou, o que é óbvio para mim

- **R6 — Linhas e prioridade.** Na ordem (e com esta prioridade no corte):
  1. identidade social: fação + patente (R7, R8);
  2. agenda: onde mora, por que está aqui, quando volta (R9);
  3. o lugar agora: rótulo público do estado do local atual e data de hoje (R10);
  4. relações da própria fação (R11), no máximo 2 linhas.
- **R7 — Fação do NPC (resolvedor único).** `self_faction(state, npc_key, row) -> str`
  resolve, nesta ordem: `world_projection.npc_affiliations[ref]` (troca de lado da 304) →
  `row["faction_id"]` → `row["faction"]` → componente do grafo → `leads` → `member_of`.
  Só vale id que é fação (`npc_world._is_faction`, `services/npc_world.py:187-196`). Fação
  `defeated` vira "você servia a X, que caiu". Sem fação → linha omitida (nunca "nenhuma").
- **R8 — Patente do NPC, derivada.** `self_rank(state, ref, row, fid) -> str`: líder
  (`npc_world.leaders()`, `services/npc_world.py:101-109`) → "líder"; senão, o primeiro
  `ranks[].name` do catálogo da fação cujo nome dobrado (sem acento, minúsculo) aparece em
  `row["role"]` ("Sargento da Legião" → "Sargento"); senão "membro". Não grava nada no
  estado.
- **R9 — Agenda (o que o NPC sabe da própria vida).**
  - Membro **ativo** da party: "Você viaja com o herói." e nada mais de agenda.
  - `RPG_NPC_WORLD=on` e há entrada em `npc_sim.npcs[ref]` (`services/npc_world.py:340-357`):
    - em casa (`pos.location_id == home`): "Você vive aqui, em {home}." + frase do arquétipo
      (`archetype_for`, `services/npc_world.py:222-232`; tabela fechada de 7 frases no módulo,
      uma por chave de `data/world/npc_agendas.json:3-96`);
    - fora de casa: "Você está de passagem; mora em {home} e chegou {há pouco|ontem|há
      dias}." + "Pretende voltar {amanhã|em poucos dias}." a partir de `pos.since_day` e
      `pos.return_day` (`services/npc_world.py:456-470`);
    - refugiado (`pos.refugee_from`): "Você fugiu de {home}{ por causa de <rótulo>}." (D3);
    - `status == "ferido"`: "Você ainda se recupera de um ferimento."
  - Modo `off`/sem entrada: só "Você vive em {home}." quando `home_location_id` resolve
    para um nome (`gamedata.get_location`), mais a frase do arquétipo.
  - Tempo sempre em palavras: as linhas de agenda **não têm dígitos**.
- **R10 — O lugar onde ele está.** Só o local **atual** da cena (onde NPC e herói estão
  juntos, portanto percebido por ambos): `location_states.public_label(row)`
  (`services/location_states.py:84-92`) do `world_projection.location_states[current_location_id]`
  ("em festa: Festa da Colheita", "sitiada"…); mais `world_calendar.clock_date_label`
  (`services/world_calendar.py:253`, mesmo uso de `agents/storyteller.py:1326`). Nunca o
  estado de outro local, nunca `severity`, `cause`, `crisis_id` nem pressão.
- **R11 — Relações da fação "só se ele saberia".** Para a fação F do NPC (R7, não
  derrotada), cada par de `world_sim.relation_bands` que contém F com banda `guerra` ou
  `alianca` (`services/faction_relations.py:80-90`, `:150-163`) vira "Sua fação está em
  guerra com Y." / "Sua fação é aliada de Y." **somente se** (a) o NPC é líder de F, **ou**
  (b) a banda **não** mudou hoje — o `event_id` de `faction_relation_changed` recalculado
  para o dia atual (`world_director.event_id(game_id, "faction_relation_changed", day, a,
  b)`, `services/world_engine.py:364-375`, `services/world_director.py:307-316`) não está
  no `event_log` —, **ou** (c) esse evento está no ledger do NPC
  (`npc_knowledge.known_subject_ids`, `services/npc_knowledge.py:787-794`). Nunca o valor
  numérico nem as bandas intermediárias `hostil`/`cordial`. Y secreta (R12) e
  desconhecida do jogador → linha omitida. Máximo 2 linhas, guerra antes de aliança,
  desempate por id.
- **R12 — Fação secreta.** Se F tem `secret: true` em `data/faction_membership.json`
  (ex.: `mao_sombria`, `:42-44`) ou visibilidade ≠ `public` no grafo, e
  `faction_intel[F].known` é falso: a linha de R7 vira "Você serve em segredo a uma
  irmandade que não pode ser nomeada; nunca admita isso." (sem o nome) e R11 é omitida.
  Com `known` verdadeiro, usa o nome e acrescenta "nunca admita isso a estranhos." (D4)

### `<MOTIVACOES_INTERNAS>` — semente da 297/306

- **R13 — Persistir a semente na ficha.** Novo campo opcional de runtime
  `npcs[key]["seed_motives"] = {desire_id, fear_id, secret_id, contradiction_id,
  mannerism_id}` (só ids). Escritores únicos: `_submit_generated_npc`
  (`agents/npc.py:574-602`) quando `seed is not None`, e `shared_pool.materialize_npc`
  (`services/shared_pool.py:747-760`) quando `entry.seed is not None` (D2). Ids que não
  existem em `data/npc_seed_tables.json` são descartados na leitura. O campo **não** entra
  em `DOCUMENT_ALLOWLIST` (`services/shared_pool_models.py:38-55`), na view da API
  (`services/npc_layers.py:251-291`, whitelist) nem no dossiê.
- **R14 — Conteúdo.** "Você deseja: {desejo}." · "Você teme: {medo}." · "Sua contradição:
  {contradição}." · "Seu jeito: {maneirismo}." (rótulos de `npc_seed.seed_labels`,
  `services/npc_seed.py:187-210`) + uma instrução fixa: "Isso guia o que você faz e
  evita; não recite estas linhas." Se houver `secret_id` com tópico em
  `data/npc_secret_topics.json` (R15): "Há um assunto que você evita: {tópico}. Se o
  jogador tocar nele, desconverse ou se irrite." Sem tópico → a linha do segredo é
  **omitida** (fail-closed).
- **R15 — Tópico do segredo, arquivo próprio.** `data/npc_secret_topics.json` mapeia cada
  um dos 44 `secrets[].id` de `data/npc_seed_tables.json:161-205` para um tópico vago
  (ex.: `sec_desertor` → "seu passado de armas"; `sec_nao_sabe_ler` → "cartas e papéis
  escritos"). Arquivo separado para não tocar a tabela sob revisão D8 da 297. Lint em
  `scripts/validate_content.py`: todo id existe na tabela; tópico ≤ 60 caracteres; o
  tópico não contém o `label` do segredo nem compartilha com ele palavra de ≥ 5 letras
  (após dobrar acento/caixa).
- **R16 — NPC canônico sem semente.** Sem `seed_motives`, o bloco é vazio. Traços ocultos
  continuam fora do prompt (`services/npc_layers.py:233-235`: "hidden nunca sai daqui pra
  cima"). Lore curada de NPC ("Voz:"/"O que sabe:", revisão §3) fica fora (ver Fora de escopo).

### `<O_QUE_VOCE_SABE>` — o que ele ouviu (ledger 215, não as notícias do jogador)

- **R17 — Só com `RPG_NPC_KNOWLEDGE=on`.** Com `off`/`shadow` o bloco é vazio (shadow
  continua byte a byte, `services/context_builder.py:620-634`).
- **R18 — Complemento sem duplicar o pack.** O pack continua injetando as linhas do gate
  como hoje (não muda `context_builder`, nem a observação do eval protegido
  `npc_knowledge`, `evals/core/adapters.py:997-1011`). `npc_knowledge_block` ganha os
  parâmetros `limit: int | None = None` (None = teto da faixa, `_lines_cap`,
  `services/npc_knowledge.py:990-1004`) e `exclude_ids: Collection[str] = ()`; o
  `npc_actor` passa `exclude_ids=pack.evidence_ids` (`services/context_builder.py:482-486`).
  Resultado: o bloco só traz o que o pack cortou por orçamento. Faixa `hostil` (teto 0)
  → bloco vazio. Assinatura secreta não revelada continua falhando fechado
  (`services/npc_knowledge.py:835-837`).
- **R19 — Nunca `world.news`.** Nenhum dos três blocos lê `world.news`,
  `world_sim.perceived_ids` ou `npc_beliefs` (crenças do **jogador**, 304).

### Não-vazamento (testes obrigatórios)

- **R20 — O motor não fala pelo NPC.** Com um estado que tenha `world_sim.pressures`,
  `bands`, `crises` (com `severity`), fase do diretor, `faction_relations` numéricas,
  `npc_sim` de **outro** NPC, `world.news` com frase-sentinela e um `route_blocked` do
  motor em outra região fora do ledger, os três blocos não contêm: nenhum valor numérico
  dessas estruturas, as palavras `severidade|tensão|pressão|crise|fase`, a sentinela de
  `world.news`, o nome/posição do outro NPC, o texto do `route_blocked`.
- **R21 — Segredo nunca literal.** Para cada um dos 44 segredos, com o NPC semeado com
  ele, o `SystemMessage` inteiro capturado por spy não contém o `label` do segredo.
- **R22 — Sem números da relação/patente.** Fora da linha de data (R10), os blocos não
  têm dígitos.
- **R23 — Campo privado.** `api.format_response` e `dossiers.build_dossiers` não contêm a
  chave `seed_motives` (padrão de `tests/test_spec298_visibilidade.py:89-95`).

### Compatibilidade

- **R24 — Save antigo.** NPC sem `seed_motives`, sem `faction_id`, sem `npc_sim` ou com
  ledger legado carrega e conversa; os blocos só ficam menores. `seed_motives` sobrevive
  ao round-trip `persistence` (`persistence.py:742`, `:1082` passam a linha inteira via
  `coalesce_runtime_npcs`, `services/entity_identity.py:130-163`).
- **R25 — Telemetria sem conteúdo.** Um `log_event("npc", "self_block", sections=[...],
  chars=N, truncated=bool)` por invoke; nunca o texto.

### Fora de escopo

- Chamada LLM nova, structured output novo ou campo novo em `NPCResponse`.
- Mudar o pack (`context_builder`), o gate da 215, a cota `current_state` ou o eval
  protegido `npc_knowledge` (relock pendente da 298 R23 é outra tarefa).
- Restringir `<FACÇÕES_DO_MUNDO>` (risco 1.6 da revisão, `agents/npc.py:968-976`) e mexer em
  `faction_reveals`.
- Semente com pool `off` (proposta R11) e pesos de raça por região.
- Lore curada de NPC canônico ("Para o narrador:"/"Voz:"/"O que sabe:" de `npcs.txt`) como
  campos estruturados.
- Patente de NPC persistida, promoção de NPC, `faction_events` da 301 (P2-1) e o lado
  "relação entre fações muda missão/desconto" da proposta R7.
- O narrador e o planner (SPEC-309, SPEC-311); regra de ouro do pack (SPEC-308).
- Preço/estoque explicado pelo mercador (proposta R9, SPEC-311).
- Marcar como "percebido pelo jogador" o que o NPC contar (é diálogo; canal futuro).

## 3. Design técnico

**Arquivos novos**

- `services/npc_self.py` — montagem dos blocos (R1–R16, R20–R22, R25).
- `data/npc_secret_topics.json` — `{ "<secret_id>": "<tópico vago>" , ... }`, 44 chaves,
  com `"_doc"` (R15). Conteúdo para revisão do dono (D5).
- `tests/test_spec310_npc_self.py` — unitários do módulo.
- `tests/test_spec310_npc_prompt.py` — spy no `npc_actor_node` (padrão
  `tests/test_spec301_llm.py:146-151`, `:179-182`).
- `tests/test_spec310_no_leak.py` — R20–R23.

**Arquivos alterados**

- `agents/npc.py` — chamar `npc_self_blocks` depois de `pack` (`:956-964`) e injetar (R2);
  `_submit_generated_npc` grava `seed_motives` (R13).
- `services/shared_pool.py` — `materialize_npc` copia `entry.seed` → `seed_motives` (R13, D2).
- `services/npc_knowledge.py` — `npc_knowledge_block(state, npc_id, limit=None,
  exclude_ids=())`; `_lines_cap` ganha alias público `lines_cap` (R18).
- `scripts/validate_content.py` — lint de R15.
- `.env.example` — `RPG_NPC_SELF=on` com uma linha de comentário.

**Schemas / assinaturas**

```python
# services/npc_self.py
SELF_MAX_CHARS = 700
MOTIVES_MAX_CHARS = 450
KNOWS_MAX_CHARS = 800
MAX_RELATION_LINES = 2

@dataclass(frozen=True)
class NpcSelfBlocks:
    sobre_voce: str = ""      # "<SOBRE_VOCE>\n...\n</SOBRE_VOCE>" ou ""
    motivacoes: str = ""      # "<MOTIVACOES_INTERNAS>\n...\n</MOTIVACOES_INTERNAS>" ou ""
    o_que_sabe: str = ""      # "<O_QUE_VOCE_SABE>\n...\n</O_QUE_VOCE_SABE>" ou ""
    def text(self) -> str: ...   # blocos não vazios unidos por "\n"

def mode() -> Literal["on", "off"]: ...                      # RPG_NPC_SELF
def self_faction(state: dict, npc_key: str, row: dict) -> str: ...
def self_rank(state: dict, ref: str, row: dict, faction_id: str) -> str: ...
def agenda_lines(state: dict, npc_key: str, row: dict) -> list[str]: ...
def place_lines(state: dict) -> list[str]: ...
def relation_lines(state: dict, ref: str, faction_id: str) -> list[str]: ...
def motive_lines(row: dict) -> list[str]: ...
def npc_self_blocks(
    state: dict, npc_key: str, npc_row: dict, *, pack_evidence_ids: Collection[str] = ()
) -> NpcSelfBlocks: ...
```

```python
# runtime: state["npcs"][key]
"seed_motives": {
    "desire_id": "des_...", "fear_id": "med_...", "secret_id": "sec_desertor",
    "contradiction_id": "con_leal_oportunista", "mannerism_id": "man_..."
}
```

**Exemplo de saída** (Sargento da Legião no Anel de Ferro, motor `on`, 215 `on`):

```
<SOBRE_VOCE>
Você é Sargento da Legião de Ferro.
Você está de passagem; mora no Anel de Lama e chegou ontem. Pretende voltar em poucos dias.
Aqui, agora: em festa: Festa da Forja. Hoje é 12 de Brasa.
Sua fação está em guerra com os Filhos da Chama Azul.
</SOBRE_VOCE>
<MOTIVACOES_INTERNAS>
Você deseja: ser promovido antes do inverno.
Você teme: ser mandado para a fronteira.
Sua contradição: leal até aparecer uma oferta melhor.
Há um assunto que você evita: seu passado de armas. Se o jogador tocar nele, desconverse ou se irrite.
Isso guia o que você faz e evita; não recite estas linhas.
</MOTIVACOES_INTERNAS>
```

(Rótulos de desejo/medo ilustrativos; os reais vêm de `data/npc_seed_tables.json`. Ids de
fação/local reais: `legiao_ferro`, `filhos_chama_azul`, `na_anel_ferro`, `na_anel_lama`.)

**Frases de arquétipo** (constante no módulo, chaves de `npc_agendas.json`):
`sedentario` → "Você raramente sai daqui."; `mercador_itinerante` → "Você vive de levar
mercadoria às regiões vizinhas."; `patrulheiro` → "Você faz ronda pela região.";
`peregrino` → "Você peregrina entre santuários."; `mensageiro` → "Você leva recados de
um lugar a outro."; `lider_residente` → "Você governa daqui."; `lider_em_campanha` →
"Você conduz sua gente em campanha."

## 4. Plano passo a passo

### Etapa 1 — Fação e patente do NPC

1. **Testes** (`tests/test_spec310_npc_self.py`): `test_faction_prefere_affiliation_da_304`
   (projection vence `faction_id`); `test_faction_le_faction_id_da_semente` (linha com só
   `faction_id`); `test_faction_lider_por_aresta_leads`; `test_faction_invalida_omitida`;
   `test_rank_lider`; `test_rank_por_role_sem_acento` ("sargento da legião" → "Sargento");
   `test_rank_default_membro`; `test_faction_derrotada_vira_passado`;
   `test_faccao_secreta_sem_intel_sem_nome` (`mao_sombria`, R12);
   `test_faccao_secreta_com_intel_nomeia_e_pede_sigilo`.
2. **Implementação:** `self_faction`, `self_rank`, linha 1 de R6.
3. **Verificação:** `bash scripts/dev/py.sh -m pytest tests/test_spec310_npc_self.py -q`.

### Etapa 2 — Agenda e lugar

1. **Testes:** `test_agenda_em_casa_com_frase_de_arquetipo`;
   `test_agenda_de_passagem_sem_digitos` (since/return → "ontem"/"em poucos dias");
   `test_agenda_refugiado`; `test_agenda_ferido`; `test_agenda_party_ativa_so_viaja`;
   `test_agenda_modo_off_usa_home` (`RPG_NPC_WORLD` off); `test_lugar_rotulo_publico_e_data`;
   `test_lugar_nunca_outro_local_nem_severidade` (estado `cerco` com `severity` em outro
   local e no atual: só o rótulo do atual aparece, sem `severity`).
2. **Implementação:** `agenda_lines`, `place_lines`.
3. **Verificação:** mesmo arquivo verde.

### Etapa 3 — Relações da fação

1. **Testes:** `test_relacao_guerra_conhecida_por_membro`;
   `test_relacao_mudou_hoje_membro_nao_sabe` (event_id do dia no `event_log`);
   `test_relacao_mudou_hoje_lider_sabe`; `test_relacao_mudou_hoje_no_ledger_sabe`;
   `test_relacao_sem_numero_nem_hostil_cordial`; `test_relacao_max_duas_linhas_ordem`;
   `test_relacao_com_faccao_secreta_desconhecida_omitida`.
2. **Implementação:** `relation_lines`.
3. **Verificação:** mesmo arquivo verde.

### Etapa 4 — Semente na ficha e motivações

1. **Testes:** `test_submit_grava_seed_motives` (gerar NPC com pool `shadow` + store em
   memória, padrão dos testes da 297); `test_materialize_copia_seed_motives`;
   `test_seed_motives_fora_da_allowlist_do_pool`; `test_motivos_labels_da_tabela`;
   `test_segredo_vira_topico_nunca_label`; `test_segredo_sem_topico_omitido`;
   `test_id_desconhecido_descartado`; `test_sem_semente_bloco_vazio`;
   `test_roundtrip_persistence_preserva_seed_motives`.
   Lint (`tests/test_content_validator.py` ou novo `tests/test_spec310_secret_topics.py`):
   `test_todo_segredo_tem_topico`, `test_topico_nao_repete_palavra_do_label`.
2. **Implementação:** `seed_motives` em `_submit_generated_npc` e `materialize_npc`;
   `motive_lines`; `data/npc_secret_topics.json` (44 tópicos); lint.
3. **Verificação:** arquivos da etapa + `tests/test_spec297_*.py` verdes.

### Etapa 5 — `<O_QUE_VOCE_SABE>` como complemento

1. **Testes** (`tests/test_spec310_npc_self.py`): `test_sabe_vazio_com_215_off_e_shadow`;
   `test_sabe_exclui_ids_do_pack`; `test_sabe_respeita_teto_da_faixa_hostil_zero`;
   `test_sabe_secreto_continua_fechado`; `test_npc_knowledge_block_default_compativel`
   (chamada antiga `npc_knowledge_block(st, id)` segue funcionando —
   `tests/test_npc_knowledge.py:410`).
2. **Implementação:** parâmetros novos em `npc_knowledge_block`; `lines_cap` público.
3. **Verificação:** `tests/test_npc_knowledge.py`, `tests/test_context_npc_gate.py`,
   `tests/test_eval_npc_knowledge.py` verdes **sem alteração**.

### Etapa 6 — Orçamento, kill switch e injeção no `npc_actor`

1. **Testes** (`tests/test_spec310_npc_prompt.py`, spy no `get_llm`):
   `test_prompt_tem_blocos_na_ordem_apos_role`; `test_bloco_vazio_sem_tag`;
   `test_orcamento_corta_por_prioridade` (estado com tudo cheio: cada bloco ≤ teto,
   relações cortadas antes da agenda); `test_flag_off_prompt_identico`;
   `test_excecao_no_modulo_nao_derruba_turno` (monkeypatch que levanta → turno responde,
   `log_fallback` chamado); `test_telemetria_sem_texto`.
2. **Implementação:** `npc_self_blocks` com corte; chamada em `agents/npc.py` após o pack.
3. **Verificação:** arquivos da etapa + `tests/test_npc_camadas.py`,
   `tests/test_spec298_visibilidade.py`, `tests/test_spec300_prompt.py`,
   `tests/test_spec301_llm.py`, `tests/test_npc_fallback.py` verdes.

### Etapa 7 — Não-vazamento

1. **Testes** (`tests/test_spec310_no_leak.py`): `test_motor_nao_fala_pelo_npc` (R20, estado
   "envenenado" descrito em R20); `test_44_segredos_nunca_literais` (R21, parametrizado,
   spy no prompt inteiro); `test_sem_digitos_fora_da_data` (R22);
   `test_seed_motives_fora_da_api_e_dossie` (R23); `test_world_news_do_jogador_ausente`.
2. **Implementação:** só correções que os testes apontarem.
3. **Verificação:** arquivos `tests/test_spec310_*.py` verdes; o coordenador roda a suíte
   completa 1× no `/spec-land`.

## 5. Critérios de aceite

- [ ] R1–R25 com teste nomeado nas etapas 1–7, todos verdes.
- [ ] `tests/test_npc_knowledge.py`, `tests/test_context_npc_gate.py`,
      `tests/test_eval_npc_knowledge.py` e `evals/` protegidos **sem alteração**.
- [ ] `scripts/validate_content.py` verde com o lint de R15.
- [ ] `uv run pytest` verde (suíte completa offline, no pouso).
- [ ] Nenhum `with_structured_output` novo (nada a guardar); o guard existente do
      `npc_actor` (`agents/npc.py:1116-1120`) intacto.
- [ ] Saves antigos continuam carregando (R24).
- [ ] Smoke §6 executado e registrado no cabeçalho.

## 6. Smoke test com LLM real

Staging ou local com DeepSeek, `RPG_WORLD_ENGINE=on`, `RPG_NPC_KNOWLEDGE=on`,
`RPG_NPC_WORLD=shadow` (como staging) e uma rodada com `on`, `RPG_SHARED_POOL=shadow`.
4–5 requests.

1. **Canônico com fação:** herói em `na_anel_ferro`, falar com o Comandante Thrace: "Quem
   é você e a quem serve?". Esperado: cita a Legião e o posto de comando; nenhum número.
2. **Guerra percebida:** forçar no save `relation_bands["filhos_chama_azul|legiao_ferro"]
   = "guerra"` (dia anterior) e perguntar "Como vão as coisas com a Chama Azul?". Esperado:
   fala da guerra. Repetir com o evento do mesmo dia: não afirma a guerra (pode especular).
3. **NPC semeado:** criar NPC genérico pelo router (pool `shadow`); conferir no save que
   `seed_motives` existe; perguntar sobre o tópico do segredo. Esperado: desconversa; a
   fala não contém o `label` do segredo (comparar com a tabela).
4. **Agenda (`RPG_NPC_WORLD=on`):** NPC mercador de passagem: "De onde você vem?".
   Esperado: cita a cidade de casa e que volta logo.
5. **Telemetria:** `log_event npc.self_block` com `chars` ≤ 1.950 em todos os turnos; 0
   `self_block_failed`.

## 7. Riscos & compatibilidade

- **Saves antigos:** campo novo opcional; leitores toleram ausência e ids inválidos (R13, R24).
- **MockLLM/FallbackLLM:** o MockLLM ignora o prompt, então só os testes com spy provam a
  injeção. FallbackLLM: caminho de erro do `npc_actor` não muda.
- **Quota/latência:** zero chamada nova; +200 tokens típicos, +490 no pior caso, por fala
  de NPC. Sem I/O novo além de leituras de JSON com cache (`lru_cache`).
- **Persona já pode conter o segredo literal.** No modo pool, o gerador recebe
  `segredo_pessoal` na semente (`agents/npc.py:446-459`) e pode escrevê-lo na persona, que
  já vai ao `<ROLE>` (`:1051`). Esta spec não piora isso, mas também não corrige; R21
  mede só os blocos novos + o prompt inteiro com persona neutra. Follow-up sugerido:
  validador de persona contra o label do segredo na 297.
- **A LLM pode contar ao jogador o que o NPC sabe.** É diálogo diegético (o NPC viu ou
  ouviu), coerente com a regra de ouro; o que ele conta não vira fato canônico nem
  "percebido" (fora de escopo).
- **Divergência de resolvedores de fação:** `self_faction` cobre a união; não altera
  `npc_world.npc_faction` nem `reputation.npc_faction_id` para não mudar 298/304. Unificar
  fica como follow-up.

## 8. Decisões do dono (recomendação em negrito; vale até ele dizer o contrário)

- **D1 — Pack × bloco próprio.** **Manter as linhas do ledger no pack e usar o bloco só
  como complemento (R18)**, para não mexer no eval protegido. Alternativa: mover tudo
  para o bloco (prompt mais limpo, mas exige nova versão do eval `npc_knowledge`).
- **D2 — Semente atravessa mundos?** **Sim: `materialize_npc` copia os motivos da
  `entry.seed`** (desejo/medo/segredo fazem parte da identidade do NPC do pool, como a
  persona). Alternativa: só no mundo de origem.
- **D3 — Refugiado diz por que fugiu?** **Sim, com o rótulo público do estado da casa**
  ("sitiada", "tomada pela praga") — ele viveu isso. Alternativa: só "você fugiu de X".
- **D4 — Fação secreta.** **Sem o nome enquanto o jogador não conhece a fação (R12).**
  Alternativa: sempre nomear e confiar na instrução "nunca admita".
- **D5 — Tópicos dos 44 segredos.** O executor escreve `data/npc_secret_topics.json`;
  **o dono revisa junto com a D8 da 297** (não bloqueia o pouso: tópico ausente = linha
  omitida).
- **D6 — Kill switch default.** **`RPG_NPC_SELF=on`** (o produto default já roda com
  muita coisa desligada, revisão §1.4). Alternativa: `off` + ligar no staging primeiro.
