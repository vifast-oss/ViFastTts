# Rà soát tái sử dụng UI & logic — 29/10/2026

> Mục đích: tìm phần **có thể dùng chung** giữa desktop, TUI, CLI, server, web,
> extension, Android, iOS và Python demo; tách khỏi UI để lần sau thêm tính năng
> không phải sửa 6–8 nơi.
>
> Trạng thái: **audit + phase 1**. Phase 1 đã tách hợp đồng settings/ETA/từ điển/
> sample text vào `vifasttts-app`, expose qua FFI/WASM; Android đã dùng lại ETA,
> từ điển và sample thay vì tự tính/khai báo.

## 0. Kết luận ngắn

- **Lõi TTS đã dùng chung rất tốt**: text pipeline, engine, karaoke, WAV, SRT/VTT,
  từ điển, ETA, model manager đều nằm trong Rust.
- **Phần chưa dùng chung không phải là "logic TTS"**, mà là **hợp đồng UI**:
  defaults/settings, catalog model, DTO HTTP, history/ETA storage, sample text,
  stream→WAV, render karaoke, model browser state.
- Các bản Android/iOS/web/extension đang **viết lại cùng một luật ở ngôn ngữ khác
  nhau**. Đây là lý do một tính năng có ở desktop nhưng thiếu ở Android, hoặc
  default lệch nhau.
- **Không nên** cố share widget, audio device, file picker, share sheet, permission.
  Nên share **schema + state machine + format + thuật toán**; UI chỉ còn hiển thị.

## 1. Bản đồ tầng hiện tại

```text
core/domain/text        chuẩn hoá, âm tiết, từ điển, chunk, karaoke, SRT/VTT
core/domain/audio       WAV, DSP
core/domain/vfts        bundle .vfa/.vfts
core/application/engine synth + stream
core/application/app    settings, history/ETA, dictionary, session
core/application/model-manager  search/files/install/installed
ports/adapters          ORT, HF, HTTP, audio sink, settings store
inbound/native|ffi|http|browser|desktop|tui|cli
UI native               egui, ratatui, DOM, Android View, SwiftUI
```

Điểm quan trọng: `vifasttts-app` đã tồn tại từ trước, nhưng **chỉ desktop và một
phần WASM dùng**. Android/iOS/web/extension vẫn tự viết lại các luật của nó.

## 2. Đã dùng chung — giữ nguyên, không tách lại

| Logic | Nguồn chuẩn | Đang dùng ở |
|---|---|---|
| Chuẩn hoá text, phương ngữ, OOV, pronunciation | `rust/crates/core/domain/text` | tất cả |
| Chunking / max ký tự | `vifasttts-text::chunking` | Rust, WASM, HTTP, FFI |
| Synth + stream | `vifasttts-engine` | native, ORT Web, HTTP, FFI |
| Karaoke + SRT/VTT | `text/src/karaoke.rs` | Rust, FFI, WASM, HTTP |
| WAV | `domain/audio::wav_bytes` | Rust, WASM, HTTP, FFI |
| Parser từ điển `key = cách đọc` | `vifasttts-app::dictionary` | FFI, HTTP, WASM, desktop |
| ETA median | `vifasttts-app::history` | desktop, WASM, **Android (mới)** |
| Model catalog/download | `vifasttts-model-manager` + `vifasttts-huggingface` | desktop, TUI, CLI, server |
| API model client JS | `web/shared/model-api.js` | web; extension copy qua build |
| Bundle `.vfa/.vfts` | `vifasttts-vfts` | Rust, WASM, FFI |

## 3. Trùng lặp thực tế & mức ưu tiên

