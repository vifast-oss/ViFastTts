# Bài đăng Facebook — ViFastTts (bản chính)

> Ảnh đi kèm: `fb-vifasttts-1080x1350.png` (1080×1350 @2x = 2160×2700) ·
> nguồn HTML: `fb-vifasttts-1080x1350.html` · link quảng cáo: https://tts.vifast.org/

---

**Đọc tiếng Việt thành giọng nói — miễn phí, không cần đăng ký 🎙️**

Dán văn bản → bấm **Đọc** → nghe. Không cài app, không tạo tài khoản, không nhập thẻ.

Mình giữ đúng 4 điều ở ViFastTts:

💸 **Miễn phí thật** — mở là dùng, không quảng cáo chen ngang, không cắt bớt câu.
⚡ **Nhanh thật** — 20 giây audio xử lý chưa tới 1 giây, ngay trên CPU (RTF ≈ 0,03, tức nhanh gấp ~30 lần thời gian thực). Model chỉ 6,1 triệu tham số, không cần GPU.
📱 **Chạy trên mọi thiết bị** — điện thoại, máy tính bảng, PC, Mac, Linux: mở web là chạy. Có thêm app Windows/macOS/Linux/Android và extension Chrome/Edge, tải model về là đọc offline.
🎤 **Và bạn có thể tạo giọng của riêng mình** — toàn bộ mã nguồn mở: thu âm giọng mình, train lại, rồi thêm vào app như một giọng mới. Mỗi model là một người nói riêng — không lẫn giọng, không cần chọn speaker.

Đọc đúng chỗ khó của tiếng Việt: 25 âm đầu · 2 âm đệm · 15 âm chính · 11 âm cuối · 6 thanh điệu (264 vần), từ điển hơn 200 mục, có quy tắc riêng cho hoá học / toán / lý / LaTeX.

Dùng để làm gì?
· Nghe báo, nghe truyện khi đang bận tay
· Chuyển tài liệu, giáo trình thành audio để học
· Voice-over cho video, clip ngắn
· Gắn giọng đọc tiếng Việt vào app của bạn qua API

👉 **Thử ngay, miễn phí: https://tts.vifast.org/**

Lưu ý để dùng cho đúng: model mẫu đang chạy cho mục đích nghiên cứu / phi thương mại; vui lòng không dùng để giả giọng người khác. Code mở MIT — ai muốn tự train giọng của mình thì repo ở comment.

#ViFastTts #TTS #TextToSpeech #TiếngViệt #AITiếngViệt #MãNguồnMở

---

## Bình luận đầu tiên (nên ghim)

Mã nguồn mở + model: https://github.com/vifast-oss/ViFastTts
Model trên Hugging Face: https://huggingface.co/dvchd/vifasttts-ngochuyen-small
Góp ý / báo lỗi đọc sai: bấm **Góp ý** ngay trên trang tts.vifast.org — mình đọc hết.

---

## Bản ngắn (dùng cho Story / quảng cáo / caption phụ)

Đọc tiếng Việt thành giọng nói — miễn phí, không cần đăng ký, chạy trên mọi thiết bị.
Dán văn bản, bấm Đọc là nghe. Nhanh gấp ~30 lần thời gian thực, và bạn còn tự tạo được giọng của riêng mình.
👉 tts.vifast.org

---

## Ghi chú khi đăng

- Ảnh 4:5 (1080×1350) chiếm nhiều diện tích feed trên mobile; nếu chạy quảng cáo
  thì dùng cùng ảnh này, tiêu đề phụ nên là "Miễn phí · Không cần đăng ký".
- Dòng đầu tiên hiển thị trước nút "Xem thêm": giữ hook trong ~120 ký tự đầu.
- Nếu muốn giảm rủi ro chính sách: bỏ chữ "miễn phí" ở dòng đầu và để ở dòng 2,
  hoặc thêm "demo nghiên cứu" ngay trong caption (đã có ở cuối bài).
- Số liệu dùng trong bài (RTF, tham số, 264 vần, >200 mục từ điển) lấy từ
  `README.md` và `deploy/vifasttts_web/static/index.html`. Nếu đổi model/ONNX
  thì cập nhật lại cả bài lẫn ảnh.
- Model mẫu Ngọc Huyền là CC BY-NC 4.0 (nghiên cứu, phi thương mại) — đừng dùng
  câu quảng cáo ngụ ý được dùng thương mại cho giọng mẫu này.
