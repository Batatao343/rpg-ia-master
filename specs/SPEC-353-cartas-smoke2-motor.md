# SPEC-353 — Cartas: correções de motor/backend do 2º smoke real do combate por cartas

> **Status:** `approved` (dono em autonomia total até 28/10 08:30; decisões do autor em §8 valem como aprovadas)
> **Criada:** 2026-10-28 · **Atualizada:** 2026-10-28
> **Origem:** smoke real de 28/10 na `main` `7c084cfc` (DeepSeek v4-flash, 26 turnos) — `docs/spec353/achados-smoke2.md`, estados `docs/spec353/smoke/state-*.json`, prints em `docs/spec353/smoke/`; log do servidor e `events.jsonl` no scratchpad do coordenador (`smoke2/server.log`, `smoke2/out/events.jsonl`)
> **Depende de:** SPEC-346 (rodada sem LLM, resumo final, `mech_log`) e SPEC-347 (`round_board`/`registro_rodada`) já na `main`; código das SPEC-328–334 na `main` (flags `off` no staging)
> **Desbloqueia:** SPEC-354 (tela; consome o contrato de §3.3) e ligar `RPG_CARD_DECK=on` no staging
> **Fronteira:** tela/layout/copy de componente é da **SPEC-354** (worktree `rpg-spec-354`). Esta spec entrega **dados, texto gerado no backend e o contrato da API**; não toca `web/`.
> **EXECUTOR_MODEL:** `Terra` (Sonnet), uma etapa por vez · **REVIEW_MODEL:** `Sol` (Opus) · **REVIEW_REQUIRED:** `true` (motor de conflito, contrato da API, prompt do resumo)
> **EVAL_AUTHORING_REQUIRED:** `false`. Nenhum evaluator, expected, baseline ou dataset de regressão muda. O golden da SPEC-330 fica **byte a byte** (R40).

---

## 1. Contexto & Objetivo

O 2º smoke real do combate por cartas (SPEC-346/347 pousadas) confirmou o que importava: **zero LLM nas 15
rodadas de meio de luta**, 5 chamadas na abertura, 2 no fim (resumo + arquivista). Mas achou 12 problemas de
motor/backend: uma Carta de Cena jogável que o motor recusa (e o id interno vaza no Livro), um resumo final
que inverte quem fez o quê, um registro que não fecha a conta do Sangromante, ordem da rodada trocada na
emboscada, nome de inimigo que é frase da narração, texto de Carta que promete um número que o motor não
usa, id cru de NPC na rodada 0, "Preparação 5/4" e uma dúzia de arestas de texto.

O objetivo é **fechar a conta entre texto, prévia, registro e motor** sem mudar nenhum número de Carta nem a
regra do Padrão/Elite (item 8 é regra, ver §1.2), e entregar à SPEC-354 o contrato do `round_board` que ela
pediu (§2.N).

Princípios: **mecânica é Python** (o resumo final recebe fatos estruturados e é validado contra eles, com
fallback determinístico); **o golden da SPEC-330 é intocado** — `tests/spec330_equivalence.py` e
`tests/fixtures/spec330_legacy_golden.json` sem diff, e a exclusão por caminho exato
(`tests/spec330_equivalence.py:23-27`) **não** é ampliada: todo registro novo nasce no nível do
orquestrador/agente, fora de `ct.resolve_turn` e `orch._resolve_reaction_effect` (os dois caminhos que o
golden hasheia, `tests/spec330_equivalence.py:114-150`); **sem flag nova** (R41).

### 1.1 Achados e causa no source

