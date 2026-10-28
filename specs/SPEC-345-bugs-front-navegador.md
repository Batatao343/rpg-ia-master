# SPEC-345 — Bugs do teste no navegador (cartas off e on): roster, texto interno, mech log e layout mobile

> **Status:** `approved` (bugfix; o dono mandou destravar em 27/10 — decisões do autor em §8, revogáveis pelo dono)
> **Criada:** 2026-10-27 · **Atualizada:** 2026-10-27
> **Depende de:** nenhuma em aberto (SPEC-199/203/293/316/320–324 `done`; o `mech_log` vem da SPEC-334, já no `main` atrás da flag)
> **Desbloqueia:** linha de base `off` da SPEC-342 (R24) e o smoke "cartas on" antes de ligar as flags

---

## 1. Contexto & Objetivo

Em 27/10 (`main` 4abb270b) o coordenador jogou no navegador com a API local em MockLLM, com as flags de cartas `off` e `on`, a 360×800 e a 1440×900. O resultado está em `docs/spec345/achados-navegador.md` e os prints em `docs/spec345/prints/`. Esta spec corrige os achados que valem **nos dois modos**. O que é só do front das cartas (mão, presságio, fila, Espólio, ações da Forja, chip de desfecho sobre o Espólio) é da SPEC-342, que está em execução em outro worktree. A fronteira está em §2.2.

Ao localizar cada causa no código, três diagnósticos do achado mudaram:

- **Item 1 ("inimigo morto segue no combate"):** o Bandido 0/8 **não está morto**. Vitalidade 0 sem excedente não gera Ferimento (`services/conflict_damage.py:330-345`), e um Padrão só cai ao preencher o último Crítico (`services/death_flow.py:41-52,66-70`; `services/conflict_orchestrator.py:1428-1437`). Por isso ele continua em `combat.enemies` (o filtro `alive` de `api.py:2801-2806` está certo), continua engajado e continua com presságio. O bug real é de **apresentação**: o chip mostra uma barra vazia "0/8" sem dizer que o inimigo ainda está de pé (`web/src/combat/TargetChip.tsx:26-33`). Há também um bug latente que o print não mostra: inimigo morto **de verdade** nunca sai de `scene.positions` (nenhum writer remove posições; `services/conflict_scene.py` não tem função de saída). A API repassa essas posições (`api.py:2838-2856`), e a Arena transforma toda posição desconhecida em chip de **aliado** (`web/src/combat/Arena.tsx:32-42`). Num combate contra 2 Bandidos, quando um morre, ele volta como "aliado" e continua aparecendo em "Engajado: …".
- **Item 7:** o corte "NOVA A…" vem do cabeçalho mobile do workspace (`web/src/workspace/Workspace.tsx:296`; `web/src/workspace.css:156-157`), não de `Hud.tsx`.
- **Item 9 (Forja):** o baixo contraste vem do global `.btn:disabled { opacity: 0.5 }` (`web/src/styles.css:150`). Mexer nisso altera a linha de base `off` da 342, e o painel da Forja é dela (R17/R21). Por isso o item vai para a 342 (D7).

O objetivo é que nenhuma superfície do jogador mostre texto interno (ids, rótulos de prompt, tags `[SISTEMA]`/`[RESULTADO]`), que o roster e o log digam a verdade sobre quem está de pé, e que a tela de 360 px não corte nem sobreponha o essencial. A mecânica continua toda no Python (princípio "mecânica é Python, não LLM"). Esta spec só mexe em views, na fronteira do texto ao jogador e em CSS.

## 2. Requisitos

### 2.1 Achados e causa (evidência)

