# ViFastTts design tokens

Nguồn duy nhất cho màu, font, spacing và radius. Các UI map token sang:

- `web/shared/theme.css` — web + extension
- `rust/crates/adapters/inbound/desktop/src/main.rs` — egui
- `mobile/ios/ViFastTtsMobile/Theme.swift` — SwiftUI
- `mobile/android/.../MainActivity.java` — Android views

Quy ước: nền kem sáng, accent đỏ, font Be Vietnam Pro; desktop/mobile/web
không cần giống pixel tuyệt đối nhưng phải cùng palette, thứ tự nút và trạng thái.