| # | Achado (prioridade) | Evidência | Causa no source |
|---|---|---|---|
| 1 | Carta de objeto de cena aparece na mão, entra na fila, e o motor recusa; o id vaza no Livro (P1) | `state-Haldor-d1.json`; print `5193459-…-fila.png`: "Carta 'cena_sino_rachado_fb2eb42a' não está preparada." 5× (t10–t14) | A carta temporária é criada por `services/scene_cards.py:639-677` (id `cena_<obj>_<hash>`, `:663`) e posta na mão por `sync_hand` (`:697-718`). A validação do agente a aceita (`agents/combat.py:1306,1321` via `in_hand`, `scene_cards.py:721-727`). Mas `cards.use_card` só aceita preparada/baralho/Virtude/`cartas_cena` (`services/cards.py:537-546`; `scene_card_ids` em `:150-152` lê só `player.cartas_cena`, do Sussurro). A recusa vira `out["logs"]` em `services/conflict_turn.py:449-453`, e o filtro do registro deixa a frase passar como "humana" (`services/round_log.py:42`). A mensagem usa o **id** (`cards.py:546`) |
| 2 | Resumo final inverte autoria (P2) | `state-Haldor-d5.json:507`: "O Sussurro Faminto… encontra teu torso" (o Sussurro foi a Última Ação do **herói**, `:1008-1019`; quem feriu o torso… foi o herói no inimigo). `state-Haldor-k4.json:473`: "sua espada… desce duas vezes… e a criatura desmorona" (o golpe errou; a criatura morreu do Sangramento). `state-Mirela-r6.json:445`: "o Corte de Troca não encontra alvo" (a Última Ação foi crítico de 20) | `outcome_facts` (`services/round_log.py:270-318`) só passa desfecho, nomes por categoria, arma, "Cartas decisivas: X" **sem ator, alvo nem resultado** (`decisive_cards`, `:330-339`) e o estado qualitativo. Ninguém diz quem deu o golpe final. A validação (`services/conflict_summary.py:349-376`) só pega "morto narrado vivo" e "capturado narrado livre". O prompt (`agents/combat.py:1863-1880`) não tem como saber a autoria |
| 3 | Custo em Vitalidade do Sangromante fora do registro (P2; R10 da 346) | print `5692211-Mirela-v1-1440-top.png`: Mirela 18→13 com 3 registrados; 13→4 com 6 | `_apply_player_card_mechanics` aplica `auto_dano` (`services/conflict_orchestrator.py:1332-1350`) e grava só um log com aritmética ("Vit N", descartado pelo filtro de `round_log.py:18-21`) e `class_mechanics` **sem** `actor_id`/`card_id` (`:1343-1348`, `_record_class_event` em `:1277-1278`). `mech_log` (`services/combat_preview.py:177-234`), `round_board` (`:282-418`) e `round_registry` (`round_log.py:152-223`) ignoram `class_mechanics`. Além disso, o texto da Carta não cita o custo: `render_card_text` (`services/card_effects.py:1505-1520`) não renderiza `mecanica_classe.auto_dano` (ex.: `data/cards/sangromante.json:24-26`, `data/cards/basicas.json:114`) |
| 4 | Emboscada: o Livro conta a rodada fora de ordem (P2) | print `5075833-…-pos-combate.png` | `round_registry` põe **sempre** herói/aliados antes dos inimigos (`round_log.py:161-218`), por regra da 346 R4. `round_board` segue a ordem real (`turn_spans`, `combat_preview.py:372-418`). `mech_log` lista ataques e **depois** todos os ticks (`:197-230`). Três superfícies, três ordens |
| 5 | Inimigo com nome de frase da narração e contagem divergente (P2) | `state-Haldor-k4.json:432,448`: "Criatura Além das Estacas" (da prosa "a criatura além das estacas veio"); Mirela: "Criatura da Fenda"; narração com três bandidos × tabuleiro menor | `hint_core` (`services/encounter_manifest.py:269-290`) corta locativos só por `_CORE_LOCATIVES` (`:244`), que não tem "além", "atrás", "sob", "sobre", "entre", "diante", "dentro", "fora", "junto", "acima", "abaixo", "perto de", e mantém o complemento "da fenda". "criatura" está no `_STOP` (`:127`), mas o complemento ("estacas", "fenda") vira token de conteúdo, então `is_generic_hint` (`:293-294`) dá falso. O scanner (que viu "Bandido") é descartado (`agents/combat.py:836-845`, `spawn_scanner_discarded`) e a dica vira grupo (`_display_enemy_name`, `:638-643`); o gerador do bestiário materializa "Criatura Além das Estacas" e a trava de identidade aceita porque divide o token "alem" (`:688-691`). Contagem: o narrador recebe só `more_requested` (`:3056-3058`); nada confere a prosa de entrada contra o N do manifesto |
| 6 | Texto da Carta ≠ prévia ≠ dano real (P2) | Golpe do Penitente: texto "Causa 3 de dano", prévia "7–14", golpes de 6–7 (print `4699240-…-previa.png`); `state-Haldor-d1.json:1165`: "9 vs 11 · crítico (dupla de 3) · 14 dano" | **Não é bug de motor nem de prévia.** O texto é o `dano_base` estático da Carta (`card_effects.py:1360-1377`; `data/cards/basicas.json:17`), usado na mão (`services/card_piles.py:629-630`). Prévia e motor usam o **mesmo** caminho (`combat_preview.py:114-131` = `conflict_turn.py:558-571`): base 3 + `early_game_damage_bonus` +2 (`combat_mechanics.py:85-97`) + modificadores = 7; crítico ×2 = 14. A prévia é **bruta, sem a defesa do alvo** por regra de ouro (`combat_preview.py:5-7`); o golpe real de 6 veio da Proteção do Anão-Eco (Carta revelada `bst_defesa_instintiva`, `state-Haldor-d1.json:666-668`; pipeline `services/conflict_damage.py:265-320`). As três superfícies dizem números diferentes **sem dizer por quê** |
| 7 | `npc_ketil` como nome na rodada 0 (P2) | print `4661367-Haldor-t1-390-combate.png` | Na abertura `on` o agente devolve `_board_opening_result` (`agents/combat.py:2208-2227`, função em `:2998-3098`) **antes** de gravar `combat_meta["scene_allies"]` (só em `:2270`, rodada 1). A view monta `participant_names` com inimigos + `party` + `scene_allies` (`api.py:2850-2856`) e cai no **id cru** (`api.py:2877`) |
| 8 | Inimigo a 0 de Vitalidade aguenta rodadas; crítico por dupla "frequente" (P2) | `state-Haldor-d1.json:640-647` (Anão-Eco elite, `vitalidade: 0`, ativo); mech_log com críticos abaixo da Esquiva | **Regra, não bug** (§1.2). Mas o registro não diz o que está acontecendo |
| 9 | "Preparação 5/4" depois do espólio (P2) | print `4908297-…-pos-espolio.png` | Com Baralho, a Carta do espólio entra no `deck` e `prepared_cards` é re-derivado do baralho (`services/card_rewards.py:269-280` → `_set_prepared_from_deck`, `:251-257`), sem teto de Preparação (o teto do Baralho é 12–24, `services/cards.py:410-411`). A API continua mandando `prepared_slots` do nível (`api.py:2427-2430`, `:2257`), e a tela conta as conhecidas marcadas `prepared` (`web/src/components/tabs/CombatDeckTab.tsx:40,45,91`). Dois modelos (Preparação × Baralho) no mesmo contador |
| 10 | Texto (P3) | `state-Haldor-d5.json:507`: "ferimento critico na região cabeça"; `state-Haldor-k4.json:487`: "Corda de Cânhamo (15m) (comum)"; "Haldor: condição desmoralizado renovada"; "Aguentar"/"Resistir" com "Fora de combate:…" em combate; Renegado (machado) com "Descarga Arcana"; "Eco da Boca" fora d'A Boca | (a) categoria crua e "na região X": `round_log.py:100,255`. (b) raridade crua entre parênteses: `agents/loot.py:535`. (c) nome do herói em vez de "Você" nas linhas de condição do motor (`_name(player)`), que passam pelo filtro humano (`round_log.py:27-28,193-195`). (d) texto `utilitaria` = "Fora de combate: …" (`card_effects.py:1409-1411`) e utilitárias entram no baralho por design (SPEC-328 R3; `cards.py:414`). (e) baralho do inimigo: a Carta vem das próprias/família/facção (`services/enemy_decks.py:209-241`); `bst_descarga_arcana` aparece 15× em `data/bestiary.json` — origem exata a confirmar na Etapa 0. (f) "Eco da Boca" é da região certa (`data/combat/cartas_de_cena.json:217-226`, `regioes: montanhas_afiadas`, tags `caverna`/`montanha`), mas a tag `montanha` a torna elegível em qualquer ponto da região (`scene_cards.py:184-198`) |
| 11 | Voto Sussurrado acerta e o inimigo ataca outro; fuga sem dado no registro (P3) | `state-Haldor-k4.json:448`: "Criatura…: Voto Sussurrado terminou." na mesma rodada; `state-Haldor-d5.json:874-879` (`chase.last_roll` existe, o `mech_log` não) | (a) Provocação é **probabilística** (50 % × multiplicador de Entropia, teto 90 %, `conflict_orchestrator.py:380-406`) e, com presságio `on`, o inimigo executa a intenção **congelada** (`:2393-2398`); a Provocação só é lida no próximo congelamento (`:242-261`). O texto diz "ele precisa atacar você" (`card_effects.py:1389-1390`). (b) A fuga entra no registro só como frase (`agents/combat.py:2276`); a rolagem (`chase.last_roll`) não vai ao `mech_log` |
| 12 | Resumo de vitória levou o turno a 18 s (P3) | timeout de 12 s do DeepSeek (log do coordenador) | Timeout do DeepSeek = 12 s (`llm_setup.py:484-489`); o resumo é texto livre sem `schema`, então o hedge da 319 não age (`llm_setup.py:1363`); `_fast_text` não tem orçamento próprio (`agents/combat.py:1702-1739`, chamada em `:1881-1890`), embora o resumo tenha fallback determinístico (`round_log.py:342-363`) |

### 1.2 Item 8 — regra ou bug (decidido: regra; registro explícito)

Texto das regras (`docs/design/valoria_conflict_migration_v2/01_VALORIA_REGRAS_CONSOLIDADAS_CONFLITOS.md`):

- §22 (`:976-984`): Vitalidade é a capacidade **imediata**; dano além dela vira **Ferimento** pelos limites de
  Gravidade. Vitalidade 0 **não** é queda.
