# Giải thích các cài đặt

Tài liệu này là nguồn chung cho phần **Giải thích cài đặt** trong mọi UI.
Mục tiêu: người không biết TTS vẫn hiểu mỗi nút dùng để làm gì.

## Tốc độ

`1.00×` là tốc độ bình thường. Nhỏ hơn `1` đọc chậm hơn, lớn hơn `1` đọc nhanh hơn.
Miền hợp lệ `0.5–2.0×`. Tốc độ được đưa trực tiếp vào model, không phải chỉ kéo dài audio.

## Độ nét mel (alpha)

Mức làm nét phổ mel trước khi vocoder tạo waveform.

- `1.5` là mặc định của model N0.
- Cao hơn: nét hơn, nhưng dễ làm rõ cả rè/nhiễu.
- Thấp hơn: mềm hơn, có thể hơi mờ.

## Pause cố định

Chèn khoảng lặng theo dấu câu thay vì để model tự dự đoán:

- khoảng `0.25 s` sau phẩy;
- khoảng `0.55 s` sau chấm/hỏi/than.

Mặc định **tắt** vì model tự ngắt nghỉ tự nhiên hơn. Bật khi cần nhịp đọc đều, dễ đoán.

## Peak normalize

Đưa đỉnh của **toàn bộ WAV** về `−3 dBFS` để tránh clip và ổn định âm lượng.
Có thể làm to cả tiếng nền/rè. **Không dùng khi stream** vì stream chỉ có từng chunk,
không biết đỉnh của cả file.

## Stream

Tổng hợp đến đâu phát ngay đến đó thay vì chờ cả câu. Giảm thời gian chờ, nhưng:

- không dùng được peak normalize;
- WAV/SRT/VTT chỉ có sau khi stream xong (nếu bật lưu).

## Max ký tự/chunk

Độ dài tối đa của một đoạn đưa vào model. Câu dài tự động được chia nhỏ.

- Nhỏ: ít RAM, nhưng nhiều lần ngắt/chia hơn.
- Lớn: ít ngắt hơn, nhưng chậm và nặng hơn.
- Miền hợp lệ `50–5000`; demo web mặc định `300` ký tự/chunk.

## Phương ngữ

`Bắc`, `Trung`, `Nam` đổi cách đọc một số từ qua normalizer (ví dụ một số vần/âm).
Model N0 hiện là **giọng Bắc**; muốn giọng nền đổi hoàn toàn cần model được train cho
vùng đó, không chỉ đổi dropdown.

## Resolve OOV

**OOV** = *out-of-vocabulary* = token lạ không có trong từ điển hoặc không parse được
thành âm tiết Việt: tên riêng, viết tắt, từ tiếng Anh, mã sản phẩm, teencode…

Khi bật:

1. thử tra từ điển viết tắt/tên sản phẩm/English có sẵn;
2. nếu token trông như viết tắt (chữ hoa, có số/ký hiệu, hoặc từ ngắn ≤4 chữ), đánh vần
   bằng tên chữ cái tiếng Việt — ví dụ `VNG` → “vê en giê”;
3. nếu vẫn không giải được, dùng fallback an toàn để không crash.

Khi tắt: giữ fallback, không tự đoán. Nếu bật mà đọc vẫn sai, thêm quy tắc vào
**Từ điển** (hoặc **Cách đọc token-level**).

## Từ điển local

Mỗi dòng một quy tắc `từ = cách đọc`, ví dụ:

```text
VPS = vi pi ét
TP.HCM = thành phố hồ chí minh
```

Quy tắc được áp trước normalizer/STEM. Ở chế độ remote, từ điển được gửi kèm request;
server cũ có thể bỏ qua.

## Cách đọc token-level

Giống từ điển nhưng dành cho **cụm/token cụ thể**, ưu tiên trước các quy tắc có sẵn.
Dùng khi cần đổi cả cụm, tên sản phẩm hoặc domain:

```text
ViFastTts = vi phát tê tê ét
khongdich.com = không dịch chấm com
```

## Local và Remote

- **Local**: model chạy trên máy/trình duyệt; riêng tư hơn, không cần server.
- **Remote**: gửi văn bản tới server TTS; server quyết định model và có thể bỏ qua
  tùy chọn nếu là server cũ.

## RTF

`RTF = thời gian xử lý / thời lượng audio`. RTF nhỏ hơn `1` là nhanh hơn thời gian thực.
Ví dụ RTF `0.05` nghĩa là xử lý nhanh gấp khoảng 20 lần so với nghe.
