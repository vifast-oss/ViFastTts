# Port Rust — kế hoạch + trạng thái triển khai

> **Trạng thái:** KẾ HOẠCH + TRIỂN KHAI WIP — **đã có mã Rust** (workspace
> `rust/`, 25 crate, ~11.6k dòng Rust, chưa đổi production).
> Xem **§15** cho trạng thái thực tế và lộ trình đa nền tảng.
> **Ngày:** 29/10/2026 (cập nhật trạng thái triển khai).
> **Phạm vi:** đường **inference production** của ViFastTts.
> **Không thay thế** `docs/handoff/TRANG_THAI.md` (nguồn trạng thái duy nhất).

Tài liệu này thay cho roadmap cũ trong `docs/archive/design/RUST_ROADMAP.md`
(bản cũ chỉ là danh sách mong muốn, không có hợp đồng, thứ tự thi công, cổng đo
hay phương án cắt Python). Đọc mục 0 trước; các mục sau là chi tiết để thi công.

---

## 0. Kết luận trước (ngắn)

1. **Nên port Rust phần inference**, nhưng **không port toàn bộ repo**.
   - Port: frontend parse/normalize → 7 ID, ONNX acoustic + vocoder, iSTFT,
     postprocess, WAV, CLI/API tối thiểu.
   - Giữ Python: train, data, export ONNX, đánh giá, G2P/IPA, lexicon/QA,
     admin/thống kê (giai đoạn đầu).
2. **Thứ tự đúng:** hợp đồng + golden corpus → Rust runtime → Rust frontend →
   end-to-end → tích hợp → cutover. **Không** bắt đầu bằng server/web.
3. **PyO3 không phải đích cuối.** PyO3 chỉ là cầu nối để đưa Rust vào FastAPI
   hiện tại; nếu dùng PyO3 trước khi port frontend thì chỉ là hybrid
   Python-frontend/Rust-runtime, không phải port đầy đủ.
4. **Lợi ích chính không phải RTF.** Cả hai đều dùng ONNX Runtime; model chiếm
   phần lớn thời gian. Rust đem lại: một binary độc lập, không cần Python/numpy
   khi chạy, khởi động/bộ nhớ tốt hơn, kiểm soát lỗi tốt hơn, nền cho WASM/edge.
   Nếu mục tiêu duy nhất là nhanh hơn, hãy tối ưu quantization/thread/model trước.
5. **Ước lượng 1 dev full-time:** khoảng **10–15 tuần** cho inference + PyO3,
   **12–18 tuần** nếu thay luôn web service bằng Rust; cộng 20–30% đệm.
   Port train/data/export là dự án khác (nhiều tháng), không nên làm.
6. **Điều kiện tiên quyết:** xác nhận crate `ort` dùng được ORT tương thích
   (live **1.31.1**; Rust dùng `load-dynamic` với đúng **1.31.1**); nếu không, phải chọn
   phiên bản ORT khác và đo lại parity trước khi viết frontend.
7. **Cập nhật 28/10/2026:** mã Rust đã có (text/audio/ports + engine/native + CLI) và đã chạy
   parity frontend; kế hoạch dưới đây giữ nguyên làm chuẩn, nhưng thứ tự tích hợp
   và phạm vi nền tảng đã đổi — xem **§15**.

---

## 1. “Đầy đủ” nghĩa là gì

### 1.1 Trong phạm vi

| Lớp | Port? | Ghi chú |
|---|---|---|
| Unicode/NFC, tone, orthography | ✅ | Thuần logic, ít phụ thuộc |
| Syllable parser + rules | ✅ | Có golden 49.104 tổ hợp |
| Vocab 7 ID + `vocab_hash` | ✅ | Q ở cuối; hash là hợp đồng |
| Tokenizer/pipeline/punctuation | ✅ | `parse_text` tương đương |
| Custom reading + OOV/English/roman | ✅ | Dữ liệu phải đưa vào `resources/` |
| Normalizer số/ngày/giờ/tiền/email/STEM | ✅ | Phần khó nhất, nhiều regex/Unicode |
| Chunking + pause | ✅ | `chunk_text`, `split_clauses`, `pause_seconds` |
| Acoustic ONNX | ✅ | `ort`, CPU, `v2_slot5` |
| Vocoder ONNX + iSTFT | ✅ | `rustfft`/`realfft`, không numpy |
| Sharpen mel, fade, WAV | ✅ | Phải khớp PCM |
| CLI | ✅ | Batch/one-shot/stream |
| HTTP API tối thiểu | ✅ (khuyến nghị) | `/healthz`, `/api/config`, `/api/tts` |
| Web admin/thống kê/feedback | ⚠️ giai đoạn sau | Có thể giữ Python hoặc port sau |
| PyO3 | ⚠️ cầu nối | Chỉ dùng khi cần giữ FastAPI |
| WASM | ⏳ sau | Model 86 MB; v2 chưa có int8/fp16 export |

### 1.2 Ngoài phạm vi (và vì sao)

- **Train**: PyTorch/MPS, loss, adversarial, optimizer — hệ sinh thái Python,
  không có lợi ích khi viết lại.
- **Data pipeline**: manifest, MFA, cache, YouTube, split — không nằm trên đường
  inference; port sẽ kéo theo cả tá tool nghiên cứu.
- **Export ONNX**: `torch.onnx.export` + quantization; Rust không có exporter
  tương đương ổn định. Giữ Python, chỉ **đọc** artifact ONNX.
- **G2P/IPA, lexicon, segment expander, QA tool**: không dùng ở runtime
  (xem `docs/FRONTEND.md`; `g2p.py` không được import bởi pipeline).
- **Web admin/feedback/thống kê**: giá trị thấp so với công sức; giữ FastAPI
  hoặc port sau khi inference đã ổn định.

> Nếu “port đầy đủ” với bạn có nghĩa là **port cả train/data/export**, hãy tách
> thành dự án riêng. Ước lượng thô: 6–12 tháng, rủi ro cao, mất hệ sinh thái
> Torch/MFA, không giúp chất lượng model.

---

## 2. Baseline hiện tại (số thật, không suy diễn)

### 2.1 Đường chạy production

```text
HTTP /api/tts
  → sanitize text, max 3.000 ký tự
  → chunk_text(max 300) hoặc split_clauses(nếu fixed_pauses)
  → parse_text: custom reading → normalize → tokenize → parse → OOV
  → 7 ID [1,N,7] int64
  → acoustic ONNX (features, speed, gate_threshold)
  → mel [1,T,100]
  → sharpen_mel_numpy(alpha=1,5)
  → vocoder ONNX → spec_real/spec_imag [1,513,T]
  → iSTFT (n_fft=1024, hop=256, Hann, center=True)
  → ghép chunk + pause
  → fade 10 ms / 20 ms
  → WAV PCM16 mono 24 kHz
```

- Đường runtime Python (frontend + runtime + types) khoảng **2.474 dòng**,
  chưa kể 1.947 dòng test liên quan.
- Tổng repo Python khoảng 12.064 dòng; phần lớn là train/data/export không cần port.
- Test hiện tại (đo lại 28/10/2026): **2.936 pass / 24 skip**; parser audit **49.104 tổ hợp, 0 lỗi**.

### 2.2 Model và ONNX

| Thành phần | Giá trị |
|---|---|
| Acoustic | `artifacts/onnx/n0_q/acoustic.onnx`, 31.626.536 B, sha256 `df61599a…` |
| Vocoder | `artifacts/onnx/n0_q/vocoder.onnx`, 54.158.691 B, sha256 `b3eb09cf…` |
| Tổng model | ~86 MB |
| Opset | 18 |
| Arch | `v2_slot5` |
| Vocab | `vi-q25-v1`, hash `1a33a9622a13443f296ee3c1f6fe5190bd0d72845ec61a1756a3d10784f1785a` |
| ORT live | Python `onnxruntime 1.31.1` (VPS); Rust `load-dynamic` dùng **1.31.1** |
| Threads | production ghim `intra_op=2` để ổn định |

Acoustic:

```text
inputs:
  features      int64  [batch, syllables, 7]
  speed         float32[1]
  gate_threshold float32[1]

outputs (thứ tự cố định):
  mel, log_duration, durations, f0, vuv_logits, energy,
  phonation, tone_logits, lengths, slot_durations, pause_gate
```

Vocoder:

```text
input:  mel          float32 [batch, frames, 100]
output: spec_real    float32 [batch, 513, frames]
        spec_imag    float32 [batch, 513, frames]
metadata: sample_rate=24000, n_fft=1024, hop_length=256, upsample_ratio=1
```

### 2.3 Frontend data

| Nguồn | Số mục | Đang live? |
|---|---:|---|
| `ACRONYM_READINGS` | 94 | Có (trong code) |
| `CASE_INSENSITIVE_ENGLISH` | 758 | Có (trong code) |
| `EXACT_PRODUCT_NAMES` | 12 | Có (trong code) |
| `overrides_vi.json` | 229 | Có (deploy config) |
| `custom_reading.json` | 7 | **Không** — file local không có trong container |
| `duration_prior_v2.json` | 923 | Không dùng ở demo ONNX |

Điểm quan trọng: **không được tự ý đưa 7 custom reading vào Rust live** nếu muốn
khớp hành vi production hiện tại. Rust nên có profile:

- `live`: built-in overrides + approved (DB) + request overrides; custom reading
  mặc định rỗng.
- `full`: thêm `custom_reading.json` khi được cấu hình rõ.

### 2.4 Web hiện tại

- FastAPI, một model nạp sẵn, **một request tổng hợp đồng thời** (lock 45 s).
- `/api/tts`: max 3.000 ký tự, rate limit 6 request/phút/IP, speed kẹp 0,8–1,2.
- `fixed_pauses`: `gate_threshold=1.01`, tách mệnh đề, pause 0,25/0,55/0,08 s.
- Mặc định: `gate_threshold=0.5`, pause do model, alpha 1,5.
- Có `/api/overrides`, suggestion, feedback, admin, SQLite stats.
- RTF end-to-end từng ghi nhận **0,032–0,045** trên VPS (model + vocoder + iSTFT).

### 2.5 Toolchain Rust

Đã cài và ghim `rust-toolchain.toml` (**1.99.1**, rustfmt + clippy); workspace
`rust/` có **25 crate** (`text`, `audio`, `engine`, `app`, `ports`, `audio-sink`,
`transport`, `settings`, `model-source`, `vfts`, `huggingface`, `model-manager`, `ort`, `ort-web`, `http-client`,
`native`, `mobile`, `desktop`, `tui`, `browser`, `ffi`, `http-server`, `cli`, `parse`, `tools`).
CI hiện chạy green trên macOS/Ubuntu/Windows, build desktop/server/Android/iOS/web/extension;
chưa đo VPS/mobile thật.

---

## 3. Kiến trúc đích

```text
┌────────────────────────────────────────────────────────────┐
│  CLI (clap)        HTTP (axum)        FFI mobile/desktop   │
└───────────────┬───────────────┬───────────────┬────────────┘
                │               │               │
                └───────────────▼───────────────┘
                        vifasttts-native
                         (facade/wiring)
                                │
                        vifasttts-engine
                 (orchestration, streaming, options)
                    │                       │
        ┌───────────▼───────────┐   ┌───────▼────────────┐
        │ vifasttts-text        │   │ vifasttts-ports  │
        │ frontend, vocab,      │   │ traits/types        │
        │ chunk, karaoke text   │   │                    │
        └───────────┬───────────┘   └───────┬────────────┘
                    │                       │
        ┌───────────▼───────────┐   ┌───────▼────────────┐
        │ vifasttts-audio       │   │ vifasttts-ort      │
        │ iSTFT/WAV/DSP         │   │ ONNX sessions      │
        └───────────────────────┘   └────────────────────┘
```

### 3.1 Workspace