| # | Achado | Causa no código | Req. |
|---|---|---|---|
| 1a | Bandido 0/8 parece morto | Vitalidade 0 ≠ derrota (`conflict_damage.py:330-345`, `death_flow.py:41-52`); o chip não distingue (`TargetChip.tsx:26-33`) | R1 |
| 1b | Morto vira "aliado" e segue em "Engajado" | `scene.positions` nunca é podado; `api.py:2838-2856` repassa; `Arena.tsx:32-42` cria chip `ally` | R2 |
| 1c | Presságio de quem já não age | `api.py:2967-2968` copia `pressagios_publicos` sem filtrar (o forecast em `agents/combat.py:2295-2310` não filtra na saída pública) | R3 |
| 2 | "Bandido"/"Bandido" no roster | `Arena.tsx:10,24` prefere `species_label` (sem número) a `enemy.name` | **SPEC-342 R28** |
| 3a | "Mortos: Bandido. Espólio: 12 ouro, 1x adaga_ferro." na narração | `agents/loot.py:45-59` troca **toda** prosa com loot por `canonical_summary_text` (`services/conflict_summary.py:291-318`, "própria para prompt/crônica", com `item_id` cru em `:315`); também `narrative_or_fallback` (`:351-356`) usado na narração de combate (`agents/combat.py:2279`) | R4 |
| 3b | "[SISTEMA] Adaga de Ferro (incomum) e +12 de ouro" | `agents/loot.py:233-236,275,326,337,388,401,493,524` e `agents/storyteller.py:2149-2152` anexam a tag; a fronteira só remove `[RESULTADO]` (`services/turn_outcome.py:81-104`) | R5 |
| 316 F-1 | Prosa só com `[RESULTADO] …` vaza crua | `player_facing_message` cai em `_last_ai_text` sem limpar (`services/turn_outcome.py:204-211`; `handoffs/SPEC-316-sol-review.md:86`) | R5 |
| 4 | `? → Bandido 2 · 2d10 …` no mech log | `store_mech_log(..., [player, *enemies])` exclui aliados (`agents/combat.py:2339`; `allies` existe em `:1906-1910`); o fallback é `"?"` (`services/combat_preview.py:180-197`) | R6 |
| 5 | Faixa preta "PREPARAÇÃO 4/4" após o combate | `.deck__head` sticky com `background: var(--bg)` (fundo da página) dentro do painel marrom, e `.deck__msg` vazio com `min-height: 1.1em` (`web/src/components/tabs/tabs.css:3,7`; `CombatDeckTab.tsx:90-94`) | R7 |
| 6 | Tab bar 360: "Personagem"/"Combate" encostam; ponto cortado | 6 botões `flex: 1 1 0` (60 px cada) em `font-size: 0.8rem` com `overflow: hidden` no botão, que corta o ponto; a reticência não funciona em `inline-flex` (`web/src/workspace.css:175-184`; `MobileTabBar.tsx:13-20`) | R8 |
| 7 | Cabeçalho mobile corta o lugar em "NOVA A…" | chip `Combate · rodada N` em `.ws-bar__status { flex: none }` rouba a largura do `.ws-mhead__place` (`Workspace.tsx:296`; `workspace.css:145-157`) | R9 |
| 8 | Banner simulado + onboarding cobrem ~60 % no 1º turno (360) | banner `warn` fixo sobre a história no mobile (`workspace.css:163-167`; texto longo em `App.tsx:357`), mais `OnboardingHint` inteiro no fluxo (`OnboardingHint.tsx:24-52`; `styles.css:1044-1048,1079`; `ChatSurface.tsx:39-40,101`) | R10 |
| 9a | Trilha de ferimentos quebra a 4ª caixa "Leve" a 360 | 3 colunas `1fr` com `flex-wrap: wrap` e caixas de `min-width: 1.3rem` + padding (`styles.css:1008-1011`; `WoundTrack.tsx:16-33`) | R11 |
| 9b | "Afiar …" desabilitado com pouco contraste e sem motivo junto | `.btn:disabled { opacity: .5 }` (`styles.css:150`); motivo só no `forja__hint` acima (`ForjaPanel.tsx:57-65`) | **SPEC-342** (D7) |
| 10 | Carta "Causa 2d6 de dano" num sistema 2d10 de dano fixo | 4 cartas de `data/cards/exemplos.json` usam `efeito.formula: "2d6"` (`golpe_devoto` :18, `corte_sangrento` :96, `praga_lenta` :191, `raio_cinza` :236). O motor **rola** a fórmula legada (`services/conflict_turn.py:261-278`), e o texto vem de `_amount_text` (`services/card_effects.py:1360-1377`). O texto é fiel à mecânica: a inconsistência é de **design** | só registro (D8) |
| e2e | `effects.spec.ts:540` perf: long task 259 > 250 ms | limiar dev `max(250, off+100)` (`web/e2e/effects.spec.ts:529`) medido com 1,9 GB livres | R12 |

### 2.2 Fronteira com a SPEC-342 (front das cartas, em execução)

- **Fica na 342 e esta spec não toca:** `DeckCombat.tsx`, `Hand.tsx`, `EnemyStrip.tsx`, `PlayQueue.tsx`, `PreviewChip.tsx`, `FolegoPips.tsx`, `MechLog.tsx` (apresentação, R23), `KeywordTip.tsx`, `EspolioPanel.tsx`, `ForjaPanel.tsx`, `SceneStrip.tsx`, `deck.ts`, `ContextSurface.tsx`, `ShortcutsSheet.tsx`. Também ficam lá o JSX de `MobileTabBar.tsx` (o `has-loot` da R19.2), `Arena.tsx` (R8 `omens` e R28 homônimos), o texto "Round" de `Hud.tsx:456` (R29), o chip de desfecho sobre o Espólio (R27) e o item 9b (D7).
- **Fica nesta spec:**
  - backend: `api.py::_combat_block` (posições e presságio sem quem saiu), `services/combat_preview.py` e `agents/combat.py:2339` (dados do `mech_log`), `agents/loot.py`, `services/conflict_summary.py`, `services/turn_outcome.py`, `services/turn_delivery.py` e `services/presentation_history.py` (texto ao jogador);
  - front: `TargetChip.tsx` (só o trecho Vitalidade), `CombatDeckTab.tsx`/`tabs.css`, o bloco `.mtabbar*` de `workspace.css`, `Workspace.tsx:296`, `OnboardingHint.tsx`, a cópia do banner em `App.tsx:357`, `WoundTrack.tsx`/CSS da trilha.
- **Arquivos compartilhados:** `TargetChip.tsx` (342 acrescenta a linha de presságio; esta spec só altera o `tchip__vit`/barra) e `workspace.css` (blocos diferentes). Quem pousar por último faz o rebase. A ordem recomendada está em D7.
- O `mech_log` desta spec muda só **dados** (nome do ator). A 342 R23 separa o ator pelo 1º ` · `, e o formato da linha não muda.

### 2.3 Requisitos

- **R1 — Inimigo sem Vitalidade, mas de pé.** Na Arena (modos `off` e `on`), um participante `enemy` com `vit === 0` e `max > 0`:
  - R1.1 — mostra, no lugar de `0/8`, o texto `sem Vitalidade` (classe `tchip__vit is-spent`). A barra fica vazia com o estilo tracejado `is-spent`, e o chip **não** ganha aparência de morto (sem riscado, sem opacidade reduzida).
  - R1.2 — o nome acessível na mira (`TargetChip.tsx:50-52`) diz `Alvo: {nome}, sem Vitalidade — o próximo golpe fere`.
  - R1.3 — nenhum dado novo do inimigo é exposto: espaços de Ferimento continuam fora de `public_panel` (`services/bestiary_knowledge.py:22-58`, R7 da spec do bestiário).
  - R1.4 — jogador e aliados com Vitalidade 0 mantêm o comportamento atual (a `WoundTrack` já mostra os Ferimentos do jogador).
