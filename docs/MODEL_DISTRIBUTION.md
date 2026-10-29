# Phân phối model `.vfts` / `.vfa`

Cả hai đều là file ZIP nhị phân thông thường, nên có thể đưa lên:

- **HuggingFace model repo** — nên là nguồn chính cho nhiều giọng/public catalog.
- **GitHub Release asset** — nên là nguồn cho model mặc định, bản offline, artifact
  gắn với tag phát hành.

## Nên đặt ở đâu?

| Loại | Nơi chính | Lý do |
|---|---|---|
| N0 mặc định | GitHub Release + app bundle | tải cùng app, offline, version gắn tag |
| Nhiều giọng public | **HuggingFace** | model card, license, revision, tải riêng |
| `models.json` catalog | HuggingFace | client đọc một URL, thêm giọng không cần app update |
| Vocoder dùng chung | HuggingFace + app bundle | `.vfa` tham chiếu SHA256 |
| Model nội bộ/riêng | private HF/server | không đưa public GitHub |
| Raw `acoustic.onnx` | repo nội bộ/dev | **không phải file phân phối cho người dùng** |
| App/CLI/server binary | GitHub Release | installer + changelog + checksum |

Không nên nhét toàn bộ giọng vào mỗi GitHub release; sẽ phình artifact. GitHub
Release giữ **mặc định + bundle tiêu biểu**, HuggingFace giữ **catalog giọng**.

**Chỉ phân phối `.vfa`/`.vfts` cho người dùng.** Raw `acoustic.onnx` thiếu
vocoder, manifest, `vocab_hash`, dictionary snapshot và license; tải riêng nó
không đủ để chạy. Giữ raw ONNX trong repo/dev/export hoặc thư mục `internal/`
của HF, không đặt làm link tải chính.

`models.json` phải trỏ tới `.vfa` (thêm giọng) hoặc `.vfts` (full/offline),
không trỏ `acoustic.onnx`.

## HuggingFace

Ví dụ repo:

```text
dvchd/vifasttts-ngochuyen-small
  models.json
  vocoders/vocos-mel-24khz.onnx
  voices/n0-ngochuyen/
    n0-ngochuyen.vfa
  voices/n0-ngochuyen-full/
    n0-ngochuyen.vfts
  LICENSE.md
```

Upload bằng Python:

```python
from huggingface_hub import HfApi
api = HfApi()
api.upload_file(
    path_or_fileobj="n0-ngochuyen.vfa",
    path_in_repo="voices/n0-ngochuyen/n0-ngochuyen.vfa",
    repo_id="dvchd/vifasttts-ngochuyen-small",
    repo_type="model",
)
```

Hoặc CLI:

```bash
hf upload dvchd/vifasttts-ngochuyen-small n0-ngochuyen.vfa \
  bundles/n0-ngochuyen.vfa
```

- Dùng Git LFS/Xet cho file lớn; không commit raw Git thường.
- Ghi SHA256, license CC-BY-NC, phiên bản arch/vocab trong `models.json` và
  model card.
- Không nên để client tin `main` mutable; manifest có SHA256, hoặc ghim revision.

## GitHub Release

```bash
gh release upload v0.1.0 \
  desktop/dist/n0-ngochuyen.vfts \
  desktop/dist/n0-ngochuyen.vfa \
  --clobber
```

- GitHub Releases cũ đã xoá 29/10/2026; nguồn chính là HuggingFace. Tag là bất biến nếu tạo release mới.
- CI job `model-vfts` (nên đổi tên `model-bundles`) đang tạo cả `.vfts` và `.vfa`;
  release job tải lên cùng app.
- Với model mặc định, đặt file cạnh app/package và kiểm SHA256 khi nạp.

## `.vfa` và vocoder

- `.vfa` chỉ chứa acoustic + frontend; manifest ghi `vocoder.sha256`.
- Nếu máy đã có vocoder bundled (N0 hiện tại là **Vocos pretrained**), `--vocoder`
  không cần thiết: loader tự tìm `models/vocoder.onnx`, `vocoder.onnx`, hoặc
  `VIFASTT_VOCODER`.
- Nếu vocoder không khớp hash, loader báo lỗi và client cần tải vocoder/full
  `.vfts`.
- `.vfts` full vẫn là fallback an toàn, nhất là khi vocoder/acoustic khác contract
  mel hoặc chưa test tai.

## Tìm model trong app

Tất cả UI dùng chung một catalog:

- native (desktop/CLI/TUI/server): `vifasttts-model-manager` +
  `vifasttts-huggingface`.
- web + extension: `web/shared/model-api.js` (extension copy khi build).
- Android/iOS: API server `/api/models/search|files|download`.

```bash
vifasttts models search
vifasttts models files <repo>
vifasttts models download <repo> <path> --output models
```

Chi tiết + bảng UI: `docs/MODEL_SEARCH.md`.

## CI hiện tại

- `model-vfts` job tạo:
  - `n0-ngochuyen.vfts` (~76 MB, full)
  - `n0-ngochuyen.vfa` (~28 MB, acoustic-only)
- Release GitHub nhận cả hai.
- Upload HF nên là workflow riêng có `HF_TOKEN` (không tự đẩy public trong CI mặc
  định).
