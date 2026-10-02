# SPEC — Fase 5.2 — Invariantes de estado (checks pós-turno)

> **Status:** `done` (2026-07-06)
> **Criada:** 2026-07-06 · **Atualizada:** 2026-07-06
> **Depende de:** 5.1 (harness — hook `on_turn_end`) `done`
> **Desbloqueia:** 5.3 (telemetria agrega violações); critério de aceite da Fase 5

---

## 1. Contexto & Objetivo

O motor valida entrada (eventos 2.6, lint 7.1, UUID fase 10), mas ninguém
valida o ESTADO RESULTANTE de um turno: HP pode negativar sem morte, ouro pode
virar -50 por um sinal trocado, item único pode duplicar por um caminho novo,
NPC morto pode voltar a falar, fação derrotada pode continuar controlando um
local — cada um desses já foi bug real ou é regressão plausível de fase futura.

Esta spec transforma as regras implícitas do motor em **invariantes
executáveis**: funções puras `check_*(state) -> list[Violation]` num módulo
único, plugadas no hook `on_turn_end` do harness 5.1 (toda campanha de
playtest audita cada turno) e reutilizáveis em teste/debug avulso
(`assert_invariants(state)` p/ usar em qualquer teste de integração).

Princípio: **estado sólido antes de features** — o invariante é a definição
executável de "sólido".

## 2. Requisitos

Cada invariante = 1 função, 1 id estável, severidade `error|warning`:

- **R1 — vitals:** `0 <= hp <= max_hp` (player, party, inimigos vivos);
  `mana/stamina` idem; `hp == 0` do player ⇒ `game_over=True` no fim do turno.
- **R2 — economia:** `gold >= 0`; qty de inventário `>= 1`; nenhum id de item
  duplicado em slots equipados; item `unique` claimado no máximo 1× no mundo
  (projection + inventário + mercadores — reusa a verdade da 6.2).
- **R3 — entidades:** NPC com `npc_killed` no event_log não aparece como
  `in_scene=True` nem responde depois do turno da morte; companion morto não
  segue na party ativa.
- **R4 — mundo:** `current_location_id` existe no grafo; `visited` ⊆ nós do
  grafo; fação com `defeated=True` não é controladora efetiva de local na
  projection; `world_clock` monotônico (dia nunca volta).
- **R5 — conhecimento:** nenhum texto de mensagem do turno contém conteúdo de
  doc `secret` não revelado (heurística: frases-assinatura dos 4 segredos
  canônicos — pacto de Valerius, Rede Carmesim, identidade do Arauto, Rei
  Subterrâneo — como a 7.3 protege; `revealed_facts` da projection libera).
- **R6 — coerência de save:** `save → load → save` produz estado equivalente
  (campos persistidos idênticos após roundtrip; migrations idempotentes já
  garantidas pela fase 10).
- **R7 — API dos checks:** `check_all(state, prev_state=None) ->
  list[Violation]`; `Violation = {id, severity, turn, message, details}`;
  checks que precisam de delta (clock monotônico, morte no turno) recebem
  `prev_state`. `assert_invariants(state)` levanta AssertionError legível com
  todas as violações (uso em testes).
- **R8 — integração 5.1:** runner ganha `--invariants` (default ON) — violação
  vira entrada em `CampaignResult.violations` (campanha continua; severidade
  error conta no exit code do CLI).
- **R9 — suíte:** teste permanente roda campanha de 10 turnos (2 perfis) com
  invariantes ON e asserta zero violação `error`.

### Fora de escopo

- Corrigir violação automaticamente (invariante detecta; fix é trabalho normal).
- Qualidade narrativa (contradição de prosa) — só estado mecânico + R5 heurístico.
- Telemetria agregada entre campanhas → **5.3**.

## 3. Design técnico

### Arquivos novos

- `playtest/invariants.py` — `CHECKS: list[Check]`, `check_all`,
  `assert_invariants`.
- `tests/test_fase52.py`

### Arquivos alterados

- `playtest/runner.py` — flag `invariants`, coleta em
  `CampaignResult.violations`, `prev_state` mantido entre turnos.
- `playtest/__main__.py` — exit 1 se violação `error`.

### Assinaturas

