import { useEffect, useRef } from "react";
import { mdLite, roleLabel } from "../lib";
import type { LogEntry } from "../types";

export function StoryLog({ entries, thinking }: { entries: LogEntry[]; thinking: boolean }) {
  const storyRef = useRef<HTMLElement>(null);

  // Auto-scroll para o fim a cada nova mensagem ou enquanto "pensa".
  useEffect(() => {
    const s = storyRef.current;
    if (s) s.scrollTop = s.scrollHeight;
  }, [entries, thinking]);

  return (
    <section className="story" aria-label="Narrativa" ref={storyRef}>
      <div className="log">
        {entries.map((e) => (
          <article
            key={e.id}
            className={"msg msg--" + (e.role === "player" ? "player" : e.type.toLowerCase())}
          >
            <p className="msg__role">{roleLabel(e.role, e.type)}</p>
            <div className="msg__body" dangerouslySetInnerHTML={{ __html: mdLite(e.text) }} />
          </article>
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