- §27.2/§27.3 (`:1146-1155`): Padrão é derrotado **ao preencher o último Crítico**; Elite/Chefe usam o
  sistema completo (Última Ação → Estado Terminal). §24 (`:1028-1050`): Terminal sem aliado capaz = morte.
- §13.2/§13.3 (`:533-553`): **qualquer dupla nos dois dados mantidos** é acerto automático e Crítico; Vantagem
  rola 3d10 e mantém os 2 maiores.

O motor segue o texto: `death_flow.uses_full_death_flow` / `critical_spaces_full` /
`should_trigger_last_stand` (`services/death_flow.py:41-83`), `_check_terminal`
(`services/conflict_orchestrator.py:1424-1460`), excedente → Ferimento (`services/conflict_damage.py:329-345`),
espaços por Corpo (`gamedata.py:330-348`: Corpo 3 = 4 Leves, 2 Graves, 2 Críticos), dupla nos mantidos
(`services/conflict_resolution.py:85-106,187-197`). Um Elite de Corpo 3 a 0 de Vitalidade aguenta, por regra,
de 2 a ~6 golpes (cada um vira Ferimento; mesma região agrava). A frequência da dupla é exata: **10 %** em
2d10 e **14,5 %** em 3d10 mantendo 2 (maiores ou menores) — 145/1000 combinações. A Última Ação usa a
Vantagem extrema do texto (3 dados).

Logo **nada muda no motor**; muda o **registro** (R27–R29) e há um teste-oráculo que prova a sequência
(R30). Como não há mudança de mecânica, a arena só roda como não-regressão (R39).

## 2. Requisitos

Todos com o Baralho `on`, salvo indicação. Em `off`/`shadow`, o fluxo fica byte a byte como hoje, exceto onde
dito "dois modos".

### A. Carta de cena jogável (item 1, P1)

- **R1 — Objeto de cena é jogável.** `cards.use_card(state, card_id)` aceita uma Carta temporária de objeto
  (`card_id` com prefixo `scene_cards.TEMP_PREFIX`, registrada em `cards._TEMP_CARDS`) **quando ela está na
  mão** de `state["combat"]["pilhas"]["mao"]` (mesma regra de `scene_cards.in_hand`). Cobra Fôlego/frequência
  como qualquer Carta (`frequencia: "cena"`, `exaurir`). Fora da mão continua recusada.
- **R2 — Contrato mão ⇄ motor.** Toda Carta que `card_piles.public_view` põe na mão como jogável (com
  `valid_targets` não vazio) é aceita por `use_card` no mesmo estado. Teste de propriedade sobre a mão
  inicial dos 5 baralhos básicos + 1 objeto de cena.
- **R3 — Recusa sem id.** Toda mensagem de erro de `use_card`/`use_ruptura` usa o **nome** da Carta
  (`get_card(id)["name"]`), nunca o id. `round_log.py:42` continua deixando a recusa passar (o jogador precisa
  saber), agora legível: "Derrubar (Sino Rachado) não pôde ser jogada."
- **R4 — Invariante de ids.** Nenhuma linha de `round_registry`, `mech_log`, `round_board[*].ator_nome/
  alvo_nome/carta_nome/efeito` ou do resumo final casa
  `\b(cena|bas|dev|san|cor|arc|vig|bst|inf|mon|npc|enemy|fallback|sus)_[a-z0-9_]+\b`.

### B. Resumo final com autoria (item 2, P2)

