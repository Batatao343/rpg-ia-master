import type { CapacitorConfig } from '@capacitor/cli';

// SPEC-193: the WebView loads the hosted site remotely (first-party cookies,
// same-origin Origin-checked CSRF, no CORS/SameSite changes). The URL is
// resolved when `npx cap sync android` runs; override with CAP_SERVER_URL.
const serverUrl = process.env.CAP_SERVER_URL || 'https://rpg-ia-master-staging.vercel.app';
const host = new URL(serverUrl).host;

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
    cleartext: false,
    // Top-level navigations stay on the trusted host; everything else opens externally.
    allowNavigation: [host],
  },
};

export default config;
