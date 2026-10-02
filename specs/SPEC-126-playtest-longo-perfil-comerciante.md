# SPEC — Playtest longo do perfil comerciante

> **Status:** `done`
> **Criada:** 2026-08-17 · **Atualizada:** 2026-08-20
> **Depende de:** `fase-5.1-harness`, `fase-5.2-invariantes`,
> `fase-5.3-telemetria-relatorio`, `fase-6.1-economia-viva`,
> `fase-6.2-itens-unicos` e
> `conflito-17-volume-conteudo-mundo-vivo` (`done`)
> **Desbloqueia:** validação de economia emergente, arbitragem regional e tuning
> baseado em campanhas completas
> **Aceite:** offline concluído no run `20260819-004210-869761`; rodada real
> concluída em `20260820-112050-208317` com 200/200, `mock=false`, zero erro/
> invariante `error` e US$ 0,162860 de US$ 0,25 aprovados. Achados:
> [relatório real](../docs/playtest-comerciante-real-2026-08-20.md).

---

## 1. Contexto & Objetivo

O perfil `comerciante` atual escolhe aleatoriamente entre quatro frases de
compra, venda e craft, sem memória, rota, leitura de estoque ou objetivo. O smoke
`comercio` prepara um mercado e prova que comprar uma poção reduz ouro e aumenta
inventário, mas não mede restock, escassez, reputação, arbitragem regional,
liquidez, sobrevivência nem interação da economia com uma campanha normal.

Esta spec transforma o perfil em um jogador determinístico, stateful e curioso:
comercia bastante, mas também explora, conversa, aceita missões, enfrenta riscos,
cura e descansa. Ele conhece apenas preços/estoques que um jogador poderia
observar no local. A validação combina cinco campanhas offline de 200 turnos com
uma campanha real de 200 turnos, sempre sobre o mesmo grafo do produto e com
telemetria econômica auditável.

## 2. Requisitos

### Comportamento do perfil

- **R1 — Estado isolado:** `Comerciante.reset()` limpa caderno de preços, rotas,
  objetivos, custo de aquisição e histórico a cada campanha. Mesmo seed/estado
  sob MockLLM produz a mesma sequência; singletons nunca vazam memória.
- **R2 — Observação pública:** o perfil consulta somente uma
  `public_market_snapshot(state)` do local atual: mercador visível, estoque
  efetivo, preços atuais de compra/venda e receitas conhecidas. Não lê estoque de
  outro local, preço futuro, flags secretas, RNG, tabela global ou projeção não
  descoberta.
- **R3 — Caderno de preços:** após observar mercado ou concluir transação, salva
  `(location_id, merchant_id, item_id, mode, unit_price, day, turn)` e custo de
  aquisição do inventário. Decisão de arbitragem usa só observações não vencidas;
  restock/mudança de controle/escassez pode invalidar cotação antiga.
- **R4 — Arbitragem legítima:** pode comprar barato e vender caro em outro local
  quando margem observada supera custo mínimo de viagem/risco. Lucro regional com
  deslocamento e tempo é comportamento desejado. Loop no mesmo local/mercador,
  criação de ouro sem item ou venda acima da própria compra imediata é bug.
- **R5 — Objetivos stateful:** máquina de estados mínima
  `survey → acquire → travel → liquidate → reassess`, interrompível por combate,
  baixa Vitalidade, inventário crítico, quest e oportunidade social. Falha de uma
  transação causa replanejamento, não repetição textual infinita.
- **R6 — Jogador normal:** em janela de 200 turnos, distribuição-alvo é:

  | Família | Faixa aceitável |
  |---|---:|
  | economia (observar/comprar/vender/craft) | 30–50% |
  | exploração/viagem | 15–30% |
  | social | 10–20% |
  | quest | 10–20% |
  | combate/recuperação/sobrevivência | 5–20% |

  Uma ação pode ter uma família primária somente para não inflar contagens.
- **R7 — Sobrevivência:** herda recovery/combat decision comum; com Vitalidade
  baixa usa cura/descanso/fuga conforme disponibilidade. Não vende último item de
  cura quando abaixo de 50%, equipamento ativo nem item necessário ao objetivo de
  quest conhecido.
