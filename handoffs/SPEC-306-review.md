# SPEC-306 — revisão independente (review)

> Nome do arquivo: `handoffs/SPEC-306-review.md` (nome fixado pela spec §4 Etapa 5 / §5 R13 e pelo coordenador).
> **Veredito:** `APPROVED_WITH_FOLLOWUPS`
> **Revisor:** Opus 5.5 (spec-reviewer, revisão independente) · **Data:** 2026-10-24 · **Commit revisado:** `3d7bb32f`

## Escopo

Branch `spec-306`, `main...3d7bb32f` (commits `93460da8` spec, `3d7bb32f` dados/script/lint).
Arquivos: `data/npc_seed_tables.json`, `services/content_validator.py`
(`validate_npc_seed_tables`), `scripts/npc_seed_review.py`,
`docs/revisao/SPEC-306-sementes-npc.md`, `tests/test_spec306_npc_seed_expansion.py`,
`tests/test_spec306_npc_seed_review.py`. Nada em `evals/`, `services/npc_seed.py` intocado,
`tests/test_spec297_npc_seed.py` sem diff.
Fora de escopo: smoke real §6.2 (3 requests DeepSeek, pendente do coordenador) e suíte completa.

Verificações:

1. **R1/R2.** Conferido de forma independente (sem usar o hash do teste): as primeiras
   36/20/20/19/17/20 linhas de cada tabela no branch são iguais, objeto a objeto, às da `main`.
   O total ficou 61/45/45/44/42/45. As linhas `-` do diff de `data/npc_seed_tables.json` são só a
   vírgula final da última linha antiga de cada lista, mais `_comment` e `version` (R17).
2. **Fontes.** Conferi 50 das 150 linhas novas contra a linha citada, lendo só aquela linha:
   - 47 são sustentadas pelo trecho citado. Exemplos: `prof_parteira_de_favores` (daily_life:71),
     `prof_medidor_de_borda` (locations:111), `prof_leitor_de_cristais` (daily_life:209),
     `des_registros_do_reino` (factions:418), `fear_gas_nas_ossadas` (daily_life:305),
     `fear_osshari_trono` (locations:338), `sec_caminho_seco` (locations:253),
     `sec_ficha_falsa` (daily_life:201), `con_osshari_metodo` (races:291),
     `man_lenco_molhado` (locations:59).
   - 3 têm fonte fraca. Estão nos achados P2.
3. **Lore, D2 e D3.**
   - D2: nenhuma linha nova usa `bandos_orc_saidas_baixas` nem `goblins_mineiros`.
   - D3: vício (`des_largar_o_vicio`, `sec_fungo_vermelho`, `sec_cha_em_excesso`) e contrabando
     (`prof_carregador_de_contrabando`) aparecem em escala pessoal e sem nada gráfico.
   - D4: Ophidia é sempre tratada como alegação (`des_provar_ophidia`, `sec_origem_inventada`,
     `con_jura_ophidia`, `fear_conhecer_de_ophidia`, `man_desenha_ilhas`).
   - R13: comparei os 19 títulos `SEGREDO —` de `lore_nova/secrets.txt` (Praga criada em
     laboratório, Víbora, corpos marcados, Comedor sob Brekmar, aprendiz de Aethelgard, a coisa
     sob Zhur etc.) com as 25 linhas novas de `secrets`. Todas são pessoais: dívida, documento
     falso, dependência, contrabando miúdo. Nenhuma toca um desses títulos. A linha que chega
     mais perto, `fear_osshari_trono`, usa texto público (locations:338), não o segredo de
     secrets.txt:241.
   - R12 (nomes próprios só do Codex público) é coberto pelo teste, que passa.
4. **Lint novo** (`services/content_validator.py:1299-1373`):
   - O prefixo por tabela e o rótulo duplicado (normalizado sem acento nem pontuação) estão
     corretos.
   - O teste de alcance reusa `npc_seed._allowed`, `npc_seed.compatible_factions` e
     `npc_seed.lore_ids`, então tem a mesma semântica do motor: com `factions` preenchido e
     `faction=None` a linha é recusada, como em `npc_seed.py:89-93`.
   - Sem falso positivo: `validate_content.py` dá 0 erros nas 282 linhas, incluindo as 132
     antigas.
