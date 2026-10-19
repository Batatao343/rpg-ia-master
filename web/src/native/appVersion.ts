// SPEC-259 R4: versao do app Android (versionName+versionCode do shell) para o header X-RPG-App-Version.
// Lida no boot (com retentativa curta) via @capacitor/app (PackageInfo nativo); no web nunca carrega o plugin.
import { isAndroidClient } from './platform';

const VERSION_RE = /^\d{1,4}(?:\.\d{1,4}){0,3}\+\d{1,9}$/;
let cached: string | null = null;

export function appVersion(): string | null { return cached; }

type InfoReader = () => Promise<{ version?: string; build?: string }>;

// Sem import do pacote: o proxy do plugin nativo `App` vem do runtime do Capacitor (como o PlayBilling).
async function capacitorInfo(): Promise<{ version?: string; build?: string }> {
  const cap = (globalThis as { Capacitor?: { registerPlugin?: (n: string) => unknown } }).Capacitor;
  const app = cap?.registerPlugin?.('App') as { getInfo?: () => Promise<{ version?: string; build?: string }> } | undefined;
  if (!app?.getInfo) throw new Error('app_plugin_unavailable');
  return app.getInfo();
}

type RetryOpts = { attempts?: number; delayMs?: number };

/**
 * Chamada no boot (fire-and-forget). Formato fechado; qualquer outra coisa e ignorada.
 * No shell com server.url remoto o `Capacitor.registerPlugin` aparece ~200 ms depois do bundle:
 * falha de leitura e transitoria -> retenta (default 15 x 200 ms = 3 s) sem bloquear o boot e sem
 * cachear a falha. Formato invalido nao e transitorio: desiste na hora.
 */
export async function loadAppVersion(
  read: InfoReader = capacitorInfo,
  android = isAndroidClient(),
  { attempts = 15, delayMs = 200 }: RetryOpts = {},
): Promise<string | null> {
  if (!android) return null;
  for (let i = 0; i < attempts; i += 1) {
    let info: { version?: string; build?: string };
    try {
      info = await read();
    } catch {
      if (i < attempts - 1) await new Promise(r => setTimeout(r, delayMs));
      continue;
    }
    const value = `${info.version ?? ''}+${info.build ?? ''}`;
    cached = VERSION_RE.test(value) ? value : null;
    return cached;
  }
  cached = null;
  return cached;
}
