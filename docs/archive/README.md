# Kho tài liệu lịch sử (archive)

> **Không dùng để quyết định hiện tại.** Trạng thái hiện hành: `docs/handoff/TRANG_THAI.md`.
> Mục lục tài liệu đang hiệu lực: `docs/README.md`.

Các tài liệu trong thư mục này được giữ để **audit, tái lập lịch sử và tránh mất số đo**.
Không xoá, không sửa nội dung cũ; nếu cần đính chính, thêm ghi chú ở đầu tài liệu hoặc
tạo tài liệu mới trong `docs/` rồi trỏ về đây.

## 1. Đã chuyển vào archive (27/10/2026)

### Thiết kế gốc

- `design/DESIGN_V1_MIEN_BAC.md` — thiết kế v1.0 (09/10/2026)
- `design/DESIGN_V2.md` — thiết kế v2.0 (09/10/2026)
- `design/FULL_DESIGN.md` — tóm tắt thiết kế gốc
- `design/RUST_ROADMAP.md` — ý tưởng port Rust, chưa triển khai

### Kế hoạch / review / nghiên cứu đã đóng

- `plans/REBUILD_PLAN_M6.md` — kế hoạch dựng lại dữ liệu trên M6 (12/10/2026)
- `plans/REVISION_PLAN_V2.md` — kế hoạch sửa nền tảng trước base (12/10/2026)
- `plans/ARCH_DISCUSSION_M6.md` — hỏi–đáp kiến trúc/ngân sách (12/10/2026)
- `plans/V2_INTEGRATION_CHECKLIST.md` — checklist tích hợp v2_slot5 (13/10/2026, đã xong)
- `reviews/AI_REVIEW_BRIEF.md` — snapshot review 12/10/2026
- `reviews/AI_REVIEW_ANSWERS_R1.md` … `R4.md` — trả lời review R1–R4
- `reviews/OPEN_QUESTIONS_R2.md` — câu hỏi chờ chốt R2 (đã đóng)
- `research/R6_DIARIZATION_RESULTS.md` — kết quả lọc diarization (12/10/2026);
  tool `tools/diarize_filter.py` vẫn dùng được, nhưng số liệu là lịch sử.
- `training/TRAINING_RUN_CODELUNG.md` — run small @codelung cũ (12/10/2026)

### Hồ sơ các vòng cũ

- `handoff/A0_*`, `handoff/V08_*` … `handoff/V1852_*`
- `handoff/DATA_V3*`, `handoff/DROPNOISE_19_10.md`, `handoff/OVERNIGHT_18_19.md`,
  `handoff/RETRAIN_SMALL_FILT.md`, `handoff/REVIEW_BRIEF.md`,
  `handoff/CAU_HOI_CO_HANG_nghien_cuu.md`, `handoff/AGENT0_INFO_21_10.md`
- `status/PROJECT_STATUS_2026-10-13.md` (đã ở archive từ trước)

Các báo cáo trong `handoff/` có thể trỏ tới tài liệu cùng thư mục hoặc đường dẫn cũ;
đó là **nội dung lịch sử**, không phải link đang hiệu lực.

## 2. Tài liệu hiện hành (không nằm trong archive)

- Trạng thái: `docs/handoff/TRANG_THAI.md`
- Nhật ký quyết định: `docs/handoff/DECISIONS.md`
- Ngoại lệ có phạm vi: `docs/handoff/EXCEPTIONS.md`
- N0: `docs/handoff/N0_DEPLOY.md`, `N0_RELEASE.md`, `N0_agent2.md`, `NGUYEN_DATA.md`
- Model/Q: `docs/NGOC_HUYEN.md`, `docs/Q_ONSET.md`
- Kỹ thuật: `docs/ARCHITECTURE.md`, `docs/MODEL_FLOW.md`, `docs/ACOUSTIC_V2.md`,
  `docs/EVAL_TOOLS.md`, `docs/FRONTEND.md`, `docs/NORMALIZER.md`,
  `docs/STEM_NORMALIZER.md`, `docs/TRAINING_N0.md`, `docs/DEPLOYMENT.md`,
  `docs/HUGGINGFACE.md`, `docs/LICENSES.md`

## 3. Quy ước

- Không sửa tài liệu archive để “cập nhật trạng thái”; tạo bản mới trong `docs/`.
- Nếu một tài liệu archive vẫn được tham chiếu từ tài liệu hiện hành, ghi rõ
  “lịch sử” cạnh link.
- Giữ nguyên hash/số đo gốc; không làm tròn lại.
