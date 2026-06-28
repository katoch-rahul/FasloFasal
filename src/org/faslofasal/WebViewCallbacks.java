package org.faslofasal;

import android.graphics.Bitmap;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * Factory for WebView callback objects whose interfaces are implemented in
 * Python via Pyjnius PythonJavaClass.
 *
 * Background: Android's WebViewClient and WebChromeClient are concrete Java
 * classes, not interfaces.  Pyjnius's PythonJavaClass can only implement Java
 * *interfaces*, not extend concrete classes.  This factory provides thin Java
 * subclasses that delegate all relevant events to plain Java interfaces that
 * Pyjnius *can* implement from Python.
 */
public class WebViewCallbacks {

    // ── Interfaces that Python will implement ─────────────────────────────────

    public interface PageListener {
        void onPageStarted(String url);
        void onPageFinished(String url);
    }

    public interface ConsoleListener {
        /** Return true if the message was consumed (suppresses default logging). */
        boolean onConsoleMessage(String message, int lineNumber, String sourceId);
    }

    // ── Factory methods ───────────────────────────────────────────────────────

    public static WebViewClient buildWebViewClient(final PageListener listener) {
        return new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                listener.onPageStarted(url);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                listener.onPageFinished(url);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                // Let the WebView handle all navigation internally so the portal
                // stays inside our WebView instead of opening the system browser.
                return false;
            }
        };
    }

    public static WebChromeClient buildWebChromeClient(final ConsoleListener listener) {
        return new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage message) {
                return listener.onConsoleMessage(
                        message.message(),
                        message.lineNumber(),
                        message.sourceId());
            }
        };
    }
}
