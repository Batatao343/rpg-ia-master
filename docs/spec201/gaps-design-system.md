# SPEC-201 — Gaps de design system e estados por componente (R5/R6)

Commit auditado: `afe9894`. Arquivo: `web/src/styles.css` (1161 linhas). Todas as contagens abaixo saem dos comandos da seção 4.

## 1. Tokens existentes (`:root`, `styles.css:8-60` — 30 custom properties)

| Grupo | Tokens | Observação |
|---|---|---|
| Cor (OKLCH) | `--bg --bg-deep --steel --surface --surface-2 --line --line-soft --ink --muted --faint --accent --accent-strong --accent-glow --on-accent --danger --danger-bright --danger-glow --mana --stamina` | 74 usos de `oklch(`; paleta coerente, um acento |
| Forma | `--r-sm 4px --r-md 8px --r-pill 999px` | 49 usos de `var(--r-*)` contra 28 `border-radius: <número>` literais |
| Tipografia | `--display --decorative --body --sans --read` | **sem escala de tamanho** (132 `font-size: …rem` soltos) |
| Sombra | `--shadow-deep` | só 1 sombra tokenizada; 53 `box-shadow` |
| Movimento | `--ease: cubic-bezier(0.16,1,0.3,1)` | 33 usos de `var(--ease)`; 4 easings hard-coded (`ease`, `ease-in-out`) |
| Camada | `--z-hud 40 --z-banner 50 --z-overlay 60` | `z-index` literais fora do escopo: 100 (`.pending-operation`, `styles.css:364`), 50 (×2, `:1048,1054`), 3 (`:780`), 2 (`:358`) |

## 2. O que falta (gaps)

1. **Duração**: nenhum token. Valores soltos: 0,16 s (18×), 0,2 s (6×), 0,4 s (5×), 0,18 s (3×), 0,12 s (2×), 0,3 s (2×), 0,5/0,55/0,25 s, mais 0,15 s em `transition:` sem easing (`:856,897,915,986`). `motion` em TSX repete 0,35/0,5/0,55 s.
2. **Elevação**: sem escala (só `--shadow-deep`); `box-shadow` literais com cores `oklch`/rgba (9 `rgba(`/`hsl(`).
3. **Estados** (hover/pressed/selected/disabled/loading/error/revealed/secret): sem tokens nem classes utilitárias. `:active` existe **uma vez** (`.btn`, `:130`). `selected` é reimplementado por componente (`.card[data-selected]`, `.tab.is-active`, `.is-selected`, `[aria-pressed]`). `loading` = `disabled`+"…". `error` = `role=alert` sem estilo próprio. `revealed/secret`: **inexistente**.
4. **Foco por contexto**: um `:focus-visible` global (`:140`, 2 px `--accent`) + exceções (`:1104,1125`); `input:focus` próprio (`:189`); combate usa `--danger` no input (`:805`). Não há halo de foco específico para cartão/alvo/aba.
5. **Espaçamento**: sem escala; 186 `padding:/gap:` literais.
6. **Tokens ausentes mas referenciados**: `--danger-dim` (7 usos; ex.: `.combat-card__play`, `.simulator-shortcut`), `--ink-soft` (3, com fallback `#cbc6ba`/`#efe9dc`), `--gold`, `--ink-faint`, `--text` (1 cada). Efeito prático: o CTA de combate "Jogar Carta" perde preenchimento (`styles.css:947`).
7. **Cores fora dos tokens**: 42 literais hex em 27 linhas — roxos de Entropia/Carga/Reação (`#a15be0`×4, `#8a4fd0`×4, `#704199`×2, `#e2c9f5`), vermelhos (`#d04f4f`×2), bronze (`#b3852f`, `#d08a4f`), neutros (`#cbc6ba`, `#efe9dc`, `#f5e9d6`, `#eadcc4`). Falta token de **recurso Entropia** (hoje só `--mana`/`--stamina`, aposentados).
8. **`transition: all`**: 5 ocorrências (`styles.css:206,252,348,482,589`) — `.btn`-like (`:206`), `.chip`/`.tab`-like, `.iconbtn` (`:348`), `.tab` (`:482`), `.worldmap__dot` (`:589`).
9. **Reduced motion**: um bloco global (`styles.css:825-828`) zera `animation`/`transition` e esconde o canvas; `MotionConfig reducedMotion="user"` não zera `opacity` do `motion`. Sem token/utilitário `--motion-fade`.
10. **Contraste** (cálculo de proxy; ver `medicoes.md`): `--faint oklch(0.58 0.026 78)` sobre `--bg oklch(0.15 0.012 250)` — L 0,58 vs 0,15 ≈ razão >4,5:1 estimada (**não medido** com ferramenta de contraste; axe `wcag2a/aa` retornou **0 violações** nas telas capturadas).

## 3. Tabela componente × estado (R6)

Legenda: **ok** / **parcial** / **ausente**. Evidência = arquivo:linha ou captura. "revealed/secret" documenta a regra: **nenhum** efeito/tooltip/imagem/atributo pode expor `hidden/secret` (ver teste do sentinela em `dados/sentinel.json`).

