# CARTAS — Acervo de Valoria (referência viva)

Referência do sistema de **Cartas** (spec conflito-02 = motor; **conflito-14** =
autoria completa). Espelha [docs/CLASSES.md](CLASSES.md). Fonte de dados:
`data/cards/{devoto,sangromante,corruptor,arcanista,medico}.json`, gerados por
[`scripts/gen_cards_v4.py`](../scripts/gen_cards_v4.py). Motor:
[`services/cards.py`](../services/cards.py).

> **Escala nova (2d10 + Virtude).** Ataque = `2d10 + Virtude` vs Esquiva.
> Dano é **flat** por categoria de arma (doc 01 §19), **não** dado:
> Leve `3` · Marcial `4` · Versátil `6` · Pesada `8`. Crítico ×2, Super ×3 no
> efeito principal. Cartas antigas (`2d6`) foram **reautoradas**, não convertidas.

---

## Schema de Carta

```jsonc
{
  "id": "dev_cons_liturgia", "name": "Liturgia da Espera",
  "origem": "conflito-14",                 // marca as Cartas autorais (vs exemplos do motor)
  "tipo": "ativa|passiva|utilitaria|reacao",
  "classe": "Devoto do Abismo", "subclasse": "consagrado" | "",  // "" = tronco
  "patamar": "inicial|avancado|superior",  // níveis 1-3 / 4-6 / 7-10
  "custo_entropia": 3, "frequencia": "livre|turno|cena|descanso_curto|descanso_longo",
  "virtude_permitida": ["corpo"],          // Virtude do ataque (escolhida ao preparar)
  "efeito": { "kind": "protecao", "valor": 4, "principal": true },
  "central": true,                          // 1 por subclasse: tem Ruptura + Evolução
  "ruptura": { "caminho_a": {…}, "caminho_b": {…} },      // efeito extremo (gera Carga)
  "evolucao": { "caminho_a": {"efeito":…, "ruptura":…},   // permanente, nível 4+, único
                "caminho_b": {"efeito":…, "ruptura":…} }
}
```

**Catálogo FECHADO de `efeito.kind`** (`services.cards.CARD_EFFECT_KINDS`) — nenhuma
Carta autora efeito sem correspondência mecânica (mesmo princípio da conflito-03
para cena). Grupos: dano/dot/cura/estabilizar · protecao/taunt/empurrao/
reposicionar/esconder/marca/aplicar_condicao/purga_condicao/contra_ataque/
vantagem · buff_* /perception · utilitaria · reduzir_carga_aliado (só Médico) ·
bonus_*_por_estagio (Cartas de Virtude).

**Dano ancorado na arma:** todo `efeito.kind == "dano"` traz `categoria_arma` +
`dano_base` (≥ base da categoria; o excedente é pago em Entropia). Guarda de
**parity**: dano puro custeado fica em `1.5 ≤ dano_base/custo ≤ 4.0`.

---

## Economia (motor, conflito-02)

- **Acervo** (`known_cards`) 6 no nível 1, cresce até o teto do nível 10.
- **Preparação** (`prepared_cards`): 4 (nv 1-3) → 5 (4-6) → 6 (7-9) → 7 (10).
  Reorganizar é livre **fora** de combate em zona segura.
- **Frequência** limita reuso por escopo (turno/cena/descanso), reset em cascata.
- **Ruptura** paga o custo normal **e** gera +1 Carga do Abismo mesmo em falha.
- **Evolução A/B** (nível 4+) é permanente e única: substitui efeito normal **e**
  Ruptura base.
- **Cartas de Virtude** (2, fora dos slots): bônus que escala com o Estágio da
  Virtude. Sugestões por combinação em `data/cards/virtude_sugeridas.json`
  (`cards.suggested_virtue_cards`).

---

## Acervo por classe (16 Cartas/classe: 7 tronco + 3×3 subclasse)

### Devoto do Abismo — *ama o Abismo* (tank)
Tronco: Golpe do Convite, Muralha Viva, Convicção, Aguentar, Provocação do
Abismo, Encaixe do Golpe, Sentinela do Fim. **Consagrado** (ritual/marca):
Marca de Sangue Frio, *Liturgia da Espera*✦, Estigma. **Zeloso** (aggro por
ciúme): Ciúme do Abismo, *Não é Seu*✦, Vigília Ciumenta. **Enlutado** (luto):
Lamento, *Peso do Luto*✦, Memória Viva.

### Sangromante — *negocia em sangue* (dano corpo-a-corpo)
Tronco: Corte de Troca, Finta de Sangue, Esquiva Calculada, Pacto Rápido, Passo
Leve, Hemorragia, Último Lance. **Exposto** (espetáculo da dor): Espetáculo,
*Credencial de Dor*✦, Plateia. **Avaro** (acumula p/ golpe único): Reserva de
Sangue, *Cobrança com Juros*✦, Sovinice. **Silencioso** (corte exato): Corte
Exato, *Veia Justa*✦, Frieza.

### Corruptor — *trabalha junto com o Abismo* (controle/DoT)
Tronco: Toque da Decadência, Esporos, Carne Dócil, Farejar Praga, Semear Praga,
Simbiose, Colapso. **Biologia** (carne): Gangrena, *Metástase*✦, Necrose Útil.
**Alma** (vontade): Semente da Dúvida, *Desespero*✦, Erosão de Vontade.
**Inorgânica** (metal/pedra): Ferrugem, *Fadiga do Material*✦, Corrosão Paciente.

### Arcanista Cinzento — *manipula por um instrumento* (dano/controle à distância)
Tronco: Descarga do Instrumento, Faísca Cinzenta, Vazão Controlada, Olho Arcano,
Empuxo Arcano, Manto de Bruma, Torrente Cinzenta. **Calibrado** (segurança):
Válvula de Segurança, *Feixe Calibrado*✦, Regulagem. **Descoberto** (sem
instrumento): Mão Nua no Éter, *Sobrecarga*✦, Nervo Exposto. **Improvisador**
(sucata): Geringonça, *Bomba de Sucata*✦, Remendo Esperto.

### Médico de Campo — *nega o Abismo* (suporte/cura)
Tronco: Sutura de Campo, Torniquete, Estabilizar, Mão Firme, Triagem, Antitoxina,
Última Hora. **Cirurgião de Trincheira** (sob fogo): Reflexo de Trincheira,
*Intervenção Imediata*✦, Sangue Frio. **Boticário** (compostos/purga): Composto
Estimulante, *Purga da Carga*✦, Reagente Certo. **Cirurgião de Ferro** (próteses):
Talas de Ferro, *Prótese de Batalha*✦, Solda Viva.

> ✦ = Carta **central** da subclasse (tem Ruptura + Evolução A/B).

---

## Como reautorar / balancear

1. Editar a fonte em [`scripts/gen_cards_v4.py`](../scripts/gen_cards_v4.py).
2. `uv run python scripts/gen_cards_v4.py` (regenera `data/cards/*.json`).
3. `uv run pytest tests/test_conflito_autoria_cartas.py` (cobertura/kind/dano/
   Ruptura/Virtude/potência/parity).

**Pendências de cutover (conflito-13):** trocar `classes.json.starting_abilities`
para as Cartas iniciais (`STARTING_RECOMENDADO` no gerador, R9) e remover
`data/player_abilities.json` — feito no cutover para não quebrar o caminho antigo
`known_abilities` antes da hora.
