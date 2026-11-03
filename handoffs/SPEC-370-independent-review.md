# SPEC-370 — revisão de fauna (independent-review)

> Parecer de fauna por lote (R3). Uma seção por lote; este arquivo recebe os lotes 2–4.
> O nome pedido no spawn (`SPEC-370-lote1-independent-review.md`) não passa em
> `scripts/check_handoff_names.py:18-20` (o papel tem de ser sol/astra/terra/luna), então
> segue o nome que a própria spec fixa no R3.

## Lote 1 — Pântano da Melancolia, Brekmar, Skallgard

> **Veredito:** `APPROVED` (depois das correções de conteúdo abaixo, feitas pelo revisor)
> **Revisor:** Opus 5.5 (`spec-reviewer`, independente; `revisor_fauna: opus-370-revisor-lote1`; autor `opus-370-lote1`)
> **Data:** 2026-11-03 · **Commits revisados:** `dfd7ad67`, `489c3bd8`, `7fdfa47e` · **Correção:** `3d9cb47f`

### Escopo

`data/bestiario/fauna/{pantano_melancolia,brekmar,skallgard}.yaml` (30 + 26 + 31 = 87
entradas, 65 fichas + 22 legados) e o trecho da Víbora / migração `suprime` em
`nova_arcadia.yaml`. Checklist da SPEC-360 §3.8 (1–7) mais a SPEC-370 §3.4 (8–12), lido
contra as fichas (`data/bestiario/fichas/<r>.yaml`: anatomia, comportamento,
mecânica) e, no legado, contra `bestiary.json` (`tactical_profile.priorities[].action_hint`,
`cartas`, `resistances`, deck de fase). Ficaram fora: o motor, o avaliador e os testes
(revisão Sol).

### Achados

| ID | Sev. | Arquivo:linha (antes) | Problema | Correção |
|---|---|---|---|---|
| F-01 | P1 | `pantano_melancolia.yaml:636`, `brekmar.yaml:157`, `:202`, `:407`, `skallgard.yaml:211`, `:555` | Item 1: a `marca` mostrava o próprio corpo (nuvem do enxame, tronco de cracas, boia com dedos, volume de verrugas, tronco peludo congelado, ombro do gigante sob a neve), não um vestígio | Trocadas por vestígios: asinhas mortas na poça sem brilho; crosta de anos num casco novo; bolhas fixas contra a corrente; caranguejo preso por fios brancos; monte de geada sem pegada saindo; encosta que "respira" |
| F-02 | P1 | `pantano_melancolia.yaml:114`, `:119` vs `:257`, `:262` | Item 6 (reskin na região): Castor e Borda que Anda tinham o mesmo rumor (a borda medida mais perto da estrada) e o mesmo resto (fita de medição dos druidas) | Castor: rumor do canal represado que não baixa; resto do marco roído com marcas de dente. A Borda fica com o motivo da medição |
| F-03 | P2 | `pantano_melancolia.yaml:400`, `:584` | Item 6: quatro rastros do Pântano com o mesmo motivo, "pegadas que saem e nenhuma volta" (Regaço, Afogado, Druida, Cordão) | Regaço: passos cada vez mais curtos e arrastados até a beira; Afogado: tropa em formação na margem. Druida (levado pela mão) e Cordão (o par se separa) ficam |
| F-04 | P2 | `brekmar.yaml:516` vs `:221` | Item 6: Capangas e Sangria abriam com "Duas linhas de pegadas…" | Capangas: ronda de porta em porta raspando a soleira |
| F-05 | P2 | `skallgard.yaml:698` vs `:305` | Item 6: Urso-Titã e Montaria Cravada com a mesma marca (pinheiro arranhado no alto) | Urso: placa de neve deslizada com rasgo de quatro garras |
| F-06 | P2 | `pantano_melancolia.yaml:65`, `:70` | Item 2: Banhado é `escala: humana` ("velho largo e curvado", mãos enormes), mas o sinal falava em "pegadas enormes" e "velho imenso" | "Pegadas fundas e largas"; "velho largo e curvado" |
| F-07 | P2 | `pantano_melancolia.yaml:591`, `:639`, `:663` | R5 (item 8): contra_jogo do legado prometia o que o baralho não tem: terreno (raso × terra firme) no Afogado e na Sanguessuga, e "ferrão que corrói" no Mosquito (ataque 1d4, cartas `fuga_suja`/`lodo_melancolia`/`coro_colmeia`) | Reescritos a partir do `action_hint` e das cartas: Afogado (resistência a perfurante, implacável), Mosquito (foge ferido, coro de colmeia), Sanguessuga (`mordida_infecciosa`, persegue o mais ferido, foge ferida) |
| F-08 | P2 | `skallgard.yaml:523` | Item 3: Enegrecido que Espera (cria de apetite que "morde quem ficou parado") caçando a Pulga de Forquilha não tem apoio na ficha; a Pulga come o que apodrece, e o Enegrecido é carne morta de gangrena. Das quatro relações da Pulga, era a única sem base | Removida. A Pulga segue com 3 predadores (Ermitão, Mandrião, Lobo da Aurora), todos de porte e hábito compatíveis. E15 continua verde |
| F-09 | P2 | `brekmar.yaml:183` vs `pantano_melancolia.yaml:429` | Item 12 (entre regiões): o mesmo molde de rumor, "mandam contar X antes de…" (luzes do píer × nós da corda) | Pescador: "o bêbado que segue a luz baixa do píer não chega ao barco" |
| F-10 | P2 | `brekmar.yaml:225` | A `marca` da Sangria era uma fala de mercador, não uma marca física | Corte do mercador fechado por uma placa de casca que não é dele |

