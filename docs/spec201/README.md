# SPEC-201 — Evidência e handoff

Commit auditado: `afe98941a541dc5643b1f2f1f4ef3ba7563fcca6`; `git status` ao fim: só `docs/spec201/**`, `web/e2e/diagnostics/**` e a spec/índice (status). Zero mudança em `web/src/**`, `api.py`, `state.py`, `evals/`.

## O que foi entregue

| Arquivo | Conteúdo |
|---|---|
| `matriz-efeitos.md` | inventário (23 superfícies), **36 linhas** M01–M36 com as colunas de R2, "o que NÃO animar", confirmações repetitivas, pontos previstos (SPEC-204/205/209–211), arte vs mecânica (R13), referências do pacote, auditoria de `motion` |
| `atrito-sem-animacao.md` | 20 itens A01–A20 com evidência e correção sem motion (inclui hitbox confirmada) |
| `gaps-design-system.md` | tokens existentes/ausentes, contagens reproduzíveis por `grep`, tabela componente × 9 estados |
| `medicoes.md` | método, máquina, 3 repetições (blur, EmberField), peso do `motion`, reduced-motion/a11y, `não medido` |
| `capturas/INDEX.md` + 90 PNGs | 1440×900 e 1280×800; baseline `reduce` e `--motion` |
| `dados/*.json` | hitbox, sentinela, estados de carta, setas do tablist, medições brutas |
| `web/e2e/diagnostics/spec201-capture.spec.ts` | captura Playwright (opt-in `RPG_SPEC201=1`) |

## Comandos executados

```bash
cd web && npm run build                                   # verde, 481 módulos
RPG_SPEC201=1 npx playwright test e2e/diagnostics --grep @spec201 --workers=1   # 16 passed, 2 skipped (no-preference de account)
npx playwright test e2e/critical-journeys.spec.ts --workers=1                    # F01-F16: 16 passed
uv run --frozen pytest -q -p no:warnings --ignore=tests/test_project_index.py    # sem falhas
```

## Achados de maior impacto (todos [F], com evidência)

1. **Hitbox do cartão do Create**: clique só no botão (4,5 % da área); centro do cartão não seleciona (confirmado por `elementFromPoint`) → M01.
2. **Dock de combate esmaga o chat**: narração fica com 99 px de altura a 900 px; texto atrás da mão → M13/A17.
3. **Botão "Depois" do LevelUp ilegível** (`.btn` sem variante) e **tokens inexistentes** (`--danger-dim`, 7 usos) deixam o CTA "Jogar Carta" sem preenchimento → M27/A02/A03.
4. **Tablist sem setas**, auto-troca de aba por combate sem aviso, **modais sem foco/Esc**, **narração sem `aria-live`** → M19/M20/M26/A08.
5. **`/data/map` entrega nós não visitados** (DOM mascara, rede não) → M23.
6. `EmberField` custa ≈+4 % de uma thread ociosa; `blur` do StoryLog não é gargalo medido (inconclusivo); `motion` ≈ 30 % do chunk (proxy).
7. Hipóteses da spec refutadas/corrigidas: não há tela de mapa nem de bestiário; `EmberField` **não** roda em `reduce`; Codex não tem estado "bloqueado".

## Handoff para SPEC-208 (top P0, na ordem R14)

P0 de interação (sem motion obrigatório): **M01** hitbox/halo/selecionado · **M15** custo/limite focável · **M14** armar→mirar→`Esc` (via SPEC-205) · **M19/M20** abas com setas e sem auto-troca · **M26/M27** foco de modal e `btn` base · **M08/M30** composer `pending` e delta de dano · **M18** reação contextual · **M23** servidor filtra o mapa (backend, SPEC-210). Transições (M03, M09, M32, M36) só depois, P1–P2.
Decisões em aberto: (D7/Q2) seleção original do arsenal; durações/easing finais e tokens de duração/elevação/estado (gaps §2) ficam para a SPEC-208; se `LazyMotion` entra para reduzir o chunk; filtro `visited` no `/data/map` precisa de spec de backend. Restrições: sob `reduce` o estado final deve ser idêntico; nenhuma imagem ou tooltip carrega custo/dano/alvo; sentinela de segredo ausente do DOM **e** da rede.

## Limites

Account sem dados reais (fixture sem `/account/*`) · estados de combate por fixture, não pelo simulador real · sem leitor de tela, sem throttling, sem mobile · fontes web podem cair no fallback offline · capturas não são baseline visual.

## Armazenamento das capturas

O spec Playwright grava PNG (formato nativo do `page.screenshot`); no repositório as 90 capturas foram convertidas
para WebP (q78) — 16 MB → 2 MB. Ao regenerar, converter com Pillow antes de versionar.
