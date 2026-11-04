# SPEC-393 — Cartas: arestas do smoke das ressalvas (texto da morte aceita, golpe final múltiplo, prosa de morte fiel ao registro, compra com cauda de ouro, aviso do import)

> **Status:** `approved` (04/11, coordenador, ordem permanente do dono "manda bala" e política de zero pendência)
> **Criada:** 2026-11-04 · **Atualizada:** 2026-11-04
> **Épico:** SPEC-327
> **Origem:** [docs/smoke-ressalvas-cartas/smoke-local.md](../docs/smoke-ressalvas-cartas/smoke-local.md) § Achados 1–6.
> **Depende de:** SPEC-346, 347, 353, 355, 387 (todas `done`).
> **Risco:** `médio` (texto de combate e de morte, gramática de compra, script de autoria) → revisor Sol (Opus), porque toca o fluxo de morte.

## 1. Contexto & Objetivo

O smoke local com LLM real das ressalvas do épico (04/11) passou nos itens 1–5. Sobraram 6 achados de texto e roteiro, e a política do dono é não deixar pendência. Esta spec fecha os que são produto (A1, A3, A4, A5, A6) e confirma ou derruba o A2.

## 2. Requisitos

- **R1 (A1).** Depois de `POST /game/death` com `accept`, a mensagem devolvida e a entrada do `/game/history` deixam de ser a pergunta "Voltar ao último respiro seguro, ou aceitar o fim aqui?" e passam a ser um texto de encerramento determinístico em voz "você", sem número nem id. Ponto provável: `services/checkpoints.py:143` (`resolve_death_choice`, ramo `accept`). O `continue` não muda.
- **R2 (A3).** `services/round_log.py:final_blow_sentence` nomeia todos os inimigos derrubados na rodada final, agrupados por autor e tipo e na ordem do registro. Exemplos: "Seu golpe termina o serviço: Goblin 1 e Goblin 2 tombam." e "Seu golpe termina o serviço: Goblin 1 tomba. Sangramento termina o serviço: Goblin 2 tomba." Com um alvo só, o texto atual não muda, byte a byte (os testes da SPEC-353 R10 e da SPEC-355 R4 seguem verdes sem edição).
- **R3 (A5).** A narração do desfecho de morte recebe os ferimentos reais do herói (parte e gravidade, do estado) e não pode contradizê-los. O guard é determinístico: se a prosa atribui a uma parte do corpo uma gravidade diferente da do registro, ou cita uma parte ferida que não está no registro, ela é descartada e entra o texto determinístico de desfecho que já existe (o mesmo fallback do FallbackLLM), com log `log_fallback` e evento registrado no catálogo. Tudo em módulo próprio (arquivo > 1.000 linhas não cresce).
- **R4 (A4).** A compra fechada de Carta (`agents/loot.py`, gramática por volta das linhas 585–603) aceita uma cauda de pagamento depois do nome: "com (as|minhas|meu|o meu)? (últimas)? (moedas|ouro|dinheiro)", com ou sem "por favor/agora/então". "Compro a <Carta> com minhas últimas moedas" compra de verdade, e o V-G (`trade_prose_rejected`) continua valendo para a prosa. Frase fora da gramática continua caindo no fluxo atual (preço + confirmação).
- **R5 (A6).** `scripts/import_bestiary_art.py`: um `bst_<id>` que não está no pool conhecido localmente gera um **aviso** claro no stdout (não erro, porque o pool é dinâmico). `--strict` transforma o aviso em erro. Se não existir fonte local do pool, o aviso diz isso. `docs/guias/AUTORIA.md` ganha 1 linha.
- **R6 (A2), investigação.** Confirmar se o `continue` que restaura uma abertura com o pedido do jogador dentro da prosa é artefato do `seed_save` (MockLLM) ou bug real do checkpoint. Teste: jogo criado por `/game/new` com MockLLM, 2 turnos, morte e `continue`. A prosa restaurada é a narração do checkpoint, não o texto da ação do jogador. Se for bug, corrigir com teste vermelho antes. Se for artefato, registrar no §9 com a evidência.
- **R7 (guardas).** Sem flag nova. Golden 330, avaliadores, arenas, `sim.py`, `web/e2e/contracts`, arquivos da SPEC-369 Fase A intocados. `test_size_budget`, `test_no_silent_except`, `test_log_event_registry`, `test_error_envelope` verdes; ruff limpo.