| Componente | default | hover | focus-visible | pressed | selected | disabled | loading | error | revealed/secret |
|---|---|---|---|---|---|---|---|---|---|
| Auth (`AuthScreen`) | ok | `.btn:hover` ok | global ok | `.btn:active` ok | n/a | opacidade (parcial) | **ausente** (só `disabled`) | parcial (`role=alert`, texto cru) | n/a |
| Saves (`SaveScreen`) | ok | parcial (borda 0,15 s `:915`) | global ok | ausente | n/a | `disabled={busy}` parcial | ausente | ausente | n/a |
| Create — cartão (raça/classe/região) | ok | parcial: hover no `article`, clique só no botão (M01) | parcial (foco no botão, não no cartão) | ausente | ok (`data-selected`, borda `--accent`) | n/a | n/a | n/a | n/a |
| Create — stepper | ok | parcial | global ok | ausente | ok (`aria-current`) | n/a | n/a | n/a | n/a |
| Create — prólogo | ok | n/a | n/a | n/a | n/a | parcial | parcial (`.prologue__pulse`) | ausente | n/a |
| Laboratório (`CombatSimulator`) | ok | ok (`.simulator-shortcut:hover`) | global ok | ausente | ok (botões nível/qtde) | parcial | parcial (`role=status`) | ausente | n/a |
| Topbar/`iconbtn` | ok | ok (`:350`) | global ok | ausente | n/a | ausente (só opacidade genérica) | ausente | n/a | n/a |
| StoryLog | ok | n/a | `tabIndex=0` da seção; foco global | n/a | n/a | n/a | parcial (`.thinking`) | ausente | n/a |
| SceneArtwork/VisualArtwork | ok | ausente | n/a | n/a | n/a | n/a | parcial (fallback por `failedKey`) | parcial | regra: só catálogo público por ID |
| Composer (input/Agir/Voz) | ok | `.btn:hover` ok | global + `input:focus` ok | `.btn:active` ok | n/a | parcial (opacidade) | parcial ("…", sem `aria-busy`) | parcial (Banner; voz com `role=alert`) | n/a |
| Chips de ação / places | ok | ok (`:987`, `:898`) | global ok | ausente | n/a | parcial (`opacity .5`, `cursor:default`) | ausente | n/a | n/a |
| CardHand — cartão | ok | **ausente** no cartão e no `.combat-card__play` | global ok | ausente | **ausente** (sem "armada") | parcial (`opacity .45`) | ausente | ausente | n/a (cartas reveladas só) |
| CardHand — Ruptura | ok | ausente | global ok | ausente | ok (`aria-pressed`) | ok | ausente | ausente | n/a |
| ReactionPrompt | ok | ausente | global ok | ausente | ok (`aria-pressed`/`is-selected`) | ok | n/a | n/a | n/a |
| WoundTrack/SceneZones | ok | n/a (não interativos) | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| Hud — abas | ok | ok (`.tab:hover`) | global ok | ausente | ok (`aria-selected`, `is-active`) | n/a | n/a | n/a | n/a |
| Hud — painéis (ficha/pessoas/facções/crônica) | ok | n/a | `tabpanel tabIndex=0` | n/a | n/a | n/a | parcial | parcial (`combat-empty`) | regra: só o que o servidor enviou |
| WorldMap | ok | ausente (`cursor:default`) | ok (`:1125`) | ausente | ok (`is-current`) | ok (`:disabled` em fog/atual) | ausente | `null` se falhar | **parcial**: DOM mascara ("???"), `/data/map` entrega os nós (M23) |
| CodexTab/Bestiário | ok | ausente | global ok | ausente | ok (`aria-selected` categoria) | n/a | parcial (texto) | parcial (vazio) | **ausente**: sem estado bloqueado; correto por construção (só descoberto) |
| QuestsTab | ok | ausente | global ok | n/a | n/a | n/a | n/a | n/a | n/a |
| LevelUpModal | ok | parcial (`.lvlup__card` borda) | global ok; **sem** foco inicial | ausente | ok (`is-picked`) | ok | ausente | ausente | n/a |
| DeathModal | ok | parcial (`.death-btn:hover`) | global ok; **sem** foco inicial | ausente | n/a | ok | ausente | ausente | n/a |
| Banner | ok | n/a | n/a | n/a | n/a | n/a | n/a | ok (`role=alert`) | n/a |
| OnboardingHint | ok | ok (`iconbtn`) | global ok | ausente | n/a | n/a | n/a | n/a | n/a |
| Image quote/portrait/art card | ok | `.btn:hover` ok | `autoFocus` no diálogo | ok | n/a | ok | parcial (`role=status`) | ok (`role=alert`) | só do dono; quote explícito |
| EmberField | ok (canvas `aria-hidden`) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## 4. Comandos reproduzíveis (R5)

Executar a partir de `web/src`:

```bash
grep -c ":hover" styles.css                          # 22
grep -c "transition: *all" styles.css                # 5  (linhas 206,252,348,482,589)
grep -c ":active" styles.css                         # 1
grep -c "#[0-9a-fA-F]\{3,8\}\b" styles.css           # 27 linhas (42 ocorrências com -o)
grep -c "oklch(" styles.css                          # 74
grep -c "var(--ease)" styles.css                     # 33
grep -c "var(--r-" styles.css; grep -c "border-radius: *[0-9]" styles.css   # 49 vs 28
grep -o "[0-9.]\+m\?s " styles.css | sort | uniq -c | sort -rn              # 0.16s 18x, 0.2s 6x, 0.4s 5x ...
for v in $(grep -o "var(--[a-z0-9-]*" styles.css | sed 's/var(//' | sort -u); do
  [ "$(grep -c -- "^ *$v:\|[ {;]$v:" styles.css)" = 0 ] && echo "undefined: $v"; done
# undefined: --danger-dim (7 usos) --gold --ink-faint --ink-soft (3) --text
```
