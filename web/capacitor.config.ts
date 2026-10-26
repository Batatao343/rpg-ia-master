import type { CapacitorConfig } from '@capacitor/cli';

// SPEC-193: the WebView loads the hosted site remotely (first-party cookies,
// same-origin Origin-checked CSRF, no CORS/SameSite changes). The URL is
// resolved when `npx cap sync android` runs; override with CAP_SERVER_URL.
const serverUrl = process.env.CAP_SERVER_URL || 'https://rpg-ia-master-staging.vercel.app';
const host = new URL(serverUrl).host;
// Cleartext is allowed ONLY for the emulator loopback in a DEBUG sync: `CAP_BUILD=debug CAP_SERVER_URL=http://10.0.2.2:8765 npx cap sync android`.
// Any other http:// URL is refused here, and app/build.gradle (checkReleaseCleartext) refuses a release build
// whose synced capacitor.config.json still points at http:// (e.g. a stale debug sync).
const debugEmulator = process.env.CAP_BUILD === 'debug' && serverUrl.startsWith('http://10.0.2.2:');
if (serverUrl.startsWith('http://') && !debugEmulator) {
  throw new Error('CAP_SERVER_URL must be https:// (http:// only with CAP_BUILD=debug and host 10.0.2.2)');
}

const config: CapacitorConfig = {
  // DEV id only (staging). This only affects the generated capacitor.config.json; the real Android
  // identity lives in android/app/build.gradle (applicationId + namespace) and the Java package
  // dev.rpgia.valoria.staging. SPEC-198 must change all of them together for production.
  appId: 'dev.rpgia.valoria.staging',
  appName: 'Valoria (staging)',
  webDir: 'dist',
  // WebView debugging is forced to BuildConfig.DEBUG in MainActivity (release is never debuggable).
  android: { allowMixedContent: false },
  server: {
    url: serverUrl,
    androidScheme: 'https',
    cleartext: debugEmulator,
    // Top-level navigations stay on the trusted host; everything else opens externally.
    allowNavigation: [host],
  },
  // SPEC-321 R8: barra de status escura (mesmo valor do `theme-color` do index.html / `--bg`).
  // Exige @capacitor/status-bar no plugin nativo (SPEC-198); sem ele a chave é ignorada.
  plugins: {
    StatusBar: { style: 'DARK', backgroundColor: '#080c10', overlaysWebView: false },
  },
};

export default config;
