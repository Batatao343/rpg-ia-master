# SPEC-330 — Cartas #03: Gramática de efeitos e palavras-chave de Valoria

> **Status:** `in-progress` (Grupo A + intérprete + texto + orçamento + glossário pousados em 27/10 após re-revisão Sol APPROVED_WITH_FOLLOWUPS; Grupo B ligado às pilhas da SPEC-328 e follow-ups P2-4/P2-5 em 27/10, correções da revisão Sol B-P1-1, B-P2-1..5 aplicadas (D-13), pendentes re-revisão e smoke real)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-328 (`comprar`/`descartar`/`Guardar`/`Exaurir` precisam das pilhas). As palavras-chave sem pilha (R5 grupo A) podem pousar antes.
> **Desbloqueia:** SPEC-332, SPEC-335, SPEC-336 (todo conteúdo novo usa esta gramática)
> **EXECUTOR_MODEL:** `Sol` (Opus) — motor de efeitos é cross-cutting · **REVIEW_MODEL:** `Sol` em contexto separado · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `false`

Rótulos: **[F]** fato (HEAD `a8361681`) · **[D?]** decisão pendente · **[R]** recomendação.

---

## 1. Contexto & Objetivo

[F] Cada carta tem **um** `efeito: {kind, ...}` (308 cartas; 31 `kind`s; `dano` 62, `aplicar_condicao` 36, `contra_ataque` 26…). Não há gatilho, condição, nem combinação entre cartas — duas cartas de `dano` diferem só no número. 35 cartas têm `descricao` vazia; as 80 de `tiers_5_plus.json` repetem a frase-modelo "converte risco acumulado em uma decisão mecânica…".

[R] Cartas com identidade nascem de **composição**: *gatilho → condição → efeito(s)* + um punhado de **palavras-chave** reconhecíveis (Magic: keywords evergreen; Slay the Spire: Exaurir/Reter/Vulnerável; Monster Train: gatilhos). Com ~12 palavras-chave e ~10 gatilhos dá para escrever centenas de cartas distintas sem um `if` novo no motor por carta.

Objetivo: um **intérprete de efeitos fechado e determinístico** + o **léxico de Valoria**, compatível com o formato atual.

## 2. Requisitos

**Formato**
- **R1** — Carta pode ter `efeitos: list[Efeito]` além de `efeito` (legado). Leitura normaliza: `efeito` → `efeitos=[efeito]`. Nenhum arquivo existente precisa mudar.
- **R2** — `Efeito = {kind, alvo?, valor?, ..., quando?: Gatilho, se?: Condicao, escala?: Escala}`. Tudo de vocabulário fechado, validado por `content_validator`.
- **R3** — **Gatilhos** (`quando`): `ao_jogar` (padrão), `inicio_rodada`, `fim_rodada`, `ao_comprar`, `ao_descartar`, `ao_exaurir`, `ao_receber_dano`, `ao_derrubar` (alvo cai), `ao_aliado_sofrer`, `ao_pressagio_frustrado` (SPEC-329), `ao_entrar_carga` (Carga do Abismo sobe).
- **R4** — **Condições** (`se`): `alvo_tem(condicao)`, `eu_tenho(condicao)`, `entropia_min(n)`, `vitalidade_max_pct(p)`, `cartas_jogadas_na_rodada_min(n)`, `ultima_carta_tipo(tipo)`, `ultima_carta_postura(classe)`, `engajado`, `zona_tem_objeto(tag)`, `alvo_familia(familia)`.

**Palavras-chave de Valoria (v1, 14)** [D? nomes]
- **R5** — Grupo A (não precisam de pilhas):
  - **Rachadura N** — alvo recebe +25 % de dano por N rodadas (o "vulnerável"; nome do ferro que cede).
  - **Torpor N** — alvo causa −25 % de dano por N rodadas.
  - **Sangria N** — N de dano no início da rodada do alvo, decai 1/rodada (mapeia `dot`/`sangrando` existentes).
  - **Vigília N** — proteção que **não** se dissipa no fim da rodada (dura até ser consumida).
  - **Marca do Abismo** — próximo dano no alvo +X e gera +1 Entropia para quem acertar (já existe `marca`; vira keyword).
  - **Interromper** — se o alvo tem presságio de ataque e cai/atordoa, conta como frustrado (SPEC-329) e dispara `ao_pressagio_frustrado`.
  - **Sacrifício N** — paga N de Vitalidade como custo adicional (Sangromante; passa pelo gatilho `on_self_harm`).
  - **Chamado** — efeito extra se `entropia_min(k)`; a carta "fica melhor perto do Abismo".
