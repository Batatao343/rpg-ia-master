# SPEC-216 — eval follow-up (specs desktop que cruzam o breakpoint mobile)

O executor NÃO editou specs/journeys existentes (a tentativa em `critical-journeys.spec.ts` foi bloqueada
pelo classificador de permissão). O contrato mobile congelado (M01: sem `tablist "Abas do painel"`,
navegação "Superfícies", composer só na superfície Chat, sem grupo "Modo de exibição" < 900px) é
incompatível com estes passos < 900px do projeto `chromium` (todos falham só pelo chrome antigo; o produto
desktop >= 900px segue verde, F01–F15, F18–F40 verdes):

- `critical-journeys.spec.ts` F16 responsive_navigation (320/390/768): `Ficha` -> esperar `surface-title`="Personagem"
  e o botão "Mapa" da barra; voltar pelo botão "Chat" da barra (sem `tab Mapa`/`Fechar ficha`).
- `critical-journeys.spec.ts` F17 workspace_modes (loop R12 320/390/768): tocar "Chat" na barra antes de exigir o composer.
- `combat-gesture.spec.ts` @390: "HP so muda..." (usa `Modo de exibição`) e "tooltip no foco" (< 900px o detalhe abre por
  `Detalhes de <Carta>`, não por foco/hover).
- `combat-outcome.spec.ts` SPEC-203 @390: usar a barra ("Chat"/"Combate") em vez do grupo `Modo de exibição`.
- `workspace-shell.spec.ts` "telefone 390" (2 testes): migrar para o contrato da barra inferior.
Alternativa: restringir esses testes a `width >= 900` (cobertura mobile já está em M01–M07).
Pré-existentes (fora da SPEC-216): 2 testes `account-lifecycle` (SPEC-190) falham também em `main`.