```python
@dataclass
class Violation:
    check_id: str          # "vitals.hp_bounds", "economy.unique_dupe", ...
    severity: Literal["error", "warning"]
    turn: int
    message: str           # PT-BR, humano
    details: dict          # valores brutos p/ debug

def check_all(state: dict, prev_state: Optional[dict] = None,
              turn: int = 0) -> List[Violation]: ...

def assert_invariants(state: dict) -> None:
    """Uso em testes: levanta AssertionError com TODAS as violações."""
```

Assinaturas dos segredos (R5): constante `_SECRET_SIGNATURES` — frases curtas
e inequívocas por segredo (ex.: "consumiu a família", "pacto com Daruun") —
mesma abordagem curada da 7.3; `revealed_facts`/`secret_revealed` no event_log
desarma a assinatura correspondente.

## 4. Plano passo a passo

### Etapa 1 — vitals + economia (R1/R2)

1. **Testes:** fixtures de estado quebrado — `test_hp_negativo_acusa`;
   `test_hp_zero_sem_game_over_acusa`; `test_ouro_negativo_acusa`;
   `test_unique_duplicado_acusa`; `test_estado_saudavel_zero_violacoes`.
2. **Implementação:** checks + `check_all` + `assert_invariants`.
3. **Verificação:** `/qa` verde.

### Etapa 2 — entidades + mundo (R3/R4)

1. **Testes:** `test_npc_morto_em_cena_acusa`; `test_faccao_derrotada_no_controle_acusa`;
   `test_local_inexistente_acusa`; `test_relogio_regressivo_acusa` (prev_state).
2. **Implementação:** checks.
3. **Verificação:** `/qa` verde.

### Etapa 3 — conhecimento + roundtrip (R5/R6)

1. **Testes:** `test_assinatura_de_segredo_em_mensagem_acusa`;
   `test_segredo_revelado_nao_acusa`; `test_roundtrip_save_load_equivalente`.
2. **Implementação:** checks.
3. **Verificação:** `/qa` verde.

### Etapa 4 — integração no runner (R8/R9)

1. **Testes:** `test_campanha_com_invariantes_zero_errors` (2 perfis × 10
   turnos); `test_violacao_plantada_aparece_no_result` (monkeypatch corrompe
   ouro no turno 2 → violations não-vazio, campanha completa).
2. **Implementação:** flag + coleta + exit code.
3. **Verificação:** `uv run pytest` completo; rodar
   `python -m playtest run --all --turns 30` na mão e ler violações.

## 5. Critérios de aceite

- [x] Estado corrompido de propósito (fixtures) → violação certa, id certo
      (hp<0, hp=0 sem game_over, ouro<0, unique dupe, npc morto em cena, fação
      derrotada no controle, local inexistente, relógio regressivo, segredo vazado)
- [x] Campanhas de 50 turnos dos 10 perfis: zero violação `error`
      (`run --all --turns 50`: `violações(err/warn)=0/0` em 10/10)
- [x] `assert_invariants` utilizável em teste avulso (mensagem legível)
- [x] `uv run pytest` verde (699 testes, 0 falhas)
- [x] Guard de FallbackLLM — N/A (zero LLM)
- [x] Saves antigos continuam carregando (roundtrip idempotente — `check_roundtrip`)

**Achado (entrega):** os 10 perfis passaram limpos em 50 turnos — nenhum bug de
estado novo. `knowledge.secret_leak` fica em severidade `warning` no 1º ciclo
(§7); zero ocorrências no mock e no smoke real (`secret_rusher --real`).

## 6. Smoke test com LLM real

(1 campanha curta) `python -m playtest run --profile secret_rusher --turns 4
--real` → R5 vigia o narrador de verdade: zero assinatura de segredo nas
respostas do Gemini.

**EXECUTADO (2026-07-06):** `secret_rusher --turns 4 --real` — perguntou direto
pelo pacto de Valerius / Rede Carmesim / Arauto / Rei Subterrâneo; narrador real
respondeu sem vazar: `violações(err/warn)=0/0`. R5 vigiou o LLM de verdade.

## 7. Riscos & compatibilidade

- **Falso positivo do R5** (narração menciona rumor público parecido):
  assinaturas são frases da VERDADE oculta, não do rumor (7.3 já separou);
  severidade `warning` no primeiro ciclo, promove a `error` depois de
  estabilizar.
- **Invariante muito estrito** (estado legítimo raro): cada check documenta a
  regra; exceção legítima → afrouxa o check no commit que a justifica.
- **Performance:** checks são O(estado); 50 turnos × 20 checks = irrelevante.
- **Saves antigos / MockLLM / quota:** sem impacto.