```text
rust/
  Cargo.toml                 # workspace, pinned toolchain
  rust-toolchain.toml
  crates/
    core/
      domain/
        text/                # types, unicode, syllable, vocab, normalizer,
                             # chunking, karaoke text
        audio/               # istft, sharpen, fade, wav
      application/
        engine/              # synthesis/stream application service
        app/                 # headless UI commands/events + ETA
      ports/
        backend/             # AcousticModel/VocoderModel + types
        audio-sink/          # PCM output contract
        transport/           # remote synthesis contract
        settings/            # storage contract
        model-source/        # model bytes contract
    adapters/
      outbound/
        ort/                 # ORT native adapter
        ort-web/             # ORT Web adapter
        http-client/         # HTTP client adapter
      inbound/
        native/              # native composition root
        mobile/              # iOS/Android composition root
        desktop/             # GUI desktop egui (local + remote + server)
        tui/                 # terminal UI dùng native/http-client
        browser/             # browser composition root
        ffi/                 # C ABI mobile/desktop
        http-server/         # axum HTTP inbound adapter
        cli/                 # clap inbound adapter
    tools/
      parse/                 # text-only parse CLI
      parity/                # mel/synth-ids parity tools
  resources/                 # nằm trong core/domain/text/resources
    vocab.json
    frontend/
      acronyms.json
      english.json
      products.json
      letter_readings.json
      overrides_vi.json
      custom_reading.json     # optional, mặc định không nạp
    models/
      n0-q.manifest.json
  tests/
    golden/                   # corpus nhỏ, commit
```

Tách `text`/`audio` khỏi `engine` để test frontend/audio không cần tải model, và
để sau này có thể chạy WASM/tract mà không kéo theo ONNX Runtime. Tách `ports`
để adapter ORT/ORT Web không phụ thuộc orchestration.

**Hiện thực tế (29/10/2026):** workspace được chia `core/domain`,
`core/application`, `core/ports`, `adapters/outbound`, `adapters/inbound`,
`tools`; tên crate theo role: `vifasttts-ports`, `vifasttts-native`,
`vifasttts-browser`, `vifasttts-http-client`, `vifasttts-http-server`.
Chưa có `vifasttts-pyo3`, desktop app, extension hay voice catalog local/cloud.
Đã có manifest model, streaming PCM, karaoke timing và browser local demo
(ORT Web + browser adapter). Dữ liệu frontend nằm trong
`rust/crates/core/domain/text/resources/`, sinh từ Python bằng
`tools/export_rust_resources.py` và nhúng bằng `include_str!` (không cần file
lúc chạy).

### 3.2 Crate/dependency chính

| Việc | Lựa chọn | Ghi chú |
|---|---|---|
| ONNX | `ort` | Ưu tiên; xem D3 về phiên bản |
| Tensor | `ndarray` | Hoặc `Vec<f32>` + shape; `ndarray` dễ đọc |
| FFT/iSTFT | `rustfft` + `realfft` | f64 để khớp numpy |
| Unicode | `unicode-normalization`, `unicode-ccc` | NFC/NFD + combining class |
| Regex | `regex`, `fancy-regex` | Lookaround cần `fancy-regex`; ưu tiên scan tay |
| Số lớn | `num-bigint` | Python đọc số nguyên không giới hạn |
| JSON | `serde`, `serde_json` | Giữ thứ tự field; hash vocab |
| Hash | `sha2`, `hex` | Model/vocab/artifact |
| WAV | tự ghi hoặc `hound` | Tự ghi để khớp header/rounding |
| CLI | `clap` | Batch/one-shot |
| HTTP | `axum`, `tokio`, `tower-http` | Nếu port web |
| SQLite | `rusqlite` | Nếu port stats/admin |
| Lỗi | `thiserror`, `anyhow` | Không panic vì input người dùng |
| Test | `proptest`, `insta`, `criterion` | Fuzz + golden + bench |
| PyO3 | `pyo3`, `maturin` | Optional |
| WASM | `wasm-bindgen` + `vifasttts-ort-web` + ORT Web (JS) | Browser local; `ort-web` là async backend, không dùng `ort` native |

Không thêm dependency nặng nếu crate nền không cần. Không dùng `unsafe` trừ FFI
tối thiểu (nếu buộc phải gọi C API).

### 3.3 Model package

Thay vì hai file ONNX rời, tạo manifest:

```json
{
  "format": "vifasttts-model-v1",
  "arch": "v2_slot5",
  "sample_rate": 24000,
  "n_mels": 100,
  "n_fft": 1024,
  "hop_length": 256,
  "vocab_version": "vi-q25-v1",
  "vocab_hash": "1a33…",
  "frontend_version": "vi-frontend-v1",
  "frontend_golden_hash": "…",
  "acoustic": {"file": "acoustic.onnx", "sha256": "df61…"},
  "vocoder": {"file": "vocoder.onnx", "sha256": "b3eb…"},
  "ort": {"min": "1.31.1", "tested": "1.31.1", "mode": "load-dynamic"},
  "license": "research/non-commercial; dataset CC-BY-NC-4.0"
}
```

Rust dùng `ort` rc.15 với `load-dynamic` và thư viện **1.31.1**; nếu không
khớp phải đo mel/wav và ghi sai lệch, không tự nới ngưỡng.

Rust **phải** kiểm tra:

- file tồn tại + SHA256;
- `arch == v2_slot5`;
- `vocab_hash` khớp canonical;
- input/output names/shape/dtype đúng;
- `sample_rate/n_mels/n_fft/hop_length` đúng;
- thiếu hash → từ chối ở production (không "transitional" âm thầm).

`frontend_version`/`frontend_golden_hash` không bắt buộc cho model cũ, nhưng nên
thêm để biết model được train/đo với frontend nào. `vocab_hash` chỉ bảo vệ vocab,
**không** bảo vệ hành vi normalizer/parser.

---

## 4. Hợp đồng bất biến

### 4.1 Frontend

- `ParsedSyllable` JSON giữ đủ: `raw`, `normalized`, `orthography`, `abstract`,
  `boundaries`, `status`, `confidence`, `punctuation`.
- Tokenizer: tương đương `\w+|[^\w\s]` của Python; **không** dùng `\w` Rust
  mặc định mà định nghĩa predicate ký tự rõ ràng, có test Unicode.
- `parse_text`:
  1. `apply_custom_reading` (nếu có bảng) — khớp token, khoá dài trước, không
     quét lại phần đã thay;
  2. `normalize_unicode` + `normalize_text` (thứ tự regex rất quan trọng);
  3. tokenize; dấu câu trước gắn vào token sau, dấu câu sau gắn vào token trước;
  4. `safe_parse_syllable`; nếu OOV và `resolve_oov` → respell rồi parse lại,
     giữ `raw` gốc, `confidence <= 0.5`;
  5. fallback: abstract hợp lệ (`A`, `NONE`, `NGANG`) để encode không crash.
- Vocab: 7 mảng, kích thước **25/2/15/11/6/4/6**, Q cuối onset.
  `encode` trả đúng thứ tự `[onset, medial, nucleus, coda, tone, boundary, punctuation]`.
- Boundary: mặc định `word_end=True`; `.!?` → sentence_end; `,;:` → phrase_end.
- Punctuation: `?` → QUESTION, `!` → EXCLAMATION, `,` → COMMA, `.` → PERIOD,
  có ký tự khác → OTHER, rỗng → NONE. Thứ tự kiểm tra phải giữ nguyên.
- `normalize_text` phải giữ **đúng thứ tự** xử lý: phrase overrides → giờ `14h30`
  → STEM → dấu nghìn → ngày → giờ:phút → điện thoại → email → toán → tiền →
  phân số → khoảng → phần trăm → số thập phân → số nguyên → 5G → English/roman.
- `chunk_text`/`split_clauses`: đếm theo **code point**, không theo byte; giữ
  dấu câu; `pause_seconds` 0,15/0,08/0,05; steady 0,55/0,25/0,08.
- `sharpen_mel`: unsharp 3×3, zero-pad, chia 9, alpha 1,5, giữ shape.
- `fade`: 10 ms in, 20 ms out, tuyến tính; `peak_normalize` chỉ khi được yêu cầu.

### 4.2 ONNX

- Chỉ chấp nhận `arch=v2_slot5` cho production; graph 2 input cũ chỉ cho test.
- `features` int64 `[1,N,7]`; `speed`/`gate_threshold` float32 `[1]`.
- Chỉ dùng output `mel`; các output khác có thể expose để debug nhưng không
  được làm thay đổi thứ tự.
- Session:
  - CPU EP mặc định;
  - `intra_op_num_threads=2`, `inter_op_num_threads=1`;
  - execution mode sequential;
  - graph optimization mặc định của Python (đo lại, không tự ý đổi).
- Không dùng CoreML/CUDA mặc định; nếu thêm, phải là feature riêng và đo parity.
- ORT version phải ghi trong manifest; live hiện 1.31.1, Rust `load-dynamic`
  cũng dùng 1.31.1. Phải đóng gói thư viện ORT cạnh binary/app.

### 4.3 Audio

- iSTFT: Hann symmetric, `n_fft=1024`, `hop=256`, `center=True`; độ dài
  `(T-1)*hop`; chia envelope `max(1e-11)`.
- Làm việc f64 trong FFT/overlap-add, cast f32 ở cuối (như numpy hiện tại).
- WAV: PCM16 mono, 24 kHz, clip `[-1,1]`, nhân 32767, **round ties-to-even**
  (NumPy `round`), không phải `f32::round()` (half away from zero).
- `postprocess`: fade trước; peak normalize sau nếu bật.
- Không tự thêm dither/normalize mới.

### 4.4 HTTP (nếu port)

- `/healthz` trả `arch`, `vocab_version`, `vocab_hash`, `alpha`, `pause`.
- `/api/config`: `max_chars`, `rate_limit`, `rate_window`.
- `/api/tts`: max 3.000 ký tự, 6 req/phút, một request đồng thời, 45 s timeout,
  speed 0,8–1,2, `fixed_pauses`, overrides.
- Header `X-Processing-Seconds`, `X-Audio-Seconds`, `X-RTF`, `X-Characters`.
- Admin/feedback/stats: **không** đưa vào Phase 4A; nếu port, làm Phase 4B.

---

## 5. Kế hoạch theo giai đoạn

Thời lượng là ước lượng cho **1 dev Rust senior, full-time**, đã quen audio/ONNX.
Đệm 20–30% chưa tính trong từng dòng.

### Trạng thái phase (28/10/2026)

| Phase | Trạng thái | Ghi chú |
|---|---|---|
| 0 Hợp đồng/golden | Phần lớn | resources + parity + manifest; còn freeze contract/golden đầy đủ |
| 1 Runtime | Phần lớn | ORT + iSTFT + WAV + parity audio macOS; còn VPS/mobile |
| 2 Frontend | Phần lớn | parser/normalizer/stem/OOV/chunking; 0 mismatch trừ ngoại lệ raw combining |
| 3 End-to-end | Phần lớn | Engine + streaming + benchmark + karaoke; chưa 1.000 request |
| 4 Tích hợp | Một phần | server axum + C ABI; chưa PyO3, desktop app/extension, XCFramework/NDK |
| 5 Cutover | Chưa | chưa shadow/canary/rollback |

### Phase 0 — Hợp đồng + golden corpus (3–5 ngày)

**Mục tiêu:** biến hành vi Python thành spec chạy được trước khi viết Rust.

Việc làm:

1. Viết `docs/RUST_PORT_CONTRACT.md` (hoặc mục 4 này được freeze) với:
   - schema `ParsedSyllable`;
   - bảng vocab + hash;
   - thứ tự normalizer;
   - I/O ONNX + metadata;
   - chunking/pause/audio/WAV;
   - profile `live` vs `full`.
2. Đưa dữ liệu canonical vào `rust/resources/`:
   - `vocab.json` (25/2/15/11/6/4/6 + version/hash);
   - `acronyms.json`, `english.json`, `products.json`, `letter_readings.json`;
   - `overrides_vi.json` (229);
   - `custom_reading.json` optional (7, không mặc định live);
   - kiểm tra Python và Rust đọc **cùng file**, hoặc có test so sánh.
3. Viết `tools/rust_golden.py`:
   - chạy Python frontend trên corpus, ghi JSONL: input, options, normalized,
     parsed, 7 ID, chunks, pause;
   - chạy Python ONNX trên 20–50 câu, ghi mel/wav/hash/shape;
   - ghi môi trường: ORT version, numpy, threads, model hash.
