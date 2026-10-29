package com.vifasttts.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.database.Cursor;
import android.graphics.Typeface;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import com.sun.jna.Callback;
import com.sun.jna.Library;
import com.sun.jna.Native;
import com.sun.jna.NativeLong;
import com.sun.jna.Pointer;
import com.sun.jna.ptr.NativeLongByReference;
import com.sun.jna.ptr.PointerByReference;
import com.sun.jna.Structure;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.ByteBuffer;
import java.text.SimpleDateFormat;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Date;
import java.util.List;
import java.util.Locale;
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
        Pointer vifasttts_synthesize_ex(Pointer engine, String text, Options options,
                                        String dialect, byte resolveOov, String dictionary,
                                        NativeLongByReference outLen);
        int vifasttts_synthesize_karaoke_ex(Pointer engine, String text, Options options,
                                            String dialect, byte resolveOov, String dictionary,
                                            PointerByReference outWav, NativeLongByReference outLen,
                                            PointerByReference outKaraoke);
        int vifasttts_synthesize_stream_ex(Pointer engine, String text, Options options,
                                           String dialect, byte resolveOov, String dictionary,
                                           StreamCallback callback, Pointer userData);
        Pointer vifasttts_karaoke_to_srt(String karaokeJson);
        Pointer vifasttts_karaoke_to_vtt(String karaokeJson);
        void vifasttts_string_free(Pointer value);
        void vifasttts_buffer_free(Pointer ptr, NativeLong len);
        String vifasttts_last_error();
    }

    interface StreamCallback extends Callback {
        int invoke(Pointer samples, NativeLong length, int sampleRate, Pointer userData);
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
    private static final String KEY_ACTIVE_ACOUSTIC = "active_acoustic";
    private static final String KEY_ACTIVE_VOCODER = "active_vocoder";
    private static final String KEY_MODE = "mode";
    private static final String KEY_SERVER = "server_url";
    private static final String KEY_TOKEN = "token";
    private static final String KEY_SPEED = "speed";
    private static final String KEY_ALPHA = "alpha";
    private static final String KEY_MAX_CHARS = "max_chars";
    private static final String KEY_FIXED_PAUSES = "fixed_pauses";
    private static final String KEY_PEAK_NORMALIZE = "peak_normalize";
    private static final String KEY_DIALECT = "dialect";
    private static final String KEY_RESOLVE_OOV = "resolve_oov";
    private static final String KEY_DICTIONARY = "dictionary";
    private static final String KEY_STREAM = "stream";
    private static final String KEY_HISTORY = "history";
    private static final int REQUEST_BUNDLE = 2001;
    private static final int REQUEST_ACOUSTIC = 2002;
    private static final int REQUEST_VOCODER = 2003;

    private Ffi ffi;
    private Pointer engine;
    private TextView status;
    private TextView modelLabel;
    private TextView settingsSummary;
    private TextView charCountLabel;
    private CheckBox streamQuick;
    private TextView subtitle;
    private TextView errorLabel;
    private TextView hintLabel;
    private TextView karaokeView;
    private EditText text;
    private EditText serverUrl;
    private EditText token;
    private LinearLayout remoteFields;
    private Button localTab;
    private Button remoteTab;
    private Button runButton;
    private Button stopButton;
    private Button modelButton;
    private Button settingsButton;
    private Button saveButton;
    private Button shareButton;
    private Button historyButton;
    private ProgressBar progress;
    private MediaPlayer player;
    private AudioTrack audioTrack;
    private Thread audioThread;
    private volatile boolean audioStopped = false;
    private HttpURLConnection streamConnection;
    private org.json.JSONArray history = new org.json.JSONArray();
    private Uri lastSavedWavUri;
    private int audioSampleRate = 24000;
    private int audioChannels = 1;
    private File lastAudioFile;
    private String lastSrt = "";
    private String lastVtt = "";
    private String lastKaraokeJson = "";
    private AudioManager audioManager;
    private AudioFocusRequest focusRequest;
    private SharedPreferences prefs;
    private String activeModelPath = "";
    private String activeAcousticPath = "";
    private String activeVocoderPath = "";
    private String mode = "local";
    private boolean remoteMode = false;
    private boolean busy = false;
    private float speechSpeed = 1.0f;
    private float sharpenAlpha = 1.5f;
    private int maxChars = 300;
    private boolean fixedPauses = false;
    private boolean peakNormalize = false;
    private String dialect = "north";
    private boolean resolveOov = true;
    private boolean streamMode = false;
    private String dictionaryText = "";
    private JSONArray karaokeUnits;
    private final Handler karaokeHandler = new Handler(Looper.getMainLooper());
    private final Runnable karaokeTick = new Runnable() {
        @Override
        public void run() {
            if (karaokeView == null || karaokeUnits == null) return;
            int position = currentPlaybackPosition();
            String active = "";
            for (int index = 0; index < karaokeUnits.length(); index += 1) {
                JSONObject unit = karaokeUnits.optJSONObject(index);
                if (unit == null) continue;
                if (position >= unit.optLong("start_ms") && position < unit.optLong("end_ms")) {
                    active = unit.optString("text", "");
                    break;
                }
            }
            if (!active.isEmpty()) karaokeView.setText(active);
            karaokeHandler.postDelayed(this, 100);
        }
    };

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
        if (!activeAcousticPath.isEmpty() && !activeVocoderPath.isEmpty()) {
            engine = ffi.vifasttts_engine_new(activeAcousticPath, activeVocoderPath);
        } else if (!activeModelPath.isEmpty()) {
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

    private void loadHistory() {
        try {
            history = new org.json.JSONArray(prefs.getString(KEY_HISTORY, "[]"));
        } catch (Throwable ignored) {
            history = new org.json.JSONArray();
        }
    }

    private void recordRun(String mode, String text, long elapsedMs, double audioSeconds) {
        try {
            JSONObject row = new JSONObject();
            row.put("mode", mode);
            row.put("chars", text.length());
            row.put("elapsed_ms", elapsedMs);
            row.put("audio_seconds", audioSeconds);
            row.put("at", System.currentTimeMillis());
            row.put("text", text.length() > 500 ? text.substring(0, 500) : text);
            history.put(row);
            while (history.length() > 20) history.remove(0);
            prefs.edit().putString(KEY_HISTORY, history.toString()).apply();
        } catch (Throwable ignored) {
            // Lịch sử chỉ là tối ưu UX.
        }
    }

    private long estimateMs(String mode, int chars) {
        if (chars <= 0) return 0;
        try {
            java.util.ArrayList<Double> samples = new java.util.ArrayList<>();
            for (int index = Math.max(0, history.length() - 12); index < history.length(); index += 1) {
                JSONObject row = history.optJSONObject(index);
                if (row == null) continue;
                String rowMode = row.optString("mode", "");
                if (!rowMode.equals(mode) && !rowMode.startsWith(mode + "-")) continue;
                double rowChars = row.optDouble("chars", 0);
                double elapsed = row.optDouble("elapsed_ms", 0);
                if (rowChars > 0 && elapsed > 0) samples.add(elapsed / rowChars);
            }
            if (samples.isEmpty()) return 0;
            java.util.Collections.sort(samples);
            double median = samples.get(samples.size() / 2);
            return Math.max(1, Math.round(median * chars));
        } catch (Throwable ignored) {
            return 0;
        }
    }

    private String estimateSuffix(String mode, String text) {
        long estimate = estimateMs(mode, text.length());
        return estimate > 0
                ? String.format(Locale.US, " · ước tính ~%.1fs", estimate / 1000.0)
                : "";
    }

    private void showHistory() {
        loadHistory();
        if (history.length() == 0) {
            setStatus("Chưa có lịch sử đọc.");
            return;
        }
        java.util.ArrayList<String> labels = new java.util.ArrayList<>();
        java.util.ArrayList<JSONObject> rows = new java.util.ArrayList<>();
        SimpleDateFormat format = new SimpleDateFormat("HH:mm", Locale.getDefault());
        for (int index = history.length() - 1; index >= 0; index -= 1) {
            JSONObject row = history.optJSONObject(index);
            if (row == null) continue;
            rows.add(row);
            Date date = new Date(row.optLong("at", System.currentTimeMillis()));
            labels.add(String.format(Locale.getDefault(), "%s · %s · %d ký tự · %.1fs",
                    format.format(date), row.optString("mode", "local"),
                    row.optInt("chars", 0), row.optDouble("audio_seconds", 0)));
        }
        new AlertDialog.Builder(this)
                .setTitle("Lịch sử đọc")
                .setItems(labels.toArray(new String[0]), (dialog, which) -> {
                    String value = rows.get(which).optString("text", "");
                    if (!value.isEmpty()) {
                        text.setText(value);
                        text.setSelection(text.length());
                    }
                })
                .setNegativeButton("Đóng", null)
                .show();
    }

    private void checkServer() {
        final String base = baseUrl();
        if (base.isEmpty()) {
            setStatus("Nhập Server URL trước.");
            return;
        }
        setStatus("Đang kiểm tra server…");
        new Thread(() -> {
            try {
                JSONObject health = new JSONObject(new String(
                        getBytes(base + "/healthz"), StandardCharsets.UTF_8));
                setStatus(String.format(Locale.US, "Server OK · %d Hz · %s · %s",
                        health.optInt("sample_rate", 24000),
                        health.optString("arch", "?"),
                        health.optString("vocab_version", "?")));
            } catch (Throwable error) {
                setStatus("Server lỗi: " + error.getMessage());
            }
        }, "vifasttts-health").start();
    }

    private void shareWav() {
        if (lastAudioFile == null || !lastAudioFile.isFile()) {
            setStatus("Chưa có WAV để chia sẻ.");
            return;
        }
        if (lastSavedWavUri == null) saveWav();
        if (lastSavedWavUri == null) {
            setStatus("Đã lưu; mở Downloads để chia sẻ trên Android cũ.");
            return;
        }
        Intent send = new Intent(Intent.ACTION_SEND);
        send.setType("audio/wav");
        send.putExtra(Intent.EXTRA_STREAM, lastSavedWavUri);
        send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        startActivity(Intent.createChooser(send, "Chia sẻ WAV"));
    }

    private void updateSettingsSummary() {
        if (settingsSummary == null) return;
        String dialectLabel = dialect.equals("central") ? "Trung" : dialect.equals("south") ? "Nam" : "Bắc";
        settingsSummary.setText(String.format(java.util.Locale.US,
                "%.2f× · alpha %.2f · %s%s", speechSpeed, sharpenAlpha, dialectLabel,
                streamMode ? " · stream" : ""));
    }

    private void updateModelLabel() {
        String name;
        if (!activeAcousticPath.isEmpty() && !activeVocoderPath.isEmpty()) {
            name = "ONNX: " + new File(activeAcousticPath).getName()
                    + " + " + new File(activeVocoderPath).getName();
        } else if (!activeModelPath.isEmpty()) {
            name = new File(activeModelPath).getName();
        } else {
            name = "Bundled acoustic/vocoder";
        }
        modelLabel.setText("Model: " + name);
    }

    private void setStatus(String value) {
        runOnUiThread(() -> status.setText(value));
    }

    private String baseUrl() {
        // Không tự đoán localhost/10.0.2.2: điện thoại thật không có localhost
        // của máy dev. UI chỉ gợi ý IP LAN, người dùng phải nhập.
        return serverUrl.getText().toString().trim().replaceAll("/+$", "");
    }

    private boolean requireServer() {
        if (!baseUrl().isEmpty()) return true;
        setStatus("Nhập server URL (LAN) trước.");
        setError("Server URL đang trống.");
        return false;
    }

    /** Trống Server URL = tải trực tiếp HuggingFace (native không bị CORS). */
    private boolean directModelMode() {
        return baseUrl().isEmpty();
    }

    private String modelSource() {
        return directModelMode() ? "HuggingFace trực tiếp" : "server " + baseUrl();
    }

    private static String encodePath(String value) {
        StringBuilder out = new StringBuilder();
        String[] parts = value.split("/", -1);
        for (int index = 0; index < parts.length; index += 1) {
            if (index > 0) out.append('/');
            out.append(encode(parts[index]).replace("+", "%20"));
        }
        return out.toString();
    }

    private String modelSearchUrl(String query) {
        if (directModelMode()) {
            return "https://huggingface.co/api/models?search=" + encode(query)
                    + "&limit=20&full=true";
        }
        return baseUrl() + "/api/models/search?q=" + encode(query) + "&limit=20";
    }

    private String modelFilesUrl(String repo) {
        if (directModelMode()) {
            return "https://huggingface.co/api/models/" + encodePath(repo)
                    + "/tree/main?recursive=true";
        }
        return baseUrl() + "/api/models/files?repo=" + encode(repo);
    }

    private String modelDownloadUrl(String repo, String path) {
        if (directModelMode()) {
            return "https://huggingface.co/" + encodePath(repo)
                    + "/resolve/main/" + encodePath(path);
        }
        return baseUrl() + "/api/models/download?repo=" + encode(repo)
                + "&path=" + encode(path);
    }

    private void hideKeyboard() {
        try {
            InputMethodManager manager = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
            if (manager != null && text != null) {
                manager.hideSoftInputFromWindow(text.getWindowToken(), 0);
            }
            if (text != null) text.clearFocus();
        } catch (Throwable ignored) {
            // Bàn phím không bắt buộc phải đóng.
        }
    }

    private void setMode(String next) {
        hideKeyboard();
        mode = "remote".equals(next) ? "remote" : "local";
        remoteMode = "remote".equals(mode);
        prefs.edit().putString(KEY_MODE, mode).apply();
        if (localTab == null) return;
        VfTheme.segmentButton(localTab, !remoteMode, VfTheme.typeface(this));
        VfTheme.segmentButton(remoteTab, remoteMode, VfTheme.typeface(this));
        remoteFields.setVisibility(remoteMode ? View.VISIBLE : View.GONE);
        subtitle.setText(remoteMode ? "Remote HTTP · server API" : "Local ONNX · Rust C ABI");
        hintLabel.setText(remoteMode
                ? "Remote TTS dùng /api/tts. Model browser: để trống URL = tải HuggingFace trực tiếp, nhập URL = qua server."
                : "Local dùng model bundled hoặc .vfa/.vfts đã tải. Model browser tự tải trực tiếp HuggingFace nếu Server URL trống.");
    }

    private void setBusy(boolean value) {
        busy = value;
        runOnUiThread(() -> {
            runButton.setEnabled(!value);
            modelButton.setEnabled(!value);
            settingsButton.setEnabled(!value);
            progress.setVisibility(value ? View.VISIBLE : View.GONE);
        });
    }

    private void setError(String value) {
        runOnUiThread(() -> {
            errorLabel.setText(value == null ? "" : value);
            errorLabel.setVisibility(value == null || value.isEmpty() ? View.GONE : View.VISIBLE);
        });
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

    private byte[] getBytesProgress(String url, String label) throws Exception {
        HttpURLConnection connection = open(url);
        try {
            int code = connection.getResponseCode();
            if (code < 200 || code >= 300) {
                String error = new String(readError(connection), StandardCharsets.UTF_8);
                throw new IllegalStateException("HTTP " + code + ": " + error);
            }
            int total = connection.getContentLength();
            try (InputStream input = connection.getInputStream();
                 ByteArrayOutputStream output = new ByteArrayOutputStream(
                         total > 0 ? total : 8192)) {
                byte[] buffer = new byte[1024 * 256];
                int read;
                int written = 0;
                int lastPercent = -1;
                while ((read = input.read(buffer)) > 0) {
                    output.write(buffer, 0, read);
                    written += read;
                    if (total > 0) {
                        int percent = written * 100 / total;
                        if (percent != lastPercent) {
                            lastPercent = percent;
                            setStatus(String.format(Locale.US, "%s · %d%% (%.1f MB)",
                                    label, percent, written / 1e6));
                        }
                    }
                }
                return output.toByteArray();
            }
        } finally {
            connection.disconnect();
        }
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private void synthesize() {
        hideKeyboard();
        final String input = text.getText().toString().trim();
        if (input.isEmpty()) {
            setStatus("Nhập text");
            return;
        }
        if (busy) return;
        setError("");
        if (remoteMode) {
            if (!requireServer()) return;
            if (streamMode) synthesizeRemoteStream(input);
            else synthesizeRemote(input);
            return;
        }
        if (streamMode) {
            synthesizeLocalStream(input);
            return;
        }
        setBusy(true);
        setStatus("Đang tổng hợp local…" + estimateSuffix("local", input));
        final long runStarted = System.currentTimeMillis();
        new Thread(() -> {
            try {
                ensureEngine();
                Options options = new Options();
                options.speed = speechSpeed;
                options.alpha = sharpenAlpha;
                options.max_chars = new NativeLong(maxChars);
                options.fixed_pauses = fixedPauses ? (byte) 1 : (byte) 0;
                options.peak_normalize = peakNormalize ? (byte) 1 : (byte) 0;
                byte[] wav = null;
                String karaoke = null;
                PointerByReference outWav = new PointerByReference();
                PointerByReference outKaraoke = new PointerByReference();
                NativeLongByReference len = new NativeLongByReference();
                int code = ffi.vifasttts_synthesize_karaoke_ex(
                        engine, input, options, dialect, resolveOov ? (byte) 1 : (byte) 0,
                        dictionaryText, outWav, len, outKaraoke);
                if (code == 0) {
                    Pointer data = outWav.getValue();
                    if (data == null) throw new IllegalStateException(lastError());
                    long size = len.getValue().longValue();
                    wav = data.getByteArray(0, (int) size);
                    ffi.vifasttts_buffer_free(data, len.getValue());
                    Pointer json = outKaraoke.getValue();
                    if (json != null) {
                        karaoke = json.getString(0, "UTF-8");
                        ffi.vifasttts_string_free(json);
                    }
                } else {
                    // Model không xuất timing: vẫn đọc được, chỉ không có phụ đề.
                    NativeLongByReference plainLen = new NativeLongByReference();
                    Pointer data = ffi.vifasttts_synthesize_ex(
                            engine, input, options, dialect, resolveOov ? (byte) 1 : (byte) 0,
                            dictionaryText, plainLen);
                    if (data == null) throw new IllegalStateException(lastError());
                    long size = plainLen.getValue().longValue();
                    wav = data.getByteArray(0, (int) size);
                    ffi.vifasttts_buffer_free(data, plainLen.getValue());
                }
                File out = new File(getCacheDir(), "vifasttts.wav");
                Files.write(out.toPath(), wav);
                lastKaraokeJson = karaoke == null ? "" : karaoke;
                lastSrt = karaokeText(karaoke, true);
                lastVtt = karaokeText(karaoke, false);
                String suffix = lastSrt.isEmpty() ? "" : " · có phụ đề";
                recordRun("local", input, System.currentTimeMillis() - runStarted,
                        wav.length / 2.0 / 24000.0);
                play(out, "Xong: " + String.format("%.2f s", wav.length / 2.0 / 24000.0) + suffix);
            } catch (Throwable error) {
                setStatus("Lỗi: " + error.getMessage());
                setError(error.getMessage());
                setBusy(false);
            }
        }).start();
    }

    private void synthesizeLocalStream(String input) {
        setBusy(true);
        setStatus("Đang stream local…" + estimateSuffix("local-stream", input));
        final long runStarted = System.currentTimeMillis();
        new Thread(() -> {
            AudioTrack track = null;
            AudioTrack streamTrack = null;
            try {
                ensureEngine();
                Options options = new Options();
                options.speed = speechSpeed;
                options.alpha = sharpenAlpha;
                options.max_chars = new NativeLong(maxChars);
                options.fixed_pauses = fixedPauses ? (byte) 1 : (byte) 0;
                options.peak_normalize = peakNormalize ? (byte) 1 : (byte) 0;
                int sampleRate = 48000;
                int channelMask = AudioFormat.CHANNEL_OUT_MONO;
                int minBuffer = AudioTrack.getMinBufferSize(
                        sampleRate, channelMask, AudioFormat.ENCODING_PCM_16BIT);
                int bufferSize = Math.max(minBuffer * 4, sampleRate * 2 * 2);
                track = new AudioTrack.Builder()
                        .setAudioAttributes(speechAudioAttributes())
                        .setAudioFormat(new AudioFormat.Builder()
                                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                                .setSampleRate(sampleRate)
                                .setChannelMask(channelMask)
                                .build())
                        .setTransferMode(AudioTrack.MODE_STREAM)
                        .setBufferSizeInBytes(bufferSize)
                        .build();
                if (track.getState() != AudioTrack.STATE_INITIALIZED) {
                    throw new IllegalStateException("AudioTrack stream chưa khởi tạo");
                }
                audioStopped = false;
                audioTrack = track;
                audioSampleRate = sampleRate;
                audioChannels = 1;
                track.play();
                streamTrack = track;
                final AudioTrack callbackTrack = streamTrack;
                requestAudioFocus();
                runOnUiThread(() -> {
                    stopButton.setEnabled(true);
                    if (saveButton != null) saveButton.setEnabled(false);
                    if (shareButton != null) shareButton.setEnabled(false);
                    stopKaraoke();
                });
                final long[] framesWritten = {0};
                StreamCallback callback = (samples, length, sampleRateValue, userData) -> {
                    if (audioStopped) return 1;
                    int count = (int) length.longValue();
                    short[] pcm = new short[count];
                    for (int index = 0; index < count; index += 1) {
                        float value = samples.getFloat(index * 4L);
                        pcm[index] = (short) Math.max(-32768, Math.min(32767,
                                Math.round(value * 32767f)));
                    }
                    short[] upsampled = resamplePcm(pcm, 24000, 48000, 1);
                    int written = callbackTrack.write(upsampled, 0, upsampled.length,
                            AudioTrack.WRITE_BLOCKING);
                    if (written > 0) framesWritten[0] += written;
                    return written < 0 ? 1 : 0;
                };
                int code = ffi.vifasttts_synthesize_stream_ex(
                        engine, input, options, dialect, resolveOov ? (byte) 1 : (byte) 0,
                        dictionaryText, callback, null);
                if (code < 0) throw new IllegalStateException(lastError());
                if (code == 0) waitForPlayback(streamTrack, framesWritten[0], 8000);
                recordRun("local-stream", input, System.currentTimeMillis() - runStarted,
                        framesWritten[0] / 48000.0);
                setStatus(code == 1 ? "Đã dừng stream" : "Xong stream local");
            } catch (Throwable error) {
                setStatus("Lỗi stream: " + error.getMessage());
                setError(error.getMessage());
            } finally {
                if (streamTrack != null && audioTrack == streamTrack) {
                    audioTrack = null;
                    try {
                        streamTrack.stop();
                    } catch (Throwable ignored) {
                        // Có thể đã stop từ UI.
                    }
                    streamTrack.release();
                }
                runOnUiThread(() -> stopButton.setEnabled(false));
                abandonAudioFocus();
                setBusy(false);
            }
        }, "vifasttts-stream").start();
    }

    private void synthesizeRemoteStream(String input) {
        final String base = baseUrl();
        setBusy(true);
        setStatus("Đang stream remote…" + estimateSuffix("remote-stream", input));
        final long runStarted = System.currentTimeMillis();
        new Thread(() -> {
            AudioTrack track = null;
            HttpURLConnection connection = null;
            try {
                String url = base.endsWith("/api/tts/stream")
                        ? base
                        : base.endsWith("/api/tts")
                        ? base + "/stream"
                        : base + "/api/tts/stream";
                connection = open(url);
                connection.setRequestMethod("POST");
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                JSONObject body = new JSONObject();
                body.put("text", input);
                body.put("speed", speechSpeed);
                body.put("alpha", sharpenAlpha);
                body.put("max_chars", maxChars);
                body.put("fixed_pauses", fixedPauses);
                body.put("peak_normalize", peakNormalize);
                body.put("dialect", dialect);
                body.put("resolve_oov", resolveOov);
                body.put("dictionary", dictionaryText);
                byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
                connection.setFixedLengthStreamingMode(payload.length);
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(payload);
                }
                int code = connection.getResponseCode();
                if (code < 200 || code >= 300) {
                    String error = new String(readError(connection), StandardCharsets.UTF_8);
                    throw new IllegalStateException("HTTP " + code + ": " + error);
                }
                int sampleRate = 48000;
                int channelMask = AudioFormat.CHANNEL_OUT_MONO;
                int minBuffer = AudioTrack.getMinBufferSize(
                        sampleRate, channelMask, AudioFormat.ENCODING_PCM_16BIT);
                track = new AudioTrack.Builder()
                        .setAudioAttributes(speechAudioAttributes())
                        .setAudioFormat(new AudioFormat.Builder()
                                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                                .setSampleRate(sampleRate)
                                .setChannelMask(channelMask)
                                .build())
                        .setTransferMode(AudioTrack.MODE_STREAM)
                        .setBufferSizeInBytes(Math.max(minBuffer * 4, sampleRate * 2 * 2))
                        .build();
                if (track.getState() != AudioTrack.STATE_INITIALIZED) {
                    throw new IllegalStateException("AudioTrack stream chưa khởi tạo");
                }
                track.play();
                final AudioTrack streamTrack = track;
                audioStopped = false;
                audioTrack = track;
                audioSampleRate = sampleRate;
                audioChannels = 1;
                streamConnection = connection;
                requestAudioFocus();
                runOnUiThread(() -> {
                    stopButton.setEnabled(true);
                    if (saveButton != null) saveButton.setEnabled(false);
                    if (shareButton != null) shareButton.setEnabled(false);
                    stopKaraoke();
                });
                long framesWritten = 0;
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                        connection.getInputStream(), StandardCharsets.UTF_8))) {
                    String line;
                    while (!audioStopped && (line = reader.readLine()) != null) {
                        if (line.trim().isEmpty()) continue;
                        JSONObject event = new JSONObject(line);
                        String type = event.optString("type", "");
                        if ("audio".equals(type)) {
                            byte[] raw = Base64.decode(event.optString("pcm_base64", ""),
                                    Base64.DEFAULT);
                            short[] pcm = new short[raw.length / 2];
                            for (int index = 0; index < pcm.length; index += 1) {
                                int low = raw[index * 2] & 0xff;
                                int high = raw[index * 2 + 1] << 8;
                                pcm[index] = (short) (low | high);
                            }
                            short[] upsampled = resamplePcm(pcm, 24000, 48000, 1);
                            int written = streamTrack.write(upsampled, 0, upsampled.length,
                                    AudioTrack.WRITE_BLOCKING);
                            if (written < 0) throw new IllegalStateException("AudioTrack write lỗi");
                            framesWritten += written;
                        } else if ("error".equals(type)) {
                            throw new IllegalStateException(event.optString("message", "server stream lỗi"));
                        }
                    }
                }
                if (!audioStopped) waitForPlayback(streamTrack, framesWritten, 8000);
                recordRun("remote-stream", input, System.currentTimeMillis() - runStarted,
                        framesWritten / 48000.0);
                setStatus(audioStopped ? "Đã dừng stream remote" : "Xong stream remote");
            } catch (Throwable error) {
                setStatus("Lỗi stream remote: " + error.getMessage());
                setError(error.getMessage());
            } finally {
                if (track != null) {
                    if (audioTrack == track) audioTrack = null;
                    try {
                        track.stop();
                    } catch (Throwable ignored) {
                        // Có thể đã stop từ UI.
                    }
                    track.release();
                }
                if (connection != null) connection.disconnect();
                streamConnection = null;
                runOnUiThread(() -> stopButton.setEnabled(false));
                abandonAudioFocus();
                setBusy(false);
            }
        }, "vifasttts-remote-stream").start();
    }

    private void synthesizeRemote(String input) {
        final String base = baseUrl();
        setBusy(true);
        setStatus("Đang gọi server…" + estimateSuffix("remote", input));
        final long runStarted = System.currentTimeMillis();
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
                body.put("speed", speechSpeed);
                body.put("alpha", sharpenAlpha);
                body.put("max_chars", maxChars);
                body.put("fixed_pauses", fixedPauses);
                body.put("peak_normalize", peakNormalize);
                body.put("dialect", dialect);
                body.put("resolve_oov", resolveOov);
                body.put("dictionary", dictionaryText);
                body.put("karaoke", true);
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
                String contentType = connection.getContentType();
                byte[] wav;
                if (contentType != null && contentType.contains("application/json")) {
                    JSONObject result = new JSONObject(new String(
                            readAll(connection.getInputStream()), StandardCharsets.UTF_8));
                    wav = Base64.decode(result.getString("audio_base64"), Base64.DEFAULT);
                    lastSrt = result.optString("srt", "");
                    lastVtt = result.optString("vtt", result.optString("vtt_karaoke", ""));
                    lastKaraokeJson = result.optJSONObject("karaoke") == null
                            ? "" : result.optJSONObject("karaoke").toString();
                } else {
                    wav = readAll(connection.getInputStream());
                    lastSrt = "";
                    lastVtt = "";
                    lastKaraokeJson = "";
                }
                File out = new File(getCacheDir(), "vifasttts-remote.wav");
                Files.write(out.toPath(), wav);
                String suffix = lastSrt.isEmpty() ? "" : " · có phụ đề";
                recordRun("remote", input, System.currentTimeMillis() - runStarted,
                        wav.length / 2.0 / 24000.0);
                play(out, "Xong remote: " + String.format("%.2f s", wav.length / 2.0 / 24000.0) + suffix);
            } catch (Throwable error) {
                setStatus("Lỗi remote: " + error.getMessage());
                setError(error.getMessage());
                setBusy(false);
            } finally {
                if (connection != null) connection.disconnect();
            }
        }).start();
    }

    private AudioAttributes speechAudioAttributes() {
        return new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build();
    }

    private void requestAudioFocus() {
        if (audioManager == null) return;
        AudioAttributes attributes = speechAudioAttributes();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            focusRequest = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                    .setAudioAttributes(attributes)
                    .setOnAudioFocusChangeListener(change -> {})
                    .build();
            audioManager.requestAudioFocus(focusRequest);
        } else {
            audioManager.requestAudioFocus(null, AudioManager.STREAM_MUSIC,
                    AudioManager.AUDIOFOCUS_GAIN);
        }
    }

    private void abandonAudioFocus() {
        if (audioManager == null) return;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (focusRequest != null) {
                audioManager.abandonAudioFocusRequest(focusRequest);
                focusRequest = null;
            }
        } else {
            audioManager.abandonAudioFocus(null);
        }
    }

    private void play(File out, String message) {
        new Thread(() -> {
            try {
                PcmClip clip = readWav(out);
                runOnUiThread(() -> startAudioTrack(out, clip, message));
            } catch (Throwable error) {
                runOnUiThread(() -> {
                    status.setText("Đã tạo WAV, lỗi đọc WAV: " + error.getMessage());
                    setError(error.getMessage());
                    setBusy(false);
                });
            }
        }, "vifasttts-wav-read").start();
    }

    private void startAudioTrack(File out, PcmClip clip, String message) {
        stopAudioPath();
        status.setText(message);
        setBusy(false);
        requestAudioFocus();
        try {
            int channelMask = clip.channels == 2
                    ? AudioFormat.CHANNEL_OUT_STEREO : AudioFormat.CHANNEL_OUT_MONO;
            // Đưa PCM lên 48 kHz ngay trong app: mixer/HAL của emulator và nhiều
            // thiết bị Android chạy 48 kHz, tránh resample 24k -> 48k gây vấp.
            int outputRate = 48000;
            short[] playbackSamples = clip.sampleRate == outputRate
                    ? clip.samples
                    : resamplePcm(clip.samples, clip.sampleRate, outputRate, clip.channels);
            int minBuffer = AudioTrack.getMinBufferSize(
                    outputRate, channelMask, AudioFormat.ENCODING_PCM_16BIT);
            if (minBuffer <= 0) minBuffer = outputRate * clip.channels * 2;
            // Buffer 2 giây: đủ lớn để emulator/thiết bị yếu không bị underrun.
            int bufferSize = Math.max(minBuffer * 4,
                    outputRate * clip.channels * 2 * 2);
            AudioTrack track = new AudioTrack.Builder()
                    .setAudioAttributes(speechAudioAttributes())
                    .setAudioFormat(new AudioFormat.Builder()
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .setSampleRate(outputRate)
                            .setChannelMask(channelMask)
                            .build())
                    .setTransferMode(AudioTrack.MODE_STREAM)
                    .setBufferSizeInBytes(bufferSize)
                    .build();
            if (track.getState() != AudioTrack.STATE_INITIALIZED) {
                track.release();
                throw new IllegalStateException("AudioTrack chưa khởi tạo");
            }
            audioTrack = track;
            audioSampleRate = outputRate;
            audioChannels = clip.channels;
            audioStopped = false;
            track.play();
            short[] samples = playbackSamples;
            audioThread = new Thread(() -> writeAudio(track, samples, clip.channels),
                    "vifasttts-audio");
            audioThread.start();
            lastAudioFile = out;
            if (saveButton != null) saveButton.setEnabled(true);
            if (shareButton != null) shareButton.setEnabled(lastAudioFile != null);
            stopButton.setEnabled(true);
            startKaraoke();
        } catch (Throwable error) {
            setError("AudioTrack lỗi: " + error.getMessage() + "; thử MediaPlayer");
            playWithMediaPlayer(out, message);
        }
    }

    private void writeAudio(AudioTrack track, short[] samples, int channels) {
        int offset = 0;
        try {
            while (!audioStopped && offset < samples.length) {
                int count = Math.min(4096, samples.length - offset);
                int written = track.write(samples, offset, count, AudioTrack.WRITE_BLOCKING);
                if (written <= 0) break;
                offset += written;
            }
            int frames = samples.length / Math.max(1, channels);
            long deadline = System.currentTimeMillis() + 5000;
            while (!audioStopped && track.getPlaybackHeadPosition() < frames
                    && System.currentTimeMillis() < deadline) {
                Thread.sleep(20);
            }
        } catch (Throwable ignored) {
            // Stop/release từ UI cũng làm write ném; không phải lỗi phát.
        }
        runOnUiThread(() -> finishAudioTrack(track));
    }

    private void finishAudioTrack(AudioTrack track) {
        if (audioTrack != track) return;
        audioStopped = true;
        audioTrack = null;
        try {
            track.stop();
        } catch (Throwable ignored) {
            // Có thể đã stop từ UI.
        }
        track.release();
        stopButton.setEnabled(false);
        stopKaraoke();
        abandonAudioFocus();
    }

    private void stopAudioPath() {
        audioStopped = true;
        if (streamConnection != null) {
            try {
                streamConnection.disconnect();
            } catch (Throwable ignored) {
                // Kết nối có thể đã đóng.
            }
            streamConnection = null;
        }
        if (audioTrack != null) {
            try {
                audioTrack.pause();
                audioTrack.flush();
                audioTrack.stop();
            } catch (Throwable ignored) {
                // Track có thể chưa play.
            }
            audioTrack.release();
            audioTrack = null;
        }
        if (audioThread != null) {
            audioThread.interrupt();
            audioThread = null;
        }
        if (player != null) {
            try {
                player.stop();
            } catch (Throwable ignored) {
                // MediaPlayer chưa start vẫn có thể ném.
            }
            player.release();
            player = null;
        }
    }

    private int currentPlaybackPosition() {
        if (audioTrack != null) {
            int frames = audioTrack.getPlaybackHeadPosition();
            return (int) (frames * 1000L / Math.max(1, audioSampleRate));
        }
        if (player != null) return player.getCurrentPosition();
        return 0;
    }

    private void playWithMediaPlayer(File out, String message) {
        status.setText(message);
        setBusy(false);
        try {
            stopAudioPath();
            requestAudioFocus();
            player = new MediaPlayer();
            player.setAudioAttributes(speechAudioAttributes());
            player.setDataSource(out.getAbsolutePath());
            player.setOnCompletionListener(done -> {
                stopButton.setEnabled(false);
                stopKaraoke();
                abandonAudioFocus();
            });
            player.setOnErrorListener((mp, what, extra) -> {
                setError("MediaPlayer lỗi " + what + "/" + extra);
                abandonAudioFocus();
                return false;
            });
            player.prepare();
            player.start();
            lastAudioFile = out;
            if (saveButton != null) saveButton.setEnabled(true);
            if (shareButton != null) shareButton.setEnabled(lastAudioFile != null);
            stopButton.setEnabled(true);
            startKaraoke();
        } catch (Throwable error) {
            status.setText("Đã tạo WAV, lỗi phát: " + error.getMessage());
            setError(error.getMessage());
            abandonAudioFocus();
        }
    }

    private static short[] resamplePcm(short[] input, int sourceRate, int targetRate, int channels) {
        int sourceFrames = input.length / Math.max(1, channels);
        int targetFrames = Math.max(1, Math.round(sourceFrames * (float) targetRate / sourceRate));
        short[] output = new short[targetFrames * channels];
        double step = (double) sourceRate / targetRate;
        for (int frame = 0; frame < targetFrames; frame += 1) {
            double source = frame * step;
            int left = Math.min(sourceFrames - 1, (int) source);
            int right = Math.min(sourceFrames - 1, left + 1);
            float fraction = (float) (source - left);
            for (int channel = 0; channel < channels; channel += 1) {
                int a = input[left * channels + channel];
                int b = input[right * channels + channel];
                output[frame * channels + channel] = (short) Math.round(a + (b - a) * fraction);
            }
        }
        return output;
    }

    private static final class PcmClip {
        final short[] samples;
        final int sampleRate;
        final int channels;

        PcmClip(short[] samples, int sampleRate, int channels) {
            this.samples = samples;
            this.sampleRate = sampleRate;
            this.channels = channels;
        }
    }

    private static PcmClip readWav(File file) throws Exception {
        byte[] bytes = Files.readAllBytes(file.toPath());
        if (bytes.length < 44 || bytes[0] != 'R' || bytes[1] != 'I'
                || bytes[2] != 'F' || bytes[3] != 'F') {
            throw new IllegalArgumentException("không phải WAV RIFF");
        }
        ByteBuffer buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN);
        int sampleRate = 0;
        int channels = 0;
        int bits = 0;
        int dataOffset = -1;
        int dataSize = 0;
        int position = 12;
        while (position + 8 <= bytes.length) {
            int id = buffer.getInt(position);
            int size = buffer.getInt(position + 4);
            int content = position + 8;
            if (id == 0x20746d66) { // "fmt " little-endian
                channels = buffer.getShort(content + 2) & 0xffff;
                sampleRate = buffer.getInt(content + 4);
                bits = buffer.getShort(content + 14) & 0xffff;
            } else if (id == 0x61746164) { // "data" little-endian
                dataOffset = content;
                dataSize = Math.min(size, bytes.length - content);
                break;
            }
            position = content + size + (size & 1);
        }
        if (sampleRate <= 0 || channels <= 0 || bits != 16 || dataOffset < 0 || dataSize < 2) {
            throw new IllegalArgumentException("WAV không phải PCM16 mono/stereo hợp lệ");
        }
        short[] samples = new short[dataSize / 2];
        buffer.position(dataOffset);
        buffer.asShortBuffer().get(samples);
        return new PcmClip(samples, sampleRate, channels);
    }

    private void waitForPlayback(AudioTrack track, long frames, long timeoutMs) {
        if (track == null || frames <= 0) return;
        long deadline = System.currentTimeMillis() + timeoutMs;
        try {
            while (!audioStopped && track.getPlaybackHeadPosition() < frames
                    && System.currentTimeMillis() < deadline) {
                Thread.sleep(20);
            }
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        } catch (Throwable ignored) {
            // Track có thể đã bị stop từ UI.
        }
    }

    private void stopPlayback() {
        stopAudioPath();
        stopKaraoke();
        stopButton.setEnabled(false);
        abandonAudioFocus();
        setStatus("Đã dừng phát");
    }

    private void startKaraoke() {
        stopKaraoke();
        if (karaokeView == null || lastKaraokeJson.isEmpty()) {
            if (karaokeView != null) karaokeView.setVisibility(View.GONE);
            return;
        }
        try {
            karaokeUnits = new JSONObject(lastKaraokeJson).optJSONArray("units");
        } catch (Throwable error) {
            karaokeUnits = null;
        }
        if (karaokeUnits == null || karaokeUnits.length() == 0) {
            karaokeView.setVisibility(View.GONE);
            return;
        }
        karaokeView.setText("");
        karaokeView.setVisibility(View.VISIBLE);
        karaokeHandler.post(karaokeTick);
    }

    private void stopKaraoke() {
        karaokeHandler.removeCallbacks(karaokeTick);
        karaokeUnits = null;
        if (karaokeView != null) karaokeView.setVisibility(View.GONE);
    }

    private void showSettings() {
        Typeface font = VfTheme.typeface(this);
        LinearLayout form = new LinearLayout(this);
        form.setOrientation(LinearLayout.VERTICAL);
        int pad = VfTheme.dp(this, 18);
        form.setPadding(pad, VfTheme.dp(this, 8), pad, VfTheme.dp(this, 8));

        TextView speedLabel = new TextView(this);
        VfTheme.text(speedLabel, font, 13, VfTheme.INK, true);
        form.addView(speedLabel);
        SeekBar speedBar = new SeekBar(this);
        speedBar.setMax(150);
        speedBar.setProgress(Math.round((speechSpeed - 0.5f) * 100f));
        form.addView(speedBar);
        speedLabel.setText(String.format("Tốc độ: %.2f×", speechSpeed));
        speedBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                speedLabel.setText(String.format("Tốc độ: %.2f×", 0.5f + progress / 100f));
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        TextView alphaLabel = new TextView(this);
        VfTheme.text(alphaLabel, font, 13, VfTheme.INK, true);
        LinearLayout.LayoutParams alphaLabelParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        alphaLabelParams.topMargin = VfTheme.dp(this, 10);
        form.addView(alphaLabel, alphaLabelParams);
        SeekBar alphaBar = new SeekBar(this);
        alphaBar.setMax(250);
        alphaBar.setProgress(Math.round((sharpenAlpha - 0.5f) * 100f));
        form.addView(alphaBar);
        alphaLabel.setText(String.format("Độ nét mel (alpha): %.2f", sharpenAlpha));
        alphaBar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                alphaLabel.setText(String.format("Độ nét mel (alpha): %.2f", 0.5f + progress / 100f));
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        TextView maxLabel = new TextView(this);
        VfTheme.text(maxLabel, font, 13, VfTheme.INK, true);
        LinearLayout.LayoutParams maxLabelParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        maxLabelParams.topMargin = VfTheme.dp(this, 10);
        form.addView(maxLabel, maxLabelParams);
        maxLabel.setText("Max ký tự mỗi chunk");
        EditText maxInput = new EditText(this);
        maxInput.setText(String.valueOf(maxChars));
        maxInput.setInputType(InputType.TYPE_CLASS_NUMBER);
        VfTheme.input(maxInput, font);
        form.addView(maxInput);

        CheckBox fixed = new CheckBox(this);
        fixed.setText("Pause cố định theo dấu câu");
        fixed.setChecked(fixedPauses);
        VfTheme.text(fixed, font, 14, VfTheme.INK, false);
        fixed.setButtonTintList(android.content.res.ColorStateList.valueOf(VfTheme.ACCENT));
        form.addView(fixed);

        CheckBox peak = new CheckBox(this);
        peak.setText("Peak normalize");
        peak.setChecked(peakNormalize);
        VfTheme.text(peak, font, 14, VfTheme.INK, false);
        peak.setButtonTintList(android.content.res.ColorStateList.valueOf(VfTheme.ACCENT));
        form.addView(peak);

        CheckBox stream = new CheckBox(this);
        stream.setText("Stream local (phát ngay khi tổng hợp)");
        stream.setChecked(streamMode);
        VfTheme.text(stream, font, 14, VfTheme.INK, false);
        stream.setButtonTintList(android.content.res.ColorStateList.valueOf(VfTheme.ACCENT));
        form.addView(stream);

        TextView dialectLabel = new TextView(this);
        VfTheme.text(dialectLabel, font, 13, VfTheme.INK, true);
        LinearLayout.LayoutParams dialectLabelParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        dialectLabelParams.topMargin = VfTheme.dp(this, 10);
        form.addView(dialectLabel, dialectLabelParams);
        dialectLabel.setText("Phương ngữ");
        Spinner dialectSpinner = new Spinner(this);
        String[] dialectLabels = {"Bắc", "Trung", "Nam"};
        ArrayAdapter<String> dialectAdapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, dialectLabels);
        dialectAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        dialectSpinner.setAdapter(dialectAdapter);
        dialectSpinner.setSelection(dialect.equals("central") ? 1 : dialect.equals("south") ? 2 : 0);
        form.addView(dialectSpinner);

        CheckBox oov = new CheckBox(this);
        oov.setText("Resolve OOV");
        oov.setChecked(resolveOov);
        VfTheme.text(oov, font, 14, VfTheme.INK, false);
        oov.setButtonTintList(android.content.res.ColorStateList.valueOf(VfTheme.ACCENT));
        form.addView(oov);

        TextView dictionaryLabel = new TextView(this);
        VfTheme.text(dictionaryLabel, font, 13, VfTheme.INK, true);
        LinearLayout.LayoutParams dictionaryLabelParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        dictionaryLabelParams.topMargin = VfTheme.dp(this, 10);
        form.addView(dictionaryLabel, dictionaryLabelParams);
        dictionaryLabel.setText("Từ điển local (mỗi dòng `từ = cách đọc`)");
        EditText dictionaryInput = new EditText(this);
        dictionaryInput.setText(dictionaryText);
        dictionaryInput.setHint("AI = ây ai\nVPS = vi pi ét");
        dictionaryInput.setMinLines(4);
        dictionaryInput.setGravity(Gravity.TOP | Gravity.START);
        dictionaryInput.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        VfTheme.input(dictionaryInput, font);
        form.addView(dictionaryInput);

        TextView note = new TextView(this);
        VfTheme.text(note, font, 12, VfTheme.MUTED, false);
        note.setText("Local áp dụng đầy đủ: tốc độ, alpha, max, pause, peak, phương ngữ, OOV và từ điển. Remote gửi cùng bộ tùy chọn; server cũ có thể bỏ qua. Model base 60k nặng hơn small; máy yếu nên dùng small.");
        LinearLayout.LayoutParams noteParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        noteParams.topMargin = VfTheme.dp(this, 8);
        form.addView(note, noteParams);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(form);
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Cấu hình")
                .setView(scroll)
                .setPositiveButton("Lưu", null)
                .setNegativeButton("Huỷ", null)
                .create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE)
                .setOnClickListener(view -> {
                    speechSpeed = 0.5f + speedBar.getProgress() / 100f;
                    sharpenAlpha = 0.5f + alphaBar.getProgress() / 100f;
                    try {
                        maxChars = Math.max(50, Math.min(5000,
                                Integer.parseInt(maxInput.getText().toString().trim())));
                    } catch (NumberFormatException ignoredValue) {
                        maxChars = 300;
                    }
                    fixedPauses = fixed.isChecked();
                    peakNormalize = peak.isChecked();
                    streamMode = stream.isChecked();
                    int dialectIndex = dialectSpinner.getSelectedItemPosition();
                    dialect = dialectIndex == 1 ? "central" : dialectIndex == 2 ? "south" : "north";
                    resolveOov = oov.isChecked();
                    dictionaryText = dictionaryInput.getText().toString().trim();
                    maxInput.setText(String.valueOf(maxChars));
                    prefs.edit()
                            .putFloat(KEY_SPEED, speechSpeed)
                            .putFloat(KEY_ALPHA, sharpenAlpha)
                            .putInt(KEY_MAX_CHARS, maxChars)
                            .putBoolean(KEY_FIXED_PAUSES, fixedPauses)
                            .putBoolean(KEY_PEAK_NORMALIZE, peakNormalize)
                            .putBoolean(KEY_STREAM, streamMode)
                            .putString(KEY_DIALECT, dialect)
                            .putBoolean(KEY_RESOLVE_OOV, resolveOov)
                            .putString(KEY_DICTIONARY, dictionaryText)
                            .apply();
                    setStatus(String.format(
                            "Đã lưu cấu hình · %.2f× · alpha %.2f · %s · OOV %s · stream %s · tối đa %d ký tự · %d quy tắc",
                            speechSpeed, sharpenAlpha,
                            dialect.equals("central") ? "Trung" : dialect.equals("south") ? "Nam" : "Bắc",
                            resolveOov ? "bật" : "tắt", streamMode ? "bật" : "tắt", maxChars,
                            dictionaryText.isEmpty() ? 0 : dictionaryText.split("\n").length));
                    if (streamQuick != null) streamQuick.setChecked(streamMode);
                    updateSettingsSummary();
                    dialog.dismiss();
                }));
        dialog.show();
    }

    private void showModelManager() {
        String active = activeAcousticPath.isEmpty() || activeVocoderPath.isEmpty()
                ? (activeModelPath.isEmpty() ? "Bundled ONNX" : new File(activeModelPath).getName())
                : "ONNX acoustic + vocoder";
        String[] options = {
                "Dùng model bundled (ONNX)",
                "Danh sách model đã cài",
                "Tải từ HuggingFace",
                "Chọn file .vfa/.vfts",
                "Chọn acoustic.onnx",
                "Chọn vocoder.onnx",
                "Xoá model đang dùng",
        };
        new AlertDialog.Builder(this)
                .setTitle("Model · " + active)
                .setItems(options, (dialog, which) -> {
                    switch (which) {
                        case 0 -> selectBundledModel();
                        case 1 -> showInstalledModels();
                        case 2 -> showModelSearch();
                        case 3 -> chooseModelFile(REQUEST_BUNDLE);
                        case 4 -> chooseModelFile(REQUEST_ACOUSTIC);
                        case 5 -> chooseModelFile(REQUEST_VOCODER);
                        case 6 -> deleteActiveModel();
                        default -> { }
                    }
                })
                .setNegativeButton("Đóng", null)
                .show();
    }

    private void showInstalledModels() {
        File directory = new File(getFilesDir(), "models");
        File[] files = directory.listFiles((dir, name) ->
                name.endsWith(".vfa") || name.endsWith(".vfts"));
        if (files == null || files.length == 0) {
            setStatus("Chưa có model .vfa/.vfts đã cài; dùng Tải từ HuggingFace.");
            return;
        }
        java.util.Arrays.sort(files, (a, b) -> a.getName().compareToIgnoreCase(b.getName()));
        String[] labels = new String[files.length];
        for (int index = 0; index < files.length; index += 1) {
            labels[index] = files[index].getName() + " — "
                    + (files[index].length() / 1_000_000) + " MB";
        }
        new AlertDialog.Builder(this)
                .setTitle("Model đã cài")
                .setItems(labels, (dialog, which) -> selectBundleModel(files[which]))
                .setNegativeButton("Đóng", null)
                .show();
    }

    private void selectBundledModel() {
        activeModelPath = "";
        activeAcousticPath = "";
        activeVocoderPath = "";
        prefs.edit()
                .remove(KEY_ACTIVE_MODEL)
                .remove(KEY_ACTIVE_ACOUSTIC)
                .remove(KEY_ACTIVE_VOCODER)
                .apply();
        resetEngine();
        updateModelLabel();
        setStatus("Đã chọn model bundled ONNX (acoustic + vocoder).");
        Toast.makeText(this, "Đang dùng model bundled ONNX", Toast.LENGTH_LONG).show();
    }

    private void selectBundleModel(File file) {
        if (!file.isFile()) {
            setStatus("Không thấy model: " + file);
            return;
        }
        activeModelPath = file.getAbsolutePath();
        activeAcousticPath = "";
        activeVocoderPath = "";
        prefs.edit()
                .putString(KEY_ACTIVE_MODEL, activeModelPath)
                .remove(KEY_ACTIVE_ACOUSTIC)
                .remove(KEY_ACTIVE_VOCODER)
                .apply();
        resetEngine();
        updateModelLabel();
        setStatus("Đang dùng " + file.getName() + "; lần đọc tới sẽ nạp model này.");
        Toast.makeText(this, "Đã chọn model: " + file.getName(), Toast.LENGTH_LONG).show();
    }

    private void deleteActiveModel() {
        if (activeModelPath.isEmpty()) {
            setStatus("Đang dùng model bundled; không có file để xoá.");
            return;
        }
        File file = new File(activeModelPath);
        if (file.isFile() && file.delete()) {
            setStatus("Đã xoá " + file.getName() + "; chuyển về model bundled.");
        } else {
            setStatus("Không xoá được " + file.getName());
        }
        selectBundledModel();
    }

    private void chooseModelFile(int requestCode) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, requestCode);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        new Thread(() -> {
            try {
                if (requestCode == REQUEST_BUNDLE) {
                    String display = displayName(uri);
                    if (!display.endsWith(".vfa") && !display.endsWith(".vfts")) {
                        throw new IllegalStateException("File phải là .vfa hoặc .vfts");
                    }
                    File directory = new File(getFilesDir(), "models");
                    if (!directory.exists() && !directory.mkdirs()) {
                        throw new IllegalStateException("Không tạo được thư mục models");
                    }
                    String safe = display.replaceAll("[^A-Za-z0-9._-]", "_");
                    File destination = new File(directory, safe);
                    copyUri(uri, destination);
                    runOnUiThread(() -> selectBundleModel(destination));
                } else if (requestCode == REQUEST_ACOUSTIC || requestCode == REQUEST_VOCODER) {
                    File directory = new File(getFilesDir(), "onnx");
                    if (!directory.exists() && !directory.mkdirs()) {
                        throw new IllegalStateException("Không tạo được thư mục onnx");
                    }
                    boolean acoustic = requestCode == REQUEST_ACOUSTIC;
                    File destination = new File(directory, acoustic ? "acoustic.onnx" : "vocoder.onnx");
                    copyUri(uri, destination);
                    if (acoustic) activeAcousticPath = destination.getAbsolutePath();
                    else activeVocoderPath = destination.getAbsolutePath();
                    prefs.edit()
                            .putString(KEY_ACTIVE_ACOUSTIC, activeAcousticPath)
                            .putString(KEY_ACTIVE_VOCODER, activeVocoderPath)
                            .apply();
                    if (!activeAcousticPath.isEmpty() && !activeVocoderPath.isEmpty()) {
                        activeModelPath = "";
                        prefs.edit().remove(KEY_ACTIVE_MODEL).apply();
                        runOnUiThread(() -> {
                            resetEngine();
                            updateModelLabel();
                            setStatus("Đang dùng cặp ONNX acoustic + vocoder.");
                        });
                    } else {
                        setStatus("Đã chọn " + destination.getName() + "; chọn nốt file còn lại.");
                    }
                }
            } catch (Throwable error) {
                setStatus("Lỗi nhập model: " + error.getMessage());
            }
        }, "vifasttts-model-import").start();
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(
                uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                String name = cursor.getString(0);
                if (name != null && !name.isEmpty()) return name;
            }
        } catch (Throwable ignored) {
            // Dùng tên mặc định bên dưới.
        }
        String fallback = uri.getLastPathSegment();
        return fallback == null ? "model.vfa" : fallback;
    }

    private void copyUri(Uri uri, File destination) throws Exception {
        try (InputStream input = getContentResolver().openInputStream(uri);
             OutputStream output = new FileOutputStream(destination)) {
            if (input == null) throw new IllegalStateException("Không mở được file");
            byte[] buffer = new byte[1024 * 1024];
            int read;
            while ((read = input.read(buffer)) > 0) output.write(buffer, 0, read);
        }
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
        status.setText("Đang tìm model qua " + modelSource() + "…");
        new Thread(() -> {
            try {
                byte[] body = getBytes(modelSearchUrl(query));
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
        status.setText("Đang xem " + repo + " qua " + modelSource() + "…");
        new Thread(() -> {
            try {
                byte[] body = getBytes(modelFilesUrl(repo));
                JSONArray files = new JSONArray(new String(body, StandardCharsets.UTF_8));
                if (files.length() == 0) {
                    setStatus("Repo chưa có .vfa/.vfts.");
                    return;
                }
                List<String> labels = new ArrayList<>();
                List<String> paths = new ArrayList<>();
                for (int index = 0; index < files.length(); index += 1) {
                    JSONObject file = files.getJSONObject(index);
                    if (!"file".equals(file.optString("type", "file"))) continue;
                    String path = file.optString("path", "");
                    if (!path.endsWith(".vfa") && !path.endsWith(".vfts")) continue;
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
                byte[] bytes = getBytesProgress(modelDownloadUrl(repo, path), "Đang tải " + path);
                String name = path.substring(path.lastIndexOf('/') + 1).replaceAll("[^A-Za-z0-9._-]", "_");
                if (!name.endsWith(".vfa") && !name.endsWith(".vfts")) {
                    throw new IllegalStateException("Nguồn trả file không phải .vfa/.vfts");
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
                activeAcousticPath = "";
                activeVocoderPath = "";
                prefs.edit()
                        .putString(KEY_ACTIVE_MODEL, activeModelPath)
                        .remove(KEY_ACTIVE_ACOUSTIC)
                        .remove(KEY_ACTIVE_VOCODER)
                        .apply();
                runOnUiThread(() -> {
                    resetEngine();
                    updateModelLabel();
                    setStatus("Đã tải " + name + " (" + bytes.length + " B); đọc local sẽ dùng bundle.");
                    Toast.makeText(this, "Đã tải model: " + name, Toast.LENGTH_LONG).show();
                });
            } catch (Throwable error) {
                setStatus("Lỗi tải model: " + error.getMessage());
            }
        }).start();
    }

    private String karaokeText(String json, boolean srt) {
        if (json == null || json.isEmpty()) return "";
        Pointer value = null;
        try {
            value = srt ? ffi.vifasttts_karaoke_to_srt(json) : ffi.vifasttts_karaoke_to_vtt(json);
            return value == null ? "" : value.getString(0, "UTF-8");
        } catch (Throwable error) {
            return "";
        } finally {
            if (value != null) ffi.vifasttts_string_free(value);
        }
    }

    private void saveWav() {
        if (lastAudioFile == null || !lastAudioFile.isFile()) {
            setStatus("Chưa có WAV để lưu");
            return;
        }
        String base = "vifasttts-" + System.currentTimeMillis();
        lastSavedWavUri = null;
        try {
            String location = saveBytes(base + ".wav",
                    Files.readAllBytes(lastAudioFile.toPath()), "audio/wav");
            int extra = 0;
            if (shareButton != null) shareButton.setEnabled(lastSavedWavUri != null);
            if (!lastSrt.isEmpty()) {
                saveBytes(base + ".srt", lastSrt.getBytes(StandardCharsets.UTF_8), "application/x-subrip");
                extra += 1;
            }
            if (!lastVtt.isEmpty()) {
                saveBytes(base + ".vtt", lastVtt.getBytes(StandardCharsets.UTF_8), "text/vtt");
                extra += 1;
            }
            if (!lastKaraokeJson.isEmpty()) {
                saveBytes(base + ".karaoke.json",
                        lastKaraokeJson.getBytes(StandardCharsets.UTF_8), "application/json");
                extra += 1;
            }
            setStatus("Đã lưu " + location + (extra > 0 ? " + " + extra + " tệp phụ đề" : ""));
        } catch (Throwable error) {
            setStatus("Lỗi lưu file: " + error.getMessage());
            setError(error.getMessage());
        }
    }

    private String saveBytes(String name, byte[] bytes, String mime) throws Exception {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues values = new ContentValues();
            values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
            values.put(MediaStore.MediaColumns.MIME_TYPE, mime);
            values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
            Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
            if (uri == null) throw new IllegalStateException("MediaStore trả URI null");
            try (OutputStream out = getContentResolver().openOutputStream(uri)) {
                if (out == null) throw new IllegalStateException("Không mở được Downloads");
                out.write(bytes);
            }
            if ("audio/wav".equals(mime)) lastSavedWavUri = uri;
            return "Downloads/" + name;
        }
        File dir = getExternalFilesDir(Environment.DIRECTORY_MUSIC);
        if (dir == null) throw new IllegalStateException("Không có thư mục Music");
        File out = new File(dir, name);
        Files.write(out.toPath(), bytes);
        return out.getAbsolutePath();
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
        activeAcousticPath = prefs.getString(KEY_ACTIVE_ACOUSTIC, "");
        activeVocoderPath = prefs.getString(KEY_ACTIVE_VOCODER, "");
        mode = prefs.getString(KEY_MODE, "local");
        speechSpeed = prefs.getFloat(KEY_SPEED, 1.0f);
        sharpenAlpha = prefs.getFloat(KEY_ALPHA, 1.5f);
        maxChars = prefs.getInt(KEY_MAX_CHARS, 300);
        fixedPauses = prefs.getBoolean(KEY_FIXED_PAUSES, false);
        peakNormalize = prefs.getBoolean(KEY_PEAK_NORMALIZE, false);
        dialect = prefs.getString(KEY_DIALECT, "north");
        resolveOov = prefs.getBoolean(KEY_RESOLVE_OOV, true);
        dictionaryText = prefs.getString(KEY_DICTIONARY, "");
        streamMode = prefs.getBoolean(KEY_STREAM, false);
        loadHistory();
        audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
        VfTheme.applyWindow(this);
        Typeface font = VfTheme.typeface(this);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackground(VfTheme.background(this));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = VfTheme.dp(this, 18);
        int baseBottom = VfTheme.dp(this, 32);
        root.setPadding(pad, VfTheme.dp(this, 10), pad, baseBottom);
        final int baseLeft = pad;
        final int baseTop = VfTheme.dp(this, 10);
        final int baseRight = pad;
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(
                    baseLeft,
                    baseTop + insets.getSystemWindowInsetTop(),
                    baseRight,
                    baseBottom + insets.getSystemWindowInsetBottom());
            return insets;
        });
        scroll.addView(root, new ScrollView.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // Header gọn: nhận diện thương hiệu + truy cập model.
        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        ImageView icon = new ImageView(this);
        icon.setImageResource(R.mipmap.ic_launcher);
        LinearLayout.LayoutParams iconParams = new LinearLayout.LayoutParams(
                VfTheme.dp(this, 46), VfTheme.dp(this, 46));
        iconParams.rightMargin = VfTheme.dp(this, 12);
        header.addView(icon, iconParams);

        LinearLayout titleBlock = new LinearLayout(this);
        titleBlock.setOrientation(LinearLayout.VERTICAL);
        TextView title = new TextView(this);
        title.setText("ViFastTts");
        VfTheme.text(title, font, 26, VfTheme.INK, true);
        titleBlock.addView(title);
        subtitle = new TextView(this);
        VfTheme.text(subtitle, font, 12, VfTheme.MUTED, false);
        titleBlock.addView(subtitle);
        header.addView(titleBlock, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        modelButton = new Button(this);
        modelButton.setText("Model");
        VfTheme.chipButton(modelButton, font);
        modelButton.setOnClickListener(view -> showModelManager());
        header.addView(modelButton, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(header, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout modelRow = new LinearLayout(this);
        modelRow.setOrientation(LinearLayout.HORIZONTAL);
        modelRow.setGravity(Gravity.CENTER_VERTICAL);
        modelLabel = new TextView(this);
        VfTheme.text(modelLabel, font, 12, VfTheme.MUTED, false);
        modelLabel.setPadding(0, VfTheme.dp(this, 6), 0, 0);
        modelLabel.setOnClickListener(view -> showModelManager());
        modelRow.addView(modelLabel, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        settingsSummary = new TextView(this);
        VfTheme.text(settingsSummary, font, 11, VfTheme.MUTED, false);
        settingsSummary.setGravity(Gravity.END);
        modelRow.addView(settingsSummary, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(modelRow, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // Card chế độ: segmented + cấu hình remote cùng một khối.
        LinearLayout modeCard = new LinearLayout(this);
        modeCard.setOrientation(LinearLayout.VERTICAL);
        VfTheme.card(modeCard);
        TextView modeTitle = new TextView(this);
        modeTitle.setText("Chế độ đọc");
        VfTheme.text(modeTitle, font, 12, VfTheme.MUTED, true);
        modeCard.addView(modeTitle);

        LinearLayout segments = new LinearLayout(this);
        segments.setOrientation(LinearLayout.HORIZONTAL);
        segments.setBackground(VfTheme.rounded(this, VfTheme.SOFT, VfTheme.BORDER, 12, 1));
        int segmentPad = VfTheme.dp(this, 4);
        segments.setPadding(segmentPad, segmentPad, segmentPad, segmentPad);
        localTab = new Button(this);
        localTab.setText("Local");
        localTab.setOnClickListener(view -> setMode("local"));
        remoteTab = new Button(this);
        remoteTab.setText("Remote");
        remoteTab.setOnClickListener(view -> setMode("remote"));
        LinearLayout.LayoutParams tabParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        tabParams.leftMargin = VfTheme.dp(this, 2);
        tabParams.rightMargin = VfTheme.dp(this, 2);
        segments.addView(localTab, tabParams);
        segments.addView(remoteTab, tabParams);
        LinearLayout.LayoutParams segmentParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        segmentParams.topMargin = VfTheme.dp(this, 8);
        modeCard.addView(segments, segmentParams);

        remoteFields = new LinearLayout(this);
        remoteFields.setOrientation(LinearLayout.VERTICAL);
        TextView serverLabel = new TextView(this);
        serverLabel.setText("Server URL");
        VfTheme.text(serverLabel, font, 11, VfTheme.MUTED, false);
        remoteFields.addView(serverLabel);
        serverUrl = new EditText(this);
        serverUrl.setHint("http://192.168.1.100:8000");
        serverUrl.setSingleLine(true);
        serverUrl.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        VfTheme.input(serverUrl, font);
        remoteFields.addView(serverUrl, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView tokenLabel = new TextView(this);
        tokenLabel.setText("Bearer token (tuỳ chọn)");
        VfTheme.text(tokenLabel, font, 11, VfTheme.MUTED, false);
        LinearLayout.LayoutParams tokenLabelParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tokenLabelParams.topMargin = VfTheme.dp(this, 8);
        remoteFields.addView(tokenLabel, tokenLabelParams);
        token = new EditText(this);
        token.setHint("Token nếu server yêu cầu");
        token.setSingleLine(true);
        token.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        VfTheme.input(token, font);
        remoteFields.addView(token, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        Button testServer = new Button(this);
        testServer.setText("Kiểm tra server");
        VfTheme.secondaryButton(testServer, font);
        testServer.setOnClickListener(view -> checkServer());
        LinearLayout.LayoutParams testParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        testParams.topMargin = VfTheme.dp(this, 8);
        remoteFields.addView(testServer, testParams);
        LinearLayout.LayoutParams remoteParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        remoteParams.topMargin = VfTheme.dp(this, 10);
        modeCard.addView(remoteFields, remoteParams);
        LinearLayout.LayoutParams modeParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        modeParams.topMargin = VfTheme.dp(this, 14);
        root.addView(modeCard, modeParams);

        // Card nhập liệu: trọng tâm màn hình.
        LinearLayout textCard = new LinearLayout(this);
        textCard.setOrientation(LinearLayout.VERTICAL);
        VfTheme.card(textCard);
        LinearLayout textHead = new LinearLayout(this);
        textHead.setOrientation(LinearLayout.HORIZONTAL);
        textHead.setGravity(Gravity.CENTER_VERTICAL);
        TextView textTitle = new TextView(this);
        textTitle.setText("Câu cần đọc");
        VfTheme.text(textTitle, font, 15, VfTheme.INK, true);
        textHead.addView(textTitle, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        charCountLabel = new TextView(this);
        VfTheme.text(charCountLabel, font, 11, VfTheme.MUTED, false);
        textHead.addView(charCountLabel);
        TextView clearText = new TextView(this);
        clearText.setText("Xoá");
        VfTheme.text(clearText, font, 12, VfTheme.ACCENT_DARK, true);
        clearText.setPadding(VfTheme.dp(this, 12), VfTheme.dp(this, 4),
                VfTheme.dp(this, 2), VfTheme.dp(this, 4));
        clearText.setOnClickListener(view -> text.setText(""));
        textHead.addView(clearText);
        textCard.addView(textHead);

        text = new EditText(this);
        text.setText("Xin chào các bạn, đây là bản Android của ViFastTts.");
        text.setHint("Nhập hoặc dán câu tiếng Việt…");
        VfTheme.text(text, font, 15, VfTheme.INK, false);
        text.setBackgroundColor(Color.TRANSPARENT);
        text.setGravity(Gravity.TOP | Gravity.START);
        text.setMinLines(6);
        text.setLineSpacing(VfTheme.dp(this, 2), 1f);
        text.setInputType(InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE
                | InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        LinearLayout.LayoutParams editorParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, VfTheme.dp(this, 170));
        editorParams.topMargin = VfTheme.dp(this, 6);
        textCard.addView(text, editorParams);
        text.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                if (charCountLabel != null) {
                    charCountLabel.setText(s.length() + " ký tự");
                }
            }
            @Override public void afterTextChanged(Editable s) {}
        });
        charCountLabel.setText(text.length() + " ký tự");

        LinearLayout samples = new LinearLayout(this);
        samples.setOrientation(LinearLayout.HORIZONTAL);
        samples.setGravity(Gravity.CENTER_VERTICAL);
        TextView sampleLabel = new TextView(this);
        sampleLabel.setText("Mẫu");
        VfTheme.text(sampleLabel, font, 11, VfTheme.MUTED, false);
        samples.addView(sampleLabel);
        for (String[] sample : new String[][]{
                {"Chào", "Xin chào các bạn, hôm nay trời đẹp."},
                {"Android", "Xin chào các bạn, đây là bản Android của ViFastTts."},
                {"iOS", "Xin chào, đây là bản iOS của ViFastTts."},
        }) {
            Button chip = new Button(this);
            chip.setText(sample[0]);
            VfTheme.chipButton(chip, font);
            chip.setOnClickListener(view -> text.setText(sample[1]));
            LinearLayout.LayoutParams chipParams = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            chipParams.leftMargin = VfTheme.dp(this, 6);
            samples.addView(chip, chipParams);
        }
        LinearLayout.LayoutParams samplesParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        samplesParams.topMargin = VfTheme.dp(this, 6);
        textCard.addView(samples, samplesParams);

        streamQuick = new CheckBox(this);
        streamQuick.setText("Stream khi đọc (phát ngay, không lưu WAV)");
        streamQuick.setChecked(streamMode);
        VfTheme.text(streamQuick, font, 12, VfTheme.MUTED, false);
        streamQuick.setButtonTintList(android.content.res.ColorStateList.valueOf(VfTheme.ACCENT));
        streamQuick.setOnCheckedChangeListener((button, checked) -> {
            streamMode = checked;
            prefs.edit().putBoolean(KEY_STREAM, streamMode).apply();
            updateSettingsSummary();
        });
        LinearLayout.LayoutParams streamQuickParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        streamQuickParams.topMargin = VfTheme.dp(this, 6);
        textCard.addView(streamQuick, streamQuickParams);
        LinearLayout.LayoutParams textCardParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        textCardParams.topMargin = VfTheme.dp(this, 14);
        root.addView(textCard, textCardParams);

        // Hành động chính: một nút Đọc lớn, Dừng và Cấu hình ngang hàng.
        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        runButton = new Button(this);
        runButton.setText("Đọc");
        VfTheme.primaryButton(runButton, font);
        runButton.setOnClickListener(view -> synthesize());
        actions.addView(runButton, new LinearLayout.LayoutParams(
                0, VfTheme.dp(this, 52), 1f));

        stopButton = new Button(this);
        stopButton.setText("Dừng");
        VfTheme.secondaryButton(stopButton, font);
        stopButton.setEnabled(false);
        stopButton.setOnClickListener(view -> stopPlayback());
        LinearLayout.LayoutParams stopParams = new LinearLayout.LayoutParams(
                VfTheme.dp(this, 82), VfTheme.dp(this, 52));
        stopParams.leftMargin = VfTheme.dp(this, 8);
        actions.addView(stopButton, stopParams);

        settingsButton = new Button(this);
        settingsButton.setText("Cấu hình");
        VfTheme.secondaryButton(settingsButton, font);
        settingsButton.setOnClickListener(view -> showSettings());
        LinearLayout.LayoutParams settingsParams = new LinearLayout.LayoutParams(
                VfTheme.dp(this, 102), VfTheme.dp(this, 52));
        settingsParams.leftMargin = VfTheme.dp(this, 8);
        actions.addView(settingsButton, settingsParams);
        LinearLayout.LayoutParams actionParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        actionParams.topMargin = VfTheme.dp(this, 14);
        root.addView(actions, actionParams);

        // Card phát: trạng thái, karaoke và lưu file.
        LinearLayout playbackCard = new LinearLayout(this);
        playbackCard.setOrientation(LinearLayout.VERTICAL);
        VfTheme.card(playbackCard);
        LinearLayout statusRow = new LinearLayout(this);
        statusRow.setOrientation(LinearLayout.HORIZONTAL);
        statusRow.setGravity(Gravity.CENTER_VERTICAL);
        View statusDot = new View(this);
        statusDot.setBackground(VfTheme.dot(this, VfTheme.SUCCESS));
        LinearLayout.LayoutParams dotParams = new LinearLayout.LayoutParams(
                VfTheme.dp(this, 8), VfTheme.dp(this, 8));
        dotParams.rightMargin = VfTheme.dp(this, 8);
        statusRow.addView(statusDot, dotParams);
        status = new TextView(this);
        status.setText("Sẵn sàng");
        VfTheme.text(status, font, 14, VfTheme.INK, false);
        statusRow.addView(status, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        progress = new ProgressBar(this);
        progress.setIndeterminate(true);
        progress.setVisibility(View.GONE);
        statusRow.addView(progress, new LinearLayout.LayoutParams(
                VfTheme.dp(this, 22), VfTheme.dp(this, 22)));
        playbackCard.addView(statusRow);

        karaokeView = new TextView(this);
        VfTheme.text(karaokeView, font, 24, VfTheme.ACCENT, true);
        karaokeView.setGravity(Gravity.CENTER);
        karaokeView.setPadding(0, VfTheme.dp(this, 10), 0, VfTheme.dp(this, 6));
        karaokeView.setMinHeight(VfTheme.dp(this, 38));
        karaokeView.setVisibility(View.GONE);
        playbackCard.addView(karaokeView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        errorLabel = new TextView(this);
        VfTheme.text(errorLabel, font, 13, VfTheme.ERROR, false);
        errorLabel.setVisibility(View.GONE);
        playbackCard.addView(errorLabel, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        saveButton = new Button(this);
        saveButton.setText("Lưu WAV + phụ đề");
        VfTheme.secondaryButton(saveButton, font);
        saveButton.setEnabled(false);
        saveButton.setOnClickListener(view -> saveWav());
        LinearLayout.LayoutParams saveParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        saveParams.topMargin = VfTheme.dp(this, 10);
        playbackCard.addView(saveButton, saveParams);

        LinearLayout exportRow = new LinearLayout(this);
        exportRow.setOrientation(LinearLayout.HORIZONTAL);
        shareButton = new Button(this);
        shareButton.setText("Chia sẻ WAV");
        VfTheme.secondaryButton(shareButton, font);
        shareButton.setEnabled(false);
        shareButton.setOnClickListener(view -> shareWav());
        exportRow.addView(shareButton, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        historyButton = new Button(this);
        historyButton.setText("Lịch sử");
        VfTheme.secondaryButton(historyButton, font);
        historyButton.setOnClickListener(view -> showHistory());
        LinearLayout.LayoutParams historyParams = new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        historyParams.leftMargin = VfTheme.dp(this, 8);
        exportRow.addView(historyButton, historyParams);
        LinearLayout.LayoutParams exportParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        exportParams.topMargin = VfTheme.dp(this, 8);
        playbackCard.addView(exportRow, exportParams);
        LinearLayout.LayoutParams playbackParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        playbackParams.topMargin = VfTheme.dp(this, 12);
        root.addView(playbackCard, playbackParams);

        hintLabel = new TextView(this);
        VfTheme.text(hintLabel, font, 12, VfTheme.MUTED, false);
        hintLabel.setLineSpacing(VfTheme.dp(this, 2), 1f);
        LinearLayout.LayoutParams hintParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        hintParams.topMargin = VfTheme.dp(this, 10);
        root.addView(hintLabel, hintParams);

        String savedServer = prefs.getString(KEY_SERVER, "");
        if (savedServer.startsWith("http://127.0.0.1") || savedServer.startsWith("http://localhost")) {
            savedServer = "";
        }
        serverUrl.setText(savedServer);
        token.setText(prefs.getString(KEY_TOKEN, ""));
        updateModelLabel();
        updateSettingsSummary();
        setMode(mode);

        setContentView(scroll);
        root.requestApplyInsets();
        requestLocalNetworkPermission();
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (serverUrl != null) {
            prefs.edit()
                    .putString(KEY_SERVER, serverUrl.getText().toString().trim())
                    .putString(KEY_TOKEN, token.getText().toString().trim())
                    .apply();
        }
    }

    @Override
    protected void onDestroy() {
        if (player != null) player.release();
        abandonAudioFocus();
        if (engine != null && ffi != null) ffi.vifasttts_engine_free(engine);
        super.onDestroy();
    }
}