- **R5 — Fatos de autoria.** `round_log.outcome_facts` ganha, **em linguagem e sem dígitos**, uma linha por
  evento da **rodada final** (na ordem cronológica de R12): `<Ator> <verbo> <Carta|arma> em <Alvo>: <resultado
  sem número>` (ex.: "Você executou a Última Ação com Sussurro Faminto em Anão-Eco: acerto crítico, ferimento
  crítico no torso."; "Sangramento corroeu Criatura…"). As "Cartas decisivas" saem e dão lugar a estas linhas.
- **R6 — Golpe final explícito.** Fatos incluem `Golpe final: <quem/o quê> em <quem>` para cada queda/morte da
  rodada e `Quem derrubou o herói: <nome>` (ou "o dano contínuo de <condição>") no desfecho do herói. Fonte:
  `out["final_blows"]` (R7). Quando o último golpe do herói errou, o fato diz isso: "Seu último golpe errou."
- **R7 — Registro do golpe final (nível orquestrador).** `conflict_orchestrator` grava
  `out["final_blows"]: list[{target_id, kind: "ataque"|"dano_continuo"|"auto_dano"|"ultima_acao",
  by_actor_id: str|None, card_id: str|None, condition: str|None}]`:
  - ataque: no merge de `_resolve_actor_turn` (perto de `:1772-1777`), para cada id novo em
    `sub["deaths"]`/`sub["terminal"]`/`incapacitated`, o último ataque do `sub` que acertou esse alvo;
  - DoT: em `_tick_conditions_v4` (`:312-357`) quando o tick leva à queda;
  - auto_dano: em `_apply_player_card_mechanics` (`:1332-1350`).
  Nada disso entra em `ct.resolve_turn` nem em `_resolve_reaction_effect` (R40).
- **R8 — Validação de autoria.** `conflict_summary.validate_attribution(text, facts: OutcomeFacts) ->
  list[str]` (determinística, por oração, mesma técnica de `_subject_hit`, `conflict_summary.py:361-366`):
  - V1: Carta jogada **pelo herói** na mesma oração que marcador de dano no herói ("teu/tua/seu/sua" +
    região do corpo, "te atinge/acerta/rasga/encontra", "em você") → violação;
  - V2: Carta do herói que **acertou** na mesma oração que termo de falha ("não encontra", "erra", "falha",
    "corta o ar", "escapa da mão") → violação; Carta do herói que **errou** com termo de acerto/queda
    ("acerta", "rasga", "desmorona", "tomba", "cai", "morre") → violação;
  - V3: arma/golpe do herói ("tua/sua <arma>", "teu/seu golpe") com verbo de queda do inimigo quando o golpe
    final (R7) **não** foi do herói → violação.
  Violação em `validate_narrative_text` **ou** `validate_attribution` → fallback determinístico (R10). Evento
  `combat.outcome_attribution_rejected` com a lista de códigos (V1/V2/V3), sem o texto.
- **R9 — Prompt.** O bloco `<fatos>` (`agents/combat.py:1871-1873`) recebe as linhas de R5/R6 e a regra
  "Cada ação tem um autor: nunca atribua a Carta de um combatente a outro." O resto do prompt fica.
- **R10 — Fallback com autoria.** `deterministic_outcome_text` acrescenta, sem dígitos, a frase do golpe
  final (R6) — ex.: "O Sangramento termina o serviço: Criatura Além das Estacas tomba." — e nunca cita Carta
  com autor trocado.
- **R11 — Oráculo com textos reais.** Os três textos do smoke (§1.1, item 2) são rejeitados por R8; três
  textos corretos escritos à mão a partir dos mesmos fatos passam.

### C. Registro que fecha a conta e na ordem certa (itens 3 e 4, P2)

- **R12 — Uma ordem só.** `round_registry`, `mech_log` e `round_board` seguem a **mesma** ordem cronológica:
  `out["turn_spans"]` (SPEC-347 R14.1), com o tick de DoT no início do turno de quem sofre (como já faz
  `round_board`, `combat_preview.py:375-377`), reações na posição em que ocorreram, Última Ação e eventos fora
  de turno no fim, Cartas de Cena e status por último. A regra "herói primeiro" da 346 R4 cai (decisão D1).
  Sem `turn_spans` (save antigo/`off`): a ordem de hoje.
- **R13 — Auto-dano tem linha.** `_record_class_event(out, "self_harm", …)` passa a levar `actor_id` e
  `card_id`. `mech_log`: `Você · Corte de Troca · custo · 3 Vitalidade`. Registro: "Você paga 3 de
  Vitalidade por Corte de Troca." `round_board`: entrada `tipo: "custo"` (R52) com `dano` = valor pago.
  Déficit além de 0 que virou Ferimento aparece na mesma linha ("…, ferimento leve no torso").
- **R14 — Oráculo R10 estendido.** O teste de conta fechada da 346 (soma das linhas que miram o herói =
  queda de Vitalidade + excedente que virou Ferimento) inclui `auto_dano`, em 20 seeds, com o Sangromante e
  as Cartas `san_corte_troca`/`bas_san_corte_raso`.
- **R15 — Texto da Carta cita o custo.** O texto de regra gerado para a mão/Acervo/espólio (R18) acrescenta
  "Custa N de Vitalidade." quando `mecanica_classe.auto_dano` existe. `render_card_text` estático não muda
  (R18 é um renderizador novo).

### D. Spawn e contagem (item 5, P2)

- **R16 — Núcleo de dica com cabeça genérica.** `encounter_manifest.hint_core` corta também em "além",
  "atrás", "sob", "sobre", "entre", "diante", "dentro", "fora", "junto", "acima", "abaixo", "perto", "rente";
  e, quando a **primeira** palavra de conteúdo é um substantivo genérico do `_STOP` (criatura, inimigo, vulto,
  ameaça, agressor, atacante…), descarta o complemento introduzido por de/da/do/das/dos. Resultado:
  "a criatura além das estacas" → "criatura" (genérica); "criatura da fenda" → "criatura" (genérica);
  "o bandido da estrada" → "bandido da estrada" (cabeça não genérica, mantém). Com dica genérica, o scanner
  manda (346 R25), e "Bandido" deixa de ser descartado.
- **R17 — Contagem reconciliada na entrada.** `prose_guard.count_drift(text, manifest) -> list[dict]`
  detecta numeral por extenso/algarismo ligado ao nome de uma espécie do manifesto maior que o N ativo dela.
  Se houver drift, a narração de entrada ganha uma frase determinística no fim: "Só <N por extenso>
  <espécie> avança(m) contra você; o resto some na sombra." Evento `combat.entrance_count_reconciled`. Sem
  LLM extra.

### E. Texto da Carta = prévia = motor (item 6, P2)

- **R18 — Dano efetivo no texto.** Novo `card_text.effective_rule_text(player, card, *, target=None) -> str`:
  para efeitos de dano direto, troca "Causa N de dano" por "Causa E de dano" onde **E** sai de um helper
  único `combat_preview.effective_damage_base(player, card, target=None) -> tuple[int, str, list[str]]`
  (base, tipo, partes), extraído **sem mudar a conta** de `combat_preview.py:114-131`, e usado também pela
  prévia. Se E ≠ N, o texto mostra a origem: "Causa 7 de dano (3 da Carta + 2 de herói iniciante + 2 de
  <fonte>)". Usado na mão (`card_piles.public_view`), no Acervo (`api._cards_block`) e no espólio
  (`card_rewards`). `render_card_text` (estático, usado por lint e testes) não muda.
- **R19 — Prévia diz o que ignora.** `combat_preview.preview` mantém `dano_min/dano_max` brutos e passa a
  devolver `defesa_conhecida: int | None` (Proteção **pública** do alvo: condições visíveis com `stat
  protection` e `public_panel(target)["protecao"]`) e `dano_min_apos_defesa/dano_max_apos_defesa` só quando
  `defesa_conhecida` não é `None`. Nada oculto vaza (regra de ouro, `combat_preview.py:5-7`).
- **R20 — Registro diz por que caiu.** Quando a defesa do alvo absorveu parte do golpe, `mech_log` acrescenta
  `· Proteção −N` antes do dano final (o motor já sabe: `dres["log"]`, `conflict_damage.py:283-320`). O dado
  vai ao `atk` como `atk["absorvido"]` **gravado no nível do orquestrador** a partir do `sub` (R40), não dentro
  de `conflict_turn`.
- **R21 — Oráculo das três superfícies.** Para cada Carta de dano direto dos 5 baralhos iniciais, com seed
  fixa e alvo sem defesa: o E de R18 = `dano_min` da prévia = `dano_final` de um acerto não crítico do motor; e
  2E = crítico. Com alvo com Proteção pública P: `dano_min_apos_defesa` = `max(0, E−P)` = dano real.

### F. Nome exibível do participante (item 7, P2; pedido da 354)

- **R22 — Aliados de cena na abertura.** `_board_opening_result` grava `combat_meta["scene_allies"]` (a
  mesma lista de `agents/combat.py:2064`/`:2191`).
- **R23 — Nome nunca é id.** `api._combat_block` resolve nomes por: inimigos → party → `scene_allies` →
  `state["npcs"]` (por `id` ou chave) → `"Aliado"`/`"Inimigo"` conforme o lado. Nunca o id cru (`api.py:2877`
  e `:2885`). Vale para `positions[*].participant_name`, `engaged_names`, `registro_rodada` e `mech_log`.

### G. Queda do Padrão/Elite explicada (item 8, P2 — regra)

- **R27 — Linha "sem Vitalidade".** Quando um inimigo chega a 0 de Vitalidade e segue ativo, o registro
  ganha, uma vez: "<Nome> está sem Vitalidade — cada golpe agora abre Ferimentos." `round_board`: entrada
  `tipo: "queda"` com `efeito: "sem Vitalidade"`.
- **R28 — Quantos faltam, só se público.** Se o painel público revela o Corpo do inimigo (mesmo gate da
  prévia, `combat_preview.py:140-145`), a linha diz "faltam N Ferimentos Críticos". Senão, não diz número.
- **R29 — Crítico por dupla já explicado.** O rótulo `crítico (dupla de N)` da 346 R8 continua; o registro
  ganha "(dupla nos dados)" em crítico com total abaixo da Esquiva.
- **R30 — Oráculo da regra.** Teste com Elite Corpo 3 a 0 de Vitalidade, golpes roteirizados: Ferimentos
  sobem pela tabela, o 2º Crítico dispara Última Ação, depois Estado Terminal e morte sem aliado; Padrão cai ao
  2º Crítico sem Última Ação; Lacaio cai ao 1º Ferimento. Mais um teste das frequências exatas: 10 % (2d10) e
  14,5 % (3d10 mantendo 2), por enumeração com `resolve_attack`.

