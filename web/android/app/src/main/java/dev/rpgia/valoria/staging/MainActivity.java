package dev.rpgia.valoria.staging;

import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.webkit.ConsoleMessage;
import android.webkit.PermissionRequest;
import android.webkit.WebView;
import com.getcapacitor.Bridge;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebChromeClient;

/**
 * SPEC-193 trust boundary: the WebView may use the microphone (voice input, SPEC-187)
 * only for the configured hosted origin, and nothing else (no camera/MIDI/DRM) is ever
 * granted. The Capacitor default client grants whatever any frame asks for after the
 * runtime prompt, so this narrows it. The runtime RECORD_AUDIO prompt is still shown by
 * the superclass.
 */
public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(PlayBillingPlugin.class);
        super.onCreate(savedInstanceState);
        // Release builds are never WebView-debuggable, whatever the generated Capacitor config says.
        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        final Bridge b = getBridge();
        if (b == null || b.getWebView() == null) return;
        b.getWebView().setWebChromeClient(new BridgeWebChromeClient(b) {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                if (!isTrustedOrigin(b, request.getOrigin()) || !onlyAudio(request.getResources())) {
                    request.deny();
                    return;
                }
                super.onPermissionRequest(request);
            }

            // SPEC-259 R3: so em build DEBUG, erros/avisos do console do WebView vao ao logcat.
            @Override
            public boolean onConsoleMessage(ConsoleMessage m) {
                if (BuildConfig.DEBUG && m != null) {
                    ConsoleMessage.MessageLevel level = m.messageLevel();
                    String line = m.message() + " @" + m.sourceId() + ":" + m.lineNumber();
                    if (level == ConsoleMessage.MessageLevel.ERROR) Log.e("RPGWebView", line);
                    else if (level == ConsoleMessage.MessageLevel.WARNING) Log.w("RPGWebView", line);
                }
                return super.onConsoleMessage(m);
            }
        });
    }

    private static boolean onlyAudio(String[] resources) {
        if (resources == null || resources.length == 0) return false;
        for (String r : resources) {
            if (!PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(r)) return false;
        }
        return true;
    }

    private static boolean isTrustedOrigin(Bridge b, Uri origin) {
        String server = b.getServerUrl();
        if (origin == null || server == null) return false;
        Uri trusted = Uri.parse(server);
        return "https".equals(origin.getScheme())
            && trusted.getHost() != null
            && trusted.getHost().equalsIgnoreCase(origin.getHost())
            && trusted.getPort() == origin.getPort();
    }
}
