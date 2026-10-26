# EXCEPTIONS — ngoại lệ có phạm vi (không phải trạng thái hiện hành)

> **Không phải trạng thái hiện hành.** Trạng thái duy nhất nằm ở
> `docs/handoff/TRANG_THAI.md`. Tệp này chỉ ghi các ngoại lệ đã được A0 chấp nhận
> **có phạm vi**, kèm mã, số đo và điều kiện hết hiệu lực. Không thêm ngoại lệ mới
> nếu chưa có quyết định của A0.
>
> Nguyên tắc: ngoại lệ **không** phải "pass toàn bộ"; nó chỉ miễn một tiêu chí cụ thể
> cho một input cụ thể, trong một phạm vi cụ thể. Ngoài phạm vi, tiêu chí chung vẫn áp dụng.

---

## ONNX-EXC-001 — outlier phổ vocoder `2b65WyiFC9k_0030__s03`

### Quyết định
- **Nguồn**: A0 v18.41, chấp nhận **sau khi xem kết quả**; không sửa ngưỡng, không sửa runtime.
- **Mã**: `ONNX-EXC-001`.
- **Trạng thái**: có hiệu lực cho đúng phạm vi dưới đây; hết hiệu lực tự động khi bất kỳ điều kiện hết hiệu lực nào thay đổi.

### Phạm vi (đủ hẹp)
- **Input**: chỉ `2b65WyiFC9k_0030__s03`.
- **Tầng**: chỉ phổ vocoder (real/imag) trước iSTFT.
- **Mode**: chỉ **chunk mode**.
- **Execution Provider**: chỉ **CPUExecutionProvider**.
- **Mô hình**: chỉ đúng hash ONNX đang ghi trong `configs/onnx_candidate_v1841.json`
  (`p2ema_acoustic.onnx` SHA256 `ff6844ec…`, `vocos_pretrained_vocoder.onnx` SHA256 `ed193b82…`).
- **Môi trường**: chỉ đúng phiên bản `onnxruntime` đã dùng lúc đo (ghi trong report/JSON của v18.40).

### Số đo
| Chỉ số | Giá trị | Ngưỡng chung | Ghi chú |
|---|---:|---:|---|
| Spectrum max abs (real) | 0,023357868… | 0,02 | vượt tại bin (20,66) |
| Spectrum max abs (imag) | 0,017773866… | 0,02 | dưới ngưỡng |
| Spectrum mean abs | ~1e-05 | 2e-03 | đạt |
| Waveform max abs | 3,23e-04 | 5e-04 | đạt |
| End-to-end max abs | 9,16e-05 | 2e-03 | đạt |
| Clipping thêm | 0 | 0 | đạt |

### Điều kiện hết hiệu lực (bất kỳ điều nào)
1. Đổi hash model ONNX (acoustic hoặc vocoder).
2. Đổi phiên bản `onnxruntime`.
3. Đổi Execution Provider (CPU → CoreML/CUDA/TensorRT…).
4. Đổi mode (chunk → sentence/steady).
5. Đổi acoustic production (checkpoint P2 EMA bị thay).

Khi hết hiệu lực: chạy lại parity đầy đủ; ngoại lệ **không** được tự động chuyển sang mô hình/môi trường mới.

### Luật test
- Test parity **đọc danh sách ngoại lệ** từ tệp này (hoặc JSON sinh ra từ tệp này), không hard-code ngưỡng riêng.
- Với `ONNX-EXC-001`: được phép pass tiêu chí `spectrum_max_abs ≤ 0,02` **chỉ** khi đúng input + đúng phạm vi; các tiêu chí còn lại vẫn phải đạt.
- Với **mọi input khác**: `spectrum_max_abs > 0,02` vẫn **FAIL**.
- Nếu xuất hiện input thứ hai vượt ngưỡng: **không** thêm ngoại lệ; dừng, báo A0.
- Test phải chứng minh được bằng một ca âm: một input khác vượt 0,02 bị FAIL.

### Dữ liệu máy đọc (test parity đọc khối này)

```json
{
  "exceptions": [
    {
      "id": "ONNX-EXC-001",
      "input": "2b65WyiFC9k_0030__s03",
      "layer": "vocoder_spectrum",
      "mode": "chunk",
      "provider": "CPUExecutionProvider",
      "acoustic_sha256": "ff6844ec8a28b2c17a40d944d9ebe19476a159b8573c22fdd52c932cbfcdf23f",
      "vocoder_sha256": "ed193b8246ae4078203e2b88fae5bc492b53b9f6ae6fd7652a1278aca02dd3f3",
      "criterion": 0.02,
      "observed_max": {
        "real": 0.023357868194580078,
        "imag": 0.017773866653442383
      },
      "source": "A0 v18.41; xem V1841_agent2.md §1, artifacts/bench/v1840_onnx_parity/result.json"
    }
  ]
}
```