- **R6** — Grupo B (exigem SPEC-328):
  - **Exaurir** — sai até o fim do conflito.
  - **Guardar** — não é descartada no fim da rodada.
  - **Eco** — se jogada depois de outra carta da mesma Postura nesta rodada, repete o efeito principal pela metade (combo).
  - **Ressoar N** — cada vez que é jogada nesta cena, o valor sobe N (escala permanente na cena).
  - **Fardo** — carta-maldição (injogável ou ruim) que entra no baralho por efeito de inimigo/Abismo; `Purgar` remove.
  - **Vazão** — ao ser descartada sem ser jogada, ativa efeito menor (Arcanista: esfria a caldeira).
- **R7** — **Efeitos novos** (além dos 31 atuais): `comprar(n)`, `descartar(n, escolha)`, `ganhar_folego(n)`, `gerar_carta(id, pilha)`, `purgar_fardo(n)`, `copiar_ultima`, `mover_alvo_zona`, `revelar(campo)` (bestiary_knowledge).
- **R8** — **Texto da carta é gerado** a partir dos efeitos (`render_card_text(card) -> str`), em PT-BR, com as palavras-chave em negrito. A `descricao` vira só sabor (frase de lore). Garante que o texto nunca mente sobre a mecânica.
- **R9** — **Orçamento de poder**: `power_score(card) -> float` determinístico (dano/proteção/condições/compra/custos/raridade, pesos em `data/cards/_orcamento.json`). Validator falha carta fora de `faixa(raridade, custo_folego)`. Usado pela SPEC-336.
- **R10** — **Glossário** `data/cards/_glossario.json` (palavra-chave → texto curto de regra + frase de sabor), fonte única para o front (tooltip) e para o prompt do narrador.
- **R11** — Ordem de resolução documentada e testada: custos → `se` → efeitos na ordem da lista → gatilhos disparados (fila FIFO, profundidade máx. 3 — anti-loop, mesmo princípio de `rule_engine.py`).

### Fora de escopo
Autoria de cartas novas (SPEC-335). Keywords de inimigo exclusivas (SPEC-332 pode estender o léxico pelo mesmo mecanismo).

## 3. Design técnico
- **Novo** `services/card_effects.py`: `normalize(card) -> list[dict]`, `resolve_card(ctx, card) -> list[Event]`, `fire(ctx, gatilho, **kw)`, `render_card_text(card)`, `power_score(card)`. `ctx` = (actors_by_id, scene, piles, rng, out). Efeitos legados delegam aos ramos atuais de `conflict_orchestrator` (`_apply_player_card_mechanics`, `_resolve_reaction_effect`, `apply_effect_spec`) — **sem reescrever o que já funciona**.
- **Novo** `data/cards/_glossario.json`, `data/cards/_orcamento.json`.
- **Alterado** `services/content_validator.py`: valida `efeitos`, `quando`, `se`, palavras-chave, orçamento.
- **Alterado** `combat_mechanics.NAMED_CONDITIONS`: `rachadura`, `torpor`, `vigilia` (as demais reaproveitam `exposto`/`enfraquecido`/`sangrando` — decidir fusão: `exposto` ≈ Rachadura? [D?]).

## 4. Plano (TDD)
1. `tests/test_card_effects_normalize.py` — legado vira lista; resultado idêntico ao motor atual para as 308 cartas (teste de equivalência em lote, seed fixa).
2. Grupo A, uma palavra-chave por teste (`tests/test_keywords_valoria.py`).
3. Gatilhos + fila anti-loop (profundidade 3).
4. Grupo B (após 328).
5. `render_card_text` com snapshot das 308 cartas + 10 cartas compostas de exemplo.
6. `power_score`: as 308 atuais entram na faixa (calibrar pesos, não as cartas); outliers listados no hand-back.

## 5. Critérios de aceite
- [x] Equivalência: 308 cartas legadas com resultado idêntico (seed fixa) ao motor anterior — golden da `main` pré-330 (§8 D-3)
- [x] 14 palavras-chave com teste e entrada no glossário; Grupo B com efeito no motor (pilhas da 328, `RPG_CARD_DECK=on`; Eco/Ressoar valem em qualquer modo) — falta re-revisão e smoke real
- [x] Validator rejeita vocabulário fora do catálogo e carta fora do orçamento
- [ ] `uv run pytest` verde (suíte completa: coordenador, no pouso)