- **R8 — Inventário racional:** prioriza venda de excedente não equipado, preserva
  únicos por default, não compra acima de estoque/ouro e não crafta sem receita e
  materiais públicos. Quantidade é pequena e limitada por demanda/capital; nada
  de `qty` absurdo para sondar overflow.
- **R9 — Vida narrativa:** conversa com mercadores/NPCs em cena, pergunta sobre
  rotas/escassez, aceita ao menos uma quest quando oferecida e visita regiões
  diferentes. Não usa uma segunda LLM como jogador; política continua Python.
- **R10 — Progressão:** perfil opta por resolver escolhas pendentes pelo mesmo
  caminho do runner. Cinco campanhas offline rotacionam as cinco classes; a real
  usa Sangromante como baseline temático, sem hardcode mecânico da subclasse.

### Telemetria e invariantes

- **R11 — Ledger por turno:** `TurnRecord` registra ação econômica normalizada,
  merchant/local/item/qty, preço unitário, delta de ouro, estoque antes/depois,
  inventário antes/depois, custo de aquisição conhecido e sucesso/rejeição com
  código. Fonte são os outcomes Python, nunca parsing da narração.
- **R12 — Métricas agregadas:** summary/report inclui compras, vendas, crafts,
  recusas por motivo, mercados/itens/regiões distintos, volume, receita, custo,
  margem realizada, net worth, turnover, dias/restocks observados, tempo em cada
  família, rotas de arbitragem e cotações vencidas.
- **R13 — Net worth honesto:** fórmula versionada soma ouro + valor de liquidação
  do inventário no **mercado atual observado**; sem mercado/cotação, item entra a
  custo de aquisição ou valor conservador documentado. Item único não é contado
  duas vezes e equipamento não vira lucro realizado.
- **R14 — Invariantes P0:** zero ouro/qty/estoque negativos, item duplicado,
  venda sem posse, compra sem débito, craft sem consumo, unique duplicado,
  transação aplicada duas vezes, net worth não finito ou mutação econômica vinda
  apenas da prosa.
- **R15 — Invariantes de arbitragem:** mesmo merchant/item/dia deve ter
  `sell_price < buy_price`; roundtrip imediato no mesmo local nunca lucra. Rota
  regional lucrativa é registrada, não acusada, desde que inclua deslocamento e
  posse real.
- **R16 — Anti-loop:** warning se quatro ações econômicas consecutivas forem
  rejeitadas pelo mesmo motivo/item/local; error se oito ações primárias idênticas
  ocorrerem sem mudança relevante de estado. Perfil deve sair, observar ou mudar
  objetivo.
- **R17 — Baseline antes de tuning:** primeira execução produz distribuição de
  margens, net worth/turn e rejeições. Limites de inflação/deflação tornam-se
  constantes de teste somente depois do relatório; esta spec não altera preços
  durante a coleta inicial.
- **R18 — Critério mínimo offline:** cada uma das cinco campanhas completa 200
  turnos ou encerra legitimamente por memorial, com zero erro/invariante `error`.
  No agregado: compra e venda bem-sucedidas, ≥3 mercadores, ≥3 regiões, ≥15
  transações bem-sucedidas e ao menos um restock observado. Craft bem-sucedido é
  meta; ausência vira achado P1, não falsificação de materiais.
- **R19 — Rodada real:** uma campanha de 200 turnos usa LLM real para o jogo,
  `mock=false`, provider/modelo/custo observáveis e zero `FallbackLLM` terminal.
  Fallback entre providers de `ROUTES` é permitido e medido. Execução exige
  `--max-cost` positivo aprovado no momento da rodada e teto de requests coerente;
  aborto por teto é seguro, mas não satisfaz os 200 turnos.
- **R20 — Relatório de produto:** achados são classificados P0/P1/P2 com turno,
  ação, outcome, delta de estado e trecho narrativo. Mudança de economia descoberta
  vira spec própria; a spec de playtest não “conserta” preço silenciosamente.

### Fora de escopo

- Reescrever preços, receitas, escassez ou restock antes de observar a baseline.
- Criar UI completa de loja; `public_market_snapshot` é contrato read-only que
  pode ser reaproveitado depois.