| # | Logic | Các bản đang có | Vấn đề | Đích tách | Ưu tiên |
|---|---|---|---|---|---|
| 1 | Settings/defaults | `AppSettings`; `DesktopSettings`; TUI args; `DEFAULTS` extension; Android keys; iOS `@AppStorage`; web HTML | `max_chars` 0 vs 300; `resolve_oov` false/true; server URL localhost/empty; default mỗi nơi một kiểu | `vifasttts-app::contracts::SynthesisSettings` + JSON defaults/validate | **P0** |
| 2 | History/ETA | Rust `EtaSample`/`EtaEstimator`; desktop; extension; Android; iOS không có; web không có | Android từng tự median; schema history khác nhau; iOS thiếu tính năng | `EtaSample` + `EtaEstimator` (đã có), FFI/WASM JSON | **P0** |
| 3 | Sample/default text | Android hard-code; iOS hard-code; desktop hard-code; TUI; web textarea; CLI | Android/iOS default dễ lệch; thêm sample phải sửa từng UI | `contracts::SampleText` + `sample_texts_json(platform)` | **P1** |
| 4 | Model catalog | `model-manager`; desktop `model_browser.rs`; TUI `ModelPane`; CLI actions; server routes; JS `ModelApi`; iOS `ModelCatalogClient`; Android URL builders | 3–4 cách build URL HF; dedupe bundle khác; lỗi/progress khác; iOS/Android tự viết HTTP | Rust model API qua FFI/WASM, hoặc server contract + generated client | **P0** |
| 5 | DTO `/api/tts` | Rust `HttpTtsRequest`; iOS `RemoteTts`; Android `JSONObject`; web fetch; extension offscreen | field name/default lệch; response JSON/WAV fallback mỗi nơi | JSON schema/OpenAPI + generated DTO; `api_contract_json` làm mốc | **P1** |
| 6 | Karaoke render | web/extension span + timeupdate; Android Handler; iOS TimelineView; desktop lines | 4 thuật toán active unit; timing lệch | `KaraokeDocument` + helper `unit_at(ms)`/format (Rust), UI chỉ bind | **P2** |
| 7 | Stream → WAV | Android tự gom PCM + tự viết header; extension WebAudio; CLI/TUI gom; web chưa stream | chỉ Android có WAV stream; header/format tự viết; tail/drain khác | `StreamSession`/`WavWriter` trong Rust, FFI `stream_*`; audio sink native | **P1** |
| 8 | Model browser state | desktop `ModelBrowser`; TUI `ModelPane`; CLI subcommand | cùng query/results/files/status, 3 state machine | `ModelBrowserState` trong `model-manager` (không UI) | **P2** |
| 9 | Settings storage | desktop JSON; TUI args; web localStorage; extension chrome.storage; Android SharedPreferences; iOS UserDefaults | key/version/format khác; migrate khó | Giữ storage native, share **schema + key/version + normalize** | **P1** |
| 10 | Output naming/export | Android MediaStore; iOS temp URL; desktop rfd; web Blob; extension download | tên/định dạng lệch; khó test | Shared `export_name(mode, ext, timestamp)` + `PcmWav`; file I/O native | **P3** |
| 11 | WAV header PCM16 | Android `writeWavFile`; Rust `wav_bytes`; các nơi khác dùng Rust | nguy cơ header sai khi thêm channel/rate | `vifasttts-audio::wav_bytes_pcm16`, FFI | **P3** |
| 12 | Audio resample/drain | Android `resamplePcm`/`waitForPlayback`; iOS AVAudioPlayer; browser AudioContext | không thể share audio device; nhưng policy nên thống nhất | Không share code; ghi thành policy/test | — |
| 13 | UI strings/status | mỗi UI tiếng Việt riêng | khó đồng bộ wording/error | String catalog JSON (chỉ khi cần i18n) | **P4** |
| 14 | Theme tokens | `design/tokens.json`; `web/shared/theme.css`; `VfTheme.java`; iOS `Theme.swift` | màu/spacing lặp, lệch | Generate CSS/Java/Swift từ token | **P4** |
| 15 | Python demo | `deploy/vifasttts_demo/app.py` + static | stack Python riêng, không link Rust | Chỉ share HTTP contract; không gộp code | — |

