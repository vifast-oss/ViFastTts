# V18.51 — Agent 0: audit nhãn/segment bằng ASR

> **Nguyên văn quyết định nằm trong `docs/handoff/DECISIONS.md` mục V18.51** (đăng ký trước).
> Tệp này chỉ là con trỏ theo quy ước `V<NN>_agent0.md`; không chứa trạng thái hiện hành.
>
> - Phạm vi: không train, không đổi production.
> - Audit 20 câu V18.50 → toàn bộ data; truy nguyên code; sửa thử 40 clip với đệm 0,05 s.
> - ASR: faster-whisper small 1.2.1, int8 (ghi rõ trong báo cáo).
> - Trạng thái hiện hành: `docs/handoff/TRANG_THAI.md`.
> - Báo cáo thực thi: `docs/handoff/V1851_agent2.md`.
