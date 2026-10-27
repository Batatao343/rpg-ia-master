# SPEC-334 — Cartas #07: Clareza do combate no front (mão, Fôlego, presságio, preview e log)

> **Status:** `draft`
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Épico:** SPEC-327
> **Depende de:** SPEC-328 (contrato `pilhas`/`jogadas`), SPEC-329 (`pressagios_publicos`), SPEC-330 (`_glossario.json`, `render_card_text`), SPEC-320–324 (tokens, mobile, a11y, "livro não chat")
> **Desbloqueia:** `RPG_CARD_DECK=on` no staging
> **EXECUTOR_MODEL:** `Terra` · **REVIEW_MODEL:** `Sol` · **REVIEW_REQUIRED:** `true`
> **EVAL_AUTHORING_REQUIRED:** `true` — Playwright: jogar 2 cartas e encerrar; preview bate com resultado; tooltip de palavra-chave; reação com Fôlego guardado; 390 px e 1440 px.

Rótulos: **[F]** fato (HEAD `a8361681`) · **[D?]** decisão pendente · **[R]** recomendação.

---

## 1. Contexto & Objetivo

[F] `web/src/components/CardHand.tsx` mostra as preparadas em combate; `CombateTab.tsx` hospeda o encontro; o resultado mecânico chega misturado à prosa. O dono acha o front "cheio de coisa" e não sabe se o combate "está claro".

[R] Pesquisa §3: (1) **intenção visível com número**; (2) **preview do resultado antes de confirmar** — com 2d10 o jogador precisa ver a chance (Into the Breach: "não esconda consequência"); (3) **pouco texto na carta + tooltip de palavra-chave**; (4) **log mecânico separado da narração**, a LLM narra depois com números fixos.

## 2. Requisitos

- **R1** — **Faixa do inimigo**: cada inimigo mostra nome, Vitalidade/Ferimentos (como hoje) e **presságio** (ícone + número/faixa conforme conhecimento, SPEC-329 R3). Cartas de Cena (SPEC-331) numa faixa única acima, com contador de rodadas e Relógio do Abismo.
- **R2** — **Mão**: cartas com nome, custo de Fôlego (pips), custo de Entropia (se houver), texto gerado (`render_card_text`) com palavras-chave em negrito e **tooltip** do glossário (toque longo no mobile). Cartas sem Fôlego ficam esmaecidas com motivo.
- **R3** — **Fôlego e pilhas**: 3 pips de Fôlego; contadores de Compra/Descarte/Exaurida (toque abre a lista, nunca a ordem do monte). Pacto do Abismo aparece como pips "emprestados" em cor de Entropia com aviso do custo.
- **R4** — **Preview determinístico**: ao escolher carta + alvo, o front chama `POST /game/combat/preview` (sem LLM, sem efeito) → `{chance_acerto_pct, dano_min, dano_max, ferimento_provavel, efeitos_extra[], pressagio_frustrado: bool}` calculado pela mesma função do motor com distribuição exata do 2d10. Mostra "55 % · 4–7 de dano · pode Sangrar".
- **R5** — **Fila de jogadas local**: cartas escolhidas entram numa fila visível, reordenável e cancelável, sem request; **"Encerrar turno"** envia `jogadas` num request (SPEC-328 R13). Menos round-trips = menos espera.
- **R6** — **Log mecânico** colapsável, uma linha por evento: `Você · Corte Raso → 2d10 13 + Força 2 = 15 vs 12 · 5 dano · Rachadura 1`. A narração (livro, SPEC-323) vem depois e é curta por rodada.
- **R7** — **Limpeza**: no modo combate, a aba esconde o que não é combate (inventário, mapa, crônica ficam a um toque). Medir: elementos interativos visíveis em 390 px ≤ 12 [D?].
- **R8** — A11y: tudo navegável por teclado (atalhos 1–5 para cartas, `Enter` encerra, `Esc` limpa fila), leitores de tela anunciam presságio e preview (SPEC-324).
- **R9** — Modo texto puro preservado: jogador que digita "corto e me protejo" continua funcionando (SPEC-328 R15); a UI mostra a fila resultante antes de enviar.

### Fora de escopo
Arte de carta por carta (usar ícone por palavra-chave/tipo). Animações além das de `motion` já usadas.

## 3. Design técnico
- **Novo** `web/src/components/combat/` — `EnemyStrip.tsx`, `SceneStrip.tsx`, `Hand.tsx` (substitui `CardHand.tsx` atrás da flag), `FolegoPips.tsx`, `PlayQueue.tsx`, `PreviewChip.tsx`, `MechLog.tsx`, `KeywordTip.tsx`.
- **Novo** endpoint `POST /game/combat/preview` em `api.py` (puro; chama `services/combat_preview.py::preview(state, card_id, target_id)` que reaproveita as funções de acerto/dano do orquestrador com o `rng` substituído pela distribuição exata).
- `GET /data/cards/glossario` servido estático e cacheado.

## 4. Plano
1. `tests/test_combat_preview.py` — preview bate com a média de 10 000 rolagens simuladas (± 1 %) e nunca altera o estado.
2. Componentes com testes de unidade (vitest) e snapshot em 390/1440.
3. Playwright (autoria em tarefa separada, ver cabeçalho).

## 5. Critérios de aceite
- [ ] Preview exato (teste estatístico) e sem efeito colateral
- [ ] Um request por rodada do jogador
- [ ] Conferido em 390 px e 1440 px no staging
- [ ] `npm run build` e `uv run pytest` verdes

## 6. Smoke real
Rodada completa no staging com LLM real: ler presságio → preview → fila de 2 cartas → encerrar → log + narração coerentes.

## 7. Riscos
- Preview com informação demais em criatura desconhecida: preview mostra só o **seu** lado (chance/dano), nunca resistências ocultas (respeita `public_panel`).