### 3.1. Vì sao các default đang lệch

Ví dụ đang thấy trong code:

- `AppSettings::default()` (sau phase 1): `max_chars = 300`, `resolve_oov = true`,
  có `dialect`/`peak_normalize`/`custom_reading`; nhưng desktop vẫn dùng các field
  riêng `DesktopSettings.dialect/peak_normalize/resolve_oov` nên chưa nối hết.
- `DesktopSettings`: `max_chars = 300`, `resolve_oov = false`, `auto_play = true`.
- TUI: `max_chars = 300`, `resolve_oov = true`; CLI `synth`: `resolve_oov = false`;
  `tui` subcommand: `resolve_oov = true`.
- Android/iOS/extension/web: `max_chars = 300`, `resolve_oov = true`; Android/iOS
  server URL mặc định rỗng, extension mặc định `127.0.0.1:8000`.

Cùng một câu có thể cho hành vi OOV/độ dài khác nhau tuỳ UI. Đây là lỗi thiết kế
hợp đồng, không phải lỗi model.

### 3.2. Vì sao model catalog bị lặp

- Rust `huggingface::bundle_files` dùng tree API + dedupe `(name,size)`.
- Web `ModelApi.files` direct dùng `siblings`, không có size; extension copy.
- iOS `ModelCatalogClient` direct dùng `/tree/main` nhưng filter và decode riêng.
- Android tự ghép URL `api/models`, `tree/main`, `resolve/main` và tự lọc file.
- Desktop/TUI/CLI dùng `ModelManager` nhưng state machine khác nhau.

Chỉ cần một thay đổi API HF là 4–5 nơi phải sửa. Đây là ứng viên tách lớn nhất sau
settings.

## 4. Phase 1 đã làm

### 4.1. Hợp đồng mới trong Rust

File `rust/crates/core/application/app/src/contracts.rs`:

- `SynthesisSettings` = alias của `AppSettings`: mode, speed, alpha, max_chars,
  fixed_pauses, peak_normalize, dialect, resolve_oov, dictionary, custom_reading,
  stream, server_url, token, model_base_url. Không tạo schema settings thứ hai.
- `defaults()` canonical: speed 1.0 · alpha 1.5 · max 300 · resolve OOV bật ·
  dialect Bắc.
- `normalized()`: kẹp speed/alpha/max, chuẩn hoá dialect/server URL, bỏ custom
  reading rỗng.
- `validate()`: lỗi rõ thay vì âm thầm dùng giá trị sai.
- `sample_texts(platform)` và `default_text(platform)`: Android có "Android",
  iOS có "iOS".
- `eta_estimate_json`: dùng đúng `EtaEstimator`, bỏ qua field history chỉ để UI.
- `dictionary_json`: rules/warnings/overrides.
- `api_contract_json`: version + path `/api/tts`, `/healthz`, `/api/models/*`.

### 4.2. FFI/WASM

FFI mới (giữ ABI cũ, chỉ thêm hàm):

```c
char *vifasttts_settings_defaults_json(void);
char *vifasttts_settings_normalize_json(const char *json);
char *vifasttts_sample_texts_json(const char *platform);
char *vifasttts_eta_estimate_json(const char *history_json, const char *mode,
                                  uint32_t chars, uint32_t max_samples);
char *vifasttts_dictionary_json(const char *dictionary);
char *vifasttts_api_contract_json(void);
```

Tất cả trả JSON UTF-8; giải phóng bằng `vifasttts_string_free`; lỗi qua
`vifasttts_last_error`. WASM có các hàm tương ứng để web/extension dùng sau.

### 4.3. Android đã dùng lại

- `estimateMs()` không còn tự sort/median; gửi history tối thiểu sang Rust.
- `dictionarySummary()` dùng parser Rust (đếm rule/warning đúng, bỏ comment/dòng trống).
- Sample chip + text mặc định lấy từ `vifasttts_sample_texts_json("android")`;
  fallback tiếng Việt chỉ dùng khi FFI chưa nạp.