5. **Desvio de R6 em `mannerisms`** (6 universais, 14 regionais, 4 raça, 1 facção, contra o alvo
   10/10/4/1): aceitável.
   - Partindo de zero linha regional em con/man, R7 pede no mínimo 12 × 2 = 24 linhas regionais
     somadas, e o alvo de R6 dava só 8 + 10 = 18. A alternativa seria usar linhas com várias
     regiões.
   - Os pisos duros de R6 (universais ≥ 6, restritas ≥ 10, raça ≥ 2, facção ≥ 1) são cumpridos.
   - O desvio está registrado no cabeçalho da spec.
   - As outras 5 tabelas estão dentro de ±2 do alvo (conferido).
6. **Escrita do script.** `scripts/npc_seed_review.py` só grava em `SEED_TABLES_PATH`
   (`data/npc_seed_tables.json`) e em `REVIEW_PATH` (`docs/revisao/SPEC-306-sementes-npc.md`).
   Usa `write_text` com `newline="\n"` (`:75-78`) e recusa ids desconhecidos em `approve`
   (`:268-275`). Não usa LLM nem rede.
7. **Varredura geral.** Nenhum `with_structured_output` novo. Nenhum valor vindo do LLM.
   Nenhum segredo em log. O writer persistente (`approve` → `dump_tables`) tem teste de
   round-trip byte a byte (R17).

## Achados

| ID | Sev. | Arquivo:linha | Problema | Correção |
|---|---|---|---|---|
| P2-1 | P2 | `data/npc_seed_tables.json` (`sec_vende_atalhos`, source `lore_nova/locations.txt:357`) | A linha citada fala dos guias Cinzéus. Não menciona venda de atalhos a bandos nem saque. Na região, "bandos" remete às fações orc/goblin que D2 manda evitar. | Enquanto a linha está `review: "dono"`: reescrever o rótulo para algo como "cobra caro por uma rota que sabe que já mudou", ancorado nas rotas que mudam (locations:353-355), ou citar a linha das saídas baixas, se o dono quiser manter o tema. |
| P2-2 | P2 | `data/npc_seed_tables.json` (`man_de_frente_ao_mar`, source `lore_nova/factions.txt:254`) | A fonte é só o título "OS GRUPOS PIRATAS RIVAIS" e não ancora o maneirismo. | Trocar para `lore_nova/factions.txt:256` ou `:258` (guerra por rota, tensão que escala). |
| P2-3 | P2 | `data/npc_seed_tables.json` (`sec_elfo_ampulheta`, source `lore_nova/factions.txt:323`) | A linha citada é sobre a liderança de Vaelorn (Lady Aerwen). Sustenta a ampulheta só de passagem. | Trocar para `data/origins.json:28` (Ampulheta como traço da raça). Opcional. |
| P2-4 | P2 | `docs/revisao/SPEC-306-sementes-npc.md` (matriz R7) | A cobertura de con+man fica exatamente no piso (1 + 1, ou 0 + 2) nas 12 regiões. Qualquer remoção futura reprova R7. | Nenhuma ação agora. Se o dono recusar alguma linha regional de con/man, reescrever em vez de remover (já previsto em R16/D5). |

Nenhum P0 ou P1.

## Correções aplicadas

Nenhuma até agora. Os P2-1 a P2-3 podem ser corrigidos antes do `approve`, porque as linhas ainda
estão `review: "dono"`. Depois de corrigir, rodar `npc_seed_review.py build`.

## Pendências

- Smoke real §6.2 (3 requests DeepSeek). Responsável: coordenador, antes do `done`.
- Leitura do dono e `approve` (D1/D5). Bloqueia `RPG_SHARED_POOL=on`, mas não bloqueia o `done`.
- P2-1 a P2-3: o executor ou o coordenador corrige no próximo commit da `spec-306`, ou junto com
  a leitura do dono.

## Comandos rodados

```text
bash scripts/dev/py.sh -m pytest -q -p no:cacheprovider -n 2 -W ignore tests/test_spec306_npc_seed_expansion.py tests/test_spec306_npc_seed_review.py tests/test_spec297_npc_seed.py → exit 0, 101 passed
bash scripts/dev/py.sh scripts/validate_content.py → 0 ERRO(S) · 0 AVISO(S)
bash scripts/dev/py.sh scripts/npc_seed_review.py check → "página de revisão em dia", exit 0
bash scripts/dev/py.sh scripts/npc_seed_review.py sample --region skallgard --n 5 → combinações coerentes
script ad hoc: linhas originais da main == prefixo do branch nas 6 tabelas → True ×6; todas as novas com source+review
script ad hoc: linha citada impressa para 50 ids novos → 47 sustentam, 3 fracas (P2-1..3)
git diff main...HEAD -- tests/test_spec297_npc_seed.py → vazio
```
