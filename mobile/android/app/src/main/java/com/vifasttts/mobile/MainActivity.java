package com.vifasttts.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import com.sun.jna.Library;
import com.sun.jna.Native;
import com.sun.jna.NativeLong;
import com.sun.jna.Pointer;
import com.sun.jna.ptr.NativeLongByReference;
import com.sun.jna.Structure;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
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
        Pointer vifasttts_engine_new_vfts(String vfts);
        Pointer vifasttts_engine_new_vfa(String vfa, String vocoder);
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

    private static final String PREFS = "vifasttts";
    private static final String KEY_ACTIVE_MODEL = "active_model";

    private Ffi ffi;
    private Pointer engine;
    private TextView status;
    private TextView modelLabel;
    private EditText text;
    private EditText serverUrl;
    private EditText token;
    private CheckBox remote;
    private MediaPlayer player;
    private SharedPreferences prefs;
    private String activeModelPath = "";

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

    private void ensureFfi() throws Exception {
        if (ffi != null) return;
        File ort = new File(getApplicationInfo().nativeLibraryDir, "libonnxruntime.so");
        LibC libc = Native.load("c", LibC.class);
        libc.setenv("VIFASTT_ORT_DYLIB", ort.getAbsolutePath(), 1);
        Map<String, Object> options = new HashMap<>();
        options.put(Library.OPTION_STRING_ENCODING, "UTF-8");
        ffi = Native.load("vifasttts_ffi", Ffi.class, options);
    }

    private void ensureEngine() throws Exception {
        if (engine != null) return;
        ensureFfi();
        File acoustic = copyAsset("acoustic.onnx");
        File vocoder = copyAsset("vocoder.onnx");
        if (!activeModelPath.isEmpty()) {
            File bundle = new File(activeModelPath);
            if (!bundle.isFile()) {
                throw new IllegalStateException("Không thấy bundle: " + activeModelPath);
            }
            if (activeModelPath.endsWith(".vfts")) {
                engine = ffi.vifasttts_engine_new_vfts(bundle.getAbsolutePath());
            } else if (activeModelPath.endsWith(".vfa")) {
                engine = ffi.vifasttts_engine_new_vfa(
                        bundle.getAbsolutePath(), vocoder.getAbsolutePath());
            } else {
                throw new IllegalStateException("Bundle phải là .vfa hoặc .vfts");
            }
        } else {
            engine = ffi.vifasttts_engine_new(acoustic.getAbsolutePath(), vocoder.getAbsolutePath());
        }
        if (engine == null) {
            throw new IllegalStateException(lastError());
        }
    }

    private void resetEngine() {
        if (engine != null && ffi != null) {
            ffi.vifasttts_engine_free(engine);
            engine = null;
        }
    }

    private void updateModelLabel() {
        String name = activeModelPath.isEmpty()
                ? "Bundled acoustic/vocoder"
                : new File(activeModelPath).getName();
        modelLabel.setText("Model: " + name);
    }

    private void setStatus(String value) {
        runOnUiThread(() -> status.setText(value));
    }

    private String baseUrl() {
        String base = serverUrl.getText().toString().trim();
        return (base.isEmpty() ? "http://10.0.2.2:8000" : base).replaceAll("/+$", "");
    }

    private HttpURLConnection open(String url) throws Exception {
        HttpURLConnection connection = (HttpURLConnection) URI.create(url).toURL().openConnection();
        connection.setConnectTimeout(15000);
        connection.setReadTimeout(180000);
        String bearer = token.getText().toString().trim();
        if (!bearer.isEmpty()) connection.setRequestProperty("Authorization", "Bearer " + bearer);
        return connection;
    }

    private static byte[] readAll(InputStream input) throws Exception {
        try (InputStream in = input; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[1024 * 256];
            int read;
            while ((read = in.read(buffer)) > 0) out.write(buffer, 0, read);
            return out.toByteArray();
        }
    }

    private static byte[] readError(HttpURLConnection connection) throws Exception {
        InputStream error = connection.getErrorStream();
        return error == null ? new byte[0] : readAll(error);
    }

    private byte[] getBytes(String url) throws Exception {
        HttpURLConnection connection = open(url);
        try {
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                String error = new String(readError(connection), StandardCharsets.UTF_8);
                throw new IllegalStateException("HTTP " + code + ": " + error);
            }
            return readAll(connection.getInputStream());
        } finally {
            connection.disconnect();
        }
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
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
                play(out, "Xong: " + String.format("%.2f s", wav.length / 2.0 / 24000.0));
            } catch (Throwable error) {
                setStatus("Lỗi: " + error.getMessage());
            }
        }).start();
    }

    private void synthesizeRemote(String input) {
        final String base = baseUrl();
        status.setText("Đang gọi server…");
        new Thread(() -> {
            HttpURLConnection connection = null;
            try {
                String url = base.endsWith("/api/tts") ? base : base + "/api/tts";
                connection = open(url);
                connection.setRequestMethod("POST");
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                JSONObject body = new JSONObject();
                body.put("text", input);
                body.put("speed", 1.0);
                body.put("fixed_pauses", false);
                byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
                connection.setFixedLengthStreamingMode(payload.length);
                try (java.io.OutputStream out = connection.getOutputStream()) {
                    out.write(payload);
                }
                int code = connection.getResponseCode();
                if (code < 200 || code >= 300) {
                    String error = new String(readError(connection), StandardCharsets.UTF_8);
                    throw new IllegalStateException("HTTP " + code + ": " + error);
                }
                byte[] wav = readAll(connection.getInputStream());
                File out = new File(getCacheDir(), "vifasttts-remote.wav");
                Files.write(out.toPath(), wav);
                play(out, "Xong remote: " + String.format("%.2f s", wav.length / 2.0 / 24000.0));
            } catch (Throwable error) {
                setStatus("Lỗi remote: " + error.getMessage());
            } finally {
                if (connection != null) connection.disconnect();
            }
        }).start();
    }

    private void play(File out, String message) {
        runOnUiThread(() -> {
            status.setText(message);
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
    }

    private void showModelSearch() {
        EditText query = new EditText(this);
        query.setHint("Từ khoá HuggingFace");
        query.setText("vifasttts");
        query.setInputType(InputType.TYPE_CLASS_TEXT);
        new AlertDialog.Builder(this)
                .setTitle("Tìm model")
                .setView(query)
                .setPositiveButton("Tìm", (dialog, which) -> searchModels(query.getText().toString()))
                .setNegativeButton("Huỷ", null)
                .show();
    }

    private void searchModels(String query) {
        status.setText("Đang tìm model…");
        new Thread(() -> {
            try {
                byte[] body = getBytes(baseUrl() + "/api/models/search?q=" + encode(query) + "&limit=20");
                JSONArray models = new JSONArray(new String(body, StandardCharsets.UTF_8));
                if (models.length() == 0) {
                    setStatus("Không thấy repo model.");
                    return;
                }
                List<String> ids = new ArrayList<>();
                for (int index = 0; index < models.length(); index += 1) {
                    ids.add(models.getJSONObject(index).getString("id"));
                }
                runOnUiThread(() -> new AlertDialog.Builder(this)
                        .setTitle("Chọn repo")
                        .setItems(ids.toArray(new String[0]), (dialog, which) -> loadFiles(ids.get(which)))
                        .setNegativeButton("Đóng", null)
                        .show());
                setStatus("Thấy " + ids.size() + " repo.");
            } catch (Throwable error) {
                setStatus("Lỗi tìm model: " + error.getMessage());
            }
        }).start();
    }

    private void loadFiles(String repo) {
        status.setText("Đang xem " + repo + "…");
        new Thread(() -> {
            try {
                byte[] body = getBytes(baseUrl() + "/api/models/files?repo=" + encode(repo));
                JSONArray files = new JSONArray(new String(body, StandardCharsets.UTF_8));
                if (files.length() == 0) {
                    setStatus("Repo chưa có .vfa/.vfts.");
                    return;
                }
                List<String> labels = new ArrayList<>();
                List<String> paths = new ArrayList<>();
                for (int index = 0; index < files.length(); index += 1) {
                    JSONObject file = files.getJSONObject(index);
                    String path = file.getString("path");
                    paths.add(path);
                    labels.add(path + " — " + (file.optLong("size", 0) / 1_000_000) + " MB");
                }
                runOnUiThread(() -> new AlertDialog.Builder(this)
                        .setTitle(repo)
                        .setItems(labels.toArray(new String[0]), (dialog, which) ->
                                downloadModel(repo, paths.get(which)))
                        .setNegativeButton("Đóng", null)
                        .show());
                setStatus("Thấy " + paths.size() + " bundle.");
            } catch (Throwable error) {
                setStatus("Lỗi xem repo: " + error.getMessage());
            }
        }).start();
    }

    private void downloadModel(String repo, String path) {
        status.setText("Đang tải " + path + "…");
        new Thread(() -> {
            try {
                byte[] bytes = getBytes(baseUrl() + "/api/models/download?repo=" + encode(repo)
                        + "&path=" + encode(path));
                String name = path.substring(path.lastIndexOf('/') + 1).replaceAll("[^A-Za-z0-9._-]", "_");
                if (!name.endsWith(".vfa") && !name.endsWith(".vfts")) {
                    throw new IllegalStateException("Server trả file không phải .vfa/.vfts");
                }
                File directory = new File(getFilesDir(), "models");
                if (!directory.exists() && !directory.mkdirs()) {
                    throw new IllegalStateException("Không tạo được thư mục models");
                }
                File destination = new File(directory, name);
                File temporary = new File(directory, name + ".part");
                Files.write(temporary.toPath(), bytes);
                if (destination.exists() && !destination.delete()) {
                    throw new IllegalStateException("Không xoá được model cũ");
                }
                if (!temporary.renameTo(destination)) {
                    throw new IllegalStateException("Không đổi tên model tải về");
                }
                activeModelPath = destination.getAbsolutePath();
                prefs.edit().putString(KEY_ACTIVE_MODEL, activeModelPath).apply();
                runOnUiThread(() -> {
                    resetEngine();
                    updateModelLabel();
                    setStatus("Đã tải " + name + " (" + bytes.length + " B); đọc local sẽ dùng bundle.");
                });
            } catch (Throwable error) {
                setStatus("Lỗi tải model: " + error.getMessage());
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
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        activeModelPath = prefs.getString(KEY_ACTIVE_MODEL, "");
        VfTheme.applyWindow(this);
        Typeface font = VfTheme.typeface(this);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(
                VfTheme.dp(this, 24), VfTheme.dp(this, 56),
                VfTheme.dp(this, 24), VfTheme.dp(this, 24));
        root.setGravity(Gravity.TOP);
        root.setBackgroundColor(VfTheme.BG);

        TextView title = new TextView(this);
        title.setText("ViFastTts Mobile");
        VfTheme.text(title, font, 26, VfTheme.INK, true);
        root.addView(title);

        modelLabel = new TextView(this);
        VfTheme.text(modelLabel, font, 12, VfTheme.MUTED, false);
        root.addView(modelLabel);
        updateModelLabel();

        Button model = new Button(this);
        model.setText("Tải model .vfa/.vfts");
        VfTheme.secondaryButton(model, font);
        model.setOnClickListener(view -> showModelSearch());
        root.addView(model);

        text = new EditText(this);
        text.setText("Xin chào các bạn, hôm nay trời đẹp.");
        VfTheme.input(text, font);
        text.setMinLines(3);
        text.setGravity(Gravity.TOP);
        root.addView(text, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        remote = new CheckBox(this);
        remote.setText("Dùng server remote");
        VfTheme.text(remote, font, 14, VfTheme.INK, false);
        remote.setButtonTintList(android.content.res.ColorStateList.valueOf(VfTheme.ACCENT));
        root.addView(remote);

        serverUrl = new EditText(this);
        serverUrl.setText("http://10.0.2.2:8000");
        serverUrl.setHint("Server URL");
        VfTheme.input(serverUrl, font);
        root.addView(serverUrl);

        token = new EditText(this);
        token.setHint("Bearer token (tuỳ chọn)");
        VfTheme.input(token, font);
        root.addView(token);

        Button run = new Button(this);
        run.setText("Đọc");
        VfTheme.primaryButton(run, font);
        run.setOnClickListener(view -> synthesize());
        root.addView(run);

        status = new TextView(this);
        status.setText("Sẵn sàng");
        VfTheme.text(status, font, 15, VfTheme.INK, false);
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