- Đã build APK và kiểm tra màn hình: text mặc định vẫn có "Android"; ETA hiển thị
  (`ước tính ~4.6s`); không crash JNA.

### 4.4. Chưa nối (phase 2)

- iOS/web/extension chưa gọi defaults/sample/ETA contract mới.
- Android vẫn còn settings keys/defaults riêng; phase 2 mới đọc
  `settings_defaults_json` và normalize trước khi lưu.
- Model catalog/DTO/stream WAV chưa tách.

## 5. Thiết kế đích

### 5.1. Ranh giới

```text
Rust contracts/app  ── JSON/FFI/WASM ──►  UI native
- settings schema/defaults/validate      - widget/layout/theme
- sample text                            - file picker/share sheet
- history/ETA                            - audio device/audio focus
- dictionary parse                       - permission/lifecycle
- karaoke/SRT/VTT/WAV                    - storage backend
- model catalog operations               - store metadata
- API DTO/version                        - app icon/notification
```

### 5.2. API đề xuất cho phase sau

```text
vifasttts_settings_defaults_json()          # đã có
vifasttts_settings_normalize_json(json)     # đã có
vifasttts_sample_texts_json(platform)       # đã có
vifasttts_eta_estimate_json(...)            # đã có
vifasttts_dictionary_json(text)             # đã có
vifasttts_api_contract_json()               # đã có

# phase 2
vifasttts_models_search_json(query, limit)
vifasttts_models_files_json(repo)
vifasttts_models_download_to(repo, path, directory)
vifasttts_models_installed_json(directory)

# phase 3
vifasttts_stream_open(...) / push(...) / finish_wav(...)
vifasttts_karaoke_unit_at(json, ms)
vifasttts_wav_from_pcm16(pcm, rate, channels)

# phase 4
vifasttts_synthesize_karaoke_ex2(..., custom_reading_json, ...)
```

Không đổi signature cũ; chỉ thêm hàm/field có default để client cũ vẫn chạy.

Hợp đồng HTTP nên có JSON schema/OpenAPI:

```json
{
  "text": "...",
  "speed": 1.0,
  "alpha": 1.5,
  "max_chars": 300,
  "fixed_pauses": false,
  "peak_normalize": false,
  "dialect": "north",
  "resolve_oov": true,
  "dictionary": "AI = ây ai",
  "custom_reading": {"TP.HCM": "thành phố hồ chí minh"},
  "karaoke": true
}
```

## 6. Kế hoạch theo phase

| Phase | Việc | Cổng kiểm |
|---|---|---|
| **1 (xong)** | `contracts.rs`, FFI/WASM JSON, Android ETA/dictionary/sample | `cargo test -p vifasttts-app -p vifasttts-ffi -p vifasttts-browser`; Android build + màn hình |
| **2** | iOS/web/extension đọc defaults/sample; Android đọc defaults; thống nhất `resolve_oov`/`max_chars` | test contract; so screenshot/behavior 3 UI; không đổi audio |
| **3** | Model catalog qua Rust/FFI; bỏ URL builder Java/Swift; JS dùng chung `ModelApi` | search/files/download trên HF thật; lỗi mạng; hash bundle |
| **4** | `StreamSession` + WAV writer; Android/iOS/CLI/TUI dùng; stream SRT nếu có timing | test file WAV header/duration; tail drain; so full vs stream |
| **5** | JS `ui-core` (settings/history/model browser/karaoke); desktop/TUI `ModelBrowserState` | web/extension parity; TUI/desktop model flow |
| **6** | FFI `custom_reading`; generated DTO/schema; string/theme tokens | Android/iOS custom reading; OpenAPI diff |

### Điều kiện dừng/ba nhánh cho mỗi phase

