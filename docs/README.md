# Tài liệu ViFastTts — bản đồ & trạng thái

> **Cập nhật:** 29/10/2026 · **Trạng thái hiện hành:** xem `docs/handoff/TRANG_THAI.md`.
> Đây là **trang mục lục duy nhất** cho toàn bộ `docs/`. Khi có mâu thuẫn, thứ tự ưu tiên:
> `TRANG_THAI.md` (trạng thái) → `docs/README.md` (mục lục) → tài liệu chuyên đề đang hiệu lực
> → tài liệu tham chiếu → `docs/archive/` (lịch sử, không dùng để quyết định).

## 0. Đọc nhanh (5 phút)

| Nếu bạn muốn… | Đọc |
| --- | --- |
| Biết **hiện tại đang chạy gì** | `docs/handoff/TRANG_THAI.md` |
| Chạy thử model Ngọc Huyền | `README.md` mục 0 · `docs/NGOC_HUYEN.md` |
| Hiểu kiến trúc as-built | `docs/ARCHITECTURE.md` · `docs/MODEL_FLOW.md` |
| Hiểu cách tách âm tiết | `docs/SYLLABLE_GUIDE.md` · `docs/FRONTEND.md` |
| Hiểu chuẩn hoá số/STEM | `docs/NORMALIZER.md` · `docs/STEM_NORMALIZER.md` |
| Hiểu nhanh các nút cài đặt (tốc độ, OOV, peak…) | `docs/SETTINGS_GLOSSARY.md` |
| Xem thiết kế/đo acoustic v2 | `docs/ACOUSTIC_V2.md` |
| Chấm một checkpoint | `docs/EVAL_TOOLS.md` |
| Benchmark N0 + model ngoài | `docs/BENCHMARK_N0.md` |
| Train lại N0 | `docs/TRAINING_N0.md` |
| Triển khai ONNX/demo | `docs/handoff/N0_DEPLOY.md` |
| Xem quyết định Q | `docs/Q_ONSET.md` |
| Xem kế hoạch + trạng thái port Rust | `docs/RUST_PORT.md` |
| Cài đặt desktop/server/TUI/extension | `docs/INSTALL.md` |
| Phát hành Chrome/Edge extension | `docs/EXTENSION_STORE.md` |
| Kiểm tra parity tính năng các UI | `docs/UI_PARITY.md` |
| Rà soát tái sử dụng UI/logic & hợp đồng chung | `docs/UI_REUSE_AUDIT.md` |
| Hợp đồng HTTP/model API dùng chung | `docs/API_CONTRACT.md` |
| Dùng engine ONNX + stream từ Python | `docs/PYTHON_ENGINE.md` |
| Định dạng model `.vfts` | `docs/VFTS_FORMAT.md` |
| Kênh phân phối/đóng gói | `docs/DISTRIBUTION.md` |
| Mobile: model bundle/tải nhiều giọng | `docs/MOBILE_MODELS.md` |
| Phân phối `.vfts`/`.vfa` lên HF/GitHub | `docs/MODEL_DISTRIBUTION.md` |
| Tìm/tải model từ HuggingFace | `docs/MODEL_SEARCH.md` |
| Palette/font/icon dùng chung | `design/tokens.json` |
| Xem lịch sử cũ | `docs/archive/README.md` |

## 1. Trạng thái hiện tại (tóm tắt)

- **Live:** https://tts.vifast.org/ — ONNX FP32, `arch=v2_slot5`,
  `vocab_version=vi-q25-v1` / `vocab_hash`, `sharpen_alpha=1.5`, `pause_mode=model`.
- **Model đang live:** N0 Ngọc Huyền **Q-init** (`Q` = `K`, bit-exact với N0 Bắc cũ);
  checkpoint nguồn `runs/acoustic_ngochuyen_q/init_q.pt`.
- **Bản fine-tune Q 3k** (`runs/acoustic_ngochuyen_q/best.pt`) đã train/export nhưng **chưa live**;
  chỉ dùng để so tai; release tạm cũ đã xoá, artifact nằm trên [HuggingFace](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/bundles).
