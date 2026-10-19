// SPEC-259 R4: versao do app Android (versionName+versionCode do shell) para o header X-RPG-App-Version.
// Lida uma vez no boot via @capacitor/app (PackageInfo nativo); no web nunca carrega o plugin.
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

/** Chamada no boot (fire-and-forget). Formato fechado; qualquer outra coisa e ignorada. */
export async function loadAppVersion(read: InfoReader = capacitorInfo, android = isAndroidClient()): Promise<string | null> {
  if (!android) return null;
  try {
    const info = await read();
    const value = `${info.version ?? ''}+${info.build ?? ''}`;
    cached = VERSION_RE.test(value) ? value : null;
  } catch {
    cached = null;
  }
  return cached;
}
