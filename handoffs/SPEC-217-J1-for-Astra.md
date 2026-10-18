# SPEC-217 — handoff J1 → revisão Astra (congelamento antes da J2)

Executor: Sol (≡ Opus). Branch `spec-217`. Pedido: revisar o **congelamento da
estrutura J1** (R6) antes de qualquer chamada da J2. A J2 **não** foi executada.

## O que foi feito

1. **Diagnóstico offline** (`docs/spec217/j1-diagnostico.md`): raws SPEC-178/179 não
   existem localmente (registrado); causas a partir dos relatórios e do payload
   reconstruído. Principais: rótulos `COMBAT/NPC/...` × chaves `combat_agent/...`;
   DTO sem lista de cena (`FALO COM CORVO` sem saber que Corvo é NPC presente;
   "corvo" também é animal); caixa alta; argmax a 0,27–0,30 sem abstenção; opção
   de alvo sem apelidos; alvo pedido isolado da rota com duas abstenções
   (`unknown`/`none`).
2. **Código (commit `c5a721c`, antes de qualquer chamada):**
   - `services/jev_decision.py`: `DecisionState` ganhou `scene` (≤ 20 `SceneActor`
     id/nome/apelidos ≤ 4/kind/hostil), `last_speaker` (ID) e `verbs` (léxico
     fechado de 8 classes) — **opcionais, `None` ⇒ fora do fio**; payload do
     rollout SPEC-180 inalterado (teste dedicado; o teste existente de
     `test_jev_rollout.py` passou a comparar `model_dump(exclude_none=True)`).
   - `evals/experiments/jev_router_hybrid.py`: features (filtro de cena = o mesmo
     `_target_options` da SPEC-179: oculto/secret/fora de cena/sem ID canônico
     fora; > 20 ⇒ não representável, sem truncar), perguntas `legacy/plain/rich`,
     estágio de alvo (candidatos + `none`), política híbrida pura, score, seleção.
   - `evals/experiments/spec217_j1.py`: runner live DEV com ledger em disco
     (incrementa antes da requisição; teto J1 60 / spec 160), `max_retries=0`,
     para em qualquer `JevError` (HTTP/timeout/resposta inválida) sem score.
   - `tests/test_spec217_j1.py` (24 testes offline).
3. **Pré-registro** da regra de seleção e do desenho P1/P2 em
   `docs/spec217/j1-variantes.md`, commitado com o código antes das chamadas.
4. **Live DEV:** P1 = 52 chamadas (1 por elegível, todas as perguntas de rota +
   alvo no mesmo estado); P2 = 8 chamadas com a requisição exata congelada nos
   casos `critical`. **60/60**, zero erro, zero CLASSIFY.
5. **Freeze:** `FROZEN_J1_POLICY = plain+target@0.50` + `FROZEN_J1_STRUCTURE_DIGEST
   = sha256:950917371fe7c1c46326996d5adaa518e10f1c1e6e8c778103a9cf88a4d44b81`,
   travado por `test_frozen_structure_digest_matches_code`.

## Resultado DEV (52 elegíveis)

Rota standalone: legacy 51/52, plain 52/52, rich 52/52; 0 falso positivo de
combate. Variante escolhida: cobertura 35/52 (67,3 %), 0 erro de rota/alvo
coberto (25 casos com alvo), 0 escalada insegura; fallbacks = loot 13 (fora de
escopo), abstenção 2 (SQL/injeção), alvo não representável 2. Jev p50/p95 247 /
288,7 ms (P1, multi-pergunta) e 247 / 286,55 ms (P2, estrutura real). Híbrido
estimado p50 260,5 ms vs CLASSIFY 1.473 ms (referência SPEC-214). P2 concorda com a
P1 em 8/8 rotas e 8/8 alvos.

## Pontos para a revisão (onde eu olharia com desconfiança)

1. **FROZEN não aberto.** Nenhum código J1 referencia `spec217_frozen.jsonl` (teste
   de fonte); raws gravam só o hash do lock. O verificador de autoria
   (`spec217_corpus_check.py`) lê o FROZEN, mas **não foi executado** na J1.
2. **Desempate da guarda de combate.** `+guard` empatou em tudo (nunca disparou no
   DEV); a regra pré-registrada escolheu "sem guarda". A guarda (combate só com
   verbo de ataque ou combate ativo) seria uma proteção extra para R9.3 no FROZEN
   (2 casos `ambiguous`). Mudar isso agora seria decisão pós-dados: cabe à revisão
   aceitar o freeze como está ou exigir justificativa formal para trocar.
3. **P1 multi-pergunta.** As 108 políticas foram pontuadas com respostas de uma
   requisição que carregava 3–4 perguntas; a P2 mostra que a estrutura real dá as
   mesmas respostas nos 8 casos críticos — amostra pequena.
4. **Sem CLASSIFY no DEV.** A seleção usa só os erros nos casos cobertos (únicas
   perdas possíveis contra A, que fez 48/48 na SPEC-178). A latência híbrida é
   estimativa com referência externa; a J2 mede de verdade (soma Jev + CLASSIFY).
5. **Overfitting.** DEV não separa `plain` de `rich` (ambos 0 erro). Exemplos do
   `rich` não copiam frases do DEV; `plain` não tem exemplos. O léxico de verbos é
   genérico (a parte de ataque reaproveita `_EXPLICIT_HOSTILITY_RE` do router).
6. **Representabilidade.** `loot` sempre cai para CLASSIFY (o `loot_context` pelo
   Jev está fora de escopo). Para portar (R14) o alvo devolvido é ID; o router de
   produção espera nome em `active_npc_name` — o porte precisa mapear ID→chave.
7. **Fronteira R12.** Ver `test_features_are_deterministic_and_public_only` (NPC
   secreto/fora de cena não aparece no fio) e o limite de tamanho do DTO.

## Pendências para a J2 (não implementadas na J1)

Runner FROZEN (`--corpus frozen`, recusa sem freeze e na 2ª execução), funções
puras da R9, sanidade de 4 chamadas, embaralhamento por seed, braço A real
(CLASSIFY) e latência B = soma nas quedas; ledger compartilhado já soma 60/160.

## Artifacts

Ver `docs/spec217/README.md` (hashes de raw/summary/ledger). Os raws vivem em
`evals/runs/jev-router-ab/spec217-j1/` **dentro do worktree** (gitignored) —
preservar antes de remover o worktree (os raws da SPEC-178/179 se perderam assim).