### H. Preparação × Baralho (item 9, P2)

- **R31 — A API diz qual modelo vale.** Com Baralho `on` e `player.deck` não vazio, `player_stats` ganha
  `baralho: {total: int, minimo: 12, maximo: 24, do_acervo: int}` e `prepared_slots` passa a `cards.DECK_MAX`.
  A flag `prepared` de cada Carta = "está no baralho". Com `off`: idêntico a hoje.
- **R32 — Invariante.** Em qualquer modo, o número de Cartas com `prepared: true` em `player_stats.cards` é
  ≤ `prepared_slots`. Teste: espólio aceito com 4/4 (`off`) cai no Acervo; com `on`, entra no baralho e
  `baralho.total` sobe 1, com o contador ≤ 24.
- **R33 — Rótulo é da 354.** O texto "Baralho N/24" e o painel são da SPEC-354. Esta spec só garante os campos.

### I. Arestas de texto (item 10, P3)

- **R34 — Ferimento em pt-BR.** Registro e fatos usam "leve/grave/crítico" (com acento) e "no braço / na
  perna / na cabeça / no torso" (preposição por região). Nunca "na região X".
- **R35 — Espólio sem raridade crua.** `agents/loot.py:535`: raridade entra como palavra só se não for
  `comum` ("Corda de Cânhamo (15m), item incomum, e 20 de ouro"); mapa com acento (incomum, raro, épico,
  lendário). `comum` some.
