import { useEffect, useState } from "react";
import * as api from "../api";

const categories = ["game", "image", "voice"] as const;
const labels = { game: "Jogo", image: "Imagem", voice: "Voz" };
export const shards = (milli: string | number) => {
  const value = BigInt(milli);
  const whole = new Intl.NumberFormat("pt-BR").format(value / 1000n);
  const fraction = (value % 1000n).toString().padStart(3, "0").replace(/0+$/, "");
  return fraction ? `${whole},${fraction}` : whole;
};

export function AccountScreen({ onBack }: { onBack: () => void }) {
  const [period, setPeriod] = useState<"24h" | "7d" | "30d">("7d");
  const [balance, setBalance] = useState<api.AccountBalance | null>(null);
  const [series, setSeries] = useState<api.AccountPoint[]>([]);
  const [totals, setTotals] = useState<Record<"game" | "image" | "voice", string>>({ game: "0", image: "0", voice: "0" });
  const [usage, setUsage] = useState<api.AccountPage<api.AccountHistoryItem>>({ items: [], next_cursor: null });
  const [purchases, setPurchases] = useState<api.AccountPage<api.PurchaseItem>>({ items: [], next_cursor: null });
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let current = true;
    setLoading(true); setError(false);
    void Promise.all([api.getAccountBalance(), api.getAccountSeries(period),
      api.getAccountUsage(), api.getAccountPurchases()]).then(([b, s, u, p]) => {
      if (!current) return;
      setBalance(b); setSeries(s.points); setTotals(s.totals); setUsage(u); setPurchases(p); setLoading(false);
    }).catch(() => { if (current) { setError(true); setLoading(false); } });
    return () => { current = false; };
  }, [period]);

  async function moreUsage() {
    if (!usage.next_cursor) return;
    try {
      const next = await api.getAccountUsage(usage.next_cursor);
      setUsage(prev => ({ items: [...prev.items, ...next.items], next_cursor: next.next_cursor }));
    } catch { setError(true); }
  }
  async function morePurchases() {
    if (!purchases.next_cursor) return;
    try {
      const next = await api.getAccountPurchases(purchases.next_cursor);
      setPurchases(prev => ({ items: [...prev.items, ...next.items], next_cursor: next.next_cursor }));
    } catch { setError(true); }
  }

  const max = Math.max(1, ...series.map(point => Number(point.total)));
  const periodLabel = { "24h": "24 horas", "7d": "7 dias", "30d": "30 dias" }[period];

  return <main className="account-screen" aria-labelledby="account-title">
    <header className="account-screen__header">
      <button className="btn btn--ghost" onClick={onBack}>← Voltar</button>
      <h1 id="account-title">Minha conta</h1>
    </header>
    {loading && <p role="status">Carregando conta…</p>}
    {error && <p role="alert">Os dados da conta estão temporariamente indisponíveis. Tente novamente mais tarde.</p>}
    {!loading && balance && <>
      <section className="account-card" aria-label="Saldo de Estilhas">
        <p className="account-kicker">Saldo disponível</p>
        <p className="account-balance">{shards(balance.available_milli)} <span>Estilhas</span></p>
        {BigInt(balance.reserved_milli) > 0n && <p>{shards(balance.reserved_milli)} Estilhas reservadas</p>}
        <p className="muted">A compra de Estilhas ainda não está disponível.</p>
      </section>
      <section className="account-card" aria-labelledby="consumption-title">
        <div className="account-card__heading"><h2 id="consumption-title">Consumo liquidado</h2>
          <div className="account-periods" role="group" aria-label="Período do consumo">
            {(["24h", "7d", "30d"] as const).map(value => <button key={value}
              className="btn btn--ghost" aria-pressed={period === value}
              onClick={() => setPeriod(value)}>{value}</button>)}
          </div>
        </div>
        <p className="muted">{periodLabel}: {categories.map(cat => `${labels[cat]} ${shards(totals[cat])}`).join(" · ")} Estilhas.</p>
        <div className="account-chart" role="img" aria-label={`Consumo liquidado em ${periodLabel}. ${categories.map(cat => `${labels[cat]}: ${shards(totals[cat])} Estilhas`).join('. ')}`}>
          {series.map(point => <div className="account-chart__bar" key={point.start} aria-hidden="true">
            {categories.map(cat => <span key={cat} className={`account-chart__segment account-chart__segment--${cat}`}
              style={{ height: `${Number(point[cat]) / max * 100}%` }} />)}
          </div>)}
        </div>
        <p className="account-legend">Jogo · Imagem · Voz</p>
        <details className="account-chart-data">
          <summary>Ver valores por período</summary>
          <div className="account-chart-data__scroll"><table>
            <caption>Consumo liquidado por período, em Estilhas</caption>
            <thead><tr><th scope="col">Início</th><th scope="col">Jogo</th>
              <th scope="col">Imagem</th><th scope="col">Voz</th><th scope="col">Total</th></tr></thead>
            <tbody>{series.map(point => <tr key={point.start}>
              <th scope="row">{new Date(point.start).toLocaleString("pt-BR")}</th>
              {categories.map(cat => <td key={cat}>{shards(point[cat])}</td>)}
              <td>{shards(point.total)}</td>
            </tr>)}</tbody>
          </table></div>
        </details>
      </section>
      <section className="account-card" aria-labelledby="usage-title">
        <h2 id="usage-title">Histórico de uso</h2>
        <p className="muted">Atividade registrada; cada evento não representa um débito de Estilhas.</p>
        {usage.items.length ? <ul>{usage.items.map(item => <li key={item.id}>
          <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString("pt-BR")}</time>
          <span>{labels[item.category]}</span>
        </li>)}</ul> : <p className="muted">Ainda não há uso registrado.</p>}
        {usage.next_cursor && <button className="btn btn--ghost" onClick={() => void moreUsage()}>Ver mais uso</button>}
      </section>
      <section className="account-card" aria-labelledby="purchases-title">
        <h2 id="purchases-title">Histórico de compras</h2>
        {purchases.items.length ? <ul>{purchases.items.map(item => <li key={item.id}>
          <time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString("pt-BR")}</time>
          <span>{item.kind === "purchase" ? "Compra: " : "Estorno: −"}{shards(item.amount_milli)} Estilhas</span>
        </li>)}</ul> : <p className="muted">Ainda não há compras.</p>}
        {purchases.next_cursor && <button className="btn btn--ghost" onClick={() => void morePurchases()}>Ver mais compras</button>}
      </section>
    </>}
  </main>;
}
