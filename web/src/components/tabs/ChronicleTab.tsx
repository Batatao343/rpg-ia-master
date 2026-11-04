import { useEffect, useState } from "react";
import { mdLite } from "../../lib";
import { searchChronicle } from "../../api";
import type { ChronicleChapter, ChronicleSearchHit } from "../../types";
import { Icon } from "../../design/icons";

/** SPEC-213 R13: selo discreto do status da projeção da crônica (sem rede extra). */
function ProjectionSeal({ status }: { status?: string }) {
  const label = status === "pending" || status === "stale" ? "atualizando…"
    : status === "failed" ? "não atualizado" : "";
  return (
    <span className="projection-seal muted" aria-live="polite" data-status={status ?? "completed"}>
      {label}
    </span>
  );
}

export function ChronicleTab({ chapters, gameId, projectionStatus }: {
  chapters: ChronicleChapter[]; gameId?: string; projectionStatus?: string;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<ChronicleSearchHit[]>([]);
  const [searchMode, setSearchMode] = useState<string>("");
  useEffect(() => {
    const normalized = query.trim();
    if (!gameId || normalized.length < 2) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
      setHits([]);
      setSearchMode("");
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      searchChronicle({ game_id: gameId, query: normalized, top_k: 5 }, controller.signal)
        .then((result) => {
          setHits(result.hits);
          setSearchMode(result.mode === "lexical_fallback" ? "busca lexical" : "busca híbrida");
        })
        .catch((error) => {
          if (error?.name !== "AbortError") setSearchMode("filtro local");
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [gameId, query]);
  if (!chapters.length) {
    return (
      <div>
        <h3 className="hud__label">Crônica <ProjectionSeal status={projectionStatus} /></h3>
        <p className="combat-empty">A crônica se escreve sozinha: explore, lute ou escolha um lado e o primeiro feito entra aqui.</p>
      </div>
    );
  }
  const q = query.trim().toLowerCase();
  const filtered = !q
    ? chapters
    : chapters
        .map((cap) => ({
          ...cap,
          entries: cap.entries.filter((e) => e.text.toLowerCase().includes(q)),
        }))
        .filter((cap) => cap.entries.length > 0 || cap.title.toLowerCase().includes(q));
  // capítulo mais recente primeiro; dentro do capítulo, entrada mais recente primeiro
  const ordered = filtered.slice().reverse();
  return (
    <div>
      <div className="chron-tools">
        <h3 className="hud__label">Crônica da jornada <ProjectionSeal status={projectionStatus} /></h3>
        {gameId && (
          <a className="iconbtn" href={"/game/chronicle/export?game_id=" + encodeURIComponent(gameId)}
             download title="Baixar a crônica como .txt">
            <Icon name="download" /> .txt
          </a>
        )}
      </div>
      <input
        className="chron-search"
        type="search"
        placeholder="Buscar na crônica…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Buscar na crônica"
      />
      {searchMode && <p className="chron-search__mode">{searchMode}</p>}
      {hits.length > 0 && (
        <ul className="chron-results" aria-label="Resultados da busca">
          {hits.map((hit) => (
            <li key={`${hit.chapter_id}-${hit.entry_ids.join("-")}`}>
              <button onClick={() => document.getElementById(`chron-${hit.chapter_id}`)?.scrollIntoView({ behavior: "smooth" })}>
                <b>{hit.chapter_title}</b>
                <span>{hit.snippet}</span>
                <small>turnos {hit.from_turn}–{hit.to_turn} · {hit.match_kind}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
      {ordered.length === 0 && <p className="combat-empty">Nada encontrado.</p>}
      {ordered.map((cap, ci) => (
        <section key={cap.chapter_id ?? ci} id={`chron-${cap.chapter_id ?? ci}`} className="chron-chapter">
          <header className="chron-chapter__head">
            <h4 className="chron-chapter__title">{cap.title}</h4>
            <span className="chron-chapter__turn">desde o turno {cap.started_turn}</span>
          </header>
          {cap.digest && (
            <div className="chron-digest">
              <p>{cap.digest.summary}</p>
              <small>{cap.digest.covered_entry_count} entradas resumidas · turnos {cap.digest.from_turn ?? cap.started_turn}–{cap.digest.to_turn ?? cap.started_turn}</small>
            </div>
          )}
          {cap.entries.length === 0 ? (
            <p className="combat-empty">A crônica se escreve sozinha: explore, lute ou escolha um lado e o primeiro feito entra aqui.</p>
          ) : (
            <details open={!cap.digest} className="chron-raw">
              <summary>{cap.digest ? "Ver registros originais" : "Registros"}</summary>
              <ol className="chronicle">
                {cap.entries.slice().reverse().map((e, i) => (
                  <li key={e.entry_id ?? e.event_id ?? i} className={e.kind === "milestone" ? "chron chron--milestone" : "chron"}>
                    <span className="chron__mark" aria-hidden><Icon name={e.kind === "milestone" ? "combat" : "chronicle"} /></span>
                    <p className="chron__text" dangerouslySetInnerHTML={{ __html: mdLite(e.text) }} />
                  </li>
                ))}
              </ol>
            </details>
          )}
        </section>
      ))}
    </div>
  );
}