- **R2 — Quem saiu do combate sai do roster.** Em `api.py::_combat_block`, um participante inimigo fora do conjunto `alive` (mesmo predicado de `:2801-2806`: `dead` ou `status ∈ {morto, fugiu, rendido, incapacitado}`):
  - R2.1 — não aparece em `combat.scene.positions`;
  - R2.2 — não aparece em `engaged_with`/`engaged_names` de nenhuma outra posição;
  - R2.3 — o estado do jogo **não** muda: `meta["scene"]["positions"]` continua com a entrada, e só a view é filtrada (round-trip de save idêntico);
  - R2.4 — `encounter_view.participants` continua com todos os participantes e o `status` deles. É o manifesto congelado da SPEC-203, e o oráculo `roster_stable` depende dele.
- **R3 — Presságio só de quem age.** `combat.pressagios_publicos` (com a flag de presságio ativa) não contém linha cujo `actor_id` seja um inimigo fora de `alive`. É um filtro defensivo na view (`api.py:2967-2968`); a lista persistida em `meta` não muda.
- **R4 — Resumo do conflito em voz de jogador.** Toda prosa que o **jogador** vê e que hoje cai em `canonical_summary_text` passa a usar `player_summary_text(summary)`:
  - R4.1 — fallback do loot com espólio (`agents/loot.py:45-59`) e contradição na narração de combate (`agents/combat.py:2279`, via `narrative_or_fallback(..., player_facing=True)`);
  - R4.2 — `player_summary_text` não contém rótulos de campo (`Mortos:`, `Espólio:`, `Caídos:` …), `item_id` nem a lista do espólio, que fica com a linha de registro (R5) e com os chips de ganho (`turn_outcome`). Exemplo: `{"mortos": ["Bandido"]}` → `Bandido tomba.`; `{"mortos": ["Bandido 1", "Bandido 2"], "fugitivos": ["Lobo"]}` → `Bandido 1 e Bandido 2 tombam. Lobo foge.`; sem fato nenhum, a frase neutra de D3;
  - R4.3 — `canonical_summary_text` **não muda**: segue no prompt (`agents/loot.py:509-517`), no arquivista (`agents/archivist.py:882,893`) e nos testes que o assertam (`tests/test_transicoes_criticas_b1.py:211`, `tests/test_review_high_integration.py:104`);
  - R4.4 — a política anti-invenção fica igual: com loot aplicado, a prosa livre do LLM continua substituída (docstring de `agents/loot.py:46-52`). Só muda o texto que a substitui.
- **R5 — Fronteira sem tags internas (inclui 316 F-1).** Nova `strip_system_tags(text) -> str` em `services/turn_outcome.py`:
  - R5.1 — remove a linha inteira de cada `[RESULTADO] …` (comportamento atual de `strip_receipt`, que passa a delegar para ela) e remove só o prefixo `[SISTEMA]` (mais espaços) de cada linha, mantendo o conteúdo ("Adaga de Ferro (incomum) e +12 de ouro"). Linhas vazias repetidas colapsam em uma;
  - R5.2 — é aplicada em `render_player_message` (`:89-104`), nos **dois** ramos de `player_facing_message` (`:204-211`, incluindo o fallback `_last_ai_text`, que fecha o 316 F-1) e na entrega antecipada (`services/turn_delivery.py:61-83`);
  - R5.3 — se o texto ficar vazio depois da limpeza e a mensagem original não era vazia, a fronteira devolve a frase neutra de D3 (nunca `""` nem a tag);
  - R5.4 — `GET /game/history` aplica a mesma função na leitura (`services/presentation_history.py::history_page`), o que limpa entradas antigas sem migração. A função é idempotente;
  - R5.5 — as mensagens **internas** (`state["messages"]`, prompt, arquivista) continuam com a tag. Os testes que leem `out["messages"][0].content` direto do nó seguem válidos (`tests/test_remediacao_comerciante_real.py:82`, `tests/test_spec311_integration.py:58`, `tests/test_spec311_price_reasons.py:433`, `tests/test_review_high_integration.py:109`, `tests/test_loot_voice.py:14`).
- **R6 — Mech log com nome de aliado.** `agents/combat.py:2339` passa `[player, *enemies, *allies]`, e `combat_preview.mech_log` indexa por `id or name` (como `actors_by_id` em `agents/combat.py:1914-1918`). Ator ou alvo sem nome conhecido viram `Alguém`; nenhuma linha começa com `?` nem contém `→ ?`.
- **R7 — Preparação sem faixa preta.** Depois do combate (e fora dele):
  - R7.1 — `.deck__head` usa o mesmo fundo do painel que o contém (token de superfície do `.ws-panel`, nunca `var(--bg)`);
  - R7.2 — `.deck__msg` vazio ocupa altura 0 (`:empty { min-height: 0 }`), mas continua montado com `aria-live="polite"` (`CombatDeckTab.tsx:93-94`);
  - R7.3 — o sticky continua funcionando (o cabeçalho cobre as cartas ao rolar, com o fundo do painel).
