// SPEC-208 §3.3: catálogo dos efeitos ENTREGUES (não é runtime). Fonte da verdade lida por
// tests/design.test.mjs (campos obrigatórios, matrix_ref M\d{2} existente na matriz da SPEC-201,
// teste existente em e2e/effects.spec.ts, interruptible literal).
import type { DurationToken, EasingToken } from "./tokens";

export type EffectContract = {
  id: string;
  /** Linha da matriz de efeitos da SPEC-201 (docs/spec201/matriz-efeitos.md). */
  matrix_ref: string;
  reason: string;
  trigger: string;
  states: { start: string; end: string; pending?: string; error?: string };
  duration_token: DurationToken;
  easing_token: EasingToken;
  interruptible: true;
  reduced_motion_fallback: string;
  cost: { cpu: "css" | "transform" | "layout"; bundle_kb_gzip: number; frame_budget_ms: number };
  /** `arquivo::id` — o teste contém o id literal no título. */
  test: string;
  data_dependency: "none" | "player-authorized";
  /** Prompt 05: som é opcional e fica fora desta spec (§8.4). */
  sound: null;
};

const T = "e2e/effects.spec.ts";
const css = (frame = 4) => ({ cpu: "css" as const, bundle_kb_gzip: 0, frame_budget_ms: frame });
const xform = (frame = 6) => ({ cpu: "transform" as const, bundle_kb_gzip: 0, frame_budget_ms: frame });

