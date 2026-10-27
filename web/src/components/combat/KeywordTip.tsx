import { useRef, useState } from "react";
import type { Glossary } from "../../types";
import { ruleSegments } from "../../combat/deck";

/** SPEC-334 R2: palavra-chave em negrito + tooltip do glossário. Mouse: hover. Toque: pressão longa.
 *  Teclado/leitor de tela: a regra vem no `aria-describedby` da carta (sem tab stop extra por palavra). */
function Keyword({ text, regra }: { text: string; regra: string }) {
  const [open, setOpen] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const hide = () => { window.clearTimeout(timer.current); setOpen(false); };
  return (
    <strong className="kw" data-keyword={text}
      onPointerEnter={(e) => { if (e.pointerType === "mouse") setOpen(true); }}
      onPointerLeave={hide} onPointerCancel={hide} onPointerUp={() => window.clearTimeout(timer.current)}
      onPointerDown={(e) => { if (e.pointerType !== "mouse") timer.current = window.setTimeout(() => setOpen(true), 450); }}
      onContextMenu={(e) => { if (open) e.preventDefault(); }}>
      {text}
      {open && <span className="kw__tip" role="tooltip">{regra}</span>}
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
