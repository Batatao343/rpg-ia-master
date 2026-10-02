# SPEC — Execução única da matriz de longrun

> **Status:** `done`
> **Criada/Atualizada:** 2026-08-20
> **Origem:** processo órfão da matriz Groq observado durante a matriz A1
> **Depende de:** `matriz-longrun-multiperfil-niveis`

## 1. Contexto & objetivo

Uma matriz encerrada no terminal continuou viva em segundo plano e consumiu
quota junto da execução DeepSeek. Como a matriz real pode fazer milhares de
requests, o harness deve garantir uma única execução por workspace.

## 2. Requisitos

- **R1:** `matrix-suite` adquire lock atômico antes do preflight e das campanhas.
- **R2:** um PID vivo no mesmo host bloqueia imediatamente a segunda matriz.
- **R3:** lock de PID morto ou conteúdo inválido é recuperável.
- **R4:** somente o dono, identificado por token, remove o lock ao sair.
- **R5:** interrupção e exceção liberam o lock pelo context manager.
- **R6:** `run`, relatórios e o jogo não usam esse lock.

### Fora de escopo

- Coordenar workspaces ou máquinas diferentes.
- Encerrar automaticamente o processo já existente.

## 3. Design técnico

- `playtest/matrix_lock.py`: lock JSON atômico em
  `playtest_runs/.matrix-suite.lock`, contendo PID, host, token e timestamp.
- `playtest/__main__.py`: envolve perfil, preflight e matriz no lock.
- `tests/test_matrix_lock.py`: concorrência, recuperação e propriedade.

## 4. Plano passo a passo

1. Escrever testes do lock vivo, obsoleto e liberação.
2. Implementar o context manager e integrar ao comando.
3. Rodar testes focados e suíte completa.

## 5. Critérios de aceite

- [x] Segunda matriz no workspace é rejeitada sem chamar LLM.
- [x] Lock obsoleto não bloqueia execução futura.
- [x] Saída normal/excepcional libera o lock.
- [x] Suíte completa verde (1608 testes).

## 6. Smoke real

Durante A1, tentar uma segunda invocação deve retornar erro antes do preflight;
após a primeira terminar, o comando volta a adquirir o lock.

## 7. Riscos & compatibilidade

Lock é artefato runtime gitignored. Verificação limita-se ao mesmo host; isso é
coerente com o workspace local do experimento.
