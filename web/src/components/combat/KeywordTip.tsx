import { useState } from "react";
import { createPortal } from "react-dom";
import type { Glossary } from "../../types";
import { ruleSegments } from "../../combat/deck";

const MARGIN = 8, TIP_W = 256; // 16rem

/** SPEC-334 R2 + SPEC-342 R6/R9.1: palavra-chave em negrito. Mouse: tooltip em portal (`fixed`, preso ao viewport,
 *  nunca cortado pelo trilho rolável). Toque: sem tooltip — as regras aparecem na barra de mira ao armar a carta.
 *  Teclado/leitor de tela: a regra vem no `aria-describedby` da carta. */
function Keyword({ text, regra }: { text: string; regra: string }) {
  const [pos, setPos] = useState<{ left: number; top: number; above: boolean } | null>(null);
  const show = (e: React.PointerEvent<HTMLElement>) => {
    if (e.pointerType !== "mouse") return;
    const r = e.currentTarget.getBoundingClientRect();
    const left = Math.max(MARGIN, Math.min(r.left, window.innerWidth - TIP_W - MARGIN));
    const above = r.bottom + 96 > window.innerHeight;
    setPos({ left, top: above ? r.top - 4 : r.bottom + 4, above });
  };
  return (
    <strong className="kw" data-keyword={text} onPointerEnter={show} onPointerLeave={() => setPos(null)} onPointerCancel={() => setPos(null)}>
      {text}
      {pos && createPortal(
        <span className="kw__tip" role="tooltip"
          style={{ left: pos.left, top: pos.top, transform: pos.above ? "translateY(-100%)" : undefined }}>{regra}</span>,
        document.body)}
    </strong>
  );
}

export function RuleText({ texto, glossary }: { texto: string; glossary: Glossary }) {
  return (
    <>
      {ruleSegments(texto, glossary).map((s, i) =>
        s.bold ? (s.tip ? <Keyword key={i} text={s.text} regra={s.tip.regra} /> : <strong key={i}>{s.text}</strong>)
          : <span key={i}>{s.text}</span>)}
    </>
  );
}