- Usar LLM como agente-jogador ou permitir acesso onisciente ao estado.
- Tratar todo lucro como bug; arbitragem regional com risco/tempo é intencional.
- Garantir craft artificialmente sem que a campanha encontre materiais.

## 3. Design técnico

### 3.1 Observação pública

**Alterar `services/economy.py`:**

```python
class MarketQuote(TypedDict):
    item_id: str
    item_name: str
    stock: int
    buy_price: int
    sell_price: int

class PublicMarketSnapshot(TypedDict):
    location_id: str
    merchant_id: str
    day: int
    turn: int
    quotes: list[MarketQuote]
    known_recipes: list[str]

def public_market_snapshot(state: Mapping[str, Any]) -> PublicMarketSnapshot | None:
    """View read-only do mercado atual; não inicializa/muta estoque no state."""
```

Se `_ensure_stock` for necessário, o caller cria projeção/cópia profunda. Teste
garante igualdade byte a byte do estado antes/depois da observação. O snapshot
aplica hostilidade, escassez, unique holder, reputação e estoque exatamente como
`execute_trade`, evitando simulador paralelo.

### 3.2 Política comerciante

**Alterar `playtest/profiles.py`:**

```python
@dataclass
class ObservedQuote:
    location_id: str
    merchant_id: str
    item_id: str
    buy_price: int
    sell_price: int
    day: int
    turn: int

@dataclass
class TradeGoal:
    phase: Literal["survey", "acquire", "travel", "liquidate", "reassess"]
    item_id: str | None = None
    source_location_id: str | None = None
    destination_location_id: str | None = None
    expected_margin: int | None = None

class Comerciante(_Base):
    name = "comerciante"
    resolve_progression = True

    def reset(self) -> None: ...
    def observe(self, state: dict) -> None: ...
    def decide(self, state: dict, rng: random.Random) -> ProfileDecision: ...
```

Decisões usam helpers de rota/fog of war existentes e textos com item/NPC/local
canônicos. Política de mix usa contadores/necessidade, não `rng.choice` puro. RNG
desempata opções equivalentes para preservar diversidade reproduzível.

Preço observado expira após mudança de dia além do restock ou evento de
controle/rota relevante. O perfil não consulta se ficou inválido; volta a survey.

### 3.3 Telemetria

**Estender `TurnRecord`:**

```python
economy_action: dict = field(default_factory=dict)
action_family: str = ""
gold_before: int = 0
inventory_value_before: int = 0
inventory_value_after: int = 0
net_worth_after: int = 0
market_observed: bool = False
```

`economy_action` contém campos crus sanitizados do outcome; summary agrega sem
reconstruir preço por texto. `playtest/report.py` ganha seção “Economia — perfil
comerciante” e tabela por campanha/mercado/item/rota.

**Novos checks em `playtest/invariants.py`:**

- `economy.transaction_conservation`
- `economy.stock_bounds`
- `economy.immediate_roundtrip_profit`
- `economy.net_worth_finite`
- `profile.merchant_rejection_loop`
- `profile.merchant_action_loop`

Checks recebem snapshots pré/pós/outcome do runner; não inferem pela narração.

### 3.4 Execução reproduzível

Adicionar um comando/orquestrador, sem quebrar `playtest run`:

```powershell
uv run python -m playtest merchant-suite --turns 200 --seed 4100
uv run python -m playtest merchant-suite --turns 200 --seed 5100 `
  --real --max-requests $env:RPG_MERCHANT_MAX_REQUESTS `
  --max-cost $env:RPG_MERCHANT_MAX_COST
```

Offline executa seeds `base..base+4` nas cinco classes, salva manifesto único e
falha se alguma campanha faltar. Real executa uma campanha Sangromante. Saves e
runs continuam em diretórios isolados/gitignored; resume parcial não é aceito
como run completo.

## 4. Plano passo a passo

### Etapa 1 — Market view sem mutação

1. **Testes** (`tests/test_merchant_profile.py`): snapshot atual, hostil/escasso,
   unique, preço consistente com execute, zero mutação e nenhuma visão remota.
2. **Implementação:** `public_market_snapshot` reutilizando funções canônicas.
3. **Verificação:** testes focados verdes.