- **R7.4 (pedido do coordenador, 27/10) — Faixa da Preparação sobre o título do Acervo.** Nos prints da 342 (`on-1440-forja`, `on-390-espolio`) o `.deck__head` sticky mostrava cartas rolando acima dele (recuo do painel) e colava no título "Acervo". O cabeçalho passa a cobrir o recuo do painel (`margin-top` negativo = padding do `.tabpanel`, 1.1rem; 0.85rem a ≤ 480 px), com `padding-bottom` 0.5rem e borda inferior. Teste: `preparacao_sem_faixa` (e2e).
- **R8 — Tab bar a 360 px.** Com 6 superfícies a 360×800:
  - R8.1 — nenhum botão tem texto transbordando (`scrollWidth <= clientWidth`) e os retângulos dos rótulos não se sobrepõem (folga ≥ 2 px);
  - R8.2 — o ponto de luta (`.mtabbar__dot`) fica inteiro dentro do botão e visível (não cortado por `overflow`). Ele passa a ser posicionado em absoluto (canto superior direito do rótulo), sem empurrar o texto;
  - R8.3 — o alvo de toque continua ≥ 44×48 px (SPEC-216/321);
  - R8.4 — a solução é só CSS no bloco `.mtabbar*` de `workspace.css` (D4). O JSX de `MobileTabBar.tsx` fica para a 342 R19.2.
- **R9 — Cabeçalho mobile em combate.** A 360 px em combate:
  - R9.1 — `.ws-mhead__place` mostra "Nova Arcádia" inteiro (`scrollWidth <= clientWidth`);
  - R9.2 — o chip vira compacto: ícone de combate + `R{n}` visível, com nome acessível `Em combate, rodada {n}` (texto `sr-only`);
  - R9.3 — o desktop continua com "em combate" (`Workspace.tsx:296`).
- **R10 — 1º turno no celular respira.** A 360×800, no 1º turno, com o banner de modo simulado e a dica de onboarding:
  - R10.1 — os dois juntos ocupam ≤ 30 % da altura do viewport, e a 1ª linha da narração fica visível sem rolar;
  - R10.2 — no celular (≤ 600 px), a dica nasce recolhida num `<details>` com o título "Você escreve, o mundo responde" no `summary`. Aberta, mostra a lista e a dica inteiras. O "Dispensar" continua gravando no `localStorage` (`OnboardingHint.tsx:28-37`). No desktop a dica continua aberta como hoje;
  - R10.3 — o banner de modo simulado ganha cópia curta no celular: `Modo simulado: história fictícia (sem IA real).`. O texto completo com `GOOGLE_API_KEY` continua no desktop. `kind` e o auto-dismiss da SPEC-320 não mudam.
- **R11 — Trilha de ferimentos numa linha.** Com `slots = {leve: 4, grave: 2, critico: 2}` (o caso do print) e também com `leve: 5`, a 360 px, cada gravidade cabe numa linha (todos os `span` de uma `.wound-severity__slots` com o mesmo `offsetTop`). As colunas passam a usar a largura do conteúdo (`grid-template-columns: repeat(3, max-content)` com `justify-content: space-between`, ou equivalente), e as caixas ficam com `min-width` ≥ 1.1rem no compacto. O tamanho em 1440 não muda.
- **R12 — Perf do e2e reconfirmado.** `effects.spec.ts` "perf: 4x CPU — criação" roda **3 vezes** isolado (`--workers=1`) com ≥ 3 GB livres:
  - passando nas 3, fica registrado como ruído de máquina (resultado anexado ao handoff);
  - falhando em ≥ 2, abre-se um achado próprio (fora desta spec).

  Em nenhum caso esta spec mexe no limiar de `effects.spec.ts:526-531`.
- **R13 — Nada de regressão nos dois modos.** A suíte offline fica verde. Os prints "depois" são capturados com o mesmo roteiro dos "antes" (`off` e `on`, 360 e 1440) em `docs/spec345/prints/depois/`, com os mesmos nomes de arquivo. Saves antigos carregam sem migração, e nenhum campo do `GameState` muda.

### Fora de escopo

- Homônimos na Arena e no presságio (item 2): SPEC-342 R28.
- Contraste e motivo dos botões desabilitados da Forja (item 9b) e o `.btn:disabled` global: SPEC-342 (D7).
- Tudo que a §2.2 lista como da 342: mão, presságio visual, fila, Espólio, ações da Forja, chip de desfecho, "Round".
- Mudar a mecânica de Vitalidade/Ferimentos ou expor espaços de Ferimento de inimigo (R1.3).
- Converter as 4 cartas `formula: "2d6"` para `dano_base` (item 10): é balanço, fica em spec própria (D8).
- Podar `scene.positions` no estado (R2 é só da view). Isso é writer persistente e pede consulta de ownership: fica para outra spec se aparecer consumidor além da API.
- Relaxar a política anti-invenção do loot (R4.4).
- Limpar `[SISTEMA]` das mensagens internas, do prompt ou do RAG de sessão.
- Mexer no limiar de perf do e2e (R12).

## 3. Design técnico

**Arquivos novos**
- `tests/test_spec345_combat_view.py`: R2, R3 (view de `_combat_block` com inimigo morto, fugido e de Vitalidade 0).
- `tests/test_spec345_player_text.py`: R4, R5, incluindo a sonda do 316 F-1 no POST, no SSE antecipado e no `/game/history`.
- `tests/test_spec345_mech_log.py`: R6.
- `web/tests/spec345-components.test.mjs`: SSR (padrão de `web/tests/deck-components.test.mjs`) de `TargetChip` (R1), `CombatDeckTab` (R7.2: `.deck__msg` montado com `aria-live`), `OnboardingHint` (R10.2: `<details>` com prop `compact`) e `fightChipLabel` (R9.2).
- `web/e2e/spec345-layout.spec.ts`: R7–R11 com o backend fake do e2e (payloads injetados), a 360×800 e a 1440×900.