- **R36 — "Você" nas linhas do motor.** As linhas humanas vindas de `out["logs"]` trocam o nome do herói por
  "Você" (com concordância simples: "Você ganha a condição desmoralizado", "Sua condição Sangramento
  terminou"). Condições sempre com inicial maiúscula (nome do glossário).
- **R37 — Utilitária no conflito.** Em combate (mão), Cartas `utilitaria` mostram "Sem efeito no conflito. Fora
  dele: <hint>." e `valid_targets: []` com `invalid_reason: "fora_de_combate"`. Fora de combate e no espólio:
  "Fora de combate: <hint>." Quem decide tirar utilitárias do baralho é o dono (D6).
- **R38 — Coerência de conteúdo (sem número).**
  (a) Etapa 0 localiza de onde vem `bst_descarga_arcana` no Renegado. Regra nova de lint em
  `services/content_validator.py`: Carta de inimigo com `dano_tipo` arcano/abissal/elemental em criatura sem
  estilo/arquétipo conjurador (`arquetipo ∉ {conjurador, místico, abissal}` e todos os `attacks[*].type ==
  "melee"`) é `warning`; o `enemy_decks.build_enemy_deck` pula Cartas assim ao montar o baralho do inimigo
  (troca por outra da família; quantidade igual).
  (b) `data/combat/cartas_de_cena.json` `eco_da_boca`: `tags` passa a `["caverna"]` (só onde há caverna).
  Conteúdo, não número.

### J. Provocação e fuga (item 11, P3)

- **R39a — Provocação diz o que faz.** O texto de `taunt` (`card_effects.py:1389-1390`, também em R18) vira
  "Provoca o alvo{por}: a partir da próxima intenção, ele tende a atacar você". O registro da rodada em que a
  Provocação é aplicada diz "<Alvo> está provocado: a próxima intenção dele mira você (com chance)". Quando a
  Provocação **não** prende o alvo no congelamento, o registro da rodada seguinte diz "<Alvo> resiste à
  Provocação." (fonte: ausência de `special:taunt` em `_last_class_mechanics`, `conflict_orchestrator.py:398-404`).
  Regra do motor intocada (D4).
- **R39b — Fuga com dado.** A tentativa de fuga gera linha no `mech_log`:
  `Fuga · total 7 vs 11 · falhou` (de `chase.last_roll`), e entrada `round_board` `tipo: "jogada"`,
  `carta_nome: "Fugir"`, `resultado: "acerto"|"erro"`.

### K. Latência do resumo (item 12, P3)

- **R39c — Orçamento do resumo.** `_narrate_outcome` chama `_fast_text(..., budget_s=_OUTCOME_BUDGET_S)` com
  `_OUTCOME_BUDGET_S = 6.0` (constante, sem env, R41). Estourou o orçamento → usa o fallback determinístico
  (R10), evento `combat.outcome_narration_budget_exceeded` (`elapsed_ms`). A thread que ainda corre é
  abandonada sem efeito no estado (resultado descartado). Só o resumo final usa orçamento.

### L. Contrato do `round_board` pedido pela SPEC-354

Campos aditivos e opcionais (o front antigo continua funcionando):

- **R50 — `tipo`.** Toda entrada ganha `tipo ∈ {"jogada", "dano_continuo", "queda", "pressagio", "custo"}`
  (`custo` = R13). Ataque, Carta sem ataque, reação e fuga = `jogada`.
- **R51 — DoT com ator = fonte.** Entrada de tick: `ator_id/ator_nome` = quem aplicou a condição, quando
  conhecido; `alvo_id/alvo_nome` = quem sofre; `carta_nome` = nome da condição; `lado` = lado da fonte. Fonte
  desconhecida (save antigo, DoT de cena/clima): `ator_id: null`, `ator_nome` = nome da condição, `lado:
  "efeito"`. Fonte: mapa `combat_meta["fontes_condicao"]: {victim_id: {condition_name: source_actor_id}}`,
  mantido pelo **agente/orquestrador** comparando condições antes/depois de cada turno (o snapshot já existe,
  `conflict_orchestrator.py:225-226`) — nunca gravado na condição nem no ator (R40).
- **R52 — Ataque que só aplica condição.** Entrada com `efeito` preenchido ("Sangramento", "Cego 2
  rodadas", "Provocado") e `dano: null`.
- **R53 — Quedas e presságio como entradas.** "X cai", "X morre", "X desacorda", "sem Vitalidade" (R27) =
  `tipo: "queda"`, `ator` = quem caiu, `efeito` = frase curta. Presságio cumprido = `tipo: "pressagio"`,
  `ator` = inimigo, `efeito: "cumpre o presságio"`, a partir de `out["pressagios_cumpridos"]: [actor_id]`
  gravado no orquestrador onde hoje sai a linha "cumpre o que o presságio anunciava" (no `run_round`, ver
  `conflict_orchestrator.py:2393-2398`).
- **R54 — Registro da rodada final sobrevive ao fim do conflito.** `store_mech_log` roda também na rodada que
  encerra o conflito (já roda; confirmar), e `combat_meta["last_round_board"]` + `last_mech_log` **não** são
  apagados quando `pilhas` sai (`agents/combat.py:2694-2696`). A view (`api.py:3020-3025`) manda
  `registro_rodada` e `mech_log` quando `last_round_board` existe e o Baralho está `on`, **com ou sem**
  `pilhas`. A abertura de um conflito novo limpa os dois (`agents/combat.py:2080-2088`).
- **R55 — Nome exibível.** Todos os nomes do `round_board` seguem R23.

### M. Transversais

- **R40 — Golden intocado.** `git diff main -- tests/spec330_equivalence.py tests/fixtures/spec330_legacy_golden.json`
  vazio; `tests/test_card_effects_grammar.py` verde sem regenerar o golden. Todo campo novo de registro
  (`final_blows`, `absorvido`, `pressagios_cumpridos`, `fontes_condicao`, `class_mechanics[*].actor_id/card_id`)
  nasce fora de `ct.resolve_turn` e `orch._resolve_reaction_effect`. Teste usa `find_record_keys`
  (`tests/spec330_equivalence.py:46-57`) com os nomes novos sobre `LAST_STATE` e prova que nenhum aparece em
  actors/scene do golden.
- **R41 — Sem flag nova.** Nada em `config/flags.yaml`.
- **R42 — Telemetria.** Eventos novos (`combat.outcome_attribution_rejected`,
  `combat.entrance_count_reconciled`, `combat.outcome_narration_budget_exceeded`) entram em
  `docs/operacao/EVENTOS_DE_LOG.md` e no registro de eventos (`observability/events.py`).
- **R43 — Saves.** Campos novos de `combat_meta` são opcionais; save sem eles carrega (DoT sem fonte cai em
  R51 "efeito"; sem `turn_spans`, ordem antiga).
- **R44 — Guard de FallbackLLM** mantido no resumo; nenhum `with_structured_output` novo.

### Fora de escopo

- Tela, layout, rótulos de componente, ícones, onde o `RoundBoard` aparece, rótulo "Baralho N/24" — SPEC-354.
- Mudar qualquer número de Carta, a regra de crítico por dupla, a regra do Padrão/Elite, o teto 50–90 % da
  Provocação ou o congelamento do presságio (D4).
- Tirar utilitárias do baralho de conflito (D6: decisão do dono, com arena).
- Aumentar o spawn até o N do scanner (346 D8 continua).
- Hedge/timeout global do DeepSeek ou de outros nós (só o resumo final ganha orçamento).
- Router e roteamento (346 já tratou).

## 3. Design técnico

### 3.1 Arquivos novos

- `services/card_text.py` — `effective_rule_text(player: dict, card: dict, *, in_combat: bool, target: dict | None = None) -> str`
  (R15, R18, R37, R39a). Reaproveita `card_effects.render_effect` trocando só o trecho de dano e acrescentando
  custo/utilitária.
- `tests/fixtures/spec353_smoke.py` — os três resumos reais do item 2 e três corretos (R11); o texto de entrada
  com "três bandidos" (R17).
- Testes: `tests/test_spec353_scene_card.py`, `test_spec353_attribution.py`, `test_spec353_round_order.py`,
  `test_spec353_self_harm.py`, `test_spec353_spawn_hint.py`, `test_spec353_damage_text.py`,
  `test_spec353_participant_names.py`, `test_spec353_padrao_elite.py`, `test_spec353_deck_slots.py`,
  `test_spec353_text_polish.py`, `test_spec353_taunt_flee.py`, `test_spec353_outcome_budget.py`,
  `test_spec353_round_board_contract.py`, `test_spec353_golden_guard.py`.

### 3.2 Arquivos alterados

- `services/cards.py` — `use_card`: aceita temporária na mão (R1); mensagens com nome (R3).
- `services/conflict_orchestrator.py` — `final_blows` (R7), `self_harm` com `actor_id/card_id` (R13),
  `absorvido` no merge (R20), `pressagios_cumpridos` (R53). Nenhuma mudança de conta.
- `services/round_log.py` — ordem por `turn_spans` (R12), auto-dano (R13), fatos de autoria (R5/R6), fallback
  (R10), pt-BR de ferimento (R34), "Você" (R36), linha sem Vitalidade (R27/R28).
- `services/conflict_summary.py` — `validate_attribution` (R8).
- `services/combat_preview.py` — `effective_damage_base` (R18), `defesa_conhecida` (R19), `mech_log` com
  custo/Proteção/fuga/ordem (R12, R13, R20, R39b), `round_board` com R50–R53.
- `services/encounter_manifest.py` — `hint_core` (R16). `services/prose_guard.py` — `count_drift` (R17).
- `services/card_piles.py` (`_rule_text` → `card_text.effective_rule_text`), `services/card_rewards.py`
  (texto R18), `api.py` (`_cards_block` texto R18; `_combat_block` nomes R23; `player_stats.baralho` e
  `prepared_slots` R31; `registro_rodada` sem `pilhas` R54).
- `agents/combat.py` — `scene_allies` na abertura (R22), fatos/validação/orçamento do resumo (R9, R39c),
  `fontes_condicao` (R51), não apagar `last_round_board` (R54), reconciliação de contagem (R17).
- `agents/loot.py` — raridade (R35). `services/enemy_decks.py`, `services/content_validator.py` (R38a).
  `data/combat/cartas_de_cena.json` (R38b). `services/card_effects.py` — só o texto de `taunt` (R39a).

### 3.3 Formatos

Registro (rodada de emboscada, ordem real):

```
Anão-Eco ataca Você: acerto — 3 de dano.
Toque Gélido da Morte corrói Você: 3 de dano contínuo.
Você joga Golpe do Penitente em Anão-Eco: O ferro cai onde a fé já rachou; quem reza assim não pede perdão ao golpe. Acerto crítico — 14 de dano, ferimento grave no torso.
Anão-Eco está sem Vitalidade — cada golpe agora abre Ferimentos.
```

`mech_log`:

```
Você · Corte de Troca · custo · 3 Vitalidade
Você · Corte de Troca → Minotauro Esqueleto · 2d10 6 + 7 +2 = 15 vs 12 · acerto · Proteção −1 · 5 dano
Fuga · total 7 vs 11 · falhou
```

`round_board` (entrada de DoT, R51):

```json
{"tipo": "dano_continuo", "ator_id": "npc_ketil", "ator_nome": "Ketil", "lado": "aliado",
 "carta_id": null, "carta_nome": "Sangramento", "alvo_id": "fallback_criatura_1",
 "alvo_nome": "Criatura", "origem": "turno", "rotulo": "Dano contínuo",
 "resultado": "efeito", "dano": 1, "efeito": "−1 Vitalidade"}
```

Fatos do resumo (k4, sem dígitos):

```
Desfecho: vitória.
Você jogou Golpe do Penitente em Criatura: errou.
Ketil atacou Criatura: acerto, ferimento grave no braço.
Sangramento corroeu Criatura.
Golpe final: o Sangramento (dano contínuo) em Criatura. Seu último golpe errou.
Arma do herói: Espada Gasta. Herói: ileso.
```

`player_stats` com Baralho `on` (R31):

```json
{"prepared_slots": 24, "baralho": {"total": 13, "minimo": 12, "maximo": 24, "do_acervo": 5}}
```

## 4. Plano passo a passo

Cada etapa: testes primeiro → código → só os testes do escopo (`-n 2` no máximo). Suíte completa só no pouso,
pelo coordenador. Toda etapa roda também `tests/test_card_effects_grammar.py` (R40).

### Etapa 0 — Diagnóstico (sem código de produto)

1. Do `smoke2/out/events.jsonl` / `server.log` do coordenador: (a) a dica de alvo e o grupo do scanner no
   spawn de k4 e de Mirela (`spawn_scanner_discarded`); (b) de onde veio `bst_descarga_arcana` no Renegado
   (próprias × família × facção); (c) se o golpe de 6 do Penitente foi a Proteção da Defesa Instintiva
   (`mechanics_trace`). Anotar em §9. Se (c) **não** for Proteção, abrir P1 de motor nesta spec antes da
   Etapa 5.

### Etapa 1 — Carta de cena (R1–R4)

1. **Testes:** `test_object_card_in_hand_is_playable` (mão com `cena_*` registrada → `use_card` ok, Fôlego
   cobrado, exaurida); `test_object_card_not_in_hand_refused_by_name` (erro sem id); `test_hand_contract`
   (R2); `test_registry_never_has_internal_ids` (R4, sobre as 3 rodadas reais reconstruídas).
2. **Implementação:** `cards.use_card` + mensagens.

### Etapa 2 — Registro: ordem, auto-dano, contrato 354 (R12, R13, R14, R27–R29, R39b, R50–R55)

1. **Testes:** `test_ambush_order_same_in_three_surfaces` (inimigo primeiro em registro, `mech_log`,
   `round_board`); `test_self_harm_line_and_board_entry`; `test_r10_oracle_with_self_harm_20_seeds`;
   `test_zero_vitality_line_once` + `test_missing_criticals_only_if_public`; `test_flee_roll_in_mech_log`;
   `test_round_board_tipo_field`; `test_dot_actor_is_source` (Ketil → Sangramento → criatura) e
   `test_dot_unknown_source_is_efeito`; `test_condition_only_attack_has_efeito`;
   `test_falls_and_omen_entries`; `test_final_round_board_survives_end` (vitória e morte; view com
   `registro_rodada` sem `pilhas`); `test_new_conflict_clears_last_round_board`.
2. **Implementação:** orquestrador (registros), `round_log`, `combat_preview`, `agents/combat.py` (R51, R54),
   `api.py` (R54).

### Etapa 3 — Golpe final e resumo com autoria (R5–R11)

1. **Testes:** `test_final_blows_attack/dot/self_harm/last_stand`; `test_facts_have_actor_target_result`
   (sem dígitos); `test_attribution_rejects_smoke_texts` (3 reais); `test_attribution_accepts_correct_texts`
   (3 corretos); `test_fallback_names_final_blow`; `test_outcome_uses_fallback_on_attribution_violation`
   (LLM simulada devolve o texto real de d5).
2. **Implementação:** orquestrador, `round_log`, `conflict_summary`, prompt.

### Etapa 4 — Spawn e contagem (R16, R17)

1. **Testes:** `test_hint_core_generic_head_with_locative` ("a criatura além das estacas", "criatura da
   fenda", "o bandido da estrada", "o bandido mais próximo"); `test_scanner_accepted_on_generic_head`
   (scanner "Bandido ×3" + dica "criatura além das estacas" → Bandido); `test_count_drift_appends_sentence`;
   regressão dos testes da 346 R23–R25.
2. **Implementação:** `encounter_manifest`, `prose_guard`, `agents/combat.py`.

### Etapa 5 — Texto = prévia = motor (R15, R18–R21, R37, R39a)

1. **Testes:** `test_effective_damage_base_equals_preview_and_engine` (R21, 5 Posturas);
   `test_hand_text_shows_effective_damage_with_parts`; `test_self_harm_cost_in_text`;
   `test_preview_known_defense_only_public`; `test_mech_log_shows_absorbed`; `test_utility_text_in_combat`;
   `test_taunt_text_and_resist_line`.
2. **Implementação:** extrair o helper de `combat_preview.py:114-131` **sem mudar a conta** (o teste de
   prévia da SPEC-334 fica sem mudar expected); `card_text.py`; consumidores.

### Etapa 6 — Nomes, Preparação, arestas (R22, R23, R31–R36, R38)

1. **Testes:** `test_opening_sets_scene_allies`; `test_participant_name_never_raw_id` (abertura com Ketil);
   `test_deck_mode_slots_invariant` (R32, `on`/`off`); `test_wound_text_ptbr`; `test_loot_rarity_text`;
   `test_registry_uses_voce`; `test_enemy_deck_skips_caster_cards_for_melee` (quantidade igual);
   `test_eco_da_boca_only_in_caverna`.
2. **Implementação:** como §3.2.

### Etapa 7 — Orçamento do resumo (R39c)

1. **Testes:** `test_outcome_budget_exceeded_uses_fallback` (LLM simulada que dorme 7 s com relógio
   injetado; turno retorna em < 6,5 s; evento emitido); `test_outcome_within_budget_uses_llm`.
2. **Implementação:** `_fast_text(..., budget_s)` com `concurrent.futures` (1 worker, resultado descartado
   após o prazo).

### Etapa 8 — Guardas e não-regressão (R40–R44)

1. `test_spec353_golden_guard.py` (R40); `tests/test_card_effects_grammar.py`; testes da 346/347 sem mudar
   expected, **exceto** os que codificavam a ordem "herói primeiro" (346 R4 → R12, decisão D1) e o texto
   "Causa N" na mão (R18) — listar cada um em §9 com o motivo.
2. Arena de não-regressão: `docs/spec341/arena_spec341.py posturas --seeds 20:100`, níveis 1/3/5, em série;
   gravar `docs/spec353/arena.md`. Critério: cada Postura dentro de ±2 pp do `docs/spec346/arena-base.json`
   (o motor não muda; R1 só age com objeto de cena, que a arena não gera).
3. Eventos (R42), saves (R43).

## 5. Critérios de aceite

- [ ] Etapa 0 anotada em §9 (dica/scanner, origem da Descarga Arcana, golpe de 6)
- [ ] Item 1: testes da Etapa 1 verdes; invariante R4
- [ ] Item 2: testes da Etapa 3 verdes; os 3 textos reais rejeitados, os 3 corretos aceitos
- [ ] Item 3: linha de custo nas três superfícies; oráculo R10 com auto-dano em 20 seeds
- [ ] Item 4: mesma ordem nas três superfícies (emboscada e iniciativa do herói)
- [ ] Item 5: testes da Etapa 4 verdes
- [ ] Item 6: oráculo R21 nas 5 Posturas; texto da mão = dano efetivo
- [ ] Item 7: nenhum id cru na view da rodada 0
- [ ] Item 8: oráculo R30 (sequência e frequências 10 % / 14,5 %); linha "sem Vitalidade"
- [ ] Item 9: invariante R32 em `on` e `off`
- [ ] Itens 10–12: testes da Etapa 5/6/7 verdes
- [ ] Contrato 354 (R50–R55) com teste por campo
- [ ] Golden da 330 sem diff (R40); exclusão de `tests/spec330_equivalence.py` não ampliada
- [ ] Arena dentro de ±2 pp por Postura (`docs/spec353/arena.md`)
- [ ] Nenhuma flag nova; eventos registrados; saves antigos carregam
- [ ] Guard de FallbackLLM no resumo (sem `with_structured_output` novo)
- [ ] `uv run pytest` verde (suíte completa, coordenador, no pouso)
- [ ] Revisão independente `Sol` sem P0/P1 aberto
- [ ] **Smoke real §6 (coordenador)** executado e registrado em `docs/spec353/smoke-final.md`

## 6. Smoke test com LLM real (≤ 20 turnos; critério do coordenador)

API local `legacy`, flags de cartas `on` como no smoke 2 (`RPG_CARD_DECK`, `RPG_ENEMY_INTENT`,
`RPG_SCENE_CARDS`, `RPG_ENEMY_DECKS`, `RPG_CARD_REWARDS`, `RPG_COMBAT_NONLETHAL`), DeepSeek primário. Teto 20
turnos no total. Registrar em `docs/spec353/smoke-final.md` (trechos, sem segredos).

1. **Haldor (Devoto), Skallgard, com Ketil:** "Saco a espada e ataco o bandido mais próximo" → rodada 0 sem
   `npc_ketil` cru (R23); inimigos com nome de espécie (R16). Mão: texto do Golpe do Penitente = dano da
   prévia (R18). 3 rodadas: ordem igual no Livro, `mech_log` e `registro_rodada` (R12).
2. **Objeto de cena:** se a cena trouxer objeto, jogar a Carta dele → resolve, sem "não está preparada" (R1).
3. **Vitória:** resumo da IA sem autoria trocada (ou fallback com golpe final), `registro_rodada` presente no
   turno da vitória (R54). Espólio: "Preparação/Baralho" coerente (R31/R32); raridade sem parênteses crus (R35).
4. **Mirela (Sangromante):** 2–3 rodadas com Corte de Troca/Corte Raso → linha de custo e conta fechada (R13).
   Jogar até a queda → resumo sem "não encontra alvo" falso (R8) + Roda.
5. **Fuga (qualquer):** botão Fugir → `Fuga · total N vs M · …` no `mech_log` (R39b).
6. Latência: anotar o tempo do turno de desfecho; nenhum acima de ~8 s por causa do resumo (R39c).

## 7. Riscos & compatibilidade

- **Golden da 330:** o risco real é um registro novo escapar para `ct.resolve_turn`. Mitigação: R40 com teste
  dedicado e revisão Sol olhando cada `out[...] =` novo.
- **Ordem do registro (R12)** troca expected de testes da 346 que fixaram "herói primeiro"; é mudança decidida
  (D1), listada em §9.
- **`validate_attribution` (R8)** é heurística: falso positivo só custa trocar a prosa pelo fallback; falso
  negativo deixa passar um texto errado. Medir no smoke (§6) e registrar a taxa de rejeição.
- **R1 muda mecânica** (uma Carta antes inerte agora causa dano) — só com objeto de cena `on`; a arena não
  gera objeto. Sem impacto em balanço medido; registrar no CHANGELOG.
- **R18** muda o texto da mão para todo mundo com Baralho `on` (`off` usa o mesmo renderizador fora de combate;
  conferir que a aba de Cartas `off` só ganha o dano efetivo, sem perder palavras-chave).
- **R31** muda `prepared_slots` no `on`; a tela atual (até a 354) mostraria "5/24" — aceitável e verdadeiro.
- **MockLLM/FallbackLLM:** o resumo continua com guard; o orçamento só reduz latência.
- **Quota/latência:** nenhuma chamada nova; R39c corta a cauda do turno de desfecho.
- **Saves:** R43.

## 8. Decisões

### Do dono

- **D0 (28/10)** — Autonomia total até 08:30: spec nasce `approved` com as decisões do autor abaixo.
- **Princípios do pedido:** mecânica é Python; resumo com fatos estruturados e validado; golden da 330 intocado;
  nada de número de Carta mudado sem decisão; tela é da 354.

### Do autor (valem como aprovadas; o dono pode vetar na revisão)

- **D1 — Ordem cronológica em tudo (R12).** Revoga a ordem fixa "herói primeiro" da 346 R4. O jogador precisa
  ver a emboscada acontecer antes da resposta; três ordens diferentes são o achado.
- **D2 — Item 6 é texto, não motor.** Prévia e motor já usam o mesmo caminho; o texto passa a mostrar o dano
  efetivo e de onde vem (R18), a prévia diz a defesa que conhece (R19), o registro diz o que a Proteção tirou
  (R20). Nenhum número de Carta muda. Se a Etapa 0 provar que o 6 **não** foi Proteção, vira bug P1 aqui.
- **D3 — Item 8 é regra.** Evidência em §1.2. Só o registro muda; nada de arena além da não-regressão.
- **D4 — Provocação: deixar claro, não "fazer valer" já (R39a).** Fazer a Provocação furar o presságio
  congelado muda o balanço do Devoto (mais aggro garantido) e a semântica da SPEC-329/339. Fica o texto e o
  registro honestos. **Recomendação** para uma spec de balanço futura: Provocação aplicada antes do turno do
  inimigo troca o alvo do presságio se ele for um ataque, com arena por Postura.
- **D5 — Preparação vira Baralho no `on` (R31).** Com o Baralho ligado o teto que vale é 12–24; a API diz isso e
  a 354 troca o rótulo. Não se impõe o teto de 4 sobre o baralho.
- **D6 — Utilitárias no baralho de conflito:** fica como a 328 decidiu, com texto claro (R37). **Pergunta ao
  dono:** tirar utilitárias da compra em combate (mão mais limpa; pede arena)? Recomendação: **sim**, numa spec
  pequena com arena.
- **D7 — Orçamento de 6 s só no resumo (R39c).** O resumo tem fallback legível; esperar 12 s + segundo provedor
  não compensa. Constante em código, sem flag.
- **D8 — Contrato da 354 (R50–R55) é desta spec;** a 354 só desenha. `lado: "efeito"` é valor novo e a 354 o
  trata.
- **D9 — Conteúdo sem número (R38):** o baralho do inimigo pula Carta de conjurador em criatura de corpo a
  corpo (mesma quantidade) e "Eco da Boca" fica restrita a caverna.

### Para o dono confirmar (não bloqueiam a execução)

1. D6 (tirar utilitárias da compra em combate) — spec própria com arena.
2. D4 (Provocação furar o presságio) — spec de balanço própria.
3. Orçamento de 6 s (D7) — ajustar se quiser mais prosa e menos fallback.

## 9. Registro de implementação

(preencher na execução: Etapa 0, testes com expected alterado e motivo, arena)

**Decisões do coordenador (autonomia do dono, 28/10 madrugada):** D6 = sim, nesta spec: cartas `utilitaria` saem da compra em combate (continuam no Acervo/fora de combate), com arena de não-regressão ±2 pp por Postura; se sair da faixa, reverter só o D6 e registrar. D4 (Provocação valendo na mesma rodada) fica para spec de balanço própria — aqui só texto/registro honestos. D7 = 6 s aceito.