### Etapa 2 — Perfil stateful e humano

1. **Testes:** reset, determinismo, caderno, expiração, máquina de estados,
   arbitragem com viagem, proteção de cura/equip/unique, anti-loop e mix em
   campanha sintética.
2. **Implementação:** `Comerciante` e helpers.
3. **Verificação:** campanhas curtas determinísticas.

### Etapa 3 — Telemetria e invariantes

1. **Testes** (`tests/test_merchant_telemetry.py`): conservação, preço/estoque,
   net worth, transações/rejeições, mix, report e fixtures quebradas P0.
2. **Implementação:** records, summary, report e checks.
3. **Verificação:** relatório curto contém dados auditáveis.

### Etapa 4 — Suite longa offline

1. **Testes:** CLI/manifests, cinco classes/seeds, falha parcial e status final.
2. **Implementação:** `merchant-suite` e documentação.
3. **Verificação:** 5×200 MockLLM, relatório agregado e transcript amostral; abrir
   specs separadas para P0/P1 antes de tuning.

### Etapa 5 — Campanha real

1. **Preparação:** teto de custo/requests explicitamente aprovado, chaves/rotas
   verificadas, `RPG_FORCE_MOCK` ausente e diretórios isolados.
2. **Execução:** 1×200 real, watchdog e telemetria completa.
3. **Verificação:** critérios R18–R20, auditoria narrativa amostral e relatório de
   achados versionado em `docs/`.

## 5. Critérios de aceite

- [x] O comerciante não usa estado/preço/estoque não observável pelo jogador.
- [x] Política é stateful, reproduzível e limpa entre campanhas.
- [x] Mix de ações permanece nas faixas e inclui comércio, viagem, social, quest
  e sobrevivência.
- [x] Arbitragem regional legítima é distinguida de roundtrip imediato explorável.
- [x] Telemetria prova conservação de ouro/item/estoque por transação.
- [x] Report mede margem, net worth, turnover, mercados, regiões, restock e loops.
- [x] 5×200 offline completam com zero erro/invariante `error`.
- [x] Agregado offline atinge compra+venda, ≥3 mercadores/regiões, ≥15 transações
  bem-sucedidas e ≥1 restock observado.
- [x] 1×200 real completa com `mock=false`, sem FallbackLLM terminal e dentro dos
  tetos aprovados.
- [x] Achados P0/P1/P2 têm evidência; correções pontuais têm regressões
      curtas e qualquer mudança de produto nova continua exigindo spec própria.
- [x] `uv run pytest` verde (suíte completa offline).
- [x] Nenhum structured output novo sem guard de `FallbackLLM`.
- [x] Saves normais e outros perfis do harness continuam inalterados.

## 6. Smoke test com LLM real

O smoke final desta spec é a própria campanha real de 200 turnos, não uma versão
reduzida que esconderia restock/arbitragem. Antes dela, executar 10 turnos reais
para validar rota/provider/telemetria sem contar como aceite.

1. Confirmar `mock=false`, provider/modelo e tetos positivos.
2. Rodar `merchant-suite --real --turns 200` sem fallback determinístico.
3. Inspecionar pelo menos 20 turnos distribuídos entre começo/meio/fim e todas as
   famílias, comparando texto com outcome mecânico.
4. Gerar report/transcript; listar P0/P1/P2 e anexar run_id/custo.

## 7. Riscos & compatibilidade

- **Teste caro/lento:** offline encontra conservação/loops primeiro; rodada real
  só ocorre depois e sempre para em teto aprovado.
- **Perfil artificial:** faixas e máquina de estados aproximam uma pessoa curiosa,
  mas não provam diversão. Transcript amostral continua necessário.
- **Net worth ambíguo:** fórmula conservadora/versionada evita valorizar estoque
  por mercado invisível; mudanças na fórmula quebram baseline e exigem versão.
- **Craft raro:** ausência de materiais pode impedir craft em uma seed; é achado
  de acesso/economia, não autorização para spawn artificial.
- **Tuning prematuro:** a primeira rodada mede; preço só muda em spec de correção
  aprovada, preservando causalidade do relatório.