**Arquivos alterados (backend)**
- `api.py::_combat_block`:
  - `gone_ids = {id de enemy fora de alive}`;
  - o laço de posições (`:2838-2856`) pula `participant_id in gone_ids` e filtra `engaged` por `gone_ids`;
  - `pressagios_publicos` (`:2967-2968`) é filtrado por `actor_id not in gone_ids`.
- `services/conflict_summary.py`:
  - nova `player_summary_text(summary: dict) -> str` (templates abaixo);
  - `narrative_or_fallback(summary, proposed_text, *, player_facing: bool = False)`: com `player_facing=True`, o fallback é `player_summary_text`.
- `agents/loot.py:45-59`: `_validated_narrative` usa `narrative_or_fallback(..., player_facing=True)` e, com loot, `player_summary_text`.
- `agents/combat.py:2279`: `player_facing=True`.
- `agents/combat.py:2339`: `[player, *enemies, *allies]`.
- `services/combat_preview.py:177-201`:
  - chave do mapa de nomes = `str(a.get("id") or a.get("name") or "")`, com `"player"` para o jogador;
  - fallback `"Alguém"`.
- `services/turn_outcome.py`: nova `strip_system_tags`, chamada por `strip_receipt`, `render_player_message` e os dois ramos de `player_facing_message`. A frase neutra (D3) é a constante `EMPTY_NARRATION_TEXT`.
- `services/turn_delivery.py:61-83`: usa `strip_system_tags` (já passa por `player_facing_message`; garantir que o ramo `:81` não reintroduz a tag).
- `services/presentation_history.py::history_page`: aplica `strip_system_tags` ao texto de cada entrada `narrative` devolvida (cópia; o registro persistido não muda).

**Templates de `player_summary_text`** (pt-BR, determinísticos, nomes já passam pelo véu da SPEC-293 em `format_response`):

| Campo | 1 nome | 2+ nomes |
|---|---|---|
| `mortos` | `{n} tomba.` | `{a} e {b} tombam.` (vírgulas + "e") |
| `caidos` | `{n} cai.` | `{…} caem.` |
| `rendidos` | `{n} se rende.` | `{…} se rendem.` |
| `capturados` | `{n} é capturado.` | `{…} são capturados.` |
| `fugitivos` | `{n} foge.` | `{…} fogem.` |
| `inconscientes` | `{n} perde os sentidos.` | `{…} perdem os sentidos.` |

`loot_obtido` não entra (a linha de registro e os chips cobrem). Sem nenhuma cláusula, o texto é a frase neutra de D3.

**Regex de `strip_system_tags`:**
- `[RESULTADO]`: `^[ \t]*\[RESULTADO\][^\r\n]*\r?\n?`, linha inteira, multiline;
- `[SISTEMA]`: `^([ \t]*)\[SISTEMA\][ \t]*`, que vira `\1`;
- depois, `\n{3,}` vira `\n\n` e `strip()`.

**Arquivos alterados (front)**
- `web/src/combat/TargetChip.tsx:26-33,50-52`: `spent = p.role === "enemy" && p.vit === 0 && (p.max ?? 0) > 0`. Com `spent`, mostra `sem Vitalidade` em vez de `0/8`, aplica a classe `is-spent` no `tchip__vit` e na barra, e usa o `aria-label` de R1.2.
- `web/src/workspace.css`: `.tchip__bar.is-spent` tracejado com tokens da 322.
- `web/src/components/tabs/tabs.css:3,7`: o fundo de `.deck__head` passa ao token da superfície do painel (`var(--surface)` ou o que o `.ws-panel` usar; conferir em `workspace.css`), mais `.deck__msg:empty { min-height: 0 }`.
- `web/src/workspace.css:170-184` (só `.mtabbar*`):
  - `.mtabbar__btn` com `overflow: visible`, `font-size: clamp(0.68rem, 3.2vw, 0.8rem)`, `letter-spacing: 0` e `padding-inline: 0.1rem`;
  - `.mtabbar__dot` com `position: absolute; top: 0.45rem; right: 0.2rem`;
  - um `@media (max-width: 380px)` se o clamp não bastar.
- `web/src/workspace/Workspace.tsx:296`: no mobile, `<Icon name="combat" /> R{n}` + `<span className="sr-only">Em combate, rodada {n}</span>`. O texto vem de `fightChipLabel(round, mobile)`, exportada de `web/src/workspace/fightChip.ts` (novo, puro, testável).
- `web/src/components/OnboardingHint.tsx`: prop `compact?: boolean`. Com `compact`, a raiz vira `<details className="onboard">`, o `summary` leva o título e o botão Dispensar, e o corpo é igual. `ChatSurface.tsx:101` passa `compact={mobile}`.
- `web/src/App.tsx:357`: cópia do banner por viewport, via `isMobileViewport(window.innerWidth)` de `workspace/mobileSurface.ts:14` (sem hook novo).
- `web/src/styles.css:1008-1011` (trilha de ferimentos): colunas `max-content` + `justify-content: space-between`; `.wound-severity__slots { flex-wrap: nowrap }`; `min-width: 1.1rem` no compacto.

**Schemas:** nenhum campo novo em `GameState`, `GameResponse` ou tipos TS. `combat.scene.positions` e `pressagios_publicos` só encolhem quando há inimigo fora de combate.

## 4. Plano passo a passo

Testes primeiro em cada etapa. Subagente roda só os arquivos do escopo, com `-n 2` no máximo (CLAUDE.md).

