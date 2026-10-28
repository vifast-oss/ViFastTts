# Phân phối & đóng gói

Ưu tiên người dùng **desktop Windows/macOS**, sau đó Linux; các kênh khác chỉ
thêm khi bản desktop đã ổn định.

## Thứ tự kênh

| Ưu tiên | Kênh | Trạng thái / ghi chú |
|---:|---|---|
| 1 | GitHub Release portable | **Đã có** (CI tag `v*`); zip/tar + model + ORT |
| CLI/TUI/server dùng chung | `vifasttts` mặc định TUI; `server` = server + web |
| 2 | Windows installer (MSI/NSIS) + Winget/Scoop | Sau khi ký code; hiện zip portable |
| 3 | macOS `.dmg` + Homebrew cask | Sau notarize; hiện `.app` zip |
| 4 | Linux AppImage/Flatpak | Sau tar portable; cần đo desktop/audio |
| 5 | `cargo-binstall` cho CLI/TUI/server | Chỉ khi tách asset từng target + model/ORT |
| 6 | npm/bun cho web/wasm SDK | Chỉ JS/wasm, **không** đóng gói model 86 MB |
| 7 | PyPI | Python package/server/CLI Python; không thay desktop |
| 8 | Nix flake | Optional/community; cần license ORT/model và cache |

## Vì sao không “một gói cho mọi kênh”?

- Desktop cần model FP32 ~86 MB + ORT ~30 MB; npm/PyPI không phù hợp để nhồi
  binary native lớn, dễ vượt quota và khó cache.
- Windows/macOS cần ký/notarize; Python/npm không giải quyết Gatekeeper/SmartScreen.
- `cargo-binstall` hữu ích cho CLI/TUI/server, nhưng asset phải có tên target
  chuẩn và kèm ORT/model; hiện release đang gộp package desktop.
- Nix cần quyết định license model (CC-BY-NC) và ORT; chỉ nên làm sau.

## Model asset

Model nên là asset riêng hoặc bundle `.vfts`:

```text
n0-ngochuyen.vfts = manifest.json + acoustic.onnx + vocoder.onnx
                    + frontend/*.json + LICENSE/NOTICE
```

`.vfts` hiện được tạo tự động trong CI (`model-vfts`) và loader hỗ trợ CLI,
server, TUI, desktop, FFI, mobile. Frontend resources nằm trong bundle để audit;
runtime vẫn dùng resource nhúng trong `vifasttts-text`.

## Ký & an toàn

- Bản `-rc*` là pre-release, **chưa ký**, chỉ dùng thử.
- Windows: SmartScreen “More info → Run anyway”; macOS: chuột phải → Open.
- Server LAN: chỉ bind `0.0.0.0` khi cần; đặt Bearer token, firewall; chưa có TLS.
- Phát hành store cần xử lý license dataset CC-BY-NC và ký Apple/Windows.