## 6. Smoke real
1. Combo Eco (2 cartas da Postura) narrado com coerência. 2. Rachadura + golpe: número no log bate com o texto da carta.

## 7. Riscos
- Explosão combinatória: fila com profundidade máxima e efeitos fechados.
- MockLLM não exercita: tudo é Python; LLM só narra.
- Nomes das palavras-chave são do dono — lista em §2 é proposta.

## 8. Implementação (2026-10-27) — decisões e desvios

Entregue em `services/card_effects.py` (intérprete, gatilhos, texto, orçamento,
validação), `data/cards/_glossario.json`, `data/cards/_orcamento.json`; ligações em
`conflict_turn`, `conflict_orchestrator`, `conflict_damage`, `combat_mechanics`,
`cards` e `content_validator`. Testes: `tests/test_card_effects_grammar.py`,
`tests/test_keywords_valoria.py`; 12 Cartas compostas de exemplo em
`tests/fixtures/spec330_cartas_compostas.json` (fora do acervo do jogo).

- **D-1 `exposto` ≠ Rachadura (correção do coordenador, 27/10).** `exposto` mantém a
  mecânica e o nome atuais (−2 de Esquiva). **Rachadura** é condição NOVA (+25 % de
  dano recebido em golpe, arredonda meio-para-cima, não amplia DoT/auto-dano), usada
  só por Cartas novas/compostas. Nenhuma Carta legada muda de resultado.
- **D-2 Representação.** Palavras-chave que são efeito viram `kind` (`rachadura`,
  `torpor`, `sangria`, `vigilia`, `marca_do_abismo`); as que são propriedade da Carta
  ficam em `palavras_chave: {sacrificio: N, interromper, exaurir, guardar, eco,
  ressoar: N, fardo, vazao}`; **Chamado** é o campo `chamado: k` do efeito (açúcar de
  `se: {entropia_min: k}`).
- **D-3 Equivalência contra o motor anterior.** `tests/spec330_equivalence.py` resolve
  as 308 Cartas legadas com seed fixa (ativa via `resolve_turn`, reação via
  `_resolve_reaction_effect`, passiva/utilitária/virtude via modificadores) usando só
  APIs pré-330; o golden `tests/fixtures/spec330_legacy_golden.json` (hash + logs por
  Carta) foi gerado com o código da `main` pré-330 (8bd4f384) e o teste exige igualdade
  no motor novo, na forma legada e na forma `efeitos=[efeito]`. Fora da comparação só a
  contabilidade nova (`_cartas_rodada`) e stats novos zerados no dict de modificadores.
- **D-4 Efeito principal.** O catálogo deriva `efeito` = primeiro efeito `ao_jogar`
  incondicional de kind legado (senão o primeiro incondicional). Ele dirige a
  rolagem/suporte; os efeitos adicionais rodam depois e **só com acerto** quando o
  principal é ataque. Kinds novos hostis rolam ataque (como `aplicar_condicao`);
  `vigilia`/`copiar_ultima`/pilhas resolvem como suporte (alvo próprio).
- **D-5 Gatilhos.** Efeito com `quando` ≠ `ao_jogar` arma em `scene["gatilhos_armados"]`
  ao jogar (até o fim do conflito, inclusive se o ataque errar); passivas com gatilho
  ficam sempre armadas. Ligados: `inicio_rodada`, `fim_rodada`, `ao_receber_dano` e
  `ao_aliado_sofrer` (fontes: golpe, efeito extra `dano`, dano disparado por gatilho e
  DoT/Sangria; só dano > 0), `ao_derrubar` (alvo que CAIU neste turno — morte, Estado
  Terminal, incapacitado, Última Ação — comparado com o estado antes do turno; atordoar
  não conta), `ao_entrar_carga` e `ao_pressagio_frustrado`. `ao_comprar`/`ao_descartar`/
  `ao_exaurir` disparam quando a 328 existir. Fila FIFO, profundidade máx. 3: dano de
  gatilho que re-dispara `ao_receber_dano` sobe a profundidade; o 4º é descartado e
  registrado em `gatilhos_descartados`.