4. Corpus tối thiểu:
   - 49.104 tổ hợp parser;
   - toàn bộ test frontend hiện có;
   - 94 acronym + 758 English + 12 product + 229 override;
   - số/ngày/giờ/tiền/email/STEM/Unicode/emoji/CJK;
   - 7 custom reading (profile full);
   - 20–50 câu audio đại diện (ngắn/dài/dấu câu/Q/tốc độ).
5. Đo baseline Python: cold start, p50/p95, RTF, RSS, model load; cùng máy,
   cùng ORT/threads.
6. Tạo manifest model (mục 3.3) + hash.

**Cổng ra:**

- Chạy golden 2 lần cho kết quả giống nhau (trừ timestamp).
- Python test vẫn 2.936 pass / 24 skip.
- `vocab_hash` không đổi.
- Có báo cáo coverage corpus (bao nhiêu ca, phần nào chưa phủ).

**Dừng nếu:** không xác định được dữ liệu nào đang live (đặc biệt custom reading)
hoặc baseline không tái lập được.

---

### Phase 1 — Rust runtime + iSTFT + WAV (1,5–2,5 tuần)

**Mục tiêu:** chứng minh `ort` + FFT + WAV đúng, trước khi port frontend.

Việc làm:

1. Cài Rust toolchain, tạo workspace, CI (`fmt`, `clippy`, `test`), license.
2. Spike `ort`:
   - thử crate `ort` rc.15 với ORT **1.31.1** (`load-dynamic`);
   - load acoustic/vocoder, chạy 1 câu với 7 ID cho trước;
   - so mel/wav với Python;
   - ghi rõ version, feature (`load-dynamic`/bundled), cách phân phối lib.
3. Implement:
   - `AudioBuffer`, WAV writer;
   - `istft` f64 dùng `rustfft`/`realfft`;
   - `sharpen_mel`;
   - `fade`, `peak_normalize`;
   - model loader + metadata/hash validation;
   - session options (2 threads, CPU).
4. CLI `vifasttts synth-ids`:
   - nhận JSON 7 ID hoặc file `.npy`/raw;
   - xuất WAV;
   - in timing/shape/hash.
5. So sánh:
   - mel max abs / relative;
   - waveform max abs;
   - PCM hash và số mẫu lệch;
   - chạy lặp 10 lần.

**Cổng ra:**

- Model load + hash đúng; hash sai bị từ chối.
- MelSpectrogram khớp Python (cùng ORT) ≤1e-5 max abs (mục tiêu; nếu khác do ORT version,
  ghi rõ và quyết định).
- Waveform max abs ≤1e-5; PCM lệch ≤0,01% mẫu (mục tiêu byte-identical).
- Rust chạy lặp lại **byte-identical**.
- RTF không tệ hơn Python quá 5%; cold start/RSS được ghi lại.
- WAV nghe được, đúng 24 kHz/PCM16.

**Dừng nếu:** `ort` không dùng được ORT 1.31.x và không có phương án C API/FFI
rõ ràng; hoặc iSTFT lệch quá ngưỡng mà nguyên nhân không xác định.

---

### Phase 2 — Rust frontend (5–7 tuần)

Chia nhỏ để có cổng sau mỗi phần.

#### 2A. Unicode + types + tone + orthography + parser + vocab (1–1,5 tuần)

- `Tone`, `ParseStatus`, `Orthography`, `AbstractSyllable`, `Boundaries`,
  `ParsedSyllable`.
- NFC/NFD, combining class, tone extraction/placement.
- `rules.rs`: onset/coda/nucleus, compatibility, special vowels.
- `syllable.rs`: `_match_onset` (gi/ qu/ quốc), coda, vowel, semivowel.
- `vocab.rs`: encode, hash, strict verify.
- Cổng: 49.104 tổ hợp + toàn bộ test parser/syllable/tone/orthography/vocab.

#### 2B. Pipeline + tokenizer + custom reading + OOV (1–1,5 tuần)

- Tokenizer predicate tương đương Python.
- `parse_text` với punctuation/boundaries, fallback, OOV recursion.
- `custom_reading`: multiword, case-insensitive, token boundary, validation.
- `oov`: acronym/product/English/letter spelling, `isupper` tương đương.
- Cổng: 100% JSON/ID trên corpus pipeline/OOV/custom reading.

#### 2C. Normalizer (1,5–2 tuần)

- Số nguyên/thập phân (BigInt), số điện thoại, ngày/giờ, phân số, khoảng,
  phần trăm, tiền tệ, email, toán, 5G, roman.
- `_apply_phrase_overrides` + exact/English overrides.
- Giữ đúng thứ tự; test từng nhóm + precedence.
- Cổng: 100% normalized text trên corpus normalizer + fuzz 100k.

#### 2D. STEM (1 tuần)

- LaTeX (`\frac`, `\sqrt`, `\text`, mũ/chỉ số).
- Hoá học (`H2SO4`, ion, ngoặc, guard sản phẩm).
- Đơn vị SI (`m/s²`, `km/h`, `°C`).
- Cổng: toàn bộ test STEM + corpus hoá học/toán/vật lý.

#### 2E. English/roman/overrides/chunking (0,5 tuần)

- 758 English + 94 acronym + 12 product + 229 built-in.
- Roman numerals.
- `chunk_text`, `split_clauses`, `pause_seconds`.
- Cổng: 100% corpus; chunk/pause khớp.

#### 2F. Differential fuzz + freeze (1 tuần)

- `proptest`/generator sinh chuỗi Unicode, dấu câu, số, NFD, emoji, CJK.
- So Python vs Rust: normalized, parsed, 7 ID, chunks.
- Không panic; giới hạn thời gian; log diff nhỏ nhất.
- Cổng: 0 mismatch trên corpus; mọi mismatch còn lại phải có lý do tài liệu hóa
  và được chấp nhận rõ ràng (không sửa test để che).

**Cổng tổng Phase 2:**

- 100% frontend golden (trừ ngoại lệ có tên).
- 100% 7 ID.
- Không regression Python.
- Frontend Rust chạy <10 ms cho 10k ký tự (mục tiêu tham khảo; model mới là
  phần chậm).

---

### Phase 3 — End-to-end engine (1–2 tuần)

Việc làm:

1. `Engine`:
   - resolve overrides (`builtin`, `approved`, `request`, profile live/full);
   - chunk; parse; encode; acoustic; sharpen; vocoder; iSTFT; pause; concat;
     postprocess; WAV.
2. `SynthesisOptions`: speed, fixed_pauses, gate_threshold, alpha, max_chars,
   peak_normalize, target_lufs (optional), dialect, overrides.
3. Streaming iterator: yield từng chunk + pause; không giữ toàn bộ nếu có thể.
4. Error types: text rỗng, quá dài, model lỗi, hash sai, parse fallback.
5. Metrics/log: elapsed, audio seconds, RTF, chars, chunk count, model hashes.
6. So sánh end-to-end 20–50 câu; đo p50/p95/RSS; 1.000 request stress.

**Cổng ra:**

- PCM parity như Phase 1 trên toàn corpus.
- Pause đúng vị trí/độ dài; fixed_pauses và model pause đều đúng.
- Speed 0,8/1,0/1,2 đúng (v2 xử lý trong graph; không stretch mel).
- p95 ≤1,05× Python; RSS mục tiêu ≤ Python (đo, không hứa).
- Không leak/rò rỉ qua 1.000 request.

---

### Phase 4 — Tích hợp (1–3 tuần web; mobile thêm phase riêng)

#### 4A. PyO3 + FastAPI (cầu nối tạm)

- `vifasttts-pyo3`: `Engine`, `synthesize`, `synthesize_stream`, `health`.
- `py.allow_threads` quanh ONNX/FFT để không giữ GIL.
- FastAPI thay `_synthesize` bằng Rust; giữ stats/admin/feedback.
- Feature flag `VIFASTT_BACKEND=python|rust`; fallback Python có log + đếm.
- Docker multi-stage: Rust builder + Python runtime; copy `.so` + ORT lib.
- Cổng: shadow 100% request; canary; rollback trong 1 lệnh.

#### 4B. Full Rust HTTP (ưu tiên cho web)

- Axum: `/api/tts`, `/healthz`, `/api/config`, static.
- Rate limit, lock/semaphore, timeout, CORS, body limit.
- Nếu port admin: `rusqlite`, schema hiện có, basic auth; đây là +2–3 tuần.
- Cổng: load test, security, error handling, stats DB migration.

#### 4C. FFI mobile/desktop (bắt buộc cho đa nền tảng)

- `vifasttts-ffi` (UniFFI hoặc C ABI), `cdylib`/`staticlib`.
- Load model từ bytes; streaming PCM; `catch_unwind`; mã lỗi.
- iOS: XCFramework; Android: jniLibs/NDK; desktop: Tauri hoặc binary native.
- Chi tiết và ma trận nền tảng: §15.

**Khuyến nghị (cập nhật 28/10/2026):** với mục tiêu web + desktop + iOS +
Android, không nhất thiết làm 4A trước. Ưu tiên 4B (server Rust) và 4C (FFI
mobile) theo §15; PyO3 chỉ dùng nếu vẫn muốn giữ FastAPI trong giai đoạn
chuyển tiếp. Không port admin ngay.

---

### Phase 5 — Cutover + decommission (1 tuần + 30 ngày bake)

1. Shadow mode: Rust chạy song song, so hash/PCM, không trả user.
2. Canary 5–10% traffic; theo dõi RTF, lỗi, 5xx, audio.
3. Tăng dần 100%; giữ Python image + đường lui.
4. Sau 30 ngày ổn định: bỏ Python runtime khỏi container (nếu 4B), lưu image cũ.
5. Cập nhật `TRANG_THAI`, Docker, release/HF; ghi hash/commit.
6. **Không xoá** Python train/data/export.

**Cổng ra:**

- 0 lỗi nghiêm trọng; p95/RTF đạt; không khác audio đáng kể.
- Rollback đã thử thành công.
- Tài liệu vận hành + hash model/frontend.

---

## 6. Vì sao thứ tự này (phân tích lại kế hoạch cũ)

Kế hoạch cũ (archive) nói “sau khi frontend ổn định, viết Rust bổ sung” và liệt
kê parser, lexicon, manifest validator, ONNX, WAV, CLI. Nó thiếu 4 thứ quyết định:

1. **Không có golden corpus/contract** → không biết “ổn định” là gì.
2. **Không có thứ tự rủi ro** → parser/normalizer dễ trôi hơn runtime.
3. **Không có chuyện dual maintenance** → Python train vẫn dùng frontend;
   Rust mirror có thể lệch mà không ai biết.
4. **Không có cutover/rollback** → port xong vẫn không dám bỏ Python.

Thứ tự mới:

```text
P0 contract/golden
      │
      ├── P1 runtime (rủi ro số học) ──┐
      │                                ├── P3 e2e ── P4 integration ── P5
      └── P2 frontend (rủi ro ngữ nghĩa)┘
```

- Runtime trước vì nó nhỏ, đo được ngay, và xác nhận `ort`/FFT/WAV trước khi
  đầu tư vào 2.500 dòng frontend.
- Frontend sau vì nó là phần lớn nhất và dễ trôi nhất; có golden để đo.
- P1 và P2 có thể chạy **song song** nếu có 2 dev; P3 mới là điểm hội tụ.
- PyO3 **sau P3**, không phải sau P1. Nếu cần đưa Rust vào production sớm, chỉ
  dùng một adapter test nội bộ, không biến hybrid thành đích cuối.
- Web/admin cuối cùng; không để nó chặn inference.

---

## 7. Golden corpus và parity

### 7.1 Nguyên tắc

- **So giá trị, không chỉ shape.** Test cũ đã từng bỏ lọt lỗi gán slot sai vì
  chỉ kiểm shape (xem `docs/ACOUSTIC_V2.md`).
