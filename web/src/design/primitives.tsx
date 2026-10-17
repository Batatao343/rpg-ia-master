// SPEC-208 R4: wrapper fino sobre `motion`. Componentes de efeito NÃO importam `motion` direto;
// usam estes primitivos (teste em tests/design.test.mjs). Reduced-motion/kill switch/aba em
// background => estático, com a MESMA informação (R5/R10).
import { createContext, useContext, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { motion } from "motion/react";
import { transitionFor, useEffectsEnabled } from "./motion";

const cx = (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(" ");

/** Botão de controle primário: hover/press/foco via CSS (tokens); pending com texto e aria-busy. */
export function Pressable({ pending = false, pendingLabel, variant, effect = "ctrl.pending", className, children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { pending?: boolean; pendingLabel?: ReactNode; variant?: "primary" | "ghost"; effect?: string }) {
  return (
    <button {...rest} className={cx("btn", variant && `btn--${variant}`, className)}
      aria-busy={pending || undefined}
      data-effect={effect} data-effect-state={pending ? "pending" : "idle"}>
      {pending && pendingLabel != null ? pendingLabel : children}
    </button>
  );
}

/** Indicador persistente de seleção que desliza entre irmãos (layoutId compartilhado). */
export function Selectable({ selected, layoutId, children }: { selected: boolean; layoutId: string; children: ReactNode }) {
  const enabled = useEffectsEnabled();
  return (
    <span className="sel" data-effect="tab.indicator" data-effect-state={selected ? "selected" : "idle"}>
      {children}
      {selected && (
        <motion.span layoutId={layoutId} className="sel__bar" aria-hidden="true"
          transition={enabled ? transitionFor("base") : { duration: 0 }} />
      )}
    </span>
  );
}

/** Presença/abertura: anima só quando `enter` (conteúdo NOVO) e os efeitos estão habilitados.
 *  A decisão é congelada na montagem (voltar de uma aba oculta não reanima o histórico). A entrada
 *  é uma animação CSS só de opacity/transform (roda no compositor): a versão JS anterior (motion `y`)
 *  disputava o main thread com o streaming do narrador e somava frames lentos sob 4x CPU (R8). */
export function Reveal({ as = "div", enter = true, effect, className, children, id }: {
  as?: "div" | "article" | "li";
  enter?: boolean;
  effect: string;
  className?: string;
  children: ReactNode;
  id?: string;
}) {
  const enabled = useEffectsEnabled();
  const [animate] = useState(() => enter && enabled);
  const Tag = as;
  return (
    <Tag id={id} className={cx(className, animate && "fx-reveal")} data-effect={effect}
      data-effect-state={animate ? "entering" : "settled"}>
      {children}
    </Tag>
  );
}

/** Ids de entradas que acabaram de chegar do servidor (dado já autorizado — R7). */
const EMPTY: ReadonlySet<string> = new Set();
const ArrivalsContext = createContext<ReadonlySet<string>>(EMPTY);
export const ArrivalsProvider = ArrivalsContext.Provider;
export const NO_ARRIVALS = EMPTY;

export function ArrivalLi({ id, className, children }: { id: string; className?: string; children: ReactNode }) {
  const isNew = useContext(ArrivalsContext).has(id);
  return (
    <Reveal as="li" enter={isNew} effect="codex.entry.reveal" className={cx(className, isNew && "is-new")}>
      {isNew && <span className="reveal-new">Novo</span>}
      {children}
    </Reveal>
  );
}
