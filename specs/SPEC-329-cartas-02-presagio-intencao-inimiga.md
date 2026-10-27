# SPEC-329 — Cartas #02: Presságio (intenção do inimigo visível antes da jogada)

> **Status:** `draft`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-069, SPEC-283, SPEC-295 (todas `done`); **não** depende da SPEC-328 (funciona também no modo atual de 1 ação)
> **Desbloqueia:** SPEC-332 (baralhos inimigos com ciclo de intenção), SPEC-334 (ícones de intenção)
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — jornada "ler presságio → defender → presságio cumprido/frustrado".

Rótulos: **[F]** fato (HEAD `a8361681`) · **[D?]** decisão pendente do dono · **[R]** recomendação.

---

## 1. Contexto & Objetivo

[F] `enemy_declaration` (`services/conflict_orchestrator.py:465`) decide o turno do inimigo de forma determinística pelo perfil tático — mas **na hora da resolução**, depois que o jogador já escolheu. O jogador decide no escuro; defender é chute.

[R] Mostrar a intenção do inimigo antes da escolha é a peça de design mais citada em combate de cartas (Slay the Spire "intents", Into the Breach, Griftlands): transforma o turno num **quebra-cabeça legível** — "ele vai bater 9 em mim, eu tenho 2 guardas e 1 golpe; bloqueio ou mato antes?". Sem isso, cartas defensivas e de controle valem pouco.

Em Valoria isso se chama **Presságio**: o que o inimigo vai fazer aparece como um sinal na cena ("o ferro range — a Legionária ergue a lança para o teu flanco"), com um número quando o personagem **conhece** a criatura (`services/bestiary_knowledge.py`).

## 2. Requisitos

- **R1** — No início de cada rodada (antes da escolha do jogador), o motor calcula e **congela** a declaração de cada inimigo vivo via `enemy_declaration` (mesma lógica, mesmo `rng` da cena) e guarda em `combat["pressagios"][actor_id]`.
- **R2** — Presságio público: `{actor_id, tipo, alvo_id|null, valor_estimado|null, faixa|null, carta_nome|null, sinal}` onde `tipo ∈ {ataque, ataque_multiplo, defesa, reforco_proprio, enfraquecer, mover, fugir, render-se, desconhecido}` (mapeado de `action_key`/`effect_kind`), e `sinal` é uma frase curta **do catálogo** por `tipo × família` (sem LLM).
- **R3** — Gradação por conhecimento (bestiary_knowledge): **desconhecida** → só `tipo` e `alvo`; **conhecida** → `faixa` de dano (ex.: 6–9, calculada de dano_base ± variação do 2d10 contra a Defesa atual do alvo); **estudada** (revelação R8/R9) → `valor_estimado` + `carta_nome`.
- **R4** — Na resolução, o inimigo executa o presságio congelado. Ele só re-decide se o presságio ficou **impossível** (alvo morto/fora de alcance, inimigo atordoado/derrubado/fugiu). Re-decisão registrada como `pressagio_frustrado` no trace e na narração ("o golpe morreu no ar").
- **R5** — Frustrar presságio é recompensado: carta com efeito `atordoar`/`empurrao` que torna o presságio impossível registra `pressagio_frustrado` (gancho para keyword "Interromper" da SPEC-330).
- **R6** — Determinismo: mesma seed + mesmas jogadas → mesmos presságios e mesmo resultado. Testado.
- **R7** — Reforços/ações extras (`acoes_por_rodada`, SPEC-295): uma linha de presságio por ação, na ordem.
- **R8** — A narração da rodada recebe os presságios **cumpridos** e **frustrados**, não os números internos.
- **R9** — Flag `RPG_ENEMY_INTENT=off|shadow|on`. `shadow` calcula e compara com a decisão tardia de hoje (mede quantas vezes a decisão mudaria — critério de calibração).

### Fora de escopo
Ícones/UI (SPEC-334, aqui só o contrato da API). Baralhos e ciclos de intenção por facção (SPEC-332).

## 3. Design técnico

- **Novo** `services/enemy_intent.py`: `forecast_round(scene, actors_by_id, sides, rng) -> dict[str, list[Intent]]`, `public_intent(intent, knowledge_level) -> dict`, `still_possible(intent, actors_by_id, scene) -> bool`.
- **Novo** `data/combat/pressagio_sinais.json`: `{tipo: {familia|"default": [frases]}}` — ~10 tipos × 6 famílias (fera, morto-inquieto, legião, culto, ermo, abissal) × 2 frases. Voz de Valoria; revisão do dono antes de `approved` [D?].
- **Alterado** `run_round`: com flag `on`, usa `combat["pressagios"]` em vez de chamar `enemy_declaration` na hora (R4).
- **Alterado** `api.py`: `combat.pressagios_publicos` na resposta e no `state`.

## 4. Plano (TDD)
1. `tests/test_enemy_intent.py`: forecast igual à decisão atual quando nada muda; gradação por conhecimento; frustração por alvo morto e por atordoamento; determinismo por seed.
2. `shadow` na arena (SPEC-285): taxa de "decisão mudaria" registrada; se > 30 %, revisar a ordem do perfil tático antes de `on`.
3. `on` + API + narração.

## 5. Critérios de aceite
- [ ] R1–R9 com teste
- [ ] Arena `on`: dano recebido médio pelo jogador cai (cartas defensivas passam a valer) sem taxa de vitória sair de 40–80 %
- [ ] `uv run pytest` verde; saves de combate em curso sem `pressagios` continuam (calcula na próxima rodada)

## 6. Smoke real
1. Lutar contra criatura nova: só tipo/alvo. 2. Mesma família depois de estudada: faixa e nome da carta. 3. Matar o alvo antes: narração de presságio frustrado.

## 7. Riscos
- Informação demais deixa o jogo "resolvido": gradação R3 mantém mistério para o desconhecido.
- Perfis com gatilho reativo (ex.: "se o jogador fugir") passam a decidir antes: R4 cobre só impossibilidade, não "mudança de ideia" — aceitável e mais legível [R].