Conferido e **mantido** (pontos que o autor pediu para olhar):

1. **`suprime` novos.** Todos são entre humanos/ordens com conflito social ou de território, nunca bicho e presa (item 10). Banhado→Casaco é guarda da linha contra saqueador do fundo ("quem vem tirar armadura do fundo ele enfrenta", ficha). Sangria→Capangas é guarda-costas de mercador contra cobrador de sindicato. Ambos aceitos. Casaco→Mula é o mais fraco (territórios quase disjuntos), mas a Mula já `foge_de` Casaco e o efeito é só `PRESA_LIBERADA`: fica.
2. **Demônio comendo humano.** Regaço→Mula se apoia na ficha: o Regaço é resíduo da Tristeza e a Mula carrega Lágrimas que fazem "a tristeza escorrer". Sino→Anzolado também: o Sino vem do resíduo da Casa das Marés, vai atrás de quem está mais sozinho, e o Anzolado é o frequentador da Casa que perdeu o tato. Cisne→Fardo (o Cisne ataca o que brilha; o Fardo carrega moeda e cálice) fica. Boia→Rato e Pescador→Cardume (o Pescador tem porte humano e o Cardume é do tamanho de um bote) são plausíveis no limite; seguem como nota, sem bloquear.
3. **Estações extras** (Mosquito, Sapo, Cágado, Lagarta, Ermitão, Lobo da Aurora, Verme, Titã): todas coerentes com a prosa (insetos no verão; degelo solta o ferro do Ermitão; a Lagarta congela no frio; aurora e neve compacta no inverno). R4: `enemy_lobo_invernal` e `enemy_yeti` carregam inverno 1,5, como em `calendar.json:45`.
4. **Cordão e Viúva** como 2 `imediato` no hub `pantano_melancolia`: está no teto do E18, mas é justificado. O Cordão se disfarça de corda-guia e a Viúva é emboscadora nos marcos (`descoberto → recua para a ocultação`). Brekmar e Skallgard têm 1 cada no hub.
5. **Víbora em NA** ("faca cravada" → "tinteiro virado"): correto. A faca continua só na `marca`, e o R2-02 da 360 fica fechado.
6. **contra_jogo do legado a partir de `action_hint`**: o método é bom e executável. `enemy_declaration` usa `alvo_vulneravel` para mirar (`services/conflict_orchestrator.py:651-656`), e os detalhes vêm das cartas (`mimetismo_morto` → o Cervo "se esconde entre os mortos"; `fenda_sonica` → o chiado do Rato e o grito do Corvo; `roubar_calor` → Lobo da Aurora; `sino_brekmar` → provocação do Cobrador; `carregar_ruina` → carga da Viúva). Só F-07 precisou de ajuste.
7. **Sinais parecidos entre regiões**: a amostra por Jaccard (NA × lote 1, mesmo tipo) tem máximo 0,31 e nenhum par com a mesma imagem, salvo F-09. O par Soldado da Legião (NA) × Afogado da Batalha (botas no mesmo passo) ficou distinto depois do F-03.

Observações sem correção: no legado, o Torcido tem cauda (ficha `brekmar.yaml:869`), então o rastro está certo. O Urso-Titã "recua ferido de morte" segue o perfil (`plano_falhou → flee`), embora a `description` diga que ele não foge; isso é dívida de lore do legado, fora da fauna.

### Correções aplicadas

`3d9cb47f`: F-01 a F-10, as 87 entradas com `revisao: aprovada` e `revisor_fauna: opus-370-revisor-lote1`, `fauna.json` e `rumor_seeds.json` regenerados e `docs/spec360/eval-skallgard.md` reescrito pelo eval (o M3 perdeu a linha do Enegrecido e o hash do M7 mudou, com as duas execuções iguais).

### Pendências

- Nota de autoria para os próximos lotes: `marca` é vestígio, não o corpo disfarçado. Disfarce (isca, tronco, lixo) vai na `aproximacao`.
- Boia→Rato e Pescador→Cardume: plausíveis no limite. Reavaliar se a 372 (tramas) precisar de cadeia mais forte em Brekmar.

### Comandos rodados

```text
scripts/fauna/lint.py --regiao {pantano_melancolia,brekmar,skallgard,nova_arcadia} → 0 erro cada
scripts/fauna/build.py → fauna.json: 125 criaturas
scripts/build_rumor_seeds.py → ok
scripts/validate_content.py → 0 ERRO(S) · 29 AVISO(S)
scripts/fauna/eval.py --regiao pantano_melancolia → todos os gates ok (M1 0,8305 / legado 0,839; M8 0,2758; M5 −0,1632)
scripts/fauna/eval.py --regiao brekmar → todos os gates ok (M1 0,7921 / 0,7938; M8 0,2773; M5 −0,1452)
scripts/fauna/eval.py --regiao skallgard → todos os gates ok (M1 0,7375 / 0,7726; M8 0,3017; M5 −0,1549)
pytest test_spec360_build test_spec312_seeds test_spec370_suprime test_spec370_caps → 33 passed
pytest -m "not slow" test_spec370_eval test_spec360_eval → passed (os slow foram pulados)
```
