> **LỊCH SỬ — không còn hiệu lực (archive từ 27/10/2026).**
> Trạng thái hiện hành: `docs/handoff/TRANG_THAI.md`; mục lục: `docs/README.md`.
> Giữ để audit/tái lập, không dùng để quyết định.

# V18.52 — Agent 0: bộ dò tiếng nói ở đuôi (không ASR)

> **Nguyên văn quyết định nằm trong `docs/handoff/DECISIONS.md` mục V18.52** (đăng ký trước).
> Tệp này chỉ là con trỏ theo quy ước `V<NN>_agent0.md`; không chứa trạng thái hiện hành.
>
> - Phạm vi: không train, không đổi production, không ghi đè dữ liệu.
> - Bộ dò đuôi: hữu thanh ≥0,12 s + đỉnh RMS ≥−15 dB; hiệu chỉnh tai 40 segment + 8 đối chứng.
> - Không dùng ASR full/CER ASR small làm cổng.
> - Trạng thái hiện hành: `docs/handoff/TRANG_THAI.md`.
> - Báo cáo thực thi: `docs/archive/handoff/V1852_agent2.md`.
