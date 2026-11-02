# Guia do Bestiário de Valoria (esteira por região)

Fonte: SPEC-349 (§3). Uma onda = uma região = uma spec-filha (`docs/templates/spec-bestiario-onda.md`).
Painel: `docs/bestiario/PAINEL.md` (gerado). Perigos **conceituais** não entram: aqui só criaturas físicas.

## Passo a passo de uma onda

1. **Tabuleiro antes da prosa.** Em `data/bestiario/fichas/<regiao>.yaml` → `vagas:`: família, categoria, papel,
   arquétipo, plano corporal, material e habitat de cada vaga. `scripts/bestiario/lint.py --regiao <r> --vagas`
   precisa passar em U2/U3/U12 antes de escrever uma frase.
2. **Conceitos 2×** (`docs/spec349/conceitos-<r>.md`): o dobro das vagas, com o motivo de cada corte.
3. **Ficha** (`criaturas:`): anatomia (>= 3 partes concretas), silhueta, comportamento, `mecanica_assinatura`
   (o que SÓ esta criatura faz), `contra_jogo`, `padrao`, `a_cada_n`, `telegrafo` e a linha `Aparência`.
4. **Revisor de unicidade** (Opus, nunca o autor) preenche a seção da região em
   `handoffs/SPEC-349-independent-review.md` (checklist §3.9). Só `revisao: aprovada` entra.
5. **Docs gerados** (`scripts/bestiario/gerar_docs.py --regiao <r>`): Codex `curated: true`, doc de arte e `entities_extra`.
6. **Mecânica** (`data/bestiario/mecanica/<r>.yaml` → `scripts/bestiario/gerar_mecanica.py --regiao <r>`):
   Cartas próprias (`data/cards/criaturas/<r>.json`), entrada no `bestiary.json`, `fases` dos chefes em `_decks.json`.
   Vitalidade e Ferimentos vêm da tabela de Corpo; nada vem da prosa.
7. **Arena** (`scripts/bestiario/calibrar.py` e `arena.py`): 45-85 % por criatura em `RPG_ENEMY_DECKS=off` e `on`;
   reinventados com |delta| <= 8 pp contra o slot antes. Ajustes ficam em `data/bestiario/mecanica/_ajustes.yaml`.
8. **Integração**: `scripts/build_rumor_seeds.py`, `validate_content.py` (0 ERRO), `painel.py`, `_esteira.yaml`.

## Eixos e regras U (resumo)

Cada criatura declara família, plano corporal, material, escala, locomoção, percepção e papel tático
(enums fechados em `services/bestiary_lint.py`). Unicidade: U2/U3 (combinação de eixos única na região),
U6 (silhueta com similaridade < 0,6 contra qualquer ficha), U7/U13 (assinatura mecânica não repete), U9 (>= 3 partes
do corpo concretas), U12 (cotas: >= 4 por família, lacaio >= 6 etc.), R29 (mesma cria de demônio não repete
anatomia entre regiões). O gate roda em `uv run python scripts/validate_content.py`.

## Formato da mecânica (`data/bestiario/mecanica/<regiao>.yaml`)

```yaml
criaturas:
  mon_exemplo:
    cartas:
      - {n: Golpe Curto, t: "Texto curto, sem número, no léxico de Valoria.", e: ["d:marcial:cortante"]}
      - {n: Nome da Assinatura, sig: 1, t: "...", e: ["d:leve:cortante", "c:cego:1"], fol: 2}
    aprox: "efeito ideal da ficha -> aproximação da gramática atual"   # só quando o motor não suporta o ideal
```

- A 1ª Carta é o ataque básico (a que a IA joga com `off`). `sig: 1` é a assinatura (oculta; id vem da ficha).
- Atalhos: `d:<leve|marcial|versatil|pesada>:<tipo>` (dano), `a:<n>:<tipo>` (área), `c:<condição>:<rodadas>`;
  o resto é o dict cru da gramática da SPEC-330. `f` = frequência, `fol` = Fôlego, `pc` = palavras-chave.
- Chefe: `fases:` com `ate_vitalidade_pct` 60 e 35/40, `baralho_extra`, `padrao`, `assinatura` e `narracao` com `{nome}`.
- Texto da Carta: <= 140 caracteres, sem dígito, nome <= 4 palavras e único no repositório.

## Exemplos

**Bom:** Estaqueiro Afogado (proteção + provocação aproximam "a fileira que fere quem a atravessa"; a aproximação
fica registrada em `aprox`). **Reskin ruim (barrado):** "Cão de Rebite" → "Cão de Fuligem": mesmo plano corporal
(quadrúpede), mesmo papel (perseguidor), material trocado; U2/U3 e U7 recusam. Troque o plano corporal, o papel **e**
a mecânica de assinatura, não só o material ou o nome.

## Limites conhecidos do motor (efeito ideal × aproximação)

Ver SPEC-349 §9. O motor não tem: veneno determinístico por semente, escala por valor carregado pelo alvo, redução
de Vitalidade máxima do jogador, desvio de ganhos do alvo, estado de objeto reparável, refém com redirecionamento de
dano, convocação de lacaios, bloqueio de Reação e ação extra por rodada. Cada criatura que dependia disso usa a
aproximação mais próxima da gramática, registrada em `aprox:`.