### Etapa 0 — reproduzir (vermelho)
1. **Testes:**
   - `tests/test_spec345_combat_view.py::test_inimigo_morto_sai_das_posicoes_e_engajamentos`: 2 Bandidos, `bandido_1` com `dead=True, status="morto"` e ainda em `scene.positions` e no `engaged_with` do player. Asserta que `_combat_block(state)` não tem `bandido_1` em `positions` nem em `engaged_names`; **falha hoje**.
   - `::test_inimigo_vitalidade_zero_continua_no_combate`: `vitalidade=0`, sem `dead`. Asserta que ele segue em `enemies` e `positions` (passa hoje e trava a regressão).
   - `::test_pressagio_sem_ator_morto`.
   - `::test_estado_nao_muda` (deepcopy antes/depois).
   - `web/tests/spec345-components.test.mjs::targetchip_sem_vitalidade`: falha hoje.
2. **Verificação:** os novos falham pelo motivo esperado; nada mais quebra.

### Etapa 1 — roster e presságio (R1–R3)
1. **Testes:** os da Etapa 0, mais `targetchip_aria_mira_sem_vitalidade` (R1.2) e `targetchip_jogador_zero_inalterado` (R1.4).
2. **Implementação:** `api.py::_combat_block`, `TargetChip.tsx` e CSS `is-spent`.
3. **Verificação:** `bash scripts/dev/py.sh -m pytest -q tests/test_spec345_combat_view.py tests/test_combat_targeting.py tests/test_encounter_manifest.py tests/test_enemy_intent_node.py tests/test_api_jogadas.py tests/test_spec293_rotulo_faccao.py`; `cd web && node --test tests/spec345-components.test.mjs`.

### Etapa 2 — texto ao jogador (R4, R5)
1. **Testes** (`tests/test_spec345_player_text.py`):
   - `test_player_summary_templates`: parametrizado com a tabela de §3; asserta ausência de `:` de rótulo e de `_`.
   - `test_loot_tesouro_sem_id_nem_rotulo`: nó do loot com `conflict_summary` e roll fixo `adaga_ferro`. A fronteira (`format_response`) devolve `message` sem `adaga_ferro`, `Mortos:`, `Espólio:` e `[SISTEMA]`, mas com `Adaga de Ferro`.
   - `test_mensagem_interna_mantem_ledger`: `out["messages"][0].content` ainda contém `[SISTEMA]` (R5.5).
   - `test_316_f1_so_recibo_post`: `AIMessage("[RESULTADO] Voce ganhou 500 ouro")` → `player_facing_message` == `EMPTY_NARRATION_TEXT`.
   - `test_316_f1_so_recibo_sse`: idem em `turn_delivery.early_narrative`.
   - `test_sistema_prefixo_removido_conteudo_mantido`.
   - `test_idempotente`.
   - `test_history_limpa_entrada_antiga`: entrada `narrative` gravada com `[SISTEMA]` sai limpa de `history_page`.
   - `test_combate_contradicao_usa_resumo_jogador`: `agents/combat.py:2279` com prosa que "revive" um morto devolve `Bandido tomba.`.
   - **Atualizar** `tests/test_review_high_integration.py:108`: `"Espólio: 7 ouro." in rendered` passa a esperar o resumo de jogador. O assert de prompt em `:104` fica.
2. **Implementação:** `conflict_summary.py`, `loot.py`, `combat.py:2279`, `turn_outcome.py`, `turn_delivery.py`, `presentation_history.py`.
3. **Verificação:** `pytest -q tests/test_spec345_player_text.py tests/test_review_high_integration.py tests/test_loot_voice.py tests/test_fase43.py tests/test_remediacao_comerciante_real.py tests/test_spec311_integration.py tests/test_spec311_price_reasons.py tests/test_turn_delivery.py tests/test_streaming.py tests/test_turn_outcome_endpoints.py tests/test_transicoes_criticas_b1.py tests/test_conflict_summary_lifecycle.py -n 2`.

### Etapa 3 — mech log (R6)
1. **Testes** (`tests/test_spec345_mech_log.py`):
   - `test_ataque_de_aliado_tem_nome`: ataque com `actor_id` de aliado de cena (Mestre Aldric) → linha começa com `Mestre Aldric`.
   - `test_aliado_sem_id_usa_nome`.
   - `test_desconhecido_vira_alguem`: nenhuma linha com `?` como ator ou alvo.
   - `test_integra_no_no`: `combat_node` com deck `on`, aliado de cena e RNG fixo; `combat_meta["last_mech_log"]` sem `?`.
2. **Implementação:** `combat_preview.py`, `agents/combat.py:2339`.
3. **Verificação:** `pytest -q tests/test_spec345_mech_log.py tests/test_combat_preview.py`.

### Etapa 4 — layout mobile e painel (R7–R11)
1. **Testes:**
   - `web/tests/spec345-components.test.mjs`: `deck_msg_montado_vazio`, `onboarding_compact_details`, `fight_chip_label`.
   - `web/e2e/spec345-layout.spec.ts`, com `test.use({ viewport: { width: 360, height: 800 } })` e payload fake:
     - `tabbar_sem_sobreposicao` (R8.1);
     - `tabbar_ponto_visivel` (R8.2: retângulo do ponto contido no do botão; `getComputedStyle(btn).overflow !== "hidden"` ou ponto fora da área cortada);
     - `tabbar_alvo_toque` (R8.3);
     - `cabecalho_lugar_inteiro_em_combate` (R9.1);
     - `primeiro_turno_respira` (R10.1: soma das alturas de `.banner` e `.onboard` ≤ 240 px, e a 1ª `.msg--story` visível);
     - `trilha_ferimentos_uma_linha` (R11, com leve 4 e 5);
     - `preparacao_sem_faixa` (R7.1: `background-color` de `.deck__head` igual ao do painel ancestral; R7.2: altura de `.deck__msg` vazio = 0).
   - Os mesmos de R7/R11 a 1440×900, para garantir que nada mudou no desktop (R9.3, R10.2 desktop aberto).
