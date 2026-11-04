import { newsLabel, orderNews } from "../../heardNews";
import type { NewsItem } from "../../types";

/** SPEC-296 R8: rumores que o herói percebeu em viagem/descanso. */
export function HeardNews({ news }: { news: NewsItem[] | undefined }) {
  const items = orderNews(news);
  return (
    <div className="heard-news">
      <h3 className="hud__label">Ouvi dizer</h3>
      {items.length === 0 ? (
        <p className="combat-empty">Converse com alguém numa taverna ou numa estrada movimentada para ouvir boatos.</p>
      ) : (
        <ul className="heard-news__list">
          {items.map((n, i) => (
            <li key={`${n.turn}-${i}`} className="heard-news__item">
              <small className="muted">
                {newsLabel(n)}
                {n.kind === "boato" ? <span className="heard-news__seal"> · boato</span> : null}
              </small>
              <p>{n.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
