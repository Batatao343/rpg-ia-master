import { useEffect, useRef } from "react";
import { motion } from "motion/react";
import { mdLite, roleLabel } from "../lib";
import { useTypewriter } from "../hooks/useTypewriter";
import type { LogEntry } from "../types";

export function StoryLog({ entries, thinking }: { entries: LogEntry[]; thinking: boolean }) {
  const storyRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const s = storyRef.current;
    if (s) s.scrollTop = s.scrollHeight;
  }, [entries, thinking]);

  return (
    <section className="story" aria-label="Narrativa" ref={storyRef}>
      <div className="log">
        {entries.map((e) => (
          <LogEntryItem key={e.id} entry={e} />
        ))}
      </div>
      {thinking && (
        <div className="thinking" aria-live="polite">
          <span className="thinking__dot" />
          <span className="thinking__dot" />
          <span className="thinking__dot" />
          <span className="thinking__label">o narrador tece o destino…</span>
        </div>
      )}
    </section>
  );
}

function LogEntryItem({ entry }: { entry: LogEntry }) {
  const displayedText = useTypewriter(entry.text, entry.streaming);

  return (
    <motion.article
      className={"msg msg--" + (entry.role === "player" ? "player" : entry.type.toLowerCase())}
      initial={{ opacity: 0, y: 14, filter: "blur(3px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
    >
      <p className="msg__role">{roleLabel(entry.role, entry.type)}</p>
      <div
        className="msg__body"
        dangerouslySetInnerHTML={{ __html: mdLite(displayedText) }}
      />
      {entry.streaming && <span className="msg__cursor" />}
    </motion.article>
  );
}
