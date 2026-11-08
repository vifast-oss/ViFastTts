# ViFastTts brand assets

Logo chính thức của dự án. Tên hiển thị luôn viết **ViFastTts** (PascalCase).

## File

| File | Dùng cho |
|---|---|
| `vifasttts-icon.svg` | icon gốc, web/app, nền trong |
| `vifasttts-lockup.svg` | logo ngang gốc (icon + wordmark + tagline) |
| `vifasttts-lockup.png` | logo ngang đã bake font, dùng trên web/README |
| `vifasttts-icon-512.png` | app icon, avatar, manifest |
| `vifasttts-icon-192.png` | manifest / PWA |
| `favicon.ico`, `favicon-16.png`, `favicon-32.png` | favicon |
| `apple-touch-icon.png` | iOS home screen, nền đỏ full-bleed |
| `vifasttts-lockup.png` | logo ngang, nền trong |
| `vifasttts-lockup-cream.png` | README, model card, tài liệu (nền kem, đọc được ở dark mode) |
| `og-image.png` | Open Graph / Twitter card 1200×630 |
| `site.webmanifest` | manifest PWA |

Bản dùng trên web nằm ở `deploy/vifasttts_web/static/brand/` và
`huggingface/space-static/brand/`; hai thư mục này được copy từ đây. Web dùng PNG cho
lockup để font không bị lệch giữa macOS/Windows/Linux; SVG vẫn là nguồn thiết kế.

## Màu

| Vai trò | Màu |
|---|---|
| Đỏ logo (gradient) | `#E8352B` → `#B3150F` |
| Đỏ wordmark | `#D42A20` |
| Vàng sao (gradient) | `#FFE04A` → `#FFB800` |
| Chữ chính | `#1F2430` |
| Chữ phụ | `#6B7280` |
| Nền kem | `#FFF8EC` |

## Quy ước dùng

- Kích thước icon tối thiểu: **24 px**. Dưới 32 px dùng icon, không dùng lockup.
- Lockup tối thiểu: **280 px** chiều rộng; giữ khoảng trống quanh logo ít nhất bằng
  chiều cao chữ `V`.
- Không kéo giãn, đổi màu, thêm bóng/viền, hoặc đặt trên nền nhiều chi tiết.
- Nền sáng: dùng bản gốc. Nền tối: đặt logo trên nền kem hoặc panel sáng, không
  đổi màu wordmark.
- Không dùng logo để ngụ ý chứng nhận/thương mại khi chưa có quyền.

## Dựng lại PNG

Yêu cầu macOS (Quick Look `qlmanage`) + Pillow + scipy:

```bash
.venv/bin/python resources/brand/build_assets.py
```

Sau khi dựng lại, copy sang hai thư mục web:

```bash
cp resources/brand/{vifasttts-icon.svg,vifasttts-lockup.svg,vifasttts-lockup-cream.png,vifasttts-icon-192.png,vifasttts-icon-512.png,favicon.ico,favicon-16.png,favicon-32.png,apple-touch-icon.png,og-image.png,site.webmanifest} deploy/vifasttts_web/static/brand/
cp resources/brand/{vifasttts-icon.svg,vifasttts-lockup.svg,vifasttts-lockup-cream.png,vifasttts-icon-192.png,vifasttts-icon-512.png,favicon.ico,favicon-16.png,favicon-32.png,apple-touch-icon.png,og-image.png,site.webmanifest} huggingface/space-static/brand/
```

Logo do chủ dự án cung cấp. Code repo là MIT; nhãn hiệu/logo không tự động thuộc phạm vi
giấy phép MIT.