- **Cùng môi trường**: cùng ORT, cùng threads, cùng model hash, cùng CPU.
- **Sai khác phải có tên**: nếu chấp nhận ngoại lệ, ghi input + hash + lý do;
  không nới ngưỡng chung.
- **Không sửa test để pass.** Nếu Rust khác Python, xác định bên nào đúng theo
  spec; nếu spec không rõ, dừng và bổ sung spec.

### 7.2 Các tầng test

| Tầng | Nội dung | Chạy |
|---|---|---|
| Unit Rust | từng rule, Unicode, số, chunk | mọi commit |
| Golden frontend | JSONL Python → Rust | CI + local |
| Golden audio | mel/wav/hash 20–50 câu | CI có artifact |
| Property/fuzz | 100k chuỗi | nightly |
| Integration | ONNX + WAV + CLI | CI có model |
| Live canary | shadow/canary | P5 |

### 7.3 Ngưỡng audio đề xuất

- MelSpectrogram: max abs ≤1e-5 (cùng ORT); nếu ORT khác bản, đo lại và ghi.
- Waveform: max abs ≤1e-5; PCM lệch ≤0,01% mẫu, mỗi mẫu lệch ≤1 LSB.
- Mục tiêu cao hơn: PCM **byte-identical**; nếu không đạt, phải nghe A/B và
  được người dùng chấp nhận, không tự động bỏ qua.
- Determinism: 10 lần cùng input → cùng SHA256; 2 threads cố định.

### 7.4 Dữ liệu golden

- Commit corpus nhỏ (<5 MB) để CI chạy; corpus đầy đủ (49k + audio) để local/
  nightly, sinh bằng `tools/rust_golden.py`.
- Không commit model/audio lớn; dùng hash + script tải/đo.

---

## 8. Cổng hiệu năng và vận hành

Đo ở P0 trên cùng máy, cùng ORT/threads; sau đó so tương đối.

| Chỉ số | Mục tiêu |
|---|---|
| Cold start (load 2 model) | ≤2 s hoặc ≤1,2× Python |
| p50/p95 end-to-end (300 ký tự) | ≤1,05× Python |
| RTF end-to-end | ≤1,05× Python |
| RSS sau load | ≤ Python; mục tiêu ≤250 MB |
| Binary + model | ghi rõ; không phình vì ORT |
| 1.000 request | không leak, không panic, lỗi <0,1% |
| Determinism | 10/10 byte-identical |
| CPU | 2 intra-op, 1 inter-op; không oversubscribe |

Lưu ý: **RTF không phải lý do chính để port**. Nếu model chiếm 90% thời gian,
Rust frontend chỉ cải thiện phần nhỏ. Đo trước khi hứa.

---

## 9. Rủi ro và điểm dừng

| Rủi ro | Mức | Dấu hiệu | Giảm thiểu / dừng |
|---|---|---|---|
| Frontend lệch ngữ nghĩa | Cao | mismatch normalized/ID | Golden + fuzz; mismatch >0,1% ⇒ dừng, không nới test |
| Regex/Unicode khác Python | Cao | NFD, `\w`, `isupper`, lookaround | Predicate tường minh; `fancy-regex`; corpus Unicode |
| `ort` không khớp ORT 1.31.x | Cao | thư viện ORT khác bản live; mel/wav lệch | Pin `ort`/ORT 1.31.1; đóng gói lib; không ship mù |
| iSTFT/FFT lệch | Trung bình | waveform/PCM lệch | f64, cùng công thức, test impulse/sine; PCM gate |
| Rounding WAV khác NumPy | Trung bình | lệch 1 LSB | `round_ties_even`; test biên 0,5 |
| Dữ liệu frontend trôi | Cao | 229/758/7 khác | Đưa vào `resources/`, hash, test Python↔Rust |
| custom reading live/full lẫn nhau | Trung bình | audio khác live | Profile rõ; mặc định live không nạp file local |
| Dual maintenance | Cao | Python sửa parser, Rust không cập nhật | Golden CI; một nguồn dữ liệu; lên kế hoạch PyO3 cho data |
| Scope creep web/admin | Cao | kéo dài tuần | Ưu tiên 4B/4C theo §15; admin để sau |
| Mobile/FFI packaging | Cao | C ABI có, chưa XCFramework/NDK | bytes load + spike XCFramework/NDK (§15) |
| ORT dynamic lib/Docker | Trung bình | thiếu `.so`, glibc/musl | Multi-stage; pin; test trên VPS |
| WASM/model size | Cao | 86 MB; ORT wasm async, không prebuilt; v2 chưa int8 | Server-side web trước; quantize sau (§15) |
| Parity khác kiến trúc | Trung bình | PCM lệch giữa macOS/ARM/Android | Dung sai theo nền tảng; cùng ORT version |
| License dataset | Cao | CC-BY-NC | Giữ research/non-commercial; ghi notices |
| Không có artifact local | Trung bình | test skip | Script tải/kiểm hash; CI tách integration |

**Quy tắc dừng chung:** nếu một cổng lỗi mà nguyên nhân không giải thích được
trong 1 ngày, dừng nhánh đó, ghi báo cáo, không “tạm nới” để đi tiếp.

---

## 10. Quyết định cần chốt

| Mã | Câu hỏi | Khuyến nghị |
|---|---|---|
| D1 | Port inference hay cả repo? | Inference; giữ train/data/export |
| D2 | Runtime nào? | `ort` + CPU; `tract` chỉ fallback |
| D3 | ORT version? | Pin **1.31.1** qua `load-dynamic`, khớp live; đóng gói lib |
| D4 | Dữ liệu frontend ở đâu? | `resources/` dùng chung Python/Rust; hiện `rust/crates/core/domain/text/resources/` sinh bằng `tools/export_rust_resources.py`, cần test hash/không trôi |
| D5 | Hash thiếu? | Production từ chối; chỉ test mới cho legacy |
| D6 | PyO3 hay Rust HTTP? | Với mục tiêu đa nền tảng: adapter FFI + server Rust; PyO3 chỉ để giữ FastAPI tạm |
| D7 | Port web admin? | Không, giai đoạn đầu |
| D8 | WASM? | Server-side web trước; browser WASM sau, cần quantization + backend riêng |
| D9 | Concurrency? | Desktop/mobile 1 engine; web cần pool/mutex; đo trước khi pool |
| D10 | Ai là canonical frontend? | Rust làm runtime canonical; Python train tạm mirror có golden; cân nhắc PyO3 cho data sau cutover |
| D11 | Đa nền tảng? | Có: web, desktop Windows/Linux/macOS, iOS, Android; thêm backend trait, bytes, streaming, FFI (§15) |

D3 đã chốt: live ORT **1.31.1**; `ort` v1.14.5 quảng cáo ORT 1.31,
`ort` v2.0.0-rc.13 dùng ORT 1.28; bản đang dùng **rc.15** + `load-dynamic`
(xem `ort-sys/build/download/dist.tsv`). Chọn sai phiên bản sẽ làm mel/wav lệch
hoặc phải re-baseline. Không giả định “crate mới nhất = đúng bản đang chạy”.

---

## 11. Chi phí / lợi ích

### 11.1 Ước lượng (1 dev, full-time)

| Phase | Tuần |
|---|---:|
| 0 Hợp đồng/golden | 0,5–1 |
| 1 Runtime | 1,5–2,5 |
| 2 Frontend | 5–7 |
| 3 End-to-end | 1–2 |
| 4A PyO3 | 1–1,5 |
| 5 Cutover/bake | 1 + 30 ngày |
| **Tổng inference + PyO3** | **10–15** |
| 4B Full Rust HTTP | +2–3 |
| **Tổng full web** | **12–18** |

Cộng 20–30% đệm. Hai dev có thể rút ngắn P1/P2 song song, nhưng P3/P4 vẫn tuần tự.

Ước lượng trên **chưa gồm** FFI mobile, đóng gói XCFramework/NDK, streaming,
CI đa nền tảng và quantization/WASM. Với mục tiêu web + desktop + iOS + Android,
phải lập phase riêng cho các phần này trước khi chốt tiến độ (§15).

### 11.2 Lợi ích thật

- Một binary + model, không cần Python/numpy/onnxruntime Python khi chạy.
- Khởi động/bộ nhớ/đóng gói tốt hơn; dễ ký hash, kiểm model.
- Kiểu dữ liệu chặt, lỗi sớm, không panic vì input.
- Nền cho WASM/edge/mobile sau này (nhưng chưa làm ngay).
- Có thể giảm phụ thuộc pip/Docker image.

### 11.3 Không nên port nếu…

- Chỉ muốn RTF thấp hơn: hãy đo quantization/thread/model trước.
- Chưa có người duy trì Rust lâu dài: dual maintenance sẽ phản tác dụng.
- Chưa có golden corpus: port sẽ “chạy được” nhưng lệch âm thầm.
- Cần web admin gấp: giữ FastAPI + PyO3 rẻ hơn.

---

## 12. Việc làm tiếp (cập nhật 28/10/2026)

1. Chốt D1–D5 + D11 (scope, runtime, ORT, dữ liệu, hash, đa nền tảng) — phần
   lớn đã chốt trong §10.
2. Build `--release`, chạy `cargo test`/`clippy`; đo baseline Rust (cold start,
   p50/p95, RSS) — hiện mới có số debug/parity, chưa có số release.
3. Freeze parity frontend + audio, sinh golden corpus và manifest; báo cáo
   0 mismatch (hoặc ngoại lệ có tên).
4. Tách `vifasttts-native` thành `vifasttts-ort` + `vifasttts-engine`, thêm
   backend trait (§15.5).
5. `NativeEngine::from_bytes` + manifest/hash theo nền tảng.
6. Streaming PCM + giới hạn RAM.
7. FFI mobile (UniFFI/C ABI) + XCFramework/NDK.
8. CI matrix đa nền tảng + server axum cho web.
9. Quantize/WASM sau khi 1–8 ổn định.
10. Cập nhật `TRANG_THAI`/docs và commit khi có quyết định (hiện mã còn untracked).

---

## 13. Checklist “định nghĩa hoàn thành”

### Inference core (bắt buộc)

- [ ] 100% frontend golden (normalized + parsed + 7 ID + chunk/pause).
- [ ] 100% test parser matrix 49.104.
- [ ] MelSpectrogram/wav parity đạt ngưỡng; 10 lần lặp byte-identical.
- [ ] Model/vocab/hash kiểm tra; thiếu/sai bị từ chối.
- [x] CLI one-shot + batch + stream chạy.
- [ ] 1.000 request không leak/panic.
- [ ] p95/RTF/RSS đạt cổng; số đo ghi vào docs.
- [ ] CI `cargo fmt --check`, `clippy -D warnings`, `test`.
- [ ] License/notices; model package manifest.

### Tích hợp (bắt buộc cho mục tiêu đa nền tảng)

- [ ] PyO3 (tuỳ chọn): FastAPI dùng Rust, fallback Python có log/đếm.
- [ ] Hoặc Rust HTTP: `/api/tts`, `/healthz`, static; rate limit/timeout.
- [x] Load model từ bytes; streaming PCM.
- [ ] FFI (UniFFI/C ABI) cho iOS/Android.
- [ ] CI matrix: macOS arm64, Windows x64, Linux x64, iOS sim, Android arm64.
- [ ] Shadow + canary + rollback đã thử.
- [ ] `TRANG_THAI`/docs cập nhật; commit + hash.

### Không làm

- [ ] Không port train/data/export.
- [ ] Không port admin/feedback trong Phase 4A.
- [ ] Không bật WASM khi model còn 86 MB và v2 chưa có int8/fp16.

---

## 14. Câu hỏi mở

1. **Đã chốt (28/10/2026):** mục tiêu là inference **đa nền tảng** (web,
   desktop Windows/Linux/macOS, iOS, Android); không port train/data/export.
   WASM là nhánh sau, không phải mục tiêu trước mắt.
2. Có cần web admin/feedback bằng Rust ngay không? Nếu không, giữ FastAPI
   hoặc dùng 4B; xem §15.
