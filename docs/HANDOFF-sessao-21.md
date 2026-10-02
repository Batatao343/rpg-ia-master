# HANDOFF — Sessão 21 → próxima sessão

> Leia junto de `ESTADO_ATUAL.md` (topo) e `CLAUDE.md` (arquitetura).
> Escrito: 2026-07-20. Foco desta sessão: **polish de frontend** +
> **fim do playtest longo de balanceamento** (o que rodava em background na sessão 20).

---

## 1. Frontend — polish de imersão (`done`)

Spec registrada: **[specs/SPEC-054-polish-frontend-imersao.md](../specs/SPEC-054-polish-frontend-imersao.md)**
(`done`, R1–R8). Auditoria visual com Edge headless (screenshots reais). Puro
apresentação — **zero mudança de estado/schema/regra**. Arquivos:
`web/src/components/StoryLog.tsx`, `web/src/styles.css`.

O que mudou (resumo):
- **Leitura como diário iluminado, não chat:** removido o rótulo "Narrador"
  repetido em todo bloco (era o "eyebrow" proibido); capitular por cena +
  fleuron `❧` entre narrações + glow de tocha na coluna de leitura.
- **Bug de camada:** `.atmosphere`/`.ember-canvas` → `z-index:-1`. A tela de
  criação escurecia porque a vinheta pintava por cima quando o `motion` zerava o
  transform. Agora o fundo fica sempre atrás.
- **Criação iluminada:** `.create__frame` lê como pergaminho à luz (lift + glow +
  borda bronze), não bloco chapado.
- **Abas:** 8 abas do HUD quebram em 2 linhas de 4 (`flex-wrap`) — "Codex" não
  corta mais.
- **Mobile criação:** top-align + `width:100%` (respeita padding; sem overflow).

**Verificação:** `npm run build` verde; desktop confirmado por screenshot.
**Pendência honesta:** mobile não 100% verificado em pixel (Edge headless não
emula device de forma confiável pro SPA) — o fix é estritamente mais seguro que o
`96vw` antigo + `overflow-x:hidden` já presente. **Reverificar em device real.**

> `pytest` **não** foi rodado: mudança só-frontend, a suíte é backend e não
> exercita o React. O gate de frontend é `npm run build` (verde).

---

## 2. Playtest longo de balanceamento — `run_id 20260719-160014` (TERMINOU)

O run que rodava em background na sessão 20 **acabou** (exit 0). ⚠️ O aviso da
sessão 20 ("NÃO rode nada no Jina concorrente") está **VENCIDO** — Jina livre.

- **15 campanhas**, ~8,4h (`tempo_total=30247s`), **0 erros de turno**, real
  (mock=não), seed 42. 5 classes × {combate, explorador, quester}.
- **Custo ~$1.28** (classify $0.4975 / fast $0.4767 / smart $0.3071).
  Providers: **deepseek=1675 req**, groq=7 (deepseek carregou tudo).
- Relatório: `uv run python -m playtest report 20260719-160014`
  (grava `playtest_runs/20260719-160014/report.md` — gitignored). jsonl por turno
  no mesmo dir.

### Achados

1. **A telemetria de Entropia NÃO dá sinal de tuning.** `flooding=100%` e
   `starvation=0%` em **TODAS as 15 campanhas** (inclusive as reais). A métrica é
   degenerada (sempre 100/0) → os **8 knobs `[BALANCEAR]` continuam
   indecidíveis** por telemetria agregada. Antes suspeitávamos que era artefato do
   mock; agora sabemos que é da **definição da métrica** (mede algo que é sempre
   100%, provável: "turnos que usaram ataque básico" vs uso de habilidade). Ver
   [spec balanceamento §8](../specs/SPEC-049-balanceamento-classes-pos-playtest.md).
   **Próximo passo real:** ou (a) redefinir flooding/starvation em
   `playtest/telemetry.py`, ou (b) minerar o jsonl por turno pra medir gasto real
   de Entropia (habilidade ativa vs ataque básico). Sem isso, tuning segue no escuro.

2. **Letalidade de early-game persiste.** `combate` e `explorador` morrem cedo
   (turnos **7–30**, nível 1–3). `quester` sobrevive muito melhor (**67–70
   turnos**; Corruptor e Sangromante quester chegaram a **70 turnos sem morrer**,
   nível 3). Combate direto no início ainda é fatal — condizente com a pendência
   conhecida "combate morre nível 1".

3. **Mortes concentradas:** combate → Pântano da Melancolia/Profundezas (Sapo-Boi
   Ácido, Zumbi Blindado, Afogado); explorador → montanhas/farol (Yeti, Troll de
   Ponte, Lobo das Geleiras); quester → **Nova Arcádia** (quests da forja: Vulto
   da Forja, Capanga da Legião, Encapuzado da Fornalha).

4. **Carga do Abismo mal acumula** na maioria — só Devoto (severo 12 e 7) e uns
   poucos leves. Confirma que a Carga é raramente sentida fora do Devoto.

5. **Violação `narrative.recycled_npc` = 43 ocorrências** (warning, não error). A
   spec `encontros-dedupe` era pra ter matado isso — ou o vínculo de local não está
   segurando em run longo, ou é ruído de warning. **Vale investigar** (olhar quais
   NPCs reciclam no jsonl).

6. **1 `[RAG ERROR]` de faiss** no console (`could not open …/index.faiss for
   reading`) — memória de sessão do playtest sem índice inicial; **não-fatal**
   (campanhas com erros=0). Runtime do harness, não bug de produção.

---

## 3. Próximos passos sugeridos (ordem)

1. **Desbloquear o balanceamento:** consertar/redefinir a telemetria de Entropia
   (flooding/starvation degenerados) — sem isso os 8 knobs não saem do lugar.
   Depois, rodar tuning com sinal de verdade.
2. **Early-game combat lethality:** combate/explorador morrendo em <30t nível 1–3;
   revisar spawn/tuning nível 1 (a spec balanceamento-early-game já mexeu nisso —
   pode precisar de 2ª passada com os dados deste run).
3. **`recycled_npc=43`:** confirmar se `encontros-dedupe` segura em run longo.
4. **Frontend:** reverificar mobile em device real; opcionalmente auditar
   Combate/SaveScreen/LevelUpModal (herdaram os fixes mas não foram reauditados).
5. **Smokes reais adiados da sessão 20** (weather-global-vivo, itens-vivos-e-luz)
   seguem pendentes — Jina agora livre.

---

## 4. Estado do git ao fim desta sessão

- `main`, working tree limpo após os commits desta sessão.
- Commitado: frontend polish (2 arquivos) + `specs/SPEC-054-polish-frontend-imersao.md` +
  este handoff + updates de `ESTADO_ATUAL.md`/`ROADMAP.md`.
- `playtest_runs/`, `data/runtime/`, `saves_playtest/` seguem gitignored (nada de
  telemetria no git).
