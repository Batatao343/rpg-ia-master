import { Fragment, useEffect, useRef } from "react";
import { motion } from "motion/react";
import { mdLite, roleLabel } from "../lib";
import { useTypewriter } from "../hooks/useTypewriter";
import type { LogEntry } from "../types";
import { VisualArtwork } from "./VisualArtwork";

export function StoryLog({ entries, thinking, thinkingLabel }: {
  entries: LogEntry[];
  thinking: boolean;
  thinkingLabel?: string | null;
}) {
  const storyRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const s = storyRef.current;
    if (s) s.scrollTop = s.scrollHeight;
  }, [entries, thinking]);

  return (
    <section className="story" aria-label="Narrativa" ref={storyRef} tabIndex={0}>
      <div className="log">
        {entries.map((e, i) => {
          const prev = entries[i - 1];
          // Fleuron entre dois turnos de narração seguidos: separa beats como
          // num diário, sem o rótulo repetido "Narrador" (ref: livro, não chat).
          const sceneBreak = !!prev && prev.role === "narrator" && e.role === "narrator";
          return (
            <Fragment key={e.id}>
              {sceneBreak && (
                <div className="scene-break" aria-hidden>
                  <span>❧</span>
                </div>
              )}
              <LogEntryItem entry={e} />
            </Fragment>
          );
        })}
      </div>
      {thinking && (
        <div className="thinking" aria-live="polite">
          <span className="thinking__dot" />
          <span className="thinking__dot" />
          <span className="thinking__dot" />
          <span className="thinking__label">{thinkingLabel || "o narrador tece o destino…"}</span>
        </div>
      )}
    </section>
  );
}

function LogEntryItem({ entry }: { entry: LogEntry }) {
  const displayedText = useTypewriter(entry.text, entry.streaming);

  // A narração é a voz padrão do diário — não carimba "Narrador" em todo bloco
  // (era um eyebrow repetido). Rótulo só quando muda o sentido: fala do jogador,
  // diálogo de NPC, combate, espólio.
  const showRole = entry.role === "player" || (entry.role === "narrator" && entry.type !== "STORY");

  return (
    <motion.article
      className={"msg msg--" + (entry.role === "player" ? "player" : entry.type.toLowerCase())}
      initial={{ opacity: 0, y: 14, filter: "blur(3px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
    >
      {entry.visual && <VisualArtwork asset={entry.visual.asset}
        name={entry.visual.subject_name} caption={entry.visual.caption}
        className="msg__visual" />}
      {showRole && <p className="msg__role">{roleLabel(entry.role, entry.type)}</p>}
      <div
        className="msg__body"
        dangerouslySetInnerHTML={{ __html: mdLite(displayedText) }}
      />
      {entry.streaming && <span className="msg__cursor" />}
    </motion.article>
  );
}