- **Đạt** (test + build + đo parity) ⇒ commit + sang phase sau.
- **Trượt test/build** ⇒ dừng, không commit; báo log.
- **Kết quả lạ** (audio/quality khác dù options giống) ⇒ dừng, so với mốc cũ
  (full/stream, model bundled/downloaded) trước khi kết luận.

## 7. Không nên tách

- Widget/layout/theme: egui, ratatui, DOM, Android View, SwiftUI khác nhau; cố
  abstract sẽ tạo "UI framework tự chế" khó bảo trì.
- Audio playback/recording: AudioTrack, AVAudioPlayer, WebAudio, rodio.
- File picker/Downloads/share sheet/permission/notification.
- Storage backend: SharedPreferences, UserDefaults, localStorage, chrome.storage,
  file JSON.
- App lifecycle/background/foreground, store packaging/icon.

Chỉ nên share **dữ liệu vào/ra** của các phần này.

## 8. Rủi ro & lưu ý

1. **ABI FFI**: chỉ thêm hàm; không đổi `VifasttOptions`/hàm cũ. Header iOS/Android
   phải rebuild cùng lúc.
2. **JNA**: `uint32_t` dùng `int`; `size_t` dùng `NativeLong`; JSON trả `char*`
   phải free bằng `vifasttts_string_free`.
3. **Serde**: history cũ có field lạ (`audio_seconds`, `at`, `text`) vẫn parse
   được; field thiếu phải có default nếu schema đổi.
4. **Default thay đổi**: phase 2 phải migrate settings cũ, không reset im lặng.
5. **Python demo**: đang có thay đổi chưa commit của người dùng; không gộp vào
   refactor Rust. Chỉ đối chiếu HTTP contract.
6. **Đo trước/sau**: mọi thay đổi audio/stream phải so full vs stream, bundled vs
   downloaded, và kiểm file WAV thật.

## 9. Checklist rà soát UI

| UI | File chính | Logic riêng đáng chú ý | Đề xuất |
|---|---|---|---|
| Desktop egui | `rust/.../desktop/src/main.rs`, `model_browser.rs` | settings/history/model browser/audio | dùng contracts + `ModelBrowserState` |
| TUI | `rust/.../tui/src/lib.rs` | settings args, model pane, progress | dùng contracts + model state |
| CLI | `rust/.../cli/src/main.rs` | flags, export, model commands | dùng `SynthesisSettings` builder |
| Server | `rust/.../http-server/src/lib.rs` | DTO, health, model routes | schema/OpenAPI |
| Web Vite | `web/app.js`, `web/shared/*` | local WASM/remote, model, karaoke | `ui-core` + WASM contract |
| Extension | `extension/popup.js`, `offscreen.js`, `shared/*` | stream WebAudio, history, model cache | `ui-core` + Rust contract |
| Android | `MainActivity.java`, `VfTheme.java` | View UI, AudioTrack, MediaStore, model | FFI contract; giữ UI/audio |
| iOS | `ContentView.swift`, `TtsEngine.swift`, `RemoteTts.swift`, `ModelCatalog.swift` | SwiftUI, AVAudioPlayer, URLSession | FFI contract; giữ UI/audio |
| Python demo | `deploy/vifasttts_demo/app.py` + static | custom reading/server | chỉ share HTTP contract |

## 10. Kết quả phase 1 — lệnh kiểm

```bash
cd rust
cargo test -p vifasttts-app -p vifasttts-ffi -p vifasttts-browser
cargo build --release -p vifasttts-browser --target wasm32-unknown-unknown

JAVA_HOME="$(/usr/libexec/java_home -v 21)" ./mobile/android/build.sh
```

Kỳ vọng:

- 8 test `vifasttts-app` pass (gồm 4 test contracts).
- FFI/WASM compile; Android build thành công.
- Màn hình Android: text mặc định `... bản Android ...`, chip `Chào/Android/iOS`,
  ETA xuất hiện ở lần đọc thứ hai.
