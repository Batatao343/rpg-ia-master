import type { NewsItem } from "./types";

/** SPEC-296 R8: "Ouvi dizer" — da notícia mais nova para a mais antiga (a API entrega FIFO). */
export function orderNews(news: NewsItem[] | undefined | null): NewsItem[] {
  return (news ?? []).slice().reverse();
}

/** "Dia N · Período · Local" (campos ausentes são omitidos). SPEC-307 R17: com `date_label`
 * (data de Valoria) ele substitui o "Dia N". */
export function newsLabel(item: NewsItem): string {
  return [item.date_label || `Dia ${item.day}`, item.period, item.location_name]
    .filter(Boolean)
    .join(" · ");
}