3. Có chấp nhận PCM không byte-identical (≤0,01% mẫu lệch 1 LSB) không?
   **Có, nhưng phải có dung sai theo nền tảng và ghi rõ**; trong cùng một nền
   tảng vẫn giữ mục tiêu byte-identical.
4. **Đã chốt (28/10/2026):** có chạy Windows/Linux/macOS/iOS/Android; chọn
   target ngay từ P1. Xem §15 cho ma trận nền tảng và các việc kiến trúc.
5. Ai duy trì Rust sau cutover? Nếu không có, nên dừng ở PyO3 hoặc không port.
6. **Web:** server-side Rust (axum) trước; browser WASM chỉ sau quantization +
   backend riêng — xem §15.

---

## 15. Trạng thái triển khai & đa nền tảng (28/10/2026)

Mục này ghi **hiện trạng mã** (khác với kế hoạch §3–§5) và các việc kiến trúc
phải làm để chạy web + desktop + iOS + Android. Mã Rust **chưa đổi production**; mọi số đo dưới đây là trên workspace local.

### 15.1 Mã đang có

Workspace `rust/` gồm 25 crate, khoảng **11.6k dòng** Rust + resources:

| Crate | Nội dung | Ghi chú |
|---|---|---|
| `vifasttts-text` | types, unicode, tone, orthography, rules, syllable, vocab, pipeline, custom_reading, oov, english, roman, normalizer, stem, chunking, karaoke | Thuần Rust; **không** `std::fs`, không ONNX; tài nguyên nhúng `include_str!` |
| `vifasttts-audio` | iSTFT, sharpen, fade, peak, WAV | Chỉ `rustfft`, không regex/model |
| `vifasttts-ports` | `AcousticModel`/`VocoderModel` async, `MelSpectrogram`, `ComplexSpectrogram`, `ModelInfo`, `AcousticResult` | Ports cho ORT native/ORT Web |
| `vifasttts-audio-sink` | `AudioSink` port cho PCM realtime | Web Audio/AVAudioEngine/AAudio adapter sau này |
| `vifasttts-transport` | `TtsTransport` port cho remote | Adapter HTTP/URLSession/OkHttp |
| `vifasttts-settings` | `SettingsStore` port | Adapter chrome.storage/localStorage/UserDefaults |
| `vifasttts-model-source` | `ModelSource` port | Path/bytes/cache/download |
| `vifasttts-engine` | application service: synthesis, chunk/parse, streaming, timing | Phụ thuộc text/audio/ports; không biết ORT |
| `vifasttts-app` | headless command/event + ETA cho UI | Không biết DOM/Chrome/native UI |
| `vifasttts-ort` | session, metadata/hash, `load_paths`, `from_bytes`, manifest | Implement async backend; ORT native, CPU EP |
| `vifasttts-ort-web` | JS callback → async backend; kiểm shape/contract | Chỉ wasm32; ORT Web chạy model, crate này là adapter |
| `vifasttts-native` | native adapter: async engine + ORT, API sync `load`/`from_bytes`/`load_verified` | `block_on` tại biên; CLI/desktop/server/FFI dùng sync |
| `vifasttts-mobile` | mobile composition root: model, status, synth, `AudioSink` | iOS/Android; chưa có audio adapter/UI |
| `vifasttts-desktop` | desktop app egui: local ONNX + remote HTTP + server nội bộ, settings/dictionary/ETA, phát audio, lưu WAV/SRT/VTT | macOS/Linux/Windows package; CI smoke cả ba |
| `vifasttts-tui` | library TUI ratatui/crossterm; model browser `Ctrl+O` | CLI không args mở TUI |
| `vifasttts-vfts` | `.vfts` full + `.vfa` acoustic-only (vocoder hash); hash/traversal/zip-bomb | loader native/CLI/server/TUI/FFI/mobile |
| `vifasttts-huggingface` | search/files/download `.vfa/.vfts` từ HF | adapter native; web dùng API server |
| `vifasttts-model-manager` | catalog/download/install/installed dùng chung | CLI/desktop/TUI/server; web/extension/mobile qua HTTP |
| `vifasttts-browser` | browser adapter: async engine + `ort-web` + parse/karaoke/DSP | Ngang hàng `native`; JS chỉ nạp model/session + UI |
| `vifasttts-http-client` | HTTP client `/healthz`, `/api/config`, `/api/tts` (WAV/karaoke JSON) | Cho CLI remote/web/mobile; không kéo ORT |
| `vifasttts-cli` | không args = TUI (feature `tui`); `server` = HTTP + web; `inspect/synth/stream/bench/vfts` | CLI production; desktop package kèm sidecar; có thể build `--no-default-features` để bỏ TUI |
| `vifasttts-tools` | `mel-ids`, `synth-ids` | Parity model; cần native |
| `vifasttts-parse` | `parse`, `parse-batch` | Text-only; **không link ORT** |
| `vifasttts-ffi` | C ABI `cdylib`/`staticlib`, header; `vifasttts_synthesize_karaoke` trả WAV + JSON timing | `catch_unwind`, lỗi qua `vifasttts_last_error`, bytes/streaming |
| `vifasttts-http-server` | axum `/healthz`, `/api/config`, `/api/tts` (WAV/JSON), `/api/tts/stream`; `--web-dir`, `--api-only`, `--token`, `--cors` | Có streaming + karaoke |

- Dữ liệu frontend: `rust/crates/core/domain/text/resources/*.json` (vocab,
  acronyms, english, products, letter_readings, overrides_vi, custom_reading,
  frontend_meta), sinh từ Python bằng `tools/export_rust_resources.py`.
- Tool parity: `tools/rust_parity.py` (live/full, matrix, fuzz), ghi
  `artifacts/rust_parity*` — local, không commit.
- Build release: `rust/target/release/vifasttts` (~7,5 MB, gồm HTTP client) + `rust/lib/libonnxruntime`
  (1.31.1, ~32 MB); `inspect` in `ort: ORT Build Info ...`.
- Đã có: tách `engine`/`ort`, `from_bytes`, manifest + verify, streaming PCM,
  C ABI và server axum tối thiểu; **karaoke timing từ `slot_durations`** + export
  SRT/WebVTT/JSON, streaming timing.
- Còn thiếu: `vifasttts-pyo3`, browser WASM, desktop app/Tauri, extension,
  voice catalog local/cloud, đóng gói XCFramework/NDK, CI matrix chạy green,
  benchmark đa nền tảng, rate-limit/auth/admin cho server.

### 15.2 Đối chiếu phase

Bảng trạng thái phase nằm ở **§5** (đầu mục). Tóm tắt: P0–P2 đã phần lớn,
P3 đã có streaming/benchmark M6 + C ABI + server tối thiểu; còn iOS/Android
build thật. P4–P5 chưa.

**Parity frontend đã chốt (28/10/2026):**

| Bộ | Số case | Kết quả |
|---|---:|---|
| Parser matrix 49.104 tổ hợp + curated | 50.789 | **0 mismatch** (normalized + parsed + 7 ID) |
| Curated live | 1.980 | **0 mismatch** |
| Full custom reading (7 rule local) | 1.995 | **0 mismatch** |
| Fuzz NFC thực tế (chữ Việt/ASCII/CJK/emoji) | 4.980 | **0 mismatch** |
| Fuzz raw có dấu kết hợp rời (adversarial) | 6.980 | **còn mismatch** — ngoại lệ có tên: chuỗi không canonical (dấu kết hợp đứng trước/không có base), không thuộc input production |

Audio:

- Cùng ORT **1.31.0** + NumPy 1.26: nhiều câu (1 chunk, nhiều chunk, fixed
  pause, speed 0,8/1,0/1,2) cho **PCM byte-identical**.
- Rust `load-dynamic` ORT **1.31.1** vs Python `.venv-demo` 1.31.1 + NumPy 2.0.2:
  một câu 7,11 s lệch **43/170.752 mẫu, max 1 LSB** (0,025% mẫu).
- Sai khác 43 mẫu là do NumPy 2.0.2 (sharpen/rounding), không phải ORT; đã ghi
  để không đổ nhầm nguyên nhân.
- Fixed pause từng lệch do Rust fade từng chunk; đã sửa: fade/peak chỉ áp một
  lần sau khi ghép, PCM trở lại byte-identical.
- Góp ý #7 (phân số): đã mirror `_FRACTION_PERCENT_RE`, `_FRACTION_RE` mới và
  lưới `digit_slash`; parity 10/10 ca `1/2.`, `1/2,`, `1 / 2`, `1/2%`,
  `1/hai`, `1/2.5`, `1/2/2024`.

### 15.3 Bài học hiệu năng từ tool parity

Đợt `parse-batch` 6.980 dòng ban đầu >8 phút trên M6 (debug, compile regex mỗi
lần). Sau khi:

1. build `--release`;
2. cache regex bằng `OnceLock`/`RwLock` trong `normalizer.rs`; fast-path bỏ qua
   rule số/STEM khi text không có chữ số/ký hiệu;
3. tách `parse_normalized` để **không chuẩn hoá hai lần** mỗi dòng;
4. cache `ParseOptions` và không clone 229 override mỗi dòng;
5. ghi output theo dòng bằng `BufWriter` thay vì gom cả file;

thời gian còn **8,58 s cho 6.980 dòng** (release, M6; ~813 dòng/s), không đổi
hành vi. Đây là mức đủ dùng cho parity; production vẫn nên đo lại trên VPS.

**Benchmark M6 (release, 318 ký tự, 2 chunk, 20 lần, audio 19,06 s):**

| Bản | Load model | p50 | p95 | RTF | Peak RSS |
|---|---:|---:|---:|---:|---:|
| Rust + ORT 1.31.1 | 269 ms | 102,6 ms | 102,9 ms | 0,00560 | 380 MB |
| Python + ORT 1.31.1 | 125 ms | 136,3 ms | 148,7 ms | 0,00754 | 483 MB |

Rust nhanh hơn ~25% ở p50 và dùng ít RAM hơn ~22% trong lần đo này; đây là
số một lần chạy, chưa phải CI và chưa đo VPS. Load model Rust chậm hơn tuyệt
đối nhưng vẫn dưới 0,3 s.

Regex cache cũng có lợi cho production, không chỉ tool parity.

### 15.4 Ma trận nền tảng

Mục tiêu đã chốt: web, desktop Windows/Linux/macOS, iOS, Android. Theo
`ort-sys 2.0.0-rc.15/build/download/dist.tsv`, `ort` có prebuilt cho các target
dưới đây; **phải spike build/link thật**, không coi là đã chạy.

| Nền tảng | ORT lib | Hiện trạng | Việc cần |
|---|---|---|---|
| Web server Linux x64/arm64 (glibc) | Có | Engine đã chạy macOS; chưa test Linux | Ưu tiên 1: server + static |
| Desktop macOS arm64 | Có | CLI + app egui `.app` đã build/chạy smoke | ký/notarize, Windows/Linux bundle |
| Desktop Windows x64/arm64 | Có | Chưa test | CI + bundle DLL |
| Desktop Linux x64/arm64 | Có | Chưa test | CI + AppImage/deb |
| iOS arm64/sim | Có | **đã build + chạy simulator iOS 27.0** (Xcode 27.1, ORT static 1.30.0): local 2.77 s + remote 2.77 s | thiết bị thật, ký Apple Developer |
| Android arm64/x86_64 | Có | **đã build APK + chạy emulator Android 16**; jniLibs/NDK + ORT 1.31.1 | test thiết bị thật, audio, UI production |
| Web browser wasm32 | **ORT Web (JS)** | `browser` frontend + ORT Web demo | Đo tốc độ/RAM; model 86 MB; chưa production |
| Intel Mac, armv7 Android, Linux musl | **Không** | — | Build source/`load-dynamic` nếu cần |

Lưu ý:

- Rust dùng **`load-dynamic` + ORT 1.31.1** (cùng bản live). Thư viện phải được
  đóng gói cạnh binary/app; trên mobile dùng XCFramework/NDK tương ứng.
- Vẫn phải đo lại PCM trên VPS/Linux và từng nền tảng trước khi coi là tương
  đương tuyệt đối.