2. **Implementação:** CSS e TSX listados em §3.
3. **Verificação:**
   - `cd web && npm run lint && npm run typecheck && node --test tests/spec345-components.test.mjs`;
   - `npx playwright test e2e/spec345-layout.spec.ts e2e/mobile-single-pane.spec.ts e2e/mobile-budget.spec.ts e2e/combat-outcome.spec.ts e2e/visual-surfaces.spec.ts e2e/turn-wait.spec.ts --workers=1`;
   - se `visual-surfaces` tiver snapshot afetado pela mudança intencional, atualizar só os snapshots dos componentes tocados, com justificativa no commit.

### Etapa 5 — reconfirmações e prints (R12, R13)
1. Medir RAM livre. Com ≥ 3 GB, rodar 3× `npx playwright test e2e/effects.spec.ts -g "perf: 4x CPU — criação" --workers=1` e anexar `test-results/effects-perf.json` de cada rodada ao handoff.
2. Prints "depois" com o roteiro de `docs/spec345/achados-navegador.md` (API local MockLLM; flags `off` e `on`; 360 e 1440), salvos em `docs/spec345/prints/depois/` com os mesmos nomes de `prints/`.
3. Coordenador: suíte completa 1× no pouso.

## 5. Critérios de aceite

- [ ] R1: `targetchip_sem_vitalidade`, `targetchip_aria_mira_sem_vitalidade` e `targetchip_jogador_zero_inalterado` verdes; print `depois/on-360_07-conflito-inicio.png` e `depois/off-360_08-conflito-painel-mobile.png` mostram "sem Vitalidade".
- [ ] R2/R3: `tests/test_spec345_combat_view.py` verde (4 testes), `test_estado_nao_muda` incluído; `tests/test_encounter_manifest.py` e `tests/test_combat_targeting.py` sem alteração e verdes.
- [ ] R4/R5 (+316 F-1): `tests/test_spec345_player_text.py` verde; prints `depois/on-1440_12-r1-pos.png` e `depois/off-1440_13-desfecho.png` sem `adaga_ferro`/`pocao_cura`, `Mortos:` e `[SISTEMA]`; F-1 marcado como resolvido em `handoffs/SPEC-316-sol-review.md` pelo coordenador.
- [ ] R6: `tests/test_spec345_mech_log.py` verde; no smoke `on`, o mech log do ataque de Mestre Aldric traz o nome dele.
- [ ] R7: `preparacao_sem_faixa` (360 e 1440) verde; prints `depois/off-360_12-desfecho.png` e `depois/off-1440_13-desfecho.png` sem faixa preta.
- [ ] R8: `tabbar_sem_sobreposicao`, `tabbar_ponto_visivel` e `tabbar_alvo_toque` verdes; prints `depois/on-360_09-mao.png` e `depois/off-360_06-jogo.png`.
- [ ] R9: `cabecalho_lugar_inteiro_em_combate` + `fight_chip_label` verdes; print `depois/on-360_07-conflito-inicio.png` com "NOVA ARCÁDIA" inteiro.
- [ ] R10: `primeiro_turno_respira` + `onboarding_compact_details` verdes; print `depois/off-360_06-jogo.png`.
- [ ] R11: `trilha_ferimentos_uma_linha` verde (leve 4 e 5); print `depois/on-360_19-r3-pos.png`.
- [ ] R12: 3 rodadas do perf registradas no handoff (passou 3/3 = ruído; senão, achado aberto).
- [ ] R13: e2e da Etapa 4 verdes com `--workers=1`; `npm run lint`/`typecheck` limpos.
- [ ] `uv run pytest` verde (suíte completa offline, coordenador, 1×).
- [ ] Nenhum `with_structured_output` novo (sem guard novo a exigir).
- [ ] Saves antigos continuam carregando (nenhum campo de estado alterado; R2.3, R5.4).
- [ ] Revisão independente por outro agente (`spec-reviewer`).

## 6. Smoke test com LLM real

A prosa do LLM real passa pela mesma substituição do loot (R4.4) e pela mesma fronteira (R5). O MockLLM não mostra se o modelo escreve `[SISTEMA]`/`[RESULTADO]` sozinho. Roteiro com a API local e a chave real (DeepSeek, via `ROUTES`), ≤ 6 requests por modo:

1. `off`: nova jornada → "Ataco o bandido" → repetir até o desfecho → "Vasculho o corpo". Conferir no `message` do POST, no evento `narrative` do SSE e em `/game/history`: sem `[SISTEMA]`/`[RESULTADO]`, sem id com `_`, sem `Mortos:`/`Espólio:`, e o nome do item legível.
2. `on` (preset de flags de cartas): mesma sequência com Mestre Aldric em cena. Conferir que `combat.mech_log` não tem `?` e que o Bandido com Vitalidade 0 aparece como "sem Vitalidade" até cair.
3. Anotar no handoff: os textos recebidos (trecho), o provider e o modelo da telemetria, e o nº de requests.

## 7. Riscos & compatibilidade

