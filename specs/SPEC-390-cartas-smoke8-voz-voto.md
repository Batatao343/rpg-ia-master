# SPEC-390 — Cartas: 3 arestas de texto do 8º smoke (Voto na voz "você", pronome da Provocação no herói, título da missão no recibo)

> **Status:** `in-progress` (04/11, coordenador, autorização do dono "manda bala"; escopo só de texto/apresentação)
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04
> **Épico:** SPEC-327
> **Origem:** smoke local da SPEC-389 ([docs/spec389/smoke-local.md](../docs/spec389/smoke-local.md), achados 1, 2 e 4; resumo em
> [docs/spec389/smoke.md](../docs/spec389/smoke.md) § Achados restantes).
> **Depende de:** SPEC-389 (na `main`).

---

## 1. Contexto & Objetivo

O 8º smoke real (SPEC-389) passou nos 10 itens locais e mediu a oferta de retrato no staging: 12 de 12 leituras com oferta.
Sobraram 3 achados de texto, e a política do dono é não deixar pendência, nem P3. As causas foram confirmadas no código:

| # | Achado | Causa (source) |
|---|---|---|
| A1 | O registro do Voto diz "Goblin, provocado por Hi4, muda de alvo." com o nome do herói | `services/conflict_orchestrator.py:2759` monta a linha com `_name(actors_by_id[new])`, e `round_log` a deixa passar como humana (`_HUMAN_LINE_RES`, `services/round_log.py:52`) sem trocar o herói por "você" |
| A2 | O recibo do turno mostra a missão concluída com título = id (`{"id":"q368","title":"q368"}`) | `services/turn_outcome.py:242` grava em `quests_completed` só os ids, e `public_outcome` (`:211-218`) usa o id como título quando o item é `str`. Vale para toda missão, não só para a seed |
| A3 | "Você está provocado: a próxima intenção dele mira Soldado (com chance)." | `services/round_log.py:340-343` usa o texto de presságio de inimigo ("a próxima intenção dele") também quando a vítima é o herói |

## 2. Requisitos

- **R1 (A1).** A linha do desvio do Voto/Provocação não traz o nome do herói. Quando quem provoca é o herói, a linha é
  "<Inimigo>, provocado por você, muda de alvo." em `mech_log`, registro, mensagem e `/game/history`. Quando quem provoca é
  outro ator, a linha mantém o nome dele. A troca acontece num ponto só: o motor marca o ator ou o `round_log` converte, a
  critério do executor, sem duplicar a lógica de nome do herói que o `round_log` já usa.
- **R2 (A2).** `public_outcome` devolve o título real de cada missão concluída. O desfecho guarda os títulos de forma aditiva,
  por exemplo um mapa `quest_titles` capturado do estado no fechamento, sem mudar o tipo de `quests_completed` nem o cálculo
  do `receipt_id`. Para saves antigos sem título, o fallback continua sendo o id. A UI exibe o título sem mudança no front, se
  já usa `title`; se não usa, o front passa a usar.
- **R3 (A3).** Quando a vítima da Provocação é o herói, a linha é "Você está provocado por <Inimigo>." (sem "a próxima
  intenção dele"). Quando a vítima é inimigo, o texto atual fica.
- **R4 (guardas).** Nenhum id cru, nem o nome do herói, nas superfícies de texto das seeds `13 voto` e `13 armadura`, nem no
  recibo da `14 entrega`. Tudo provado por teste com a API real (MockLLM). Sem flag nova; golden 330, avaliadores, arenas e
  `web/e2e/contracts` intocados; `api.py`, `agents/npc.py` e `services/conflict_orchestrator.py` não crescem.

### Fora de escopo

Balanço (SPEC-369), novas mecânicas, mudanças de layout.

## 3. Design técnico

- **R1.** De preferência o `round_log` converte, porque já conhece o nome do herói (`names`/`actors_by_id`) e a voz
  "você". A regex de `_HUMAN_LINE_RES` continua aceitando a linha.
- **R2.** `services/turn_outcome.py`: ao montar o desfecho, guardar `quest_titles = {id: title}` das missões que acabaram de
  fechar. `public_outcome` lê esse mapa.
- **R3.** `services/round_log.py:336-343`: ramo para a vítima "Você".

## 4. Plano

1. Testes vermelhos para R1–R3: `tests/test_spec390_text.py`, com as seeds `13 voto`, `13 armadura` e `14 entrega` pela API
   real.
2. Implementar.
3. Guardas globais (`test_error_envelope`, `test_no_silent_except`, `test_log_event_registry`, `test_size_budget`), ruff e
   tsc.
4. Registro no §9.

## 5. Critérios de aceite

- [ ] R1: o registro e o `/game/history` da `13 voto` mostram "provocado por você", e o nome do herói aparece 0 vezes.
- [ ] R2: o recibo da `14 entrega` traz o título "Caça". Um save antigo sem `quest_titles` mostra o id.
- [ ] R3: a vítima herói mostra "Você está provocado por <Inimigo>.". A vítima inimigo mantém o texto atual.
- [ ] R4: guardas verdes; suíte completa verde no pouso.

## 6. Smoke real (curto, local)

1. `seed_save(13, "voto")`: 1 rodada com LLM real. Registro e Livro mostram "provocado por você".
2. `seed_save(14, "entrega")`: "Entrego a prova da caça ao contratante". O recibo mostra "Caça".
3. Provocação contra o herói, se a seed `13 armadura` a produzir: "Você está provocado por …".

Registrar em `docs/spec390/smoke.md`.

## 7. Riscos & compatibilidade

O campo `quest_titles` é aditivo, e saves antigos caem no fallback do id. Nenhum texto muda para inimigos.

## 8. Decisões

Nenhuma decisão aberta: é só texto.

## 9. Registro de implementação

04/11: R1 em `round_log._voce` (troca o herói por "você" na linha do desvio); R3 em `round_log._taunt_lines` (ramo da vítima "Você"); R2 em `turn_outcome` (`quest_titles` aditivo, escrito depois do `receipt_id`; `public_outcome` lê, fallback id). Front sem mudança (`outcomeToast` já usa `title`). Testes: `tests/test_spec390_text.py` (R1, R2, R3, R4 pela API real com MockLLM). Nenhum teste antigo precisou de ajuste. Smoke §6 real (LLM) fica com o coordenador.