- Rust `ort` crate trên wasm là **async**, không có `commit_from_file`/prebuilt →
  không dùng chung engine native. Browser dùng **ORT Web (JS)** + wasm frontend.
- Model ~86 MB FP32; mobile/web cần cân nhắc quantization (int8/fp16) nhưng
  chưa có export/đo chất lượng.
- License dataset CC-BY-NC: phát hành app store cần xử lý pháp lý trước.

### 15.5 Khoảng trống kiến trúc

1. ✅ **Backend abstraction async:** `vifasttts-ports` giữ trait async
   `AcousticModel`/`VocoderModel`; `vifasttts-engine` orchestration async;
   `vifasttts-ort` (native) và `vifasttts-ort-web` (browser) là hai
   implementation. Cả hai không depend `engine`.
2. ✅ **Không còn gắn filesystem trong engine:** `vifasttts-ort::from_bytes`
   dùng `commit_from_memory`, hash trên bytes; path chỉ ở CLI/adapter.
3. ✅ **Streaming:** `synthesize_stream` callback, fade-in/out, cancellation,
   chỉ giữ tối đa 480 mẫu cuối; `peak_normalize` chưa hỗ trợ streaming.
4. ⚠️ **FFI mobile:** đã có C ABI (`vifasttts-ffi`, `cdylib`/`staticlib`,
   header, `catch_unwind`, lỗi thread-local, bytes/streaming); chưa đóng gói
   XCFramework/NDK và chưa chạy trên thiết bị thật.
5. **Thread/concurrency cố định.** `intra_op=2`, `inter_op=1` hardcode; ORT
   `Run` không thread-safe nên `SynthesisEngine` là `&mut self`. Desktop/mobile một người
   dùng ổn; web nhiều request cần pool engine hoặc mutex, và ngân sách thread
   chung để tránh oversubscribe.
6. ⚠️ **Browser local:** đã có `vifasttts-ort-web` + `vifasttts-browser` + ORT Web
   demo (`web/`); chưa production vì model 86 MB, RAM/tốc độ, cache/versioning
   và license. Server-side vẫn là đường chính cho web phổ thông.
7. **Parity đa nền tảng & license.** Không nên kỳ vọng PCM byte-identical giữa
   macOS/ARM/Android; cần dung sai theo nền tảng, cùng ORT version, golden riêng.
   License CC-BY-NC là điều kiện tiên quyết trước khi phát hành app.
8. ✅ **Karaoke/timing:** engine lấy `slot_durations`, trả `TimedUnit`/`KaraokeLine`
   + SRT/WebVTT/JSON; CLI, server (JSON + NDJSON) và FFI đã nối. Còn đo độ chính
   xác ngữ nghĩa (map text gốc) và format trên từng nền tảng.

### 15.6 Kiến trúc đích

```text
        text (domain)            audio (DSP)
              \                    /
               \                  /
                vifasttts-engine (async application)
                  ↑           ↑
               ports        ports
              ↑                ↑
        ort (native)      ort-web (browser)
              ↑                ↑
          native            browser
              ↑                ↑
 cli | http-server | ffi   web / extension
```

Nguyên tắc:

- `text`/`audio` là canonical, không biết model; `engine` không biết filesystem;
  adapter lo I/O, model asset và audio playback.
- Model có manifest + `from_bytes` + hash theo từng nền tảng.
- `native`/`browser` là hai adapter ngang hàng; không adapter nào chứa loop synth.
- Web server-side trước; WASM chỉ sau khi có quantize + backend riêng.
- Mobile dùng ORT prebuilt + UniFFI (Swift/Kotlin) + XCFramework/NDK; desktop
  dùng Tauri hoặc binary native; server dùng axum.

### 15.7 Thứ tự làm tiếp

1. ✅ Tách `vifasttts-ort` + `vifasttts-engine`, port trait **async**.
2. ✅ `from_bytes` + manifest model (hash, arch, ORT version) + `load_verified`.
3. ✅ Streaming PCM + giới hạn RAM + cancellation.
4. ✅ Karaoke/timing: `slot_durations` → JSON units/lines + SRT/WebVTT; CLI/server/FFI.
5. ✅ C ABI + Android jniLibs/NDK + emulator; iOS còn XCFramework/Xcode; desktop `.app` đã có.
6. ⬜ Cấu hình thread theo nền tảng + pool engine cho web.
7. ⚠️ Browser local có demo (`ort-web` + browser + ORT Web); còn Worker/cache/quantize/production.
8. ⬜ Voice catalog local/cloud + desktop app/extension.
9. ⬜ Golden/parity theo nền tảng + license/notices.

### 15.8 Cổng trước khi gọi “đa nền tảng”

- [x] `cargo build --release`, `cargo test`, `clippy -D warnings` sạch trên macOS.
- [x] Workflow CI desktop (macOS/Windows/Linux) + wasm text/audio/ports/engine/ort-web/browser đã thêm; chưa chạy green.
- [ ] iOS simulator + Android arm64 trong CI (Android đã chạy tay trên emulator).
- [x] `cargo check --target wasm32-unknown-unknown` cho `vifasttts-text`, `vifasttts-audio`, `vifasttts-ports`, `vifasttts-engine`, `vifasttts-ort-web`, `vifasttts-browser`.
- [x] Parity frontend 100% (trừ ngoại lệ raw combining có tên); audio đã đo macOS.
- [x] `from_bytes` + manifest verify + streaming PCM hoạt động.
- [x] C ABI không panic trên macOS; `from_bytes` + streaming chạy.
- [x] Karaoke: `slot_durations` → JSON/SRT/WebVTT; CLI `--srt/--vtt/--karaoke`, server `karaoke:true` + `/api/tts/stream`, FFI `vifasttts_synthesize_karaoke`.
- [ ] Đo sync karaoke với audio (boundary/line, speed/pause/chunk) trên corpus.
- [x] Browser demo local (`web/`) nạp model, synth, karaoke; chưa đo hiệu năng/RAM.
- [x] Android jniLibs/NDK chạy trên emulator (x86_64/arm64); [ ] thiết bị thật; [ ] iOS XCFramework (chưa có Xcode).
- [ ] License/notices rõ trước khi phát hành app.

### 15.8b App desktop + mobile (29/10/2026)

**Desktop (macOS, đã chạy):**

```bash
rust/target/release/vifasttts-desktop --smoke
# SMOKE OK 24000 Hz · 2.51 s · 120364 B WAV · riff=true
rust/crates/adapters/inbound/desktop/package-macos.sh --run
```

- Crate `vifasttts-desktop` (egui + rodio): local ONNX/remote HTTP, settings +
  dictionary + ETA history, phát audio, lưu WAV/SRT/VTT, chọn model/dialect.
- `.app` ~127 MB (model 86 MB + ORT 32 MB + binary 13 MB); app tự tìm model trong
  `Contents/Resources` và ORT cạnh executable (đã test smoke từ bundle).
- Chưa streaming PCM trong UI; nút Dừng phát chỉ dừng audio, job local vẫn hoàn tất.
- Package desktop kèm `vifasttts` unified CLI/TUI/server; GUI không mở TUI; desktop có nút bật
  server nội bộ để extension remote kết nối `http://127.0.0.1:<port>`.

**Android (đã chạy):**

- `mobile/android`: APK 110 MB (FP32), JNA C ABI + ORT Android 1.31.1;
  emulator Android 16 arm64, câu mặc định → WAV **4,412 s / 24 kHz / mono PCM16**.
- Emulator chạy `-no-audio`; `MediaPlayer.prepare/start` không lỗi nhưng chưa
  kiểm tai; cần emulator/thiết bị có audio.
- Script tái lập: `mobile/android/build.sh`.

**iOS (đã chạy simulator 29/10/2026):**

- `mobile/ios` có SwiftUI + C bridge + XcodeGen project + build script.
- Xcode 27.1; simulator iOS 27.0; ORT static 1.30.0 (`api-30`).
- Local FFI: `Xong local · 2.77 s`; Remote `/api/tts`: `Xong remote · 2.77 s`.
- `.vfa/.vfts` + model browser + remote Server URL/token.
- Thiết bị thật vẫn cần ký Apple Developer + ORT device slice.

### 15.8c CI/CD đa nền tảng (29/10/2026)

Workflow `.github/workflows/ci.yml` (push main/PR/tag, dispatch):

| Job | Nội dung |
|---|---|
| `rust` | fmt + clippy + test trên macOS/Ubuntu/Windows; wasm check |
| `python-lint` | Python 3.12 + `ruff check .` (full pytest local do suite torch/onnx nặng) |
| `web-extension` | build wasm-bindgen + ORT Web; zip extension; Vite web dist |
| `desktop` | macOS `.app` zip, Linux tar.gz, Windows zip (kèm CLI/TUI/server sidecar); `--smoke` từng gói |
| `server` | macOS/Linux/Windows: binary + ORT + model + launcher; artifact riêng |
| `android` | SDK 36/NDK 28.2, cargo-ndk, APK, upload |
| `ios` | macOS runner: Rust staticlib + ORT pod `1.30.0` + xcodebuild simulator; artifact có model |
| `release` | tag `v*`: tải artifact và tạo/cập nhật GitHub Release |

- Model CI lấy từ HuggingFace `dvchd/vifasttts-ngochuyen-small/onnx` (pin sha256), ORT
  desktop/Android tải bản 1.31.1; iOS dùng pod archive 1.30.0 vì CocoaPods chưa
  có 1.31.1.
- iOS job build simulator với ORT static 1.30.0; local/remote đã test trên máy
  dev. Artifact simulator được phát hành; thiết bị thật cần ký developer.
- Linux/Windows desktop package đã có script; CI là nơi build/kiểm tra thật,
  máy dev hiện chỉ test macOS.

### 15.9 Lệnh parity và benchmark

```bash
# Build một lần
cd rust && cargo build --release -p vifasttts-cli -p vifasttts-tools -p vifasttts-parse && cd ..

# Frontend: matrix 49.104 + curated (dùng output đã sinh)
.venv/bin/python tools/rust_parity.py --matrix --reuse \
  --output artifacts/rust_parity_matrix

# Full custom reading
.venv/bin/python tools/rust_parity.py --full-custom \
  --output artifacts/rust_parity_full

# Fuzz thực tế (NFC; không có dấu kết hợp rời)
.venv/bin/python tools/rust_parity.py --fuzz 3000 \
  --output artifacts/rust_parity_fuzz_clean

# Fuzz adversarial (dấu kết hợp rời; có ngoại lệ đã ghi)
.venv/bin/python tools/rust_parity.py --fuzz 3000 --fuzz-raw \
  --fuzz-combining --reuse --output artifacts/rust_parity_fuzz

# Server tối thiểu
cargo run --release -p vifasttts-cli -- server --port 8000

# C ABI
cargo build --release -p vifasttts-ffi

# Benchmark trong một process
rust/target/release/vifasttts bench --text "..." --runs 20 --warmup 3
```

`--reuse` chỉ dùng lại input/expected đã sinh; bỏ nó để sinh lại. Không commit
`artifacts/`.

---

## 16. Karaoke/timing (28/10/2026)

### 16.1 Nguyên tắc

- **Canonical là JSON** `KaraokeDocument`; SRT/VTT chỉ là export.
- Timing lấy từ `slot_durations` của acoustic — cùng tensor sinh mel, nên khớp
  audio đến từng frame (~1 hop = 10,67 ms @ 24 kHz).
- Không chạy forced alignment ở MVP; nếu chất lượng ngữ nghĩa chưa đủ mới thêm
  post-pass.
- Timing phải được sinh **trong cùng lần synth** với audio; không synth hai lần.

### 16.2 Dữ liệu

`slot_durations [1+5N]` = `lead` + 5 slot mỗi âm tiết `(O, M, N, C, G)`.
Với âm tiết `i`:

```text
base   = 1 + 5*i
voiced = slot[base] + slot[base+1] + slot[base+2] + slot[base+3]
gap    = slot[base+4]
start  = lead + Σ(voiced[j] + gap[j]) với j < i
end    = start + voiced
sample = frame * hop_length
ms     = sample * 1000 / sample_rate
```