- **Saves antigos:** nenhum campo novo. R2 e R3 só filtram a view. R5.4 limpa o histórico antigo na leitura, de forma idempotente, sem reescrever o save.
- **MockLLM / FallbackLLM:** o caminho do loot já cai no fallback determinístico, que agora é `player_summary_text`. O `FallbackLLM` continua tratado em `agents/loot.py:166-169`.
- **Quota/latência:** nenhuma chamada LLM nova. `strip_system_tags` é regex O(n) na fronteira.
- **Oráculos e evals:** `encounter_view` fica intacto (R2.4), então `roster_stable` (SPEC-212) não muda. Nenhum evaluator, dataset ou baseline é tocado. O assert atualizado em `tests/test_review_high_integration.py:108` é teste de produto, não eval protegido (`evals/protected-paths.txt`).
- **SPEC-342:** há conflito de merge em `TargetChip.tsx` e `workspace.css` (blocos distintos). As mudanças visíveis no modo `off` (tab bar, cabeçalho, Preparação, trilha, banner/onboarding, texto do loot) alteram a linha de base R24 da 342. Ver D7.
- **Playtest:** invariantes e transcrito leem o estado e a mensagem interna (R5.5), que continuam com a tag. `playtest transcript` pode passar a usar `strip_system_tags` em spec futura.

## 8. Decisões (autor, por delegação do dono em 27/10; o dono pode revogar)

- **D1 — Item 1 é apresentação, não morte.** Escolha: rótulo "sem Vitalidade" no chip, sem expor espaços nem contagem de Ferimentos do inimigo (mantém a R7 do bestiário). *Alternativa:* mostrar "ferido" quando o inimigo já levou Ferimento. O jogador deduz isso pelo log, mas seria campo público novo. *Recomendação:* a escolha. Se no playtest "sem Vitalidade" ainda confundir, abrir spec curta para "ferido".
- **D2 — `[SISTEMA]` na fronteira.** Escolha: remover só a tag ao entregar ao jogador e manter o conteúdo; o estado interno continua com a tag (R5.5). *Alternativas:* (a) apagar a linha quando os chips de ganho já cobrem o espólio, o que perde a raridade "(incomum)" e quebra avisos como "Não há mercado disponível"; (b) reescrever as 7 origens em `agents/loot.py`/`storyteller.py`, o que toca 5 testes de nó e não cobre `[RESULTADO]` vindo do LLM. *Recomendação:* a escolha. Cobre as duas tags, inclusive vindas do modelo.
- **D3 — Frase neutra quando a limpeza esvazia o texto.** Escolha: `EMPTY_NARRATION_TEXT = "O momento passa; o registro do turno guarda o resultado."`. Também serve de resumo sem fatos em `player_summary_text`. *Recomendação:* aceitar. Ajuste de voz é troca de constante.
- **D4 — Tab bar só com CSS.** Escolha: fonte com `clamp`, ponto em absoluto e `overflow` visível; nada de rótulos curtos (no desktop, "Ficha" e "Personagem" são coisas distintas) nem ícones novos. Isso evita conflito com a 342 R19.2 em `MobileTabBar.tsx`. *Alternativa:* ícone sobre rótulo (família da 322). *Recomendação:* a escolha. Se a 360 o `clamp` deixar o texto < 11 px, passar para ícone + rótulo em spec da 322.
- **D5 — Chip de combate compacto no celular.** Escolha: `⚔ R{n}` visível, com nome acessível por extenso. O título da superfície já diz "Combate" quando a aba está aberta. *Recomendação:* aceitar.
- **D6 — Onboarding recolhido e banner curto só no celular.** Escolha: `<details>` fechado e cópia curta. O desktop fica como está. *Alternativa:* adiar o banner simulado até a dica ser dispensada. *Recomendação:* a escolha. Em staging com LLM real o banner nem aparece.
- **D7 — Fronteira e ordem de pouso com a 342.** Escolha:
  - item 2 (homônimos) fica na 342 R28, que já o especifica;
  - item 9b (Forja e `.btn:disabled` global) vai para a 342, como R32 sugerida: "botões desabilitados com motivo junto e rótulo legível, sem `opacity` no texto". A Forja é dela (R17/R21), e mexer no `.btn:disabled` global muda a linha de base R24 dela;
  - **a 345 pousa primeiro** (é menor e só corrige bug), e a 342 captura ou recaptura a linha de base R24 depois do rebase.

  *Recomendação:* o coordenador avisa a sessão da 342 sobre R32 e a ordem de pouso.
- **D8 — Item 10 (2d6) só registrado.** As 4 cartas de `data/cards/exemplos.json` (`golpe_devoto` é carta inicial do Devoto) rolam `2d6` de verdade pela via legada (`services/conflict_turn.py:276-278`). O texto é fiel. Trocar por `dano_base` muda o balanço (média 7 contra os 3–5 das cartas novas) e afeta a arena por Postura (339/341). *Recomendação:* spec própria de balanço ou incluir na SPEC-341, com o dono decidindo o número. Não mudar nada nesta spec.
- **D9 — Sem flag nova.** É correção nos dois modos. O texto e o layout não pedem rollout gradual, e o registro de flags da SPEC-340 não muda. *Recomendação:* aceitar.

**Desvios da execução:** (a) R10.2: o botão Dispensar fica dentro do `<details>` (primeira linha do corpo), não no `summary` (botão interativo dentro de summary é frágil); (b) R8.3: altura mínima de toque medida = 44 px (o `.play .mtabbar__btn` já impõe 44; 48 nunca valeu em runtime); (c) teste SSR `deck_msg_montado_vazio` não escrito (CombatDeckTab pesado para SSR), coberto pelo e2e `preparacao_sem_faixa`.

**Nota do coordenador (27/10):** D7 ajustada — a SPEC-342 pousa primeiro (já em revisão); a 345 faz rebase sobre ela, absorve o item 9b (`.btn:disabled`/Forja, ex-R32 sugerida) e regrava a linha de base R24 da 342 quando suas correções mudarem o caminho `off`.
