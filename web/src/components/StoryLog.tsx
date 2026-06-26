import { useEffect, useRef } from "react";
import { motion } from "motion/react";
import { mdLite, roleLabel } from "../lib";
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
          <motion.article
            key={e.id}
            className={"msg msg--" + (e.role === "player" ? "player" : e.type.toLowerCase())}
            initial={{ opacity: 0, y: 14, filter: "blur(3px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="msg__role">{roleLabel(e.role, e.type)}</p>
            <div className="msg__body" dangerouslySetInnerHTML={{ __html: mdLite(e.text) }} />
          </motion.article>
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
