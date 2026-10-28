package com.vifasttts.mobile;

import android.app.Activity;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import com.sun.jna.Library;
import com.sun.jna.Native;
import com.sun.jna.NativeLong;
import com.sun.jna.Pointer;
import com.sun.jna.ptr.NativeLongByReference;
import com.sun.jna.Structure;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class MainActivity extends Activity {
    private interface LibC extends Library {
        int setenv(String name, String value, int overwrite);
    }

    private interface Ffi extends Library {
        Pointer vifasttts_engine_new(String acoustic, String vocoder);
        void vifasttts_engine_free(Pointer engine);
        Pointer vifasttts_synthesize(Pointer engine, String text, Options options,
                                     NativeLongByReference outLen);
        void vifasttts_buffer_free(Pointer ptr, NativeLong len);
        String vifasttts_last_error();
    }

    public static class Options extends Structure {
        public float speed;
        public float alpha;
        public NativeLong max_chars;
        public byte fixed_pauses;
        public byte peak_normalize;

        @Override
        protected List<String> getFieldOrder() {
            return Arrays.asList("speed", "alpha", "max_chars", "fixed_pauses", "peak_normalize");
        }
    }

    private Ffi ffi;
    private Pointer engine;
    private TextView status;
    private EditText text;
    private EditText serverUrl;
    private EditText token;
    private CheckBox remote;
    private MediaPlayer player;

    private String lastError() {
        try {
            String error = ffi == null ? null : ffi.vifasttts_last_error();
            return error == null || error.isEmpty() ? "unknown FFI error" : error;
        } catch (Throwable ignored) {
            return "unknown FFI error";
        }
    }

    private File copyAsset(String name) throws Exception {
        File out = new File(getFilesDir(), name);
        if (out.length() > 0) return out;
        try (InputStream in = getAssets().open(name);
             FileOutputStream os = new FileOutputStream(out)) {
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = in.read(buffer)) > 0) {
                os.write(buffer, 0, read);
            }
        }
        return out;
    }

    private void ensureEngine() throws Exception {
        if (engine != null) return;
        File acoustic = copyAsset("acoustic.onnx");
        File vocoder = copyAsset("vocoder.onnx");
        File ort = new File(getApplicationInfo().nativeLibraryDir, "libonnxruntime.so");
        LibC libc = Native.load("c", LibC.class);
        libc.setenv("VIFASTT_ORT_DYLIB", ort.getAbsolutePath(), 1);
        Map<String, Object> options = new HashMap<>();
        options.put(Library.OPTION_STRING_ENCODING, "UTF-8");
        ffi = Native.load("vifasttts_ffi", Ffi.class, options);
        engine = ffi.vifasttts_engine_new(acoustic.getAbsolutePath(), vocoder.getAbsolutePath());
        if (engine == null) {
            throw new IllegalStateException(lastError());
        }
    }

    private void setStatus(String value) {
        runOnUiThread(() -> status.setText(value));
    }

    private void synthesize() {
        final String input = text.getText().toString().trim();
        if (input.isEmpty()) {
            status.setText("Nhập text");
            return;
        }
        if (remote.isChecked()) {
            synthesizeRemote(input);
            return;
        }
        status.setText("Đang tổng hợp local…");
        new Thread(() -> {
            try {
                ensureEngine();
                Options options = new Options();
                options.speed = 1.0f;
                options.alpha = 1.5f;
                options.max_chars = new NativeLong(0);
                options.fixed_pauses = 0;
                options.peak_normalize = 0;
                NativeLongByReference len = new NativeLongByReference();
                Pointer data = ffi.vifasttts_synthesize(engine, input, options, len);
                if (data == null) throw new IllegalStateException(lastError());
                long size = len.getValue().longValue();
                byte[] wav = data.getByteArray(0, (int) size);
                ffi.vifasttts_buffer_free(data, len.getValue());
                File out = new File(getCacheDir(), "vifasttts.wav");
                Files.write(out.toPath(), wav);
                runOnUiThread(() -> {
                    status.setText(String.format("Xong: %.2f s", wav.length / 2.0 / 24000.0));
                    try {
                        if (player != null) player.release();
                        player = new MediaPlayer();
                        player.setDataSource(out.getAbsolutePath());
                        player.prepare();
                        player.start();
                    } catch (Exception error) {
                        status.setText("Đã tạo WAV, lỗi phát: " + error.getMessage());
                    }
                });
            } catch (Throwable error) {
                setStatus("Lỗi: " + error.getMessage());
            }
        }).start();
    }

    private void synthesizeRemote(String input) {
        final String base = serverUrl.getText().toString().trim();
        final String bearer = token.getText().toString().trim();
        if (base.isEmpty()) {
            status.setText("Nhập server URL");
            return;
        }
        status.setText("Đang gọi server…");
        new Thread(() -> {
            java.net.HttpURLConnection connection = null;
            try {
                String url = base.replaceAll("/+$", "");
                if (!url.endsWith("/api/tts")) url += "/api/tts";
                connection = (java.net.HttpURLConnection) java.net.URI.create(url).toURL().openConnection();
                connection.setRequestMethod("POST");
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(120000);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                if (!bearer.isEmpty()) connection.setRequestProperty("Authorization", "Bearer " + bearer);
                JSONObject body = new JSONObject();
                body.put("text", input);
                body.put("speed", 1.0);
                body.put("fixed_pauses", false);
                byte[] payload = body.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
                connection.setFixedLengthStreamingMode(payload.length);
                try (java.io.OutputStream out = connection.getOutputStream()) {
                    out.write(payload);
                }
                int code = connection.getResponseCode();
                if (code < 200 || code >= 300) {
                    String error = new String(connection.getErrorStream() == null
                            ? new byte[0]
                            : connection.getErrorStream().readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
                    throw new IllegalStateException("HTTP " + code + ": " + error);
                }
                byte[] wav;
                try (java.io.InputStream in = connection.getInputStream()) {
                    wav = in.readAllBytes();
                }
                File out = new File(getCacheDir(), "vifasttts-remote.wav");
                Files.write(out.toPath(), wav);
                runOnUiThread(() -> {
                    status.setText(String.format("Xong remote: %.2f s", wav.length / 2.0 / 24000.0));
                    try {
                        if (player != null) player.release();
                        player = new MediaPlayer();
                        player.setDataSource(out.getAbsolutePath());
                        player.prepare();
                        player.start();
                    } catch (Exception error) {
                        status.setText("Đã tạo WAV, lỗi phát: " + error.getMessage());
                    }
                });
            } catch (Throwable error) {
                setStatus("Lỗi remote: " + error.getMessage());
            } finally {
                if (connection != null) connection.disconnect();
            }
        }).start();
    }

    private void requestLocalNetworkPermission() {
        if (Build.VERSION.SDK_INT >= 36) {
            requestPermissions(new String[]{"android.permission.ACCESS_LOCAL_NETWORK"}, 1001);
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 48, 32, 32);
        root.setGravity(Gravity.TOP);

        TextView title = new TextView(this);
        title.setText("ViFastTts Mobile");
        title.setTextSize(24);
        root.addView(title);

        text = new EditText(this);
        text.setText("Xin chào các bạn, hôm nay trời đẹp.");
        text.setMinLines(3);
        text.setGravity(Gravity.TOP);
        root.addView(text, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        remote = new CheckBox(this);
        remote.setText("Dùng server remote");
        root.addView(remote);

        serverUrl = new EditText(this);
        serverUrl.setText("http://10.0.2.2:8000");
        serverUrl.setHint("Server URL");
        root.addView(serverUrl);

        token = new EditText(this);
        token.setHint("Bearer token (tuỳ chọn)");
        root.addView(token);

        Button run = new Button(this);
        run.setText("Đọc");
        run.setOnClickListener(view -> synthesize());
        root.addView(run);

        status = new TextView(this);
        status.setText("Sẵn sàng");
        status.setTextSize(16);
        root.addView(status);

        setContentView(root);
        requestLocalNetworkPermission();
    }

    @Override
    protected void onDestroy() {
        if (player != null) player.release();
        if (engine != null && ffi != null) ffi.vifasttts_engine_free(engine);
        super.onDestroy();
    }
}