export const EFFECTS: EffectContract[] = [
  { id: "ctrl.hover", matrix_ref: "M27", reason: "Mostra que o botão é acionável (elevação <= 2px, sem layout shift).",
    trigger: "pointerenter (hover:hover)", states: { start: "repouso", end: "elevado (--elev-1), troca no ato (R8: sombra não transita)" },
    duration_token: "instant", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Borda/brilho estáticos; sem translate.", cost: css(), test: `${T}::ctrl.hover`, data_dependency: "none", sound: null },
  { id: "ctrl.press", matrix_ref: "M27", reason: "Confirma o toque antes do envio (pressionar).",
    trigger: "pointerdown / :active", states: { start: "repouso", end: "pressionado (translateY 1px)" },
    duration_token: "instant", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Sem translate; fundo --state-pressed.", cost: css(2), test: `${T}::ctrl.press`, data_dependency: "none", sound: null },
  { id: "ctrl.focus", matrix_ref: "M01", reason: "Foco visível independente de hover (teclado).",
    trigger: "focus-visible", states: { start: "sem anel", end: "anel --focus-ring" },
    duration_token: "instant", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Mesmo anel (estático).", cost: css(1), test: `${T}::ctrl.focus`, data_dependency: "none", sound: null },
  { id: "ctrl.pending", matrix_ref: "M08", reason: "Ação enviada: rótulo textual e aria-busy; sem espera por animação.",
    trigger: "busy=true", states: { start: "Agir", end: "Enviando…", pending: "Enviando…", error: "botão reabilitado + Banner" },
    duration_token: "fast", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Texto 'Enviando…' + cursor progress.", cost: css(), test: `${T}::ctrl.pending`, data_dependency: "none", sound: null },
  { id: "choice.select", matrix_ref: "M01", reason: "Cartão inteiro seleciona; seleção persiste com marcador textual.",
    trigger: "click em qualquer ponto do cartão", states: { start: "não selecionado", end: "selecionado (borda + 'Selecionado')" },
    duration_token: "fast", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Borda --accent + marcador 'Selecionado'; sem translate.", cost: css(), test: `${T}::choice.select`, data_dependency: "none", sound: null },
  { id: "chat.pending", matrix_ref: "M08", reason: "Composer em estado pendente mostra a fase SSE e bloqueia reenvio.",
    trigger: "busy=true no composer", states: { start: "pronto", end: "pendente", pending: "aria-busy=true", error: "reabilita com texto" },
    duration_token: "fast", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "aria-busy + rótulo 'Aguardando o narrador' (depois do ack).", cost: css(), test: `${T}::chat.pending`, data_dependency: "none", sound: null },
  { id: "turn.status.ink", matrix_ref: "M08", reason: "Traço de tinta na linha de status do turno: o narrador trabalha (SPEC-320).",
    trigger: "turno em espera (stage=waiting)", states: { start: "sem traço", end: "traço desenhado (scaleX 0 → 1)", pending: "repete enquanto espera" },
    duration_token: "slow", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Traço estático e cheio; as fases ✓ seguem em texto.", cost: xform(), test: `${T}::turn.status.ink`, data_dependency: "none", sound: null },
  { id: "tab.indicator", matrix_ref: "M19", reason: "Aba ativa inequívoca; indicador desliza entre abas (layoutId).",
    trigger: "seleção de aba (clique/setas)", states: { start: "indicador na aba anterior", end: "indicador na aba ativa" },
    duration_token: "base", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Troca instantânea; is-active + aria-selected seguem visíveis.", cost: xform(8), test: `${T}::tab.indicator`, data_dependency: "none", sound: null },
  { id: "tab.content", matrix_ref: "M19", reason: "Cross-fade curto do painel sem desmontar o chat nem perder foco/scroll.",
    trigger: "painel de contexto passa a visível", states: { start: "opacity 0", end: "opacity 1" },
    duration_token: "fast", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Troca direta.", cost: css(), test: `${T}::tab.content`, data_dependency: "none", sound: null },
  { id: "split.toggle", matrix_ref: "M13", reason: "Contêiner chat<->split anima só as colunas; sem animação durante o arraste.",
    trigger: "alternar modo split", states: { start: "colunas anteriores", end: "colunas novas" },
    duration_token: "base", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Troca instantânea.", cost: { cpu: "layout", bundle_kb_gzip: 0, frame_budget_ms: 10 }, test: `${T}::split.toggle`, data_dependency: "none", sound: null },
  { id: "card.hover", matrix_ref: "M15", reason: "Carta disponível sobe levemente; custo/frequência legíveis sem hover.",
    trigger: "pointerenter / focus em carta disponível", states: { start: "repouso", end: "elevada (--elev-2)" },
    duration_token: "fast", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Borda --accent, sem translate.", cost: xform(), test: `${T}::card.hover`, data_dependency: "none", sound: null },
  { id: "card.blocked", matrix_ref: "M16", reason: "Carta indisponível não parece clicável: sem lift e com razão textual.",
    trigger: "aria-disabled=true", states: { start: "repouso", end: "indisponível (cursor not-allowed, sem lift)" },
    duration_token: "fast", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Mesmo estado textual.", cost: css(), test: `${T}::card.blocked`, data_dependency: "none", sound: null },
  { id: "card.arm", matrix_ref: "M14", reason: "Carta armada sobe e permanece; aria-pressed=true; Esc desarma.",
    trigger: "armed (gesto SPEC-205)", states: { start: "repouso", end: "armada (--elev-3)" },
    duration_token: "fast", easing_token: "ease-spring-soft", interruptible: true,
    reduced_motion_fallback: "Borda/contorno --accent + 'Mirando…'.", cost: xform(), test: `${T}::card.arm`, data_dependency: "none", sound: null },
  { id: "target.valid", matrix_ref: "M14", reason: "Alvos válidos destacados; inválidos tracejados; rótulo textual no aria-label.",
    trigger: "mira ativa", states: { start: "alvo neutro", end: "alvo válido (halo) / inválido (tracejado)" },
    duration_token: "fast", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Contorno estático + aria-label.", cost: css(), test: `${T}::target.valid`, data_dependency: "none", sound: null },
  { id: "card.resolve", matrix_ref: "M14", reason: "Carta gasta esmaece SÓ depois da confirmação do servidor (card.spent).",
    trigger: "server-confirmed (card.spent)", states: { start: "disponível", end: "gasta (opacity .52)" },
    duration_token: "base", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Estado gasta aplicado direto.", cost: css(), test: `${T}::card.resolve`, data_dependency: "none", sound: null },
  { id: "hit.feedback", matrix_ref: "M30", reason: "Barra de Vitalidade atualiza no lugar (largura animada) quando o servidor confirma o dano.",
    trigger: "server-confirmed (vitalidade)", states: { start: "largura anterior", end: "largura nova" },
    duration_token: "base", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Largura nova direta; o número N/M segue visível.", cost: css(), test: `${T}::hit.feedback`, data_dependency: "none", sound: null },
  { id: "codex.entry.reveal", matrix_ref: "M24", reason: "Entrada descoberta depois da abertura aparece com marcador 'Novo' e fade curto.",
    trigger: "dado autorizado chegou do servidor (GET /game/codex)", states: { start: "ausente do DOM", end: "visível + 'Novo'" },
    duration_token: "base", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Entrada aparece direto com o marcador 'Novo'.", cost: xform(), test: `${T}::codex.entry.reveal`, data_dependency: "player-authorized", sound: null },
  { id: "map.marker", matrix_ref: "M22", reason: "Nó viajável tem cursor e halo; fog e local atual se distinguem por texto.",
    trigger: "hover/focus em nó viajável", states: { start: "ponto neutro", end: "halo + cursor pointer" },
    duration_token: "fast", easing_token: "ease-out", interruptible: true,
    reduced_motion_fallback: "Halo estático; rótulo 'Região inexplorada' no fog.", cost: css(), test: `${T}::map.marker`, data_dependency: "player-authorized", sound: null },
  { id: "ember.pause", matrix_ref: "M25", reason: "Brasas pausam com aba oculta, kill switch e mudança de preferência de movimento.",
    trigger: "visibilitychange / matchMedia change", states: { start: "rodando", end: "pausado (0 frames)" },
    duration_token: "slow", easing_token: "ease-in-out", interruptible: true,
    reduced_motion_fallback: "Canvas oculto.", cost: { cpu: "transform", bundle_kb_gzip: 0, frame_budget_ms: 4 }, test: `${T}::ember.pause`, data_dependency: "none", sound: null },
];
