import type { ReactNode } from "react";

// Ornamentos SVG desenhados à mão. Tudo herda `currentColor` (casa com a paleta).

function CornerFiligree({ cls }: { cls: string }) {
  return (
    <svg className={cls} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M1 9 V3 a2 2 0 0 1 2-2 H9"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path d="M5 1 V5 H1" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
      <circle cx="3" cy="3" r="0.9" fill="currentColor" />
    </svg>
  );
}

/** Moldura com filigrana nos 4 cantos. Envolve qualquer painel. */
export function Frame({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={"frame " + className}>
      <span className="frame__edge" />
      <CornerFiligree cls="frame__corner frame__corner--tl" />
      <CornerFiligree cls="frame__corner frame__corner--tr" />
      <CornerFiligree cls="frame__corner frame__corner--bl" />
      <CornerFiligree cls="frame__corner frame__corner--br" />
      {children}
    </div>
  );
}

/** Divisória central com losango ornamentado. */
export function Divider() {
  return (
    <div className="divider" aria-hidden>
      <svg width="22" height="10" viewBox="0 0 22 10" fill="none">
        <path d="M11 1 L15 5 L11 9 L7 5 Z" fill="currentColor" opacity="0.9" />
        <path d="M2 5 H6 M16 5 H20" stroke="currentColor" strokeWidth="1" />
      </svg>
    </div>
  );
}

/** Medalhão geométrico (alusão ao medalhão de lobo). */
export function Medallion({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden>
      <circle cx="20" cy="20" r="18.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="20" cy="20" r="14.5" stroke="currentColor" strokeWidth="0.7" opacity="0.55" />
      {/* dentes/raios ao redor */}
      {Array.from({ length: 12 }).map((_, i) => {
        const a = (i / 12) * Math.PI * 2;
        const x1 = 20 + Math.cos(a) * 18.5;
        const y1 = 20 + Math.sin(a) * 18.5;
        const x2 = 20 + Math.cos(a) * 16;
        const y2 = 20 + Math.sin(a) * 16;
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="currentColor" strokeWidth="0.8" opacity="0.7" />;
      })}
      {/* focinho de lobo estilizado */}
      <path
        d="M13 14 L20 11 L27 14 L24 17 L26 24 L20 29 L14 24 L16 17 Z"
        stroke="currentColor"
        strokeWidth="1.1"
        fill="currentColor"
        fillOpacity="0.08"
        strokeLinejoin="round"
      />
      <circle cx="17" cy="18.5" r="1" fill="currentColor" />
      <circle cx="23" cy="18.5" r="1" fill="currentColor" />
    </svg>
  );
}