- `fixed_pauses`/steady: gate=1.01 → gap model = 0; pause ngoài được cộng vào
  `sample_offset` giữa các chunk.
- `speed`: `slot_durations` đã scale trong graph; dùng output, không tự chia.
- iSTFT `center=True`: audio dài `(T-1)*hop`; clamp cue cuối.

### 16.3 JSON

```json
{
  "version": 1,
  "sample_rate": 24000,
  "duration_ms": 2378,
  "units": [
    {"text":"Xin","start_ms":0,"end_ms":224,"kind":"syllable"}
  ],
  "lines": [
    {"text":"Xin chào","start_ms":0,"end_ms":810,"units":[...]}
  ]
}
```

- `units`: highlight từng âm tiết.
- `lines`: cue SRT/VTT (gộp theo dấu câu, tối đa ~80 ký tự).
- `punctuation`, `sentence_end`, `phrase_end` giữ từ parser để group line.

### 16.4 Bề mặt đã nối

| Nơi | API |
|---|---|
| `vifasttts-text` | `KaraokeDocument`, `TimedUnit`, `to_srt`, `to_vtt`, `to_vtt_karaoke` |
| `vifasttts-engine` | `Synthesis.karaoke`; `synthesize_stream_with_units` |
| `vifasttts-cli` | `synth --srt --vtt --vtt-karaoke --karaoke`; `stream` cũng có |
| `vifasttts-http-server` | `POST /api/tts` với `"karaoke": true` → JSON + audio base64; `POST /api/tts/stream` → NDJSON `units`/`audio`/`done` |
| `vifasttts-ffi` | `vifasttts_synthesize_karaoke` → WAV + JSON (free bằng `vifasttts_buffer_free` / `vifasttts_string_free`) |

### 16.5 Ví dụ

```bash
rust/target/release/vifasttts synth \
  --text "Xin chào các bạn, hôm nay trời đẹp." \
  --output out.wav --srt out.srt --vtt-karaoke out.karaoke.vtt \
  --karaoke out.json

curl -sS -X POST http://127.0.0.1:8000/api/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"Xin chào","karaoke":true}' > out.json

curl -sS -N -X POST http://127.0.0.1:8000/api/tts/stream \
  -H 'Content-Type: application/json' \
  -d '{"text":"Xin chào"}' > out.ndjson
```

### 16.6 Giới hạn đã biết

- Text hiển thị hiện là **normalized/syllable**; số/ngày/STEM nở âm tiết nên
  chưa map 1-1 về ký tự gốc. Nếu cần SRT hiển thị đúng văn bản gốc, phải thêm
  offset/ký tự gốc từ normalizer.
- Chưa đo sync trên corpus lớn; mới kiểm câu ngắn + speed/fixed pauses.
- Chưa xử lý Opus/MP3 encoder delay; WAV/PCM là đường chính xác.
- `to_vtt_karaoke` là WebVTT inline timestamp; client cần render highlight.
- Chưa có UI karaoke; mới có dữ liệu và export.

---

## 17. Mô hình crate & luồng gọi (28/10/2026)

### 17.1 Sơ đồ phụ thuộc

Mũi tên = “được phép gọi/phụ thuộc”, không phải data flow runtime:

```text
text ──┬──► engine ◄── ports ◄── ort       (native)
audio ─┘       ▲             ◄── ort-web    (wasm32)
               │
        ┌──────┴──────┐
      native        browser
        ▲              ▲
 cli/tools/ffi/http-server  web/extension

text ──► http-client (karaoke types)
text ──► parse (text-only CLI)
```

- `text`, `audio`, `ports` không phụ thuộc crate nào trong workspace.
- `ports` khai báo **async** `AcousticModel`/`VocoderModel`; đây là port
  duy nhất để native và browser dùng chung engine.
- `engine` phụ thuộc `text` + `audio` + `ports`; **không** biết ORT/fs; mọi
  method synth là async.
- `ort` phụ thuộc `ports` (implement trait) + `text` (vocab hash); **không**
  phụ thuộc `engine`. Method async nhưng ORT native trả Ready ngay.
- `ort-web` phụ thuộc `ports` + `js-sys`/`wasm-bindgen`; implement async
  backend bằng cách chờ Promise ORT Web. **Không** phụ thuộc `engine`/`browser`.
- `native` phụ thuộc `engine` + `ort`; là adapter native, bọc async engine bằng
  `block_on` và expose API sync cho CLI/server/FFI.
- `browser` phụ thuộc `text` + `audio` + `engine` + `ort-web`; là adapter browser,
  expose API async. Ngang hàng `native`, không chứa loop synth riêng.
- `http-client` phụ thuộc `text` (parse KaraokeDocument) + HTTP; **không** ORT.
- `cli` dùng `native` (local) hoặc `http-client` (remote); `tools`/`ffi`/`http-server`
  dùng `native`; `parse` chỉ dùng `text`.

Không có vòng phụ thuộc. `ort`/`ort-web` → `ports` là dependency inversion:
ports là port, hai crate kia là adapter.

Trait async **không ràng buộc `Send`** để future ORT Web (`!Send`) dùng được.
Native không poll future trên executor async: `native` gọi `block_on` trên
thread blocking (CLI/server dùng `spawn_blocking`), nên ORT native vẫn chạy
đồng bộ và không cần `Send` cho future.

### 17.2 Trách nhiệm và ranh giới

| Crate | Được phép biết | Không được làm | Test |
|---|---|---|---|
| `text` | Unicode, parser, vocab, chunk, karaoke text | ORT, fs, thread, model, audio DSP | unit + golden + fuzz, không cần model |
| `audio` | iSTFT, sharpen, fade, WAV | text, ORT, fs, model | unit DSP |
| `ports` | async trait + `MelSpectrogram`/`ComplexSpectrogram`/`ModelInfo` | text/audio/engine/ORT | compile-time |
| `engine` | `text`, `audio`, `ports`, options, streaming, timing | `ort`, đọc file, HTTP/CLI | fake async backend + unit |
| `app` | command/event/ETA headless | DOM, Chrome, ORT, native audio | unit |
| `ort` | `ports`, `text` (vocab), `ort` crate | `engine`, luật ngôn ngữ, CLI/server/FFI | integration với model |
| `ort-web` | `ports`, ORT Web callback (JS), shape contract | `engine`, `browser`, audio/chunk/karaoke | wasm build + browser |
| `native` | `engine`, `ort`, manifest, sync `block_on` | orchestration chi tiết, parse/audio | integration + facade |
| `mobile` | `native`, `audio-sink`, `model-source` | UI/FFI, audio platform cụ thể | integration + device |
| `browser` | `text`, `audio`, `engine`, `ort-web` | ORT native, runtime, loop synth riêng | wasm build |
| `http-client` | `text` (KaraokeDocument), HTTP | ORT/model, logic TTS | HTTP mock/e2e |
| `cli` | `text` (options), `audio` (WAV), `native` (local), `http-client` (remote) | logic TTS | CLI/e2e |
| `tools` | `native` (mel/synth-ids) | logic TTS production | parity |
| `parse` | `text` | ORT/model/audio | parse/e2e |
| `ffi` | `native`, C ABI | ORT type lộ ra ngoài | ctypes/host app |
| `http-server` | `native`, axum | logic TTS | HTTP/e2e |

`vifasttts-tools` link `native` cho `mel-ids`/`synth-ids`; `vifasttts-parse`
chỉ depend `text` nên không kéo ORT.

Quy tắc thực thi:

1. `text` không có `std::fs`, không import `ort`/`engine`/adapter.
2. `audio` không import `text`/`engine`/`ort`.
3. `ports` không import crate nào trong workspace.
4. `engine` không import `ort`/`ort-web`/`ports`; chỉ gọi trait; không đọc file.
5. `ort`/`ort-web` không import `engine`/adapter; chỉ implement trait.
6. Chỉ `native` construct/wire `AsyncSynthesisEngine` + `OrtAcousticModel`/`OrtVocoderModel`; chỉ
   `browser` construct/wire `AsyncSynthesisEngine` + `OrtWebAcousticModel`/`OrtWebVocoderModel`.
   Adapter không `use ort` trực tiếp; CLI đọc metadata qua `native::NativeEngine::info()`.
7. Adapter không chứa chunk/parse/model; chỉ map input/output.
8. Karaoke type/format ở `text`; timing từ model ở `engine`; transport ở adapter.

### 17.3 Luồng gọi khi synth local

```text
CLI synth / FFI synthesize / server /api/tts
  → native::load / from_bytes / load_verified
      → ort::load_paths / from_bytes
          → ORT session + metadata + SHA256 + manifest verify
          → OrtAcousticModel, OrtVocoderModel, ModelInfo
      → AsyncSynthesisEngine::new(acoustic, vocoder, info)
  → native::NativeEngine::synthesize (sync wrapper)
      → block_on(async engine.synthesize)
          → text::chunk_text / parse_text / vocab
          → AcousticModel::run(...).await       (OrtAcousticModel)
          → audio::sharpen_mel
          → VocoderModel::spectrogram(...).await (OrtVocoderModel)
          → audio::istft / postprocess / wav_bytes
          → text::karaoke::KaraokeDocument (từ slot_durations)
```

`native` **không** chứa logic synth; nó chỉ load/verify/wire, bọc async và
forward. `vifasttts-engine::SynthesisEngine` là concrete generic async, không phải trait.
`block_on` ở native chỉ là cầu nối vì ORT backend trả Ready ngay.

CLI remote:

```text
vifasttts-cli --server URL
  → vifasttts-http-client
      → POST /api/tts (WAV hoặc karaoke JSON)
      → POST /api/tts/stream (NDJSON)  [nếu client hỗ trợ]
```

`http-client` chỉ parse JSON/karaoke; không biết ORT hay model local.

### 17.4 Luồng mobile/embedded

```text
SwiftUI / Compose / Flutter
  → C ABI (vifasttts-ffi) hoặc UniFFI
      → vifasttts-mobile::MobileRuntime
          → native::from_bytes / from_source
          → native::NativeEngine (sync wrapper)
              → block_on(async engine::SynthesisEngine)
                  → text + audio + OrtAcousticModel/OrtVocoderModel
          → AudioSink (AVAudioEngine/AAudio)
```

- Model lấy từ asset/download → bytes, không cần path.
- Không mở localhost server trên mobile.
- Karaoke: `vifasttts_synthesize_karaoke` trả WAV + JSON; UI tự highlight.
- `vifasttts-mobile` là composition root; `vifasttts-ffi` chỉ là cửa vào C ABI.
- Extension local dùng `vifasttts-browser`; dictionary/ETA của extension gọi wasm
  `vifasttts-app` (`dictionary_json`, `eta_estimate`). Settings form vẫn là JS vì
  `chrome.storage` là adapter UI.

### 17.5 Luồng server/web

```text
Web/Extension/CLI remote
  → HTTP /api/tts | /api/tts/stream
      → vifasttts-http-server (axum)
          → native::NativeEngine (Mutex/pool)
              → engine + ort
```

- Server không gọi trực tiếp `ort`; chỉ dùng `native`.
- `/api/tts` mặc định WAV; `karaoke:true` trả JSON + audio base64.
- `/api/tts/stream` trả NDJSON: `units` → `audio` (PCM16 base64) → `done`.
- Local server mode dùng **cùng binary**; chỉ khác host/token/auth.
- Request `/api/tts` nhận `dictionary` text; server parse bằng
  `vifasttts-app::parse_dictionary` (dùng chung với extension/desktop), không có
  parser `key = value` riêng trong server.

### 17.6 Target / feature

