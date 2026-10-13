import { useEffect, useRef, useState } from "react";
import * as api from "../api";

const categories = ["game", "image", "voice"] as const;
const labels = { game: "Jogo", image: "Imagem", voice: "Voz" };
export const shards = (milli: string | number) => {
  const value = BigInt(milli);
  const whole = new Intl.NumberFormat("pt-BR").format(value / 1000n);
  const fraction = (value % 1000n).toString().padStart(3, "0").replace(/0+$/, "");
  return fraction ? `${whole},${fraction}` : whole;
};

const brl = (amount: string) => new Intl.NumberFormat("pt-BR", {
  style: "currency", currency: "BRL",
}).format(Number(amount));
const ORDER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const finalOrderStatuses = new Set(["paid", "refunded", "disputed", "reconciliation_required", "expired"]);

export function AccountScreen({ onBack, onBalanceChange }: {
  onBack: () => void; onBalanceChange?: (availableMilli: string) => void;
}) {
  const [period, setPeriod] = useState<"24h" | "7d" | "30d">("7d");
  const [balance, setBalance] = useState<api.AccountBalance | null>(null);
  const [series, setSeries] = useState<api.AccountPoint[]>([]);
  const [totals, setTotals] = useState<Record<"game" | "image" | "voice", string>>({ game: "0", image: "0", voice: "0" });
  const [usage, setUsage] = useState<api.AccountPage<api.AccountHistoryItem>>({ items: [], next_cursor: null });
  const [purchases, setPurchases] = useState<api.AccountPage<api.PurchaseItem>>({ items: [], next_cursor: null });
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [skus, setSkus] = useState<api.CheckoutSku[]>([]);
  const [checkoutAvailable, setCheckoutAvailable] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(true);
  const [checkoutBusy, setCheckoutBusy] = useState<string | null>(null);
  const [checkoutError, setCheckoutError] = useState("");
  const [checkoutNotice, setCheckoutNotice] = useState("");
  const [order, setOrder] = useState<api.CheckoutOrder | null>(null);
  const [orderError, setOrderError] = useState("");
  const [orderLoading, setOrderLoading] = useState(false);
  const [orderRefresh, setOrderRefresh] = useState(0);
  const checkoutIds = useRef<Record<string, string>>({});
  const financialGeneration = useRef(0);
  const query = new URLSearchParams(window.location.search);
  const returnKind = query.get("checkout");
  const rawOrderId = query.get("order_id") || "";
  const returnOrderId = (returnKind === "success" || returnKind === "cancel") && ORDER_ID.test(rawOrderId)
    ? rawOrderId : null;

  function refreshFinancial(isCurrent: () => boolean = () => true) {
    const generation = ++financialGeneration.current;
    void Promise.all([api.getAccountBalance(), api.getAccountPurchases()])
      .then(([nextBalance, nextPurchases]) => {
        if (isCurrent() && financialGeneration.current === generation) {
          setBalance(nextBalance); setPurchases(nextPurchases);
          onBalanceChange?.(nextBalance.available_milli);
        }
      }).catch(() => { /* A later account load or manual refresh can retry. */ });
  }

  useEffect(() => {
    let current = true;
    const generation = financialGeneration.current;
    setLoading(true); setError(false);
    void Promise.all([api.getAccountBalance(), api.getAccountSeries(period),
      api.getAccountUsage(), api.getAccountPurchases()]).then(([b, s, u, p]) => {
      if (!current) return;
      if (financialGeneration.current === generation) {
        setBalance(b); setPurchases(p); onBalanceChange?.(b.available_milli);
      }
      setSeries(s.points); setTotals(s.totals); setUsage(u); setLoading(false);
    }).catch(() => { if (current) { setError(true); setLoading(false); } });
    return () => { current = false; };
  }, [period]);

  useEffect(() => {
    let active = true;
    void api.getCheckoutSkus().then(result => {
      if (!active) return;
      setSkus(result.items);
      setCheckoutAvailable(result.items.length > 0);
    }).catch(() => {
      if (active) { setSkus([]); setCheckoutAvailable(false); }
    }).finally(() => { if (active) setCheckoutLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!returnOrderId) return;
    let active = true;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const abort = new AbortController();
    const poll = async () => {
      setOrderLoading(true);
      try {
        const next = await api.getCheckoutOrder(returnOrderId, abort.signal);
        if (!active) return;
        setOrder(next); setOrderError(""); setOrderLoading(false);
        if (next.status === "paid") {
          // Only the server's wallet and purchase ledger can update these views.
          refreshFinancial(() => active);
        } else if (!finalOrderStatuses.has(next.status) && ++attempts < 12) {
          timer = setTimeout(poll, 5000);
        }
      } catch {
        if (active) { setOrderError("Não foi possível consultar o pedido. Atualize o status mais tarde."); setOrderLoading(false); }
      }
    };
    void poll();
    return () => { active = false; abort.abort(); clearTimeout(timer); };
  }, [returnOrderId, orderRefresh]);

  async function beginCheckout(sku: api.CheckoutSku) {
    if (checkoutBusy || !checkoutAvailable) return;
    const requestId = checkoutIds.current[sku.sku_id] ||= crypto.randomUUID();
    setCheckoutBusy(sku.sku_id); setCheckoutError(""); setCheckoutNotice("");
    try {
      const result = await api.createCheckout(sku.sku_id, requestId);
      if (!result.checkout_url) {
        if (["paid", "refunded", "disputed", "expired"].includes(result.status))
          delete checkoutIds.current[sku.sku_id];
        if (result.status === "paid") {
          // A replay can observe a settled order after this screen loaded.
          refreshFinancial();
        }
        setCheckoutNotice(result.status === "paid"
          ? "Este pedido já foi confirmado pelo servidor. Consulte seu saldo e histórico de compras."
          : "Este pedido já está registrado. Consulte o status mais tarde; nenhum crédito será antecipado.");
        setCheckoutBusy(null);
        return;
      }
      const destination = new URL(result.checkout_url);
      if (destination.protocol !== "https:" || destination.hostname !== "checkout.stripe.com")
        throw new Error("Destino de pagamento inválido.");
      window.location.assign(destination.href);
    } catch {
      setCheckoutError("Não foi possível abrir o pagamento. Você pode tentar novamente sem criar outra compra.");
      setCheckoutBusy(null);
    }
  }

  function leaveAccount() {
    if (returnKind === "success" || returnKind === "cancel") {
      const url = new URL(window.location.href);
      url.searchParams.delete("checkout"); url.searchParams.delete("order_id");
      window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    }
    onBack();
  }

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
      <button className="btn btn--ghost" onClick={leaveAccount}>← Voltar</button>
      <h1 id="account-title">Minha conta</h1>
    </header>
    {loading && <p role="status">Carregando conta…</p>}
    {error && <p role="alert">Os dados da conta estão temporariamente indisponíveis. Tente novamente mais tarde.</p>}
    {!loading && balance && <>
      <section className="account-card" aria-label="Saldo de Estilhas">
        <p className="account-kicker">Saldo disponível</p>
        <p className="account-balance">{shards(balance.available_milli)} <span>Estilhas</span></p>
        {BigInt(balance.reserved_milli) > 0n && <p>{shards(balance.reserved_milli)} Estilhas reservadas</p>}
        {checkoutLoading ? <p className="muted" role="status">Consultando pacotes de Estilhas…</p>
          : !checkoutAvailable && <p className="muted">A compra de Estilhas ainda não está disponível.</p>}
      </section>
      {(returnKind === "success" || returnKind === "cancel") && <section className="account-card" aria-label="Retorno do pagamento">
        <h2>Pedido de Estilhas</h2>
        <p className="muted">{returnKind === "cancel"
          ? "Você saiu do Checkout. O pedido será conferido pelo servidor."
          : "Você voltou do Checkout. A confirmação depende do pagamento recebido pelo servidor."}</p>
        {!returnOrderId ? <p role="alert">Não foi possível identificar o pedido. Nenhum saldo foi alterado por esta página.</p>
          : <>
            {orderLoading && <p role="status">Consultando o pedido…</p>}
            {orderError && <p role="alert">{orderError}</p>}
            {order && <p role="status">{order.status === "paid" ? "Pagamento confirmado pelo servidor. Consulte seu saldo e histórico de compras."
              : order.status === "refunded" ? "Pagamento estornado. Consulte o histórico financeiro."
                : order.status === "disputed" ? "Pagamento em contestação. Consulte o histórico financeiro."
                  : order.status === "reconciliation_required" ? "Pedido em conferência financeira. Nenhum crédito será antecipado."
                    : order.status === "expired" ? "Pedido expirado. Nenhum crédito será antecipado."
                      : "Aguardando confirmação do pagamento. Nenhum crédito será antecipado."}</p>}
            <button className="btn btn--ghost" type="button" disabled={orderLoading}
              onClick={() => setOrderRefresh(value => value + 1)}>Atualizar status do pedido</button>
          </>}
      </section>}
      {checkoutAvailable && <section className="account-card" aria-labelledby="checkout-title">
        <h2 id="checkout-title">Comprar Estilhas</h2>
        <p className="muted">Escolha um pacote. O pagamento abre no Checkout seguro do Stripe; seu saldo é atualizado após a confirmação pelo servidor.</p>
        <ul className="checkout-packages">{skus.map(sku => <li key={sku.sku_id}>
          <span>{shards(sku.shard_milli)} Estilhas · {brl(sku.gross_brl)}</span>
          <button className="btn btn--primary" type="button" disabled={checkoutBusy !== null}
            onClick={() => void beginCheckout(sku)}>Comprar pacote</button>
        </li>)}</ul>
        {checkoutError && <p role="alert">{checkoutError}</p>}
        {checkoutNotice && <p role="status">{checkoutNotice}</p>}
      </section>}
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