- **D-6 Interromper × SPEC-329 (formato real).** Com `RPG_ENEMY_INTENT=on`, o
  `run_round` entrega ao contexto os presságios congelados (`combat["pressagios"]`,
  `{actor_id: [intent]}`) e o cursor de ações já consumidas. Interromper vale se o
  presságio PENDENTE do alvo é `ataque`/`ataque_multiplo` e: o alvo CAIU (conta sempre),
  ou foi atordoado ANTES da 1ª ação da rodada (cursor 0). Atordoar depois da 1ª ação não
  nega a ação extra de Chefe (SPEC-295) e não é Interromper. Marca
  `intent["interrompido_por"]` e dispara `ao_pressagio_frustrado` na hora; o `_frustrate`
  registra o frustrado com `por`/`via: "interromper"` (sem disparar de novo), e presságio
  interrompido nunca é executado nem entra em `pressagios_cumpridos`. Presságio frustrado
  sem Interromper dispara o gatilho para a mira (`alvo_id`). Inerte em `off`/`shadow`.
- **D-7 Marca do Abismo.** `control: marca` (mantém a Vantagem da `marca` legada) +
  `abismo_bonus: X`, duração 3; o próximo dano direto consome: +X e +1 Entropia (com
  teto) para quem acertou. A `marca` legada não muda.
- **D-8 Vigília.** Stat `vigilia` (fora da Proteção somada), `persistente`, acumula;
  absorve depois de armadura/Proteção e só some ao zerar.
- **D-9 Orçamento.** `custo_folego` = campo explícito ou regra da 328 R6; raridade por
  `patamar`. Faixas calibradas nas 308 (pesos/faixas, não as Cartas); utilitária e
  virtude isentas.
- **D-10 Grupo B no motor (substituída pela D-12).** Na 1ª passada os efeitos de pilha só
  registravam `pendente_pilhas`; continua assim fora do modo `on` (e para o inimigo, exceto
  Fardo).
- **D-12 Grupo B sobre as pilhas (2ª passada, 27/10; efeitos de pilha, Exaurir, Guardar e Vazão só com `RPG_CARD_DECK=on`; Eco e Ressoar em qualquer modo — D-13).** `Ctx.piles`/
  `piles_actor` são ligados em `run_round` quando `deck_mode(state) == "on"`; sem isso nada
  muda (golden das 308 igual; `shadow`/`off` seguem inertes, `pendente_pilhas` incluso).
  - **Exaurir:** `play_to_pile` manda para `exaurida` (como `cena`/`descanso_*`) e dispara o
    `ao_exaurir` da própria Carta. **Guardar:** `end_round` (fim da rodada, depois de
    `fim_rodada`) marca `piles["guardadas"]`; `begin_round` já poupava essas.
  - **Vazão:** no mesmo `end_round`, toda Carta com Vazão que sobra na mão (não jogada, não
    guardada) dispara o `ao_descartar` dela; também dispara quando `descartar` a leva.
    `pile_trigger` (próprio da Carta: `ao_comprar`/`ao_descartar`/`ao_exaurir`) tem
    profundidade máx. 3 (`ctx.pile_depth`). `ao_comprar` só nas compras por efeito; a compra
    de início de rodada (`begin_round`) fica fora do contexto e não dispara.
  - **Eco:** em `resolve_extras`, antes de `record_play`: se há Carta anterior da mesma
    Postura na rodada, repete o efeito principal com o valor numérico ÷ 2 (mín. 1; efeito
    sem valor numérico repete igual). **Ressoar N:** `scene["ressoar"]["ator:carta"]` conta
    jogadas na cena (`record_play(..., scene)`); `prepare_play` devolve cópia da Carta com
    N × jogadas anteriores somados ao valor do principal (catálogo intacto).
  - **Fardo:** palavra-chave `fardo` (glossário); `Estilhaço de Cinza` agora declara
    `palavras_chave: {fardo: true}` e `is_fardo` vale para o id base, `injogavel` ou a
    palavra-chave (plano/pagamento/`public_view`). `gerar_carta` aceita `mao`/`compra`
    (topo)/`descarte`; Fardo gerado soma em `fardos`. Inimigo pode plantar Fardo na mão do
    jogador via `gerar_carta`; nenhum outro efeito de pilha vale para o inimigo.
  - **Efeitos de pilha:** `comprar(n)` (reembaralha + Fardo como em 328), `descartar(n,
    escolha)` — com `escolha` a política determinística (sem UI ainda) leva Fardo, depois
    Carta com Vazão, depois a mais à direita; sem `escolha`, ao acaso com o RNG persistido;
    poupa uma cópia da Carta em jogo —, `ganhar_folego(n)` (bônus da próxima rodada, teto `FOLEGO_MAX` = 6 — D-13), `gerar_carta`, `purgar_fardo` (mão → descarte → monte).
    Eventos em `out["pilhas_eventos"]` (agregado pela rodada via `TURN_EVENT_KEYS`).
