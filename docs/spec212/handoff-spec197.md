# SPEC-212 → SPEC-197: handoff do gate "beta jogável desktop"

Entrega para o coordenador/dono incorporar na SPEC-197 (esta spec **não** edita SPEC-197, SPEC-198 nem
`scripts/release/checklist.py`).

## Evidência

- Arquivo: `docs/spec212/evidence/gameplay-gate-<sha12>.json` (+ `.md`), formato no estilo do `checklist-<sha12>.json`
  (`schema`, `gate`, `sha`, `dirty_files`, `ok`, `failing`, `results[]` com `name/status/blocking/detail`).
- Pré-condição do go (D6): `ok == true`, `dirty_files == 0`, `strict == true`.
- SHA exigido: o mesmo SHA do `checklist-<sha12>.json` de produção, ou um ancestral comprovado
  (`git merge-base --is-ancestor <sha-do-gate> <sha-do-checklist>`).

## Como gerar (no commit candidato, árvore limpa; Supabase local no ar via `scripts/dev_stack.py start`)

```
uv run python scripts/beta_gameplay_gate.py --strict
```

O script valida o Supabase local, sobe `scripts/audit_local_server.py` (perfil `local`, `RPG_FORCE_MOCK=1`,
`RPG_CLIENT_LATENCY_REPORT=1`) em `--api-port` (default 8204) e o Vite em `--vite-port` (default 4204), gera configs
Playwright temporárias (apagadas ao fim; `workers=1`), roda F01–F40 em `desktop-1440` e `desktop-1280` e a J-V1
(V01–V09) nos dois viewports, aplica os oráculos da régua aos traces, confere `known-issues.md` e grava a evidência.
`--reuse` só relê `web/test-results/` (útil para depurar o relatório; não substitui a execução).
Saída: `{"ok": ..., "failing": [...], "json": ..., "md": ...}` e exit 1 se `ok` for falso.
`dirty_files` é calculado **antes** de gerar qualquer arquivo; commite a evidência depois, em commit seguinte
(o SHA avaliado é o do commit anterior à evidência).

## Proposta de linha para o `decision-request` da SPEC-197

> **Beta jogável desktop certificado:** sim/não — `docs/spec212/evidence/gameplay-gate-<sha12>.json`
> (`ok: true`, `dirty_files: 0`, `strict`), SHA `<sha12>` = SHA do checklist de produção ou ancestral. J-V1 (V01–V09) e
> F01–F40 verdes em 1440x900 e 1280x800; zero pageerror/console.error/request inesperado, zero turno duplicado,
> zero segredo vazado, latência TTFMC/TTLT presente (baseline sem meta), axe sem serious/critical.
> Known issues: `docs/spec212/known-issues.md` sem bloqueador aberto.

## Condições que continuam fora do gate

- Convite de testers: SPEC-218/219 `done` (D-212-5).
- Consentimento/texto legal do export (D-212-4): item da SPEC-197.
- Smoke com provider real (opt-in, spec §6) não faz parte do `done`.