- **Model/ONNX cũ** thiếu `vocab_hash` không còn được hỗ trợ; **không có adapter Q→K**.
- **Test:** xem `docs/handoff/TRANG_THAI.md`; `ruff` sạch (30/10/2026).
- **Demo:** custom reading local-first, gửi duyệt khi bật checkbox, STEM examples,
  feedback/báo lỗi, admin thống kê; nội dung feedback chờ `ADMIN_PASSWORD`.

## 2. Tài liệu đang hiệu lực

### 2.1 Vận hành & model

| Tài liệu | Nội dung |
| --- | --- |
| `docs/handoff/TRANG_THAI.md` | **Nguồn sự thật duy nhất** về trạng thái, việc đang chờ, quyết định hiện hành |
| `docs/handoff/N0_DEPLOY.md` | ONNX N0/Q, service VPS, demo, admin, feedback, release asset |
| `docs/handoff/N0_RELEASE.md` | 2 release chính + preview Q + 3 mẫu VPS, asset/hash, license |
| `docs/handoff/N0_agent2.md` | Báo cáo train/đo N0 gốc; đọc cùng `N0_DEPLOY` + `TRANG_THAI` |
| `docs/handoff/NGUYEN_DATA.md` | Dataset `ngochuyen_voice`, pipeline MFA/segment/cache |
| `docs/NGOC_HUYEN.md` | Model card, license, quickstart, cách đọc, giới hạn |
| `docs/Q_ONSET.md` | Quyết định Q, parser, checkpoint/ONNX, fine-tune, validator |
| `docs/HUGGINGFACE.md` | Model repo + static Space demo |
| `docs/LICENSES.md` | Giấy phép code/model/dataset/thành phần tham chiếu |
| `docs/DEPLOYMENT.md` | ONNX Runtime, quantization, provider, HTTP server |

### 2.2 Frontend

| Tài liệu | Nội dung |
| --- | --- |
| `docs/FRONTEND.md` | Parser, profile/lexicon, segments, G2P, OOV, Q |
| `docs/NORMALIZER.md` | Số/ngày/giờ, dấu thanh, i/y, dialect profile |
| `docs/STEM_NORMALIZER.md` | Toán/LaTeX, hoá học, đơn vị vật lý, guard |
| `docs/SYLLABLE_GUIDE.md` | Giải thích âm tiết cho người không chuyên |
| `docs/G2P_VIETNAMESE.md` | Khảo sát G2P + IPA Bắc/Trung/Nam (chỉ phân tích) |
| `docs/GLOSSARY.md` | Thuật ngữ âm đầu/đệm/chính/cuối, tone, alignment |
| `docs/SETTINGS_GLOSSARY.md` | Giải thích các cài đặt UI: tốc độ, alpha, OOV, peak, stream, RTF… |

### 2.3 Model, dữ liệu, đánh giá

| Tài liệu | Nội dung |
| --- | --- |
| `docs/ARCHITECTURE.md` | Sơ đồ as-built, quyết định thiết kế, v1/v2_slot5 |
| `docs/MODEL_FLOW.md` | Luồng train → inference → export, tensor/loss, ONNX |
| `docs/ACOUSTIC_V2.md` | Nhật ký thiết kế/đo acoustic v2 (§0–§51) |
| `docs/EVAL_TOOLS.md` | Danh mục thước đo, lệnh, mốc so, bẫy thống kê |
| `docs/B0_BASELINE.md` | Mốc B0 acoustic v1 (13/10/2026) |
| `docs/DATASET_V2.md` | Ảnh chụp dataset codelung v2 (lọc, split, chuẩn hoá; 12–13/10) |
| `docs/TRAINING.md` | Quy trình train tổng quát + cảnh báo alignment |
| `docs/TRAINING_N0.md` | Run N0 Ngọc Huyền: pipeline, thời gian, chọn dữ liệu |
| `docs/TRAINING_ESTIMATES.md` | Ước lượng dữ liệu/tham số/thời gian/máy/chi phí |
| `docs/APPLE_SILICON.md` | MPS/MLX/ANE, provider ONNX trên Mac |
| `docs/DATA_PIPELINE.md` | Pipeline dữ liệu từ YouTube → manifest |
| `docs/YOUTUBE_DATASET.md` | `vifasttts youtube-fetch` và giấy phép dữ liệu |
| `docs/VOCODER_VOCOS.md` | Vocos pretrained + fine-tune, quy trình chốt (N0 dùng pretrained) |

