import type { KnowledgeNote, KnowledgeStamp } from "../../types";
import { knowledgeBadgeText, knowledgeTooltip } from "../../codexKnowledge";

/** SPEC-206 R13 / SPEC-211 R7: selo de certeza (fato/relato/rumor/suspeita/percepção).
 *  O rótulo vem do servidor (`knowledge.label`); o tooltip só tem rótulo + turnos. */
export function CertaintyBadge({ stamp }: { stamp?: KnowledgeStamp }) {
  if (!stamp) return null;
  return (
    <span
      className={"codex-knowledge codex-knowledge--" + stamp.knowledge_kind}
      title={knowledgeTooltip(stamp)}
      data-knowledge-kind={stamp.knowledge_kind}
    >
      {knowledgeBadgeText(stamp)}
    </span>
  );
}

export function KnowledgeNotes({ notes }: { notes?: KnowledgeNote[] }) {
  if (!notes?.length) return null;
  return (
    <ul className="codex-notes">
      {notes.map((n) => (
        <li key={n.memory_id} className="codex-note">
          <CertaintyBadge stamp={n} /> {n.text}
        </li>
      ))}
    </ul>
  );
}
