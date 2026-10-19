# SPEC-292 — revisão (review)

> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus (coordenador-revisor) · **Data:** 2026-10-19 · **Commit revisado:** `93a18bf`

## Escopo

Branch `spec-292` (`9bc4714`, `93a18bf`) sobre `main`: `world_utils.py` (mistura sob pressão de
caça, `concealed_faction`, `public_encounter_hint`, `unknown_faction_names`, `check_encounter`),
`agents/storyteller.py` (`encounter_handoff`), `agents/combat.py` (`_faction_withhold_clause`,
`_narrate(withhold=)`), testes em `tests/test_spec289_ameaca_tematica.py`. Fora: renomear a criatura
em `enemies[].name`/API (fora de escopo pela própria spec).

## Verificação por foco

1. **Pool regional (R1).** `regional` é o `filtered` do porte (≤2 Minion, 3 todos, ≥4 Elite), já sem
   BOSS; com `themed`, `strict == regional`, então os extras têm pontuação 0 e entram com peso ×1
   (`theme(e) or 1`). Mistura só quando a média base < `MIGRANT_THRESHOLD + 0.2` (0,5); população
   intacta (base 1×boost) não mistura e o vetor de pesos é idêntico ao da SPEC-289 (todas as
   temáticas têm pontuação > 0). Ordem por id + `rng` → determinístico (teste com 60 seeds repetido).
   Migrantes seguem desligados na camada temática. OK.
2. **Não-vazamento da fação.** Ver P1-1 abaixo: o `public_hint` é calculado e carregado no handoff,
   mas **nenhum consumidor o usa**; o nome canônico com o radical da fação continua visível.
3. **Cláusula do `_narrate`.** Smoke real (abaixo): DeepSeek obedeceu, mas o fallback Groq repetiu
   "Iniciado da Chama Azul" — o próprio prompt manda usar "espécies EXATAS" e lista o nome inteiro
   em "Inimigos ativos". Corrigido na revisão (P2-1).
4. **`hint` canônico/dedupe/manifesto.** `hint` inalterado (teste), dedupe lê `hint`,
   `encounter_handoff` mantém `enemy_id/reason/hint` e só acrescenta `public_hint` quando difere;
   manifesto `systemic` resolve por `enemy_id`. Save sem `public_hint` → nada muda. OK.

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P1-1 | P1 | `world_utils.py:1062-1104`, `agents/storyteller.py:110-123` | `public_hint` não tem consumidor: o objetivo P2-3 (não expor a fação ao jogador que não a conhece) **não é atingido nas superfícies visíveis**. Continuam com o nome canônico ("Iniciado da Chama Azul", "Degolador da Mão Sombria", "Soldado da Legião de Ferro", "Cultista da Destilação"…): `enemies[].name` em `/game/state`/POST/SSE (HUD de combate), `species_label` no `public_view` do manifesto, linhas do log mecânico/chips, e o Bestiário/dossiê via `record_rumor(enemy_id)` no spawn. `combat_target` também recebe o `hint` canônico. | Fora do escopo aprovado da spec (renomear em `enemies[].name`/API). Registrar spec nova: camada de **rótulo de exibição** por observador (nome público derivado de `concealed_faction` até `apply_faction_reveal`), aplicada em state/POST/SSE/history/manifesto público/log/dossiê; o `hint`/id canônicos seguem internos. |
| P2-1 | P2 | `agents/combat.py:818-857` | A cláusula proibia o nome da fação, mas o elenco ("espécies EXATAS") e "Inimigos ativos" entregam o nome da criatura com o radical; smoke real com Groq (fallback FAST) narrou "Iniciado da Chama Azul". | **Corrigido na revisão:** `_concealed_species` lista as espécies cujo nome expõe fação desconhecida e a cláusula manda chamá-las só pelo papel ("'Iniciado da Chama Azul' apenas de 'Iniciado'"), prevalecendo sobre o elenco. Teste novo. |

## Correções aplicadas

- P2-1: cláusula do narrador com rótulo curto por espécie + teste
  `test_narrator_clause_overrides_canonical_name_with_short_label` (commit desta revisão).

## Pendências

- P1-1 → spec nova (dono: coordenador), "rótulo público de combatente de fação oculta" — enquanto
  isso, a SPEC-292 entrega só a parte de narração (prosa) e o dado `public_hint` para o futuro consumidor.

## Comandos rodados

```text
pytest test_spec289 + 288 + 287 + fase2 + fase63 + fase64 + encounter_manifest + fase0 → exit 0
pytest tests/test_spec289_ameaca_tematica.py (pós-correção) → 20 passed
smoke real _narrate, fação desconhecida (Iniciado da Chama Azul), ~12 chamadas FAST (< US$ 0,01):
  antes: DeepSeek 2/2 sem nome; Groq 1/1 citou "Iniciado da Chama Azul"
  depois: Groq forçado 3/3 e DeepSeek 3/3 só "Iniciado" (1 menção descritiva "chama azul" à arma, sem nome da fação)
  fação conhecida: sem cláusula, prosa usa "Iniciado"
suíte completa 1x → ver hand-back
```