- **D-11 Revisão Sol (`handoffs/SPEC-330-sol-review.md`).** Corrigidos: P1-1 (Interromper
  × ações extras, D-6), P1-2 (`ao_derrubar` por categoria, D-5), P2-1 (efeito hostil sem
  `alvo` em Carta de suporte vai ao 1º oponente, nunca ao conjurador/aliado), P2-2 (teste
  do caminho de erro: extras não rodam, gatilhos armam, `record_play` registra), P2-3
  (D-5), P2-6 (dano extra usa o modo não-letal do golpe declarado — SPEC-325), P2-7
  (`alvo_tem`/`eu_tenho` só aceitam condição do catálogo: nomeadas, controles, `marca`,
  `sangramento` e palavras-chave). Testes em `tests/test_card_effects_review_spec330.py`.
- **D-13 Correções da revisão Sol do Grupo B (27/10).**
  - **B-P1-1 retenção.** `comprar` e `gerar_carta` (para a mão) durante a resolução gravam as
    Cartas em `piles["retidas"]`; `discard_hand` poupa `guardadas` e depois `retidas`
    (prioridade nessa ordem), e as poupadas contam dentro do limite da mão (`MAO_BASE` = 5):
    o excedente vai ao descarte. O Fardo plantado também fica retido (pesa na próxima mão).
    `ganhar_folego` vira `piles["folego_bonus"]` (≤ `FOLEGO_MAX` − base), somado por
    `begin_round` ao Fôlego cheio da próxima rodada e zerado (a lista de jogadas já foi
    paga, então não há ganho na rodada corrente). Com monte e descarte vazios `comprar` não
    compra nem gera Fardo. Testes: `run_round` → `card_piles.begin_round` (a chamada do nó).
  - **B-P2-1.** Seeds extra = (2, 13, 21): erro, crítico, acerto (sem Mira); o golden grava
    `res` (resultado dos ataques) e um teste exige acerto+erro+crítico no `extra`. O golden
    foi regerado no `8bd4f384` (worktree descartável); o harness da reação ganhou
    `deaths`/`terminal` no `out` (o motor antigo estourava `KeyError` quando a reação matava).
  - **B-P2-2 Eco/Ressoar independem das pilhas** (decisão do coordenador): valem com
    `RPG_CARD_DECK` em qualquer modo (nota no glossário). Eco é inerte com 1 ação por
    rodada; Ressoar escala por cena (testes em `off`). Só os efeitos de pilha, Exaurir,
    Guardar e Vazão exigem `on`.
  - **B-P2-3/4.** `descartar` ao acaso testado com `rng=random` (módulo, como o nó) e
    round-trip JSON; Fardo do inimigo ponta a ponta via `run_round` em `on`/`shadow`/`off`.
  - **P3.** `gain_folego` nunca devolve ganho negativo; só um inimigo (`sides["enemy"]`)
    planta Fardo — aliado não. Registrado e adiado: `_bump` mexe na 1ª chave entre
    `valor`/`dano_base`/`n` (fixar na autoria, SPEC-335); `descartar` é quase sem custo
    enquanto a mão toda vai ao descarte no fim da rodada (só dispara Vazão ou tira Carta com
    Guardar).
- **D-11 follow-ups fechados (27/10).** P2-4: o golden (`spec330_legacy_golden.json`,
  regerado com o código pré-330 `8bd4f384` num worktree descartável) tem a seed 7 com Mira
  e `extra` com as seeds 21 e 1337 SEM Mira (erro/acerto/crítico), além de `on_attack`/
  `on_hit` das passivas/virtudes e `cards.use_card` das utilitárias; o teste compara os
  três cenários nas formas legada e `efeitos=[efeito]`. P2-5: `revelar` (`resistencias`/
  `cartas`) agora grava no `bestiary_knowledge` (perfil `legacy`; outros perfis só marcam
  `revealed_*` na ficha; falha → `combat.revelar_knowledge_failed`, cosmética).
- **Follow-ups abertos.** Fardo por evento do Abismo (hoje só por Carta de inimigo/efeito);
  política de `descartar` com `escolha` real exige UI (SPEC-333); `ao_comprar` na compra de
  início de rodada; texto/UI do `FOLEGO_MAX`; smoke real (§6) e re-revisão do Grupo B.