### Fora de escopo

Balanço (SPEC-369), roteiro do smoke da 387 (o texto do roteiro é doc), chefe `unico` entre contas (só staging), ramo `place_as_actor` com LLM real.

## 3. Design técnico

- R1: constante de texto junto do `resolve_death_choice` ou no módulo de texto de morte existente; a resposta da API usa a mensagem nova.
- R2: agrupar `final_blows` por (autor, tipo, condição); juntar nomes com ", " e " e "; verbo no plural com 2 ou mais.
- R3: módulo novo, por exemplo `services/death_prose_guard.py`, com `check(prose: str, wounds: list[dict]) -> str | None` (motivo ou `None`), com um vocabulário fechado de partes do corpo e gravidades igual ao do registro. Os ferimentos entram no prompt da narração de morte como fatos.
- R4: estender o `tail` com o grupo opcional de pagamento; testes de gramática positivos e negativos.
- R5: aviso com `print` (é script de CLI); fonte do pool a ser localizada pelo executor (`Grep "bst_"` em `data/`).

## 4. Plano

1. Testes vermelhos: R1 (API real, MockLLM, seed de morte), R2 (unidade com 2 golpes do mesmo autor e de autores diferentes), R3 (unidade do guard, mais integração com um fake LLM que contradiz o registro e cai no fallback), R4 (gramática com a frase do smoke, mais compra pela API), R5 (script com o pool falso), R6 (teste de investigação).
2. Implementar.
3. Guardas do R7.
4. §9.

## 5. Critérios de aceite

- [x] R1: `accept` devolve o texto de encerramento; o history não repete a pergunta.
- [x] R2: 2 inimigos na rodada final nomeados; 1 alvo byte-idêntico.
- [x] R3: prosa contraditória cai no fallback com log; prosa fiel passa.
- [x] R4: "Compro a <Carta> com minhas últimas moedas" compra; V-G intacto.
- [x] R5: aviso e `--strict`.
- [x] R6: causa registrada (e corrigida, se for bug).
- [ ] R7: guardas verdes; suíte completa verde no pouso.

## 6. Smoke real (curto, local)

Morte com `accept` (texto de encerramento), vitória com dois inimigos caindo juntos, "Compro a <Carta> com minhas últimas moedas" com o nome da prateleira do próprio jogo. Registrar em `docs/spec393/smoke.md`.

## 7. Riscos & compatibilidade

R3 pode descartar prosa boa por falso positivo: o vocabulário é fechado e o fallback já existe e é testado. R4 amplia a gramática só com o grupo de pagamento.

## 8. Decisões

Nenhuma aberta: é texto e robustez.

## 9. Registro de implementação

- R1: `services/death_ending.py` (`ACCEPT_TEXT`, `apply_accept_text`) troca `WHEEL_TEXT` na última mensagem da IA e em `presentation_history`; sem pergunta a trocar, anexa o texto. Chamado no ramo `accept` de `resolve_death_choice`.
- R2: `round_log.final_blow_sentence` agrupa por (autor, tipo, condição); novo `_blow_subject`. Alvo único: byte-idêntico.
- R3: `services/death_prose_guard.py` (`check`, `wounds_from_player`); só para `death`; ganchado como código de rejeição (`death_prose_guard.codes`) no mesmo ponto da atribuição, para não crescer `combat.py`: fonte `fallback_attribution`, evento existente `outcome_attribution_rejected` e `log_fallback` (sem evento novo, catálogo intacto). Prosa sobre parte do corpo de outro dono ("braço do Goblin") é ignorada.
- R4: grupo opcional `pay` na cauda da gramática de `_card_shop_turn`.
- R5: `pool_warnings`/`known_pool_ids` (fichas do bestiário como fonte local) e `--strict`; linha em AUTORIA.md.
- R6 (A2): ARTEFATO, não bug. Em `/game/new` com MockLLM a abertura ecoa o pedido ("Você descreva o cenário ao meu redor. Sou um Sangromante de nível 1."); o `continue` restaura exatamente essa narração. Teste `test_continue_restores_checkpoint_narration_not_player_text`.
- Testes: `tests/test_card_epic_caveats.py` (14). Desvio: §6 (smoke real com LLM) não executado pelo executor (sem chave); coberto por testes com API real + MockLLM, fica para o coordenador.
