# Changelog

## 2026-10-27

- Từ commit `60b5cf9`: thêm âm đầu **Q** cho chữ `qu` (onset thứ 25, ở cuối vocab;
  ID cũ 0–23 không đổi). Đây là chuẩn bị đa phương ngữ; N0 Bắc dùng Q-init (Q = K, bit-exact), fine-tune 3k là candidate.
- Checkpoint/ONNX trước commit này chưa có Q, `qu = K`, chỉ train giọng Bắc.
  Model cũ thiếu cờ `onset_has_q=true` bị từ chối rõ ràng; không có adapter Q→K.
- `D/GI/R/V` vẫn là 4 token riêng; lý do là một số thổ ngữ Bắc Trung Bộ còn phân biệt
  (Trung bộ chính và Nam gộp D/GI; Nam đọc R khác D/GI).
- Sửa override cụm/domain: key có dấu chấm/space được áp trước tách token
  (`khongdich.com = không dịch chấm com`).
- `GET /api/overrides` + nút “Xem từ điển & STEM”: hiển thị cả ví dụ quy tắc STEM nội bộ
  (hoá học/toán/vật lý/LaTeX), kèm ghi chú quy tắc người dùng được ưu tiên.
- Thêm ví dụ rule hoá học/toán/LaTeX/vật lý trong UI; textarea 3 dòng đủ cao;
  cho phép ký tự `>`/`<` trong rule literal (vẫn escape khi hiển thị admin).
- Override cụm/domain tự gửi duyệt khi tạo âm thanh (nếu checkbox bật), không cần bấm Lưu trước.
- Bố cục lại giao diện: 3 cột trên desktop, tùy chọn nâng cao và góp ý hiện ngay;
  nghỉ cố định chuyển vào tùy chọn nâng cao, kèm tooltip giải thích.
- Thêm validator cảnh báo W sau phụ âm môi, allowlist `resources/loanword_labial_w.txt`
  (`buýt`, `voan`, `boa`).
- TODO: nếu train một model chung nhiều vùng, bắt buộc thêm dialect/speaker embedding;
  train riêng từng vùng thì không cần.
