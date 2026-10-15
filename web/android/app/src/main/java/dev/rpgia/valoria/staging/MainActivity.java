package dev.rpgia.valoria.staging;

import android.net.Uri;
import android.os.Bundle;
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
