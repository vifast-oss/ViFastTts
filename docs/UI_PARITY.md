# UI parity — kiểm tra tính năng cơ bản

Cập nhật: 29/10/2026. Mục tiêu: mọi UI đều đủ để dùng hằng ngày, không có
trường hợp một bản thiếu cấu hình cơ bản như Android/iOS trước đây.

## Checklist cơ bản

- [x] Nhập text và đọc
- [x] Chọn Local / Remote
- [x] Chọn/tải model
- [x] Phát và dừng
- [x] Trạng thái/lỗi rõ ràng
- [x] Tốc độ
- [x] Pause cố định
- [ ] Alpha / peak normalize / max ký tự trên mọi UI
- [x] Lưu/chia sẻ WAV trên desktop/web/extension/Android/iOS
- [ ] Từ điển/custom reading trên mobile
- [ ] Karaoke/SRT/VTT trên mobile

## Trạng thái từng UI

| UI | Local/Remote | Model | Cấu hình âm thanh | Xuất file | Ghi chú |
|---|---|---|---|---|---|
| Desktop egui | Có | Bundle/ONNX, browser | Speed, alpha, fixed pause, peak, max chars, dialect, OOV | WAV, SRT, VTT | Đầy đủ nhất |
| CLI | Có | `--vfa/--vfts`, models | flags speed/fixed/alpha | WAV/SRT/VTT | Phụ thuộc flags |
| TUI | Có | `Ctrl+O` | Speed, fixed pause, dictionary | WAV | Alpha/peak/max chưa có UI |
| Web Python (server) | Remote | Không có browser trong trang demo | Speed, fixed pause | WAV | Là demo server, không phải client đầy đủ |
| Web Vite local | Có | HF browser/manual bundle | Speed, fixed pause | WAV (đã thêm) | Chưa có alpha/peak/max |
| Chrome extension | Có | HF browser qua server | Speed, fixed pause, dictionary | WAV/SRT/VTT | Chưa có alpha/peak/max |
| Android | Có | HF trực tiếp/server, bundle | Speed, alpha, fixed, peak, max | WAV vào Downloads (Android 10+) | Đã sửa top inset; tên app `ViFastTts` |
| iOS | Có | HF trực tiếp/server, bundle | Speed, alpha, fixed, peak, max | Chia sẻ WAV qua ShareLink | Chưa test thiết bị thật |

## Các gap còn lại (không chặn dùng cơ bản)

1. **Mobile chưa có từ điển/custom reading** — desktop/extension có, nhưng FFI C
   ABI hiện chỉ nhận text + options; cần mở rộng ABI hoặc xử lý dictionary ở
   tầng app trước khi gọi FFI.
2. **Mobile chưa có karaoke/SRT/VTT** — cần dùng `vifasttts_synthesize_karaoke`
   hoặc thêm ShareLink/Intent cho file phụ đề.
3. ~~Android chưa có nút chia sẻ WAV~~ — đã thêm **Lưu WAV** vào Downloads
   trên Android 10+; máy cũ lưu vào thư mục Music của app.
4. **TUI chưa có alpha/peak/max UI** — TUI hiện chỉ chỉnh speed/fixed; các tham
   số còn lại dùng default. Không chặn dùng, nhưng chưa ngang desktop.
5. **Web/Extension chưa có alpha/peak/max** — server web dùng alpha cố định;
   extension WASM hiện chỉ truyền speed/fixed. Cần mở rộng options nếu muốn parity.
6. **Audio mobile cần test máy thật** — đã thêm AudioFocus/AVAudioSession và
   cảnh báo base model nặng; nếu vẫn giật, thu clip + tên model/thiết bị.

## Kết luận

Các UI hiện **đủ để dùng cơ bản**: nhập text, local/remote, model, phát/dừng,
trạng thái/lỗi, speed và pause. Desktop vẫn là bản đầy đủ nhất. Android/iOS đã
được nâng từ mức “chỉ đọc” lên mức có cấu hình âm thanh và tải model trực tiếp;
các phần từ điển/karaoke/export nâng cao có thể làm tiếp mà không chặn bản dùng
hằng ngày.
