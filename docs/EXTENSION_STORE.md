# Đưa extension lên Chrome Web Store và Microsoft Edge Add-ons

Trạng thái hiện tại: extension MV3 `0.3.5`; các thay đổi UI 29/10 (alpha/peak/
max, HuggingFace trực tiếp, OOV, karaoke) nằm trên `main` và cần build package
mới trước khi nộp store.

## 1. Package gửi store

Không upload thư mục `extension/`; phải upload file ZIP có `manifest.json` ở
**root**.

```text
https://github.com/dvchd/ViFastTts/releases/download/v0.1.1/vifasttts-extension.zip
sha256 5ded1ce7d45479fa12df2d9e592ec260f96f60612d835573029f48f261017933
```

Kiểm tra nhanh:

```bash
unzip -p vifasttts-extension.zip manifest.json | head
unzip -l vifasttts-extension.zip | head -20
```

Package hiện có cả `vendored/ORT/model`; không cần build lại nếu dùng đúng tag
`v0.1.1`. Không đưa `build.sh`, `.gitignore`, file local hoặc token vào package.

## 2. Chrome Web Store

### Tài khoản

1. Đăng nhập Chrome Web Store Developer Dashboard:
   <https://chrome.google.com/webstore/devconsole>
2. Đăng ký developer account (Google account), xác minh email/2FA.
3. Trả phí đăng ký một lần của Google (hiện ~5 USD; kiểm tra trang thanh toán).
4. Hoàn tất thông tin publisher.

Phần này **bắt buộc đăng nhập/2FA bằng tài khoản của bạn**; không thể làm thay
qua CLI.

### Tạo item

1. **New item** → upload `vifasttts-extension.zip`.
2. Điền Store listing:
   - Name: `ViFastTts Local`
   - Summary: `Đọc tiếng Việt local-first bằng WASM + ONNX; hỗ trợ đọc trang và đoạn bôi đen.`
   - Category: **Productivity** (hoặc Accessibility nếu phù hợp hơn).
   - Language: **Vietnamese**.
   - Homepage: `https://vifasttts.hoctuthien.com/`
   - Support: `https://github.com/dvchd/ViFastTts/issues`
   - Privacy policy: `https://github.com/dvchd/ViFastTts/blob/main/docs/EXTENSION_PRIVACY.md`
3. Screenshots:
   - Chrome yêu cầu ít nhất 1 ảnh **1280×800** hoặc **640×400**.
   - Nên có 3 ảnh: popup đọc text, đọc trang/bôi đen, cài đặt model.
   - Icon 128×128 đã có tại `extension/icons/icon128.png`.
4. Privacy practices:
   - Single purpose: “Đọc văn bản tiếng Việt bằng giọng nói, local hoặc qua server do người dùng cấu hình.”
   - Website content: có xử lý, chỉ sau thao tác người dùng; không lưu server.
   - User-generated content: có xử lý text người dùng nhập.
   - Authentication information: có thể lưu Bearer token local nếu người dùng nhập.
   - Không bán dữ liệu, không quảng cáo, không analytics.
5. Permission justification:
   - `offscreen`: WASM/ONNX và audio rendering cần DOM ngoài service worker.
   - `storage`, `unlimitedStorage`: settings/history/model cache.
   - `contextMenus`: đọc đoạn bôi đen/trang qua menu chuột phải.
   - `activeTab`, `scripting`: chỉ đọc nội dung trang sau khi người dùng bấm.
   - `host_permissions`: localhost (server TTS local), `huggingface.co` và
     `*.hf.co` (tìm/tải model trực tiếp khi người dùng bật checkbox).
   - `optional_host_permissions` HTTP/HTTPS: server LAN/online do người dùng nhập;
     xin quyền lúc chạy.
6. Remote code:
   - Trả lời **No remote code**. WASM, ORT và JS đều đóng trong package.
   - `.vfa/.vfts` tải về là **model data**, không phải JavaScript; extension kiểm
     SHA256 trước khi dùng.
7. Gửi review. Thời gian thường 1–3 ngày làm việc, có thể lâu hơn nếu reviewer
   hỏi về quyền host hoặc mô hình ONNX.

## 3. Microsoft Edge Add-ons

Edge dùng cùng package MV3 và cùng `manifest.json`.

1. Đăng nhập Microsoft Partner Center:
   <https://partner.microsoft.com/dashboard/microsoftedge/>
2. Tạo tài khoản developer (Microsoft account; Edge Add-ons miễn phí).
3. **New extension** → upload cùng `vifasttts-extension.zip`.
4. Điền:
   - Name, summary, description: dùng cùng nội dung Chrome.
   - Category: Productivity.
   - Privacy policy: cùng URL GitHub.
   - Screenshots 1280×800.
   - Age rating và markets (chọn Vietnam + All markets nếu muốn).
5. Gửi certification. Edge thường duyệt 1–7 ngày làm việc.

Không cần build package riêng cho Edge nếu dùng API Chromium/MV3 chuẩn; extension
hiện dùng `chrome.*`, `offscreen`, `contextMenus`, `activeTab`, `scripting`.

## 4. Trước khi bấm Submit — checklist

- [ ] `manifest.json` nằm ở root ZIP.
- [ ] `version` là `0.3.5` (hoặc bump version nếu sửa package).
- [ ] Không có token, `.env`, file local, `node_modules`, `target`.
- [ ] Test **Load unpacked** trên Chrome sạch; bấm icon → Đọc không cần server.
- [ ] Test đọc trang/bôi đen, Remote mode với server local, và **HuggingFace trực tiếp**.
- [ ] Có ít nhất 1 screenshot 1280×800.
- [ ] Privacy policy URL mở được khi không đăng nhập.
- [ ] Giải thích rõ `optional_host_permissions` và mô hình ONNX.
- [ ] Kiểm tra license: model sample CC-BY-NC-4.0; không hứa production thương mại.

## 5. Giới hạn hiện tại

- Extension có thể gọi **HuggingFace trực tiếp** (checkbox trong mục thêm giọng)
  hoặc dùng server `/api/models/*`. Local mode vẫn chạy được nếu đã có model
  bundled hoặc bundle trong Cache Storage.
- Cần tài khoản developer/2FA để nộp; không có API công khai không cần đăng nhập.
- Nếu Chrome reviewer yêu cầu thu hẹp quyền, có thể bỏ host `huggingface.co` và
  `*.hf.co`; khi đó chỉ dùng model bundled/server, không tìm/tải HF trực tiếp.
- Screenshots hiện chưa được commit; cần tạo từ extension UI trước khi nộp.
