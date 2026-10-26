# V18.49 — Agent 0: tái lập chunk + nghe mù

> **Nguyên văn quyết định nằm trong `docs/handoff/DECISIONS.md` mục V18.49** (đăng ký trước).
> Tệp này chỉ là con trỏ theo quy ước `V<NN>_agent0.md`; không chứa trạng thái hiện hành.
>
> - Phạm vi: không train, không đổi production, không thử w khác.
> - A2: tái lập chunk trên 40 câu mới bằng checkpoint PILOT/CONTROL V18.48.
> - A3: nghe mù 28 lượt, 16 câu mới seed 1849.
> - A4: chỉ ứng viên khi A2 ĐẠT và A3 PILOT thắng; chưa đổi production.
> - Trạng thái hiện hành: `docs/handoff/TRANG_THAI.md`.
> - Báo cáo thực thi: `docs/handoff/V1849_agent2.md`.
