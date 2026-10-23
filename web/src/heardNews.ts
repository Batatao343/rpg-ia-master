import type { NewsItem } from "./types";

/** SPEC-296 R8: "Ouvi dizer" — da notícia mais nova para a mais antiga (a API entrega FIFO). */
export function orderNews(news: NewsItem[] | undefined | null): NewsItem[] {
  return (news ?? []).slice().reverse();
}

/** "Dia N · Período · Local" (campos ausentes são omitidos). */
export function newsLabel(item: NewsItem): string {
  return [`Dia ${item.day}`, item.period, item.location_name].filter(Boolean).join(" · ");
}
