import { useState } from "react";
import type { Condition, CreaturePortrait, OmenView } from "../types";
import { Icon } from "../design/icons";
import { familyIcon } from "./familyIcon";

export interface Participant {
  id: string;
  name: string;
  role: "player" | "enemy" | "ally";
  vit?: number;
  max?: number;
  esquiva?: number | null;
  protecao?: number | null;
  conditions: Condition[];
  intel: string[];
  concealment?: string;
  posture?: string;
  engagedNames: string[];
  /** SPEC-347 R13: retrato do inimigo (a chave só existe com a flag `on` ou arte curada). */
  retrato?: CreaturePortrait;
}

export type AimMark = { valid: boolean; reason?: string } | undefined;

/** SPEC-205 R11: participante da arena. Vira botão só enquanto há mira ativa. */
/** SPEC-347 R13.8: retrato à esquerda do nome. `pronto`/`gerando` → <img> (a melhor arte disponível);
 *  `marcador` → ícone da família (aria-hidden; o nome segue no texto). Tamanho fixo, sem salto de layout. */
export function Portrait({ r }: { r: CreaturePortrait }) {
  return (
    <span className={`tchip__portrait tchip__portrait--${r.estado}`} data-portrait={r.estado}>
      {r.src ? <img src={r.src} alt={r.alt} loading="lazy" decoding="async" />
        : <span className="tchip__portrait-icon" aria-hidden="true"><Icon name={familyIcon(r.familia, r.icone)} /></span>}
      {r.estado === "gerando" && <em className="tchip__portrait-badge">Gerando retrato…</em>}
    </span>
  );
}

/** SPEC-347 R13.8: oferta paga de gerar o retrato, com confirmação inline (sem modal). Só renderiza com `onGenerate`. */
function PortraitOffer({ p, onGenerate, disabled }: { p: Participant; onGenerate: (enemyId: string) => void; disabled?: boolean }) {
  const [asking, setAsking] = useState(false);
  const offer = p.retrato?.gerar;
  if (!offer) return null;
  const alone = offer.escopo === "unico";
  if (!asking) {
    return (
      <button type="button" className="btn btn--ghost btn--sm tchip__gen" data-gen-portrait={p.id}
        aria-disabled={disabled || undefined} onClick={() => { if (!disabled) setAsking(true); }}>
        {`Gerar retrato (${offer.preco_estilhas} Estilhas)`}
      </button>
    );
  }
  return (
    <span className="tchip__gen-confirm" role="group" aria-label={`Gerar o retrato de ${p.name}`}>
      <span>{`Gerar o retrato de ${p.name} por ${offer.preco_estilhas} Estilhas? ${alone ? `A imagem é só deste ${p.name}.` : "A imagem fica no bestiário e outros jogadores a verão."}`}</span>
      <button type="button" className="btn btn--primary btn--sm" data-gen-go onClick={() => { setAsking(false); onGenerate(p.id); }}>Gerar</button>
      <button type="button" className="btn btn--ghost btn--sm" data-gen-no onClick={() => setAsking(false)}>Agora não</button>
    </span>
  );
}

export function TargetChip({ p, aim, onPick, omen, onGenerate, genDisabled }: {
  p: Participant;
  aim: AimMark;
  onPick: (id: string) => void;
  /** SPEC-342 R8: presságio do inimigo (só no modo Baralho). */
  omen?: OmenView;
  /** SPEC-347 R13.6: pedido de geração (cotação → confirmação). Ausente = sem oferta na tela. */
  onGenerate?: (enemyId: string) => void;
  genDisabled?: boolean;
}) {
  const pct = p.vit != null && p.max ? Math.max(0, Math.min(100, Math.round((p.vit / p.max) * 100))) : null;
  const spent = p.role === "enemy" && p.vit === 0 && (p.max ?? 0) > 0; // SPEC-345 R1: de pé, sem Vitalidade
  const body = (
    <>
      {p.retrato && <Portrait r={p.retrato} />}
      <span className="tchip__top">
        <strong>{p.name}</strong>
        {p.vit != null && p.max != null && <span className={`tchip__vit${spent ? " is-spent" : ""}`}>{spent ? "sem Vitalidade" : `${p.vit}/${p.max}`}</span>}
      </span>
      {pct !== null && <span className={`tchip__bar${spent ? " is-spent" : ""}`} aria-hidden="true" data-effect="hit.feedback" data-pct={pct}><span style={{ transform: `scaleX(${pct / 100})` }} /></span>}
      <span className="tchip__meta">
        {p.role === "enemy" && (p.esquiva != null ? `Esquiva ${p.esquiva}` : "Esquiva ?")}
        {p.role === "enemy" && p.protecao != null ? ` · Proteção ${p.protecao}` : ""}
        {p.concealment && p.concealment !== "visivel" ? ` · ${p.concealment}` : ""}
        {p.posture && p.posture !== "neutro" ? ` · ${p.posture}` : ""}
      </span>
      {p.engagedNames.length > 0 && <span className="tchip__meta">{`Engajado: ${p.engagedNames.join(", ")}`}</span>}
      {p.conditions.length > 0 && (
        <span className="tchip__tags">{p.conditions.map((c, i) => <em key={i}>{c.name}</em>)}</span>
      )}
      {p.intel.length > 0 && <span className="tchip__meta">{`Revelado: ${p.intel.join(", ")}`}</span>}
      {omen && (
        <span className={`tchip__omen${omen.veiled ? " is-veiled" : ""}`} data-omen={omen.veiled ? "veiled" : "known"}>
          <Icon name={omen.icon} />
          <span>{omen.text}{omen.card ? ` — ${omen.card}` : ""}</span>
          {omen.num && <span className="tchip__omen-num">{omen.num}</span>}
        </span>
      )}
    </>
  );
  const cls = `tchip tchip--${p.role}${aim ? (aim.valid ? " is-valid" : " is-invalid") : ""}${p.retrato ? " tchip--portrait" : ""}`;
  if (!aim) {
    return (
      <div className={cls} data-participant={p.id}>
        {body}
        {p.retrato?.gerar && onGenerate && <PortraitOffer p={p} onGenerate={onGenerate} disabled={genDisabled} />}
      </div>
    );
  }
  const effectState = aim.valid ? "valid" : "invalid";
  const label = (aim.valid
    ? spent ? `Alvo: ${p.name}, sem Vitalidade — o próximo golpe fere`
      : `Alvo: ${p.name}${p.vit != null ? `, Vitalidade ${p.vit} de ${p.max}` : ""}`
    : `${p.name}: alvo inválido${aim.reason ? ` — ${aim.reason}` : ""}`) + (omen ? `. Presságio: ${omen.spoken}` : "");
  return (
    <button type="button" className={cls} data-target={p.id} data-aim-safe aria-label={label}
      data-effect="target.valid" data-effect-state={effectState}
      aria-disabled={!aim.valid || undefined} title={aim.valid ? undefined : aim.reason}
      onClick={() => { if (aim.valid) onPick(p.id); }}>
      {body}
    </button>
  );
}