| Crate | native | wasm32 | mobile | Ghi chú |
|---|---|---|---|---|
| `text` | ✅ | ✅ (đã check) | ✅ | không ORT/fs/audio |
| `audio` | ✅ | ✅ (đã check) | ✅ | chỉ FFT |
| `ports` | ✅ | ✅ (đã check) | ✅ | không I/O |
| `audio-sink` / `transport` / `settings` / `model-source` | ✅ | ✅ (contract) | ✅ | port thuần |
| `engine` | ✅ | ✅ | ✅ | async, text+audio+ports |
| `app` | ✅ | ✅ | ✅ | command/event/ETA headless |
| `ort` | ✅ | ❌ | ✅ (ORT mobile) | async trait; `load-dynamic` native |
| `ort-web` | — (rỗng) | ✅ | ❌ | chỉ có nghĩa với ORT Web/JS |
| `native` | ✅ | ❌ | ✅ | adapter native, sync `block_on` |
| `mobile` | ✅ (desktop build) | ❌ | ✅ | composition root iOS/Android |
| `desktop` | ✅ | ❌ | ❌ | GUI egui + rodio; dùng native/http-client |
| `tui` | ✅ | ❌ | ✅ | library + binary; CLI không args mở TUI |
| `browser` | ❌ (chỉ wasm) | ✅ | ❌ | adapter browser, async |
| `http-client` | ✅ | ✅ (HTTP) | ✅ | ureq; không ORT |
| `cli` | ✅ | ❌ | ❌ | production |
| `tools` | ✅ | ❌ | ❌ | parity model |
| `parse` | ✅ | ✅ (text-only) | ✅ | không ORT |
| `ffi` | ✅ | ❌ | ✅ | cdylib/staticlib |
| `http-server` | ✅ | ❌ | ❌ | axum |

### 17.7 Kiểm tra ranh giới

```bash
cd rust
cargo tree -p vifasttts-text          # không thấy ort/engine/audio
cargo tree -p vifasttts-audio         # chỉ rustfft
cargo tree -p vifasttts-ports         # không workspace deps
cargo tree -p vifasttts-engine        # text + audio + ports
cargo tree -p vifasttts-ort           # ports + text + ort
cargo tree -p vifasttts-ort-web       # ports + js-sys/wasm-bindgen; không engine
cargo tree -p vifasttts-native       # engine + ort
cargo tree -p vifasttts-browser       # engine + ort-web + text/audio
cargo tree -p vifasttts-http-client   # text + ureq; không ORT
cargo tree -p vifasttts-tools         # native (mel/synth-ids)
cargo tree -p vifasttts-parse         # text only; không ORT/ureq
cargo check -p vifasttts-text -p vifasttts-audio -p vifasttts-ports \
  -p vifasttts-engine -p vifasttts-ort-web -p vifasttts-browser \
  --target wasm32-unknown-unknown
```

- CI đã có bước wasm cho text/audio/ports/engine/ort-web/browser.
- Nếu `text`/`audio`/`ports` xuất hiện `ort` trong `cargo tree`, đó là lỗi
  kiến trúc, không phải “tạm thời”.

### 17.8 Thêm backend mới

1. Tạo crate `vifasttts-<adapter>` phụ thuộc `vifasttts-ports` (+ `text` nếu
   cần vocab) — **không** phụ thuộc `engine`.
2. Implement **async** `AcousticModel`/`VocoderModel`, trả `AcousticResult`
   (mel + `slot_durations` nếu có).
3. Tạo loader `load_*`/`from_bytes`, metadata/hash/manifest; hoặc constructor
   callback nếu backend do host (JS/mobile) chạy.
4. Thêm constructor/type alias trong adapter tương ứng: native → `native`,
   browser → `browser`; **không** thêm loop synth vào adapter.
5. Giữ nguyên adapter API; chỉ đổi wiring.
6. Đo parity mel/PCM + karaoke timing; ghi vào `docs/ACOUSTIC_V2.md`/`RUST_PORT.md`.

Không sửa `text`/`audio` chỉ để đổi backend. Chỉ sửa `text` nếu contract ngôn ngữ
thay đổi; `audio` nếu contract DSP thay đổi.

### 17.9 Voice local/cloud (kế hoạch)

```text
VoiceCatalog (native)
  ├── LocalVoiceProvider  → SynthesisEngine<Ort...> (mặc định)
  └── CloudVoiceProvider  → HTTP client (chưa làm)
```

- `voice_id` quyết định provider; mặc định local.
- Cloud là lựa chọn chủ động của user, không silently fallback.
- `text`/`audio`/`engine` không biết “local/cloud”; chỉ adapter/runtime biết.
- Server VPS host cloud voices; local server chỉ host voice local.


---

## 18. Browser local (WASM + ORT Web, 28/10/2026)

### 18.1 Kiến trúc

```text
text/audio/ports Rust ──► vifasttts-engine (async)
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                     native                     browser
                         │                         │
                         ▼                         ▼
                    ort (native)             ort-web (JS callback)
                         │                         │
                         ▼                         ▼
                   ONNX Runtime              ONNX Runtime Web
```

- Model chạy **trong browser** bằng `onnxruntime-web`; không server, không gửi text.
- `vifasttts-engine` async dùng chung native/browser; `SynthesisPlan` chunk/parse/pause,
  `SynthesisAssembler` ghép audio/karaoke.
- `vifasttts-ort-web` là **backend thật** cho browser: nhận callback JS, chờ
  Promise, kiểm shape rồi trả `AcousticResult`/`ComplexSpectrogram`.
- `vifasttts-browser` là **adapter** ngang hàng `vifasttts-native`: gọi engine,
  không còn loop/chunk/audio riêng trong `synthesize`.
- `web/app.js` chỉ còn nạp model/session, cung cấp callback, phát audio/hiển thị.

```text
native :  native adapter  ──► async engine ──► AcousticModel/VocoderModel ◄── ort
browser:  browser adapter ──► async engine ──► AcousticModel/VocoderModel ◄── ort-web
```

### 18.2 Build

```bash
cargo install wasm-bindgen-cli --version 0.2.129  # một lần
./web/build.sh   # copy cả *.wasm + *.mjs của ORT Web
cd web && npm run dev
```

Chi tiết: `web/README.md`.

### 18.3 Vì sao không dùng tract?

Đã thử `tract-onnx 0.23.9` (pure Rust, wasm-friendly):

- native macOS: crash `SIGILL` trong `apple_amx_mmm_f32_32x32` — tract bật AMX
  trên Apple Silicon nhưng instruction không chạy được trên M6/macOS 27;
  `TRACT_CPU_ISA=-apple-amx` thì tránh crash.
- sau đó fail ở `CumSum` (`TDim is not a number`) trong `length_regulator`;
  đây là op acoustic bắt buộc. Chưa có patch tract trong repo.
- Vì vậy browser dùng **ORT Web** (op coverage đầy đủ, đã tối ưu wasm) thay vì
  tract. `vifasttts-tract` không được đưa vào workspace.

### 18.4 Giới hạn

- Model ~86 MB: lần đầu tải lâu; cần cache/HTTP cache; chưa có quantize.
- ✅ Đã chạy thử bằng **Chrome for Testing 156** (qua `agent-browser`):
  model load, synth local, audio, karaoke, SRT/WebVTT hoạt động. `web/vite.config.js`
  phải trả ORT `.mjs` nguyên bản vì Vite chặn import module từ `public/`.
- ORT Web WASM: chậm hơn native; `numThreads=1` mặc định (threads cần COOP/COEP).
- Chưa Web Worker/WebGPU/WebNN; UI có thể đứng khi synth câu dài.
- Karaoke timing từ `slot_durations`; text hiển thị theo normalized/syllable.
- License dataset CC-BY-NC vẫn áp dụng; chưa phát hành công khai.
- Chưa có service worker/offline cache; demo cần model files cùng origin.

### 18.5 Việc tiếp theo

1. Web Worker + transferable PCM để không block UI.
2. Cache model bằng Cache Storage/OPFS + hash.
3. Quantize FP16/INT8 + đo chất lượng; giảm 86 MB.
4. WebGPU/WebNN nếu trình duyệt hỗ trợ; đo lại.
5. Đóng gói `web/` thành PWA; license/notices.

---

## 19. Chrome extension MVP (28/10/2026)

Mã: `extension/`; build: `./extension/build.sh`; hướng dẫn: `extension/README.md`.

### 19.1 Kiến trúc

```text
popup.html/js                  context menu / Đọc trang
  │ chrome.runtime.sendMessage       │
  └──────────────┬──────────────────┘
                 ▼
background.js (MV3 service worker)
  │ ensure offscreen; route request
  ▼
offscreen.html/js
  ├── vifasttts-browser  (async engine)
  ├── vifasttts-ort-web (async backend)
  ├── ORT Web         (model inference)
  └── Cache Storage   (model tải remote)
```

- Service worker không có DOM/audio → offscreen document chạy wasm/ORT.
- Offscreen tạo Blob WAV URL; popup phát audio hoặc offscreen phát ẩn.
- Local: model bundle `extension/models/` hoặc tải từ **Model base URL** rồi cache.
- Remote: gọi `POST /api/tts` (JSON karaoke + audio base64) tới server cấu hình.
- Host permission: localhost mặc định; server khác xin quyền qua `chrome.permissions`.
- Không có `ttsEngine`/`tts`; một bản duy nhất, ít cảnh báo quyền hơn.

### 19.2 Đã kiểm chứng

- Load unpacked extension ID `bilbhokjcelbelnipbojekndmdcbpalp` bằng Chrome for Testing 156.
- Local: synth “Xin chào…”, 8 âm tiết, audio 2,38 s, SRT/karaoke đúng.
- Remote: server axum `127.0.0.1:8123`, 11 âm tiết, audio 2,83 s.
- Cache first-run: tải `acoustic.onnx` + `vocoder.onnx` từ HTTP local, cache;
  tắt server + mở lại profile vẫn synth được từ cache.
- Context-menu reader path: mở `popup.html?text=...&autorun=1`, tự synth
  (1,73 s, 7 âm tiết).
- Direct hidden read: `speak-selection` phát audio qua offscreen, badge
  `…/▶/!`.
- Local stream: Chrome for Testing, audio PCM theo chunk + karaoke; lần chạy
  sau hiện ước tính từ history.
- Remote stream: `/api/tts/stream`, NDJSON units/audio/done.
- Từ điển local `xyzabc = ích zét`: karaoke 2 unit nhưng audio “a” do
  `zét` fallback; `ích dét` VALID. Đã ghi cảnh báo trong UI/README.

### 19.3 Đã bổ sung

- ✅ Bỏ `ttsEngine`/`tts`; một bản duy nhất, không cảnh báo quyền đọc TTS.
- ✅ Context menu nhiều chế độ:
  - “Đọc đoạn bôi đen (theo cài đặt)”;
  - “Đọc ẩn” — offscreen phát audio, badge;
  - “Đọc trong popup” — `chrome.action.openPopup()` + `storage.session`;
  - “Mở tab đọc” — reader tab;
  - “Đọc toàn bộ trang” — `activeTab` + `scripting.executeScript`.
- ✅ Popup có **Đọc trang**, chọn cách bôi đen, đọc ẩn/popup/tab trong Cài đặt.
- ✅ Từ điển local trong popup (`key = cách đọc`), lưu `chrome.storage.local`;
  wasm merge với built-in overrides qua `synthesize_with_options`; remote gửi
  `overrides` (cả Python demo và Rust server đã đọc field này).
- ✅ Stream: local dùng `synthesize_stream_with_options` + Web Audio; remote
  đọc NDJSON `/api/tts/stream`; nút Dừng; karaoke unit theo chunk.
- ✅ Ước lượng thời gian: lưu 20 lần chạy gần nhất (`mode`, chars, elapsed,
  audio seconds), lấy median ms/char của 8 lần cùng mode.
- ✅ Local bỏ cắt 3000 ký tự; page/selection cap 50.000; remote vẫn theo
  `max_chars` của server.
- ✅ Remote domain VPS: optional host permission `https://*/*`, token Bearer;
  cần TLS hợp lệ.
- ✅ Logo/icon extension (16/32/48/128) resize từ `resources/brand/`
  (cùng brand với Python `deploy/vifasttts_demo/static/brand/`).

### 19.4 Chưa có

- Native messaging tới desktop app.
- Hash/manifest verification cho model tải remote.
- Web Worker riêng cho synth nền; stream hiện chạy trong offscreen.
- Voice catalog/multi-voice.
- Test Edge thật (chưa cài Edge trên máy này).
- `ttsEngine` (đã bỏ có chủ đích để giảm quyền).
