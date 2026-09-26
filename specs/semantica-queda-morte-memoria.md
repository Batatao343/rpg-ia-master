# SPEC — Semântica canônica de queda, morte e memória narrativa

> **Status:** `in-progress`
> **Criada:** 2026-08-27 · **Atualizada:** 2026-09-17
> **Origem:** matriz B interrompida `20260827-141144-990850`, turnos 134 e 162
> **Depende de:** `conflito-12`, `checkpoints-morte`, `cronica-avancada`

## 1. Contexto & Objetivo

Nas duas quedas da B1 o evento correto foi `player_downed`, mas o
`ConflictSummary` incluiu o protagonista em `mortos` porque a flag interna
`dead` também representa a derrota que ainda aguarda “Continuar/Aceitar”. O
archivist gravou “Playtest-normal morreu no conflito” e essa falsidade poderia
contaminar RAG, Crônica e narração futura.

O objetivo é separar resultado mecânico transitório de fato histórico. Somente
`player_died`/memorial confirmado autoriza a palavra e o fato “morreu”.

## 2. Requisitos

- **R1 — Vocabulário fechado:** resultado do ator é `survived`, `downed`,
  `unconscious`, `dead`, `fled`, `surrendered` ou `captured`; precedência e
  combinações válidas vivem em Python.
- **R2 — Queda não é morte:** `death_pending` e `player_downed` classificam o
  protagonista como `downed`, mesmo que a engine use `dead=True` internamente
  até a escolha de checkpoint.
- **R3 — Morte confirmada:** somente memorial aceito ou `game_over` confirmado
  produz `player_died` e entrada em `mortos`.
- **R4 — Summary tipado:** `ConflictSummary` expõe `caidos` separadamente de
  `mortos`; `summary_facts` e texto fallback usam os campos corretos.
- **R5 — Evento exclusivo:** um mesmo `conflict_id` não pode publicar
  `player_downed` e `player_died` como se fossem o mesmo estágio.
- **R6 — Memória fail-closed:** arquivista, crônica, resumo e busca derivada
  recusam fato de morte do player sem evidência canônica do evento terminal.
- **R7 — Correção sem apagar história:** facts incorretos de saves anteriores são
  preservados para auditoria, mas quarentenados por evento na montagem de
  contexto; não se edita Codex, FAISS ou memória de outra campanha.
- **R8 — Apresentação:** prosa de queda pode ser dramática, mas não afirma morte
  definitiva antes da escolha. O recibo informa “queda/checkpoint disponível”.
- **R9 — Invariantes:** `narrative.false_player_death` compara texto/fatos com o
  outcome canônico e é coberto sem longrun.

### Fora de escopo

Alterar a UX da tela de morte, o número de checkpoints ou a letalidade.

## 3. Design técnico

- `services/conflict_summary.py`: classificador puro e campo `caidos`.
- `agents/combat.py`: passa outcome explícito ao resumo em vez de depender da
  flag interna sobrecarregada.
- `services/chronicle.py`/archivist: templates e facts orientados pelo evento.
- `playtest/invariants.py`: contrato texto↔evento sem heurística de Vitalidade.

## 4. Plano TDD

1. Reproduzir os turnos B1 134/162: `dead=True + death_pending=True +
   player_downed` gera `caidos`, nunca `mortos`.
2. Cobrir morte aceita, inimigo morto, aliado inconsciente, fuga e captura.
3. Provar que memória/Crônica não persistem “morreu” antes do memorial.
4. Cobrir dedupe/supersession e saves legados.

## 5. Critérios de aceite

### Adendo aprovado — 19/09

A proteção não exige um `player_downed` prévio: morte afirmada diretamente pelo
nome/sujeito do protagonista exige `player_died` do player na timeline atual ou
memorial. Quest, morte de NPC e evento de outra timeline não servem. Negações
diretas são preservadas. A invariante também roda sem evento de queda. Os
padrões são fechados; não se promete interpretação semântica irrestrita.
Plano/gates no [adendo pré-matriz](remediacao-local-contratos-pre-matriz.md).

- [x] Queda recuperável nunca entra em `mortos`.
- [x] Morte confirmada continua registrada uma única vez.
- [x] Archivist/RAG/Crônica usam a mesma semântica.
- [x] Invariante curta captura a falsidade observada na B1.
- [x] Suíte completa offline verde após a revisão de 17/09 (1681 passed).
- [ ] Smoke real dirigido de queda/memorial confirma a integração; B integral é gate global separado.

Revisão de 17/09: o template de `player_downed` também deixa de afirmar que o
herói já se levantou ou foi saqueado. A crônica mantém a escolha pendente até o
evento canônico seguinte. Regressão curta cobre queda versus morte confirmada.
O [gate real](../docs/fechamento-local-2026-09-17.md) depende da recarga DeepSeek.

## 6. Smoke real

No replay do par 1, inspecionar toda ocorrência de `player_downed`: summary,
eventos, fatos e narrativa devem dizer queda/derrota; “morte” somente após
`player_died` confirmado.

## 7. Riscos

Inimigos realmente mortos não podem ser reclassificados. A exceção vale somente
para o protagonista sob o protocolo explícito de checkpoint.
