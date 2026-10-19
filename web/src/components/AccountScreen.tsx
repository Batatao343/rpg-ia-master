import { buildShort } from "../build";
import { isAndroidClient } from "../native/platform";
import { playAdapter, type StoreProduct } from "../purchases";
import { useEffect, useRef, useState } from "react";
import * as api from "../api";
import { TurnstileChallenge } from "./TurnstileChallenge";

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

export function AccountScreen({ onBack, onBalanceChange, lifecycleAvailable, captcha, onDeletionStarted, onDeleted,
  onRecoveryRequired }: {
  onBack: () => void; onBalanceChange?: (availableMilli: string) => void;
  lifecycleAvailable: boolean; captcha?: api.AuthConfig["captcha"];
  onDeletionStarted: () => void; onDeleted: () => void;
  onRecoveryRequired: () => void;
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
  const [playProducts, setPlayProducts] = useState<StoreProduct[]>([]);
  const [playDisabled, setPlayDisabled] = useState(false);
  const [playBusy, setPlayBusy] = useState<string | null>(null);
  const [playNotice, setPlayNotice] = useState("");
  const [playError, setPlayError] = useState("");
  const [checkoutError, setCheckoutError] = useState("");
  const [checkoutNotice, setCheckoutNotice] = useState("");
  const [reauthPassword, setReauthPassword] = useState("");
  const [reauthCaptchaToken, setReauthCaptchaToken] = useState("");
  const [reauthCaptchaRevision, setReauthCaptchaRevision] = useState(0);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [accountAction, setAccountAction] = useState<"export" | "delete" | null>(null);
  const [accountActionError, setAccountActionError] = useState("");
  const [accountActionNotice, setAccountActionNotice] = useState("");
  const [deletionPending, setDeletionPending] = useState(false);
  const [deleteNeedsPassword, setDeleteNeedsPassword] = useState(false);
  const [deleteNeedsSignIn, setDeleteNeedsSignIn] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteCaptchaToken, setDeleteCaptchaToken] = useState("");
  const [deleteCaptchaRevision, setDeleteCaptchaRevision] = useState(0);
  const [order, setOrder] = useState<api.CheckoutOrder | null>(null);
  const [orderError, setOrderError] = useState("");
  const [orderLoading, setOrderLoading] = useState(false);
  const [orderRefresh, setOrderRefresh] = useState(0);
  const checkoutIds = useRef<Record<string, string>>({});
  const financialGeneration = useRef(0);
  const mounted = useRef(false);
  const deletionStarted = useRef(false);
  const accountReads = useRef(new Set<AbortController>());
  const nativeCaptcha = captcha?.required === true && captcha.mode === "gotrue";
  function startRead() {
    const controller = new AbortController();
    accountReads.current.add(controller);
    return controller;
  }
  function stopRead(controller: AbortController) { accountReads.current.delete(controller); }
  function cancelReads() {
    for (const controller of accountReads.current) controller.abort();
    accountReads.current.clear();
  }
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);
  const query = new URLSearchParams(window.location.search);
  const returnKind = query.get("checkout");
  const rawOrderId = query.get("order_id") || "";
  const returnOrderId = (returnKind === "success" || returnKind === "cancel") && ORDER_ID.test(rawOrderId)
    ? rawOrderId : null;

  function refreshFinancial(isCurrent: () => boolean = () => true) {
    if (deletionStarted.current) return;
    const generation = ++financialGeneration.current;
    const controller = startRead();
    void Promise.all([api.getAccountBalance(controller.signal), api.getAccountPurchases(undefined, controller.signal)])
      .then(([nextBalance, nextPurchases]) => {
        if (isCurrent() && mounted.current && !deletionStarted.current
            && financialGeneration.current === generation) {
          setBalance(nextBalance); setPurchases(nextPurchases);
          onBalanceChange?.(nextBalance.available_milli);
        }
      }).catch(() => { /* A later account load or manual refresh can retry. */ })
      .finally(() => stopRead(controller));
  }

  useEffect(() => {
    let current = true;
    const controller = startRead();
    const generation = financialGeneration.current;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    setLoading(true); setError(false);
    void Promise.all([api.getAccountBalance(controller.signal), api.getAccountSeries(period, controller.signal),
      api.getAccountUsage(undefined, controller.signal), api.getAccountPurchases(undefined, controller.signal)]).then(([b, s, u, p]) => {
      if (!current || deletionStarted.current) return;
      if (financialGeneration.current === generation) {
        setBalance(b); setPurchases(p); onBalanceChange?.(b.available_milli);
      }
      setSeries(s.points); setTotals(s.totals); setUsage(u); setLoading(false);
    }).catch(() => { if (current && !deletionStarted.current) { setError(true); setLoading(false); } })
      .finally(() => stopRead(controller));
    return () => { current = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- deps deliberadas: o efeito deve reexecutar só nestas chaves (callbacks/valores recriados a cada render não podem disparar de novo)
  }, [period]);

  useEffect(() => {
    let active = true;
    // Android: Stripe checkout is not offered (store policy); Play Billing (SPEC-194) lists Store products.
    if (isAndroidClient()) {
      const adapter = playAdapter(api.googlePlayBackend);
      const unsubscribe = adapter.subscribe(r => {
        if (!active) return;
        setPlayBusy(null);
        if (r.status === "fulfilled") { setPlayNotice("Compra confirmada pelo servidor. Seu saldo foi atualizado."); refreshFinancial(() => active); }
        else if (r.status === "pending") setPlayNotice("Pagamento pendente. Nenhum crédito será dado até o servidor confirmar.");
        else if (r.status === "cancelled") setPlayNotice("Compra cancelada. Nada foi cobrado.");
        else if (r.status === "error") setPlayError("Não foi possível confirmar a compra agora. Ela será conferida novamente ao reabrir o app.");
      });
      void adapter.restorePending().catch(() => {});   // single-flight; token dedupe lives in the adapter
      void adapter.listProducts().then(items => {
        if (!active || deletionStarted.current) return;
        setPlayDisabled(adapter.disabled); setPlayProducts(items);
      }).catch(() => { if (active) setPlayError("A loja não está disponível neste momento."); })
        .finally(() => { if (active && !deletionStarted.current) setCheckoutLoading(false); });
      return () => { active = false; unsubscribe(); };
    }
    const controller = startRead();
    void api.getCheckoutSkus(controller.signal).then(result => {
      if (!active || deletionStarted.current) return;
      setSkus(result.items);
      setCheckoutAvailable(result.items.length > 0);
    }).catch(() => {
      if (active && !deletionStarted.current) { setSkus([]); setCheckoutAvailable(false); }
    }).finally(() => { stopRead(controller); if (active && !deletionStarted.current) setCheckoutLoading(false); });
    return () => { active = false; };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- deps deliberadas: o efeito deve reexecutar só nestas chaves (callbacks/valores recriados a cada render não podem disparar de novo)
  }, []);

  useEffect(() => {
    if (!returnOrderId || deletionPending) return;
    let active = true;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const abort = new AbortController();
    accountReads.current.add(abort);
    const poll = async () => {
      if (deletionStarted.current) return;
      setOrderLoading(true);
      try {
        const next = await api.getCheckoutOrder(returnOrderId, abort.signal);
        if (!active || deletionStarted.current) return;
        setOrder(next); setOrderError(""); setOrderLoading(false);
        if (next.status === "paid") {
          // Only the server's wallet and purchase ledger can update these views.
          refreshFinancial(() => active);
        } else if (!finalOrderStatuses.has(next.status) && ++attempts < 12) {
          timer = setTimeout(poll, 5000);
        }
      } catch {
        if (active && !deletionStarted.current) { setOrderError("Não foi possível consultar o pedido. Atualize o status mais tarde."); setOrderLoading(false); }
      }
    };
    void poll();
    return () => { active = false; abort.abort(); stopRead(abort); clearTimeout(timer); };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- deps deliberadas: o efeito deve reexecutar só nestas chaves (callbacks/valores recriados a cada render não podem disparar de novo)
  }, [returnOrderId, orderRefresh, deletionPending]);

  async function beginCheckout(sku: api.CheckoutSku) {
    if (checkoutBusy || accountAction || deletionStarted.current || !checkoutAvailable) return;
    const requestId = checkoutIds.current[sku.sku_id] ||= crypto.randomUUID();
    setCheckoutBusy(sku.sku_id); setCheckoutError(""); setCheckoutNotice("");
    try {
      const result = await api.createCheckout(sku.sku_id, requestId);
      if (!mounted.current || deletionStarted.current) return;
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
    if (!usage.next_cursor || deletionStarted.current) return;
    const controller = startRead();
    try {
      const next = await api.getAccountUsage(usage.next_cursor, controller.signal);
      if (!deletionStarted.current && mounted.current)
        setUsage(prev => ({ items: [...prev.items, ...next.items], next_cursor: next.next_cursor }));
    } catch { if (!deletionStarted.current && mounted.current) setError(true); }
    finally { stopRead(controller); }
  }
  async function morePurchases() {
    if (!purchases.next_cursor || deletionStarted.current) return;
    const controller = startRead();
    try {
      const next = await api.getAccountPurchases(purchases.next_cursor, controller.signal);
      if (!deletionStarted.current && mounted.current)
        setPurchases(prev => ({ items: [...prev.items, ...next.items], next_cursor: next.next_cursor }));
    } catch { if (!deletionStarted.current && mounted.current) setError(true); }
    finally { stopRead(controller); }
  }

  function beginDeletion() {
    deletionStarted.current = true;
    financialGeneration.current++;
    cancelReads();
    setDeletionPending(true);
    onDeletionStarted();
  }

  async function accountDataAction(action: "export" | "delete") {
    if (accountAction || checkoutBusy || deletionStarted.current || !reauthPassword
        || (nativeCaptcha && !reauthCaptchaToken)
        || (action === "delete" && deleteConfirmation !== "EXCLUIR")) return;
    setAccountAction(action); setAccountActionError(""); setAccountActionNotice("");
    try {
      await api.reauthenticate(reauthPassword, reauthCaptchaToken || undefined);
      if (!mounted.current || deletionStarted.current) return;
      setReauthPassword("");
      if (action === "export") {
        const blob = await api.exportAccount();
        if (!mounted.current || deletionStarted.current) return;
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url; link.download = "cronicas-valoria-conta.json";
        document.body.appendChild(link); link.click(); link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
        setAccountActionNotice("Arquivo da conta preparado para download.");
      } else {
        // The server may revoke access before its response reaches the browser.
        beginDeletion();
        const result = await api.deleteAccount();
        if (!mounted.current) return;
        if (result.status === "deleted") onDeleted();
        else setAccountActionNotice("Exclusão em andamento. Tente concluir novamente se necessário.");
      }
    } catch (cause) {
      if (!mounted.current) return;
      if (deletionStarted.current) {
        if (cause instanceof api.HttpError && cause.status === 403) {
          setDeleteNeedsPassword(true);
          setAccountActionError("A confirmação da sessão expirou. Confirme sua senha para retomar.");
        } else if (cause instanceof api.HttpError && [401, 422].includes(cause.status)) {
          setDeleteNeedsSignIn(true);
          setAccountActionError("A sessão não permite concluir a exclusão. Entre novamente para verificar a conta.");
        } else setAccountActionError("Não foi possível concluir a exclusão. Tente novamente.");
        return;
      }
      setAccountActionError(cause instanceof api.HttpError && cause.status === 403
        ? "Confirme sua senha e tente novamente."
        : "Não foi possível concluir. Tente novamente mais tarde.");
    } finally {
      setAccountAction(null);
      if (nativeCaptcha) { setReauthCaptchaToken(""); setReauthCaptchaRevision(value => value + 1); }
    }
  }

  async function retryDeletion() {
    if (accountAction || !mounted.current || deleteNeedsSignIn
        || (deleteNeedsPassword && (!deletePassword || (nativeCaptcha && !deleteCaptchaToken)))) return;
    setAccountAction("delete"); setAccountActionError("");
    try {
      if (deleteNeedsPassword) {
        await api.reauthenticate(deletePassword, deleteCaptchaToken || undefined);
        if (!mounted.current) return;
        setDeletePassword(""); setDeleteNeedsPassword(false);
      }
      const result = await api.deleteAccount();
      if (!mounted.current) return;
      if (result.status === "deleted") onDeleted();
      else setAccountActionNotice("Exclusão em andamento. Tente concluir novamente se necessário.");
    } catch (cause) {
      if (!mounted.current) return;
      if (cause instanceof api.HttpError && cause.status === 403) {
        setDeleteNeedsPassword(true);
        setAccountActionError("Confirme sua senha para retomar a exclusão.");
      } else if (cause instanceof api.HttpError && [401, 422].includes(cause.status)) {
        setDeleteNeedsSignIn(true);
        setAccountActionError("A sessão expirou. Entre novamente para verificar a conta.");
      } else setAccountActionError("Não foi possível consultar a exclusão. Tente novamente.");
    }
    finally {
      setAccountAction(null);
      if (nativeCaptcha) { setDeleteCaptchaToken(""); setDeleteCaptchaRevision(value => value + 1); }
    }
  }

  const max = Math.max(1, ...series.map(point => Number(point.total)));
  const periodLabel = { "24h": "24 horas", "7d": "7 dias", "30d": "30 dias" }[period];

  if (deletionPending) return <main className="account-screen" aria-labelledby="delete-pending-title">
    <h1 id="delete-pending-title">Exclusão em andamento</h1>
    <p role="status">Seus dados de jogo não estão mais disponíveis nesta sessão.</p>
    {accountActionNotice && <p>{accountActionNotice}</p>}
    {accountActionError && <p role="alert">{accountActionError}</p>}
    {deleteNeedsPassword && !deleteNeedsSignIn && <>
      <label htmlFor="delete-retry-password">Senha atual</label>
      <input id="delete-retry-password" type="password" autoComplete="current-password"
        value={deletePassword} onChange={event => setDeletePassword(event.target.value)} />
      {nativeCaptcha && <TurnstileChallenge required siteKey={captcha?.site_key ?? null}
        action="reauth" revision={deleteCaptchaRevision} onToken={setDeleteCaptchaToken} />}
    </>}
    {deleteNeedsSignIn ? <button className="btn btn--primary" onClick={onRecoveryRequired}>
      Voltar para entrar</button> : <button className="btn btn--primary"
      disabled={accountAction !== null || (deleteNeedsPassword && (!deletePassword || (nativeCaptcha && !deleteCaptchaToken)))}
      onClick={() => void retryDeletion()}>Concluir exclusão</button>}
  </main>;

  return <main className="account-screen" aria-labelledby="account-title">
    <header className="account-screen__header">
      <button className="btn btn--ghost" disabled={accountAction !== null || checkoutBusy !== null}
        onClick={leaveAccount}>← Voltar</button>
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
          : !checkoutAvailable && !isAndroidClient() && <p className="muted">A compra de Estilhas ainda não está disponível.</p>}
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
      {isAndroidClient() && !checkoutLoading && <section className="account-card" aria-labelledby="play-title">
        <h2 id="play-title">Comprar Estilhas</h2>
        {playDisabled ? <p className="muted" role="status">Compras temporariamente indisponíveis.</p>
          : playProducts.length === 0 ? <p className="muted">A compra de Estilhas ainda não está disponível.</p>
            : <>
              <p className="muted">O pagamento é feito pela Google Play; o saldo só muda depois da confirmação do servidor.</p>
              <ul className="checkout-packages">{playProducts.map(p => <li key={p.productId}>
                <span>{p.shardMilli ? `${shards(p.shardMilli)} Estilhas · ` : ""}{p.displayPrice}</span>
                <button className="btn btn--primary" type="button" disabled={playBusy !== null || accountAction !== null}
                  onClick={() => {
                    setPlayBusy(p.productId); setPlayError(""); setPlayNotice("");
                    void playAdapter(api.googlePlayBackend).purchase(p.productId).then(r => {
                      if (r.status === "disabled") { setPlayDisabled(true); setPlayBusy(null); }
                      else if (r.status === "cancelled") setPlayBusy(null);
                    }).catch(() => { setPlayError("Não foi possível abrir a loja."); setPlayBusy(null); });
                  }}>Comprar pacote</button>
              </li>)}</ul>
            </>}
        {playError && <p role="alert">{playError}</p>}
        {playNotice && <p role="status">{playNotice}</p>}
      </section>}
      {checkoutAvailable && <section className="account-card" aria-labelledby="checkout-title">
        <h2 id="checkout-title">Comprar Estilhas</h2>
        <p className="muted">Escolha um pacote. O pagamento abre no Checkout seguro do Stripe; seu saldo é atualizado após a confirmação pelo servidor.</p>
        <ul className="checkout-packages">{skus.map(sku => <li key={sku.sku_id}>
          <span>{shards(sku.shard_milli)} Estilhas · {brl(sku.gross_brl)}</span>
          <button className="btn btn--primary" type="button" disabled={checkoutBusy !== null || accountAction !== null}
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
      {lifecycleAvailable && <section className="account-card account-lifecycle" aria-labelledby="account-data-title">
        <h2 id="account-data-title">Dados e segurança da conta</h2>
        <p className="muted">Baixe seus dados de jogo ou solicite a exclusão da conta. Confirme sua senha antes de continuar.</p>
        <label htmlFor="account-reauth-password">Senha atual</label>
        <input id="account-reauth-password" type="password" autoComplete="current-password"
          value={reauthPassword} onChange={event => setReauthPassword(event.target.value)} />
        {nativeCaptcha && <TurnstileChallenge required siteKey={captcha?.site_key ?? null}
          action="reauth" revision={reauthCaptchaRevision} onToken={setReauthCaptchaToken} />}
        <button className="btn btn--ghost" type="button" disabled={accountAction !== null || checkoutBusy !== null || !reauthPassword || (nativeCaptcha && !reauthCaptchaToken)}
          onClick={() => void accountDataAction("export")}>Baixar meus dados</button>
        <details>
          <summary>Excluir minha conta</summary>
          <p className="muted">Campanhas, memórias e artes serão removidas. Registros financeiros necessários para conciliação permanecem conforme a política de retenção.</p>
          <label htmlFor="account-delete-confirmation">Digite EXCLUIR para confirmar</label>
          <input id="account-delete-confirmation" value={deleteConfirmation}
            onChange={event => setDeleteConfirmation(event.target.value)} autoComplete="off" />
          <button className="btn btn--ghost" type="button"
            disabled={accountAction !== null || checkoutBusy !== null || !reauthPassword || (nativeCaptcha && !reauthCaptchaToken) || deleteConfirmation !== "EXCLUIR"}
            onClick={() => void accountDataAction("delete")}>Excluir conta</button>
        </details>
        {accountActionError && <p role="alert">{accountActionError}</p>}
        {accountActionNotice && <p role="status">{accountActionNotice}</p>}
        <p className="muted">Suporte: canal de atendimento será informado aqui quando estiver disponível.</p>
      </section>}
      {/* SPEC-261 R4: build curto para relatos de bug (casa com client_build no log do servidor). */}
      <p className="muted account-build">Versão do app: <code>{buildShort()}</code></p>
  </main>;
}