### 2.4 Nghiên cứu & tham chiếu

| Tài liệu | Nội dung |
| --- | --- |
| `docs/TTS_ARCHITECTURE_RESEARCH.md` | Khảo sát họ kiến trúc TTS + đề xuất tương lai |
| `docs/ENGLISH_FROM_VI.md` | Đọc tiếng Anh từ kiến trúc Việt: cơ chế 5 ID, thí nghiệm splice/N=0, inventory, kế hoạch M0–M2 |
| `docs/MULTISPEAKER_EXPRESSIVE_RESEARCH.md` | Đa giọng Việt, Việt–Anh, biểu cảm, sắc thái đọc: model/dataset/license, kiến trúc, lộ trình R1–R4 |
| `docs/SYLLABLE_SYSTEMS_RESEARCH.md` | So sánh mô hình tách/gộp âm tiết + audit biên |
| `docs/VI_TTS_DATA_REFERENCE.md` | Model/dataset TTS tiếng Việt công khai |
| `docs/SOCIAL_POST.md`, `docs/SOCIAL_POST_GROUPS.md` | Nội dung công bố (không phải trạng thái kỹ thuật) |

### 2.5 Port Rust (kế hoạch + trạng thái WIP)

| Tài liệu | Nội dung |
| --- | --- |
| `docs/RUST_PORT.md` | Kế hoạch + trạng thái 29/10/2026: phạm vi, hợp đồng, phase/gate, parity, karaoke, mô hình crate, desktop/mobile, rủi ro, chi phí |
| `web/README.md` | Demo browser local: wasm frontend + ONNX Runtime Web, karaoke/SRT |
| `desktop/README.md` | App desktop egui: local ONNX/remote, settings/từ điển/ETA, phát audio, lưu WAV/SRT/VTT |
| `mobile/android/README.md` | APK local-first đã build/chạy emulator; JNA + C ABI + ORT Android |
| `mobile/ios/README.md` | Scaffold SwiftUI + script; CI simulator build; runtime/thiết bị chưa test |
| `server/README.md` | Server axum macOS/Windows/Linux, desktop → server → extension |

## 3. Kho lịch sử

`docs/archive/` giữ tài liệu **đã hoàn thành/không còn hiệu lực** để audit, **không xoá**.
Không dùng số liệu trong archive để quyết định hiện tại. Xem `docs/archive/README.md`.

- `docs/archive/design/` — thiết kế gốc, roadmap Rust.
- `docs/archive/plans/` — REBUILD/REVISION/ARCH_DISCUSSION/V2 checklist đã đóng.
- `docs/archive/reviews/` — AI review R1–R4, brief, open questions.
- `docs/archive/training/` — run @codelung cũ.
- `docs/archive/research/` — R6 diarization (kết quả lịch sử).
- `docs/archive/handoff/` — toàn bộ báo cáo vòng V08–V18.52 và dossier cũ.
- `docs/archive/status/PROJECT_STATUS_2026-10-13.md` — snapshot trạng thái 13/10.
- `docs/recording_script_v1.md`, `docs/rare_syllables_v1.txt` — output sinh kịch bản thu cũ,
  giữ tại chỗ vì `tools/build_recording_script.py` mặc định ghi vào đây; đánh dấu lịch sử.

## 4. Quy ước cập nhật

1. **Trạng thái chỉ nằm ở** `docs/handoff/TRANG_THAI.md`; `DECISIONS.md` chỉ ghi thêm,
   `EXCEPTIONS.md` chỉ ghi ngoại lệ có phạm vi.
2. Tài liệu mới phải được thêm vào bảng ở trang này.
3. Tài liệu hết hiệu lực: chuyển vào `docs/archive/` (không xoá), thêm dòng đầu
   “LỊCH SỬ — không còn hiệu lực”, rồi cập nhật mục lục và các link trỏ tới.
4. Số liệu trong tài liệu phải ghi **ngày đo + commit/checkpoint**; không chép số cũ
   sang tài liệu mới mà không kiểm lại.
5. Trước khi kết luận: chạy `pytest -q` + `ruff check .`; demo phải test tải thật.
